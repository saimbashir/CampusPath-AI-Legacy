from datetime import timedelta
import os
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select,update,delete
from app.db import get_db
from app.models import VivaSession,VivaTurn,Topic,Mastery,Revision,Misconception,User,now
from app.schemas import VivaStart,VivaAnswer,VivaReview
from app.auth.security import current_user,course_access,role,audit,throttle
from app.services.learning import snapshot
from app.mastery.engine import update_mastery,revision_dates
from app.ai.viva import evaluate,offline_evaluation
from app.ai.viva_variation import prompt_for_turn
from app.config import DEMO_MODE
router=APIRouter(prefix='/api')
def prompt_for(db,session):
    topic=db.get(Topic,session.topic_ids[session.cursor])
    style,prompt=prompt_for_turn(session.id,session.student_id,session.course_id,session.cursor,topic.name)
    return topic,prompt

def payload(db,session):
    turns=db.scalars(select(VivaTurn).where(VivaTurn.session_id==session.id).order_by(VivaTurn.turn_index)).all()
    result={'id':session.id,'index':session.cursor,'total':len(session.topic_ids),'complete':session.cursor>=len(session.topic_ids) or session.expires<now(),
        'turns':[{'id':t.id,'topic_id':t.topic_id,'prompt':t.prompt,'answer':t.answer,'evaluation':t.evaluation,'provider':t.provider,'proposed_score':t.proposed_score,'reviewed_score':t.reviewed_score,'teacher_feedback':t.teacher_feedback,'mastery_before':t.mastery_before,'mastery_after':t.mastery_after} for t in turns]}
    if not result['complete']:
        topic,prompt=prompt_for(db,session);result['question']={'topic_id':topic.id,'topic':topic.name,'prompt':prompt,'style':prompt_for_turn(session.id,session.student_id,session.course_id,session.cursor,topic.name)[0]}
    return result
@router.post('/courses/{cid}/viva/start')
def start(cid:int,data:VivaStart,user=Depends(current_user),db=Depends(get_db)):
    role(user,'student');course_access(db,user,cid)
    topics=db.scalars(select(Topic).where(Topic.course_id==cid)).all()
    if data.topic_id:
        topics=[t for t in topics if t.id==data.topic_id]
    else:
        order=[x['id'] for x in snapshot(db,user.id,cid)['path']]
        topics.sort(key=lambda t:order.index(t.id) if t.id in order else len(order))
    if not topics:raise HTTPException(409,'Add course concepts before starting viva practice.')
    topic_ids=[topics[i % len(topics)].id for i in range(data.count)]
    session=VivaSession(student_id=user.id,course_id=cid,topic_ids=topic_ids,cursor=0,expires=now()+timedelta(hours=1))
    db.add(session);db.commit();return payload(db,session)
@router.get('/viva/{vid}')
def get_viva(vid:int,user=Depends(current_user),db=Depends(get_db)):
    session=db.get(VivaSession,vid)
    if not session or session.student_id!=user.id:raise HTTPException(404,'Viva not found.')
    course_access(db,user,session.course_id);return payload(db,session)
@router.post('/viva/{vid}/answer')
async def answer_viva(vid:int,data:VivaAnswer,user=Depends(current_user),db=Depends(get_db)):
    role(user,'student');session=db.get(VivaSession,vid)
    if not session or session.student_id!=user.id:raise HTTPException(404,'Viva not found.')
    course_access(db,user,session.course_id);throttle(db,'viva:'+str(user.id),30)
    if session.expires<now() or session.cursor>=len(session.topic_ids):raise HTTPException(409,'Viva is complete or expired.')
    if data.turn_index!=session.cursor:raise HTTPException(409,'This turn is already submitted or not currently issued.')
    topic,prompt=prompt_for(db,session);index=session.cursor
    evaluation=offline_evaluation(topic.name,topic.description,data.text);score=None;provider='TEACHER REVIEW'
    if not DEMO_MODE and os.getenv('LLM_API_KEY'):
        try:
            result=await evaluate(prompt,data.text,topic.name,topic.description);evaluation=result.model_dump();score=result.score;provider='AI PROVISIONAL'
        except Exception:
            provider='PROVIDER FALLBACK';evaluation['feedback']='The AI evaluator is unavailable. Your transcript is saved for teacher review; no AI grade was invented.'
    claimed=db.execute(update(VivaSession).where(VivaSession.id==vid,VivaSession.cursor==index).values(cursor=index+1))
    if claimed.rowcount!=1:db.rollback();raise HTTPException(409,'This turn was already saved in another request.')
    turn=VivaTurn(session_id=vid,turn_index=index,topic_id=topic.id,prompt=prompt,answer=data.text,evaluation=evaluation,provider=provider,proposed_score=score)
    db.add(turn);db.commit();db.refresh(session)
    return {'evaluation':evaluation,'proposed_score':score,'status':provider,'message':'Only teacher-reviewed viva scores affect mastery.','next':payload(db,session)}
@router.get('/courses/{cid}/viva/history')
def viva_history(cid:int,user=Depends(current_user),db=Depends(get_db)):
    role(user,'student');course_access(db,user,cid)
    return [payload(db,s) for s in db.scalars(select(VivaSession).where(VivaSession.course_id==cid,VivaSession.student_id==user.id).order_by(VivaSession.id.desc()).limit(15))]
@router.get('/courses/{cid}/viva/review')
def review_queue(cid:int,user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid,True)
    rows=db.execute(select(VivaTurn,VivaSession,User).join(VivaSession,VivaSession.id==VivaTurn.session_id).join(User,User.id==VivaSession.student_id).where(VivaSession.course_id==cid).order_by(VivaTurn.created.desc()).limit(100)).all()
    audit(db,user,'viva records viewed',cid);db.commit()
    return [{'id':t.id,'student_id':u.id,'name':u.name,'university_id':u.university_id,'topic':db.get(Topic,t.topic_id).name,'reference':db.get(Topic,t.topic_id).description,'prompt':t.prompt,'answer':t.answer,'evaluation':t.evaluation,'proposed_score':t.proposed_score,'reviewed_score':t.reviewed_score,'teacher_feedback':t.teacher_feedback,'provider':t.provider} for t,s,u in rows]
@router.post('/viva/turns/{tid}/review')
def review(tid:int,data:VivaReview,user=Depends(current_user),db=Depends(get_db)):
    turn=db.get(VivaTurn,tid);session=db.get(VivaSession,turn.session_id) if turn else None
    if not session:raise HTTPException(404,'Viva response not found.')
    course_access(db,user,session.course_id,True)
    claimed=db.execute(update(VivaTurn).where(VivaTurn.id==tid,VivaTurn.reviewed_at.is_(None)).values(reviewed_score=data.score,teacher_feedback=data.feedback,reviewed_by=user.id,reviewed_at=now()))
    if claimed.rowcount!=1:db.rollback();raise HTTPException(409,'This viva response has already been reviewed.')
    state=db.scalar(select(Mastery).where(Mastery.student_id==session.student_id,Mastery.topic_id==turn.topic_id))
    if not state:state=Mastery(student_id=session.student_id,topic_id=turn.topic_id,probability=.2,attempts=0,correct=0);db.add(state);db.flush()
    before=state.probability;correct=data.score>=70
    # Teacher-confirmed open-response evidence; no multiple-choice chance advantage.
    after=update_mastery(before,correct,2,guess=.1)
    result=db.execute(update(Mastery).where(Mastery.id==state.id,Mastery.attempts==state.attempts,Mastery.probability==before).values(probability=after,attempts=Mastery.attempts+1,correct=Mastery.correct+int(correct),last_practiced=now()))
    if result.rowcount!=1:db.rollback();raise HTTPException(409,'Progress changed during review. Retry.')
    turn.mastery_before=before;turn.mastery_after=after
    db.execute(delete(Revision).where(Revision.student_id==session.student_id,Revision.topic_id==turn.topic_id,Revision.done.is_(False)))
    for due in revision_dates(now(),after):db.add(Revision(student_id=session.student_id,topic_id=turn.topic_id,due=due))
    if not correct:db.add(Misconception(student_id=session.student_id,topic_id=turn.topic_id,evidence='Teacher viva feedback: '+data.feedback))
    audit(db,user,'viva reviewed',tid)
    from app.services.notifications import notify
    notify(db,session.student_id,session.course_id,f'viva-reviewed:{tid}','Viva feedback confirmed','Your teacher reviewed a viva response and updated your learning evidence.','voice')
    db.commit()
    return {'ok':True,'mastery':{'before':round(before*100),'after':round(after*100)}}
