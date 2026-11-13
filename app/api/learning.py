import os
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from app.db import get_db
from app.models import Course,Topic,Question,QuizRun,Answer,Revision,Conversation,now
from app.schemas import TutorInput,StartQuiz,AnswerInput,PlanInput,TextInput
from app.auth.security import current_user,role,course_access,student_access
from app.services.learning import snapshot,observe
from app.mastery.engine import next_difficulty
from app.ai.retrieval import LexicalStore,HybridStore
from app.ai.providers import CompatibleLLM
from app.knowledge_graph.engine import algorithm_steps
from app.config import DEMO_MODE
router=APIRouter(prefix='/api')
from app.assessment.feedback import teaching_feedback
@router.get('/courses/{cid}/students/{sid}/progress')
def progress(cid:int,sid:int,user=Depends(current_user),db=Depends(get_db)):
    student_access(db,user,cid,sid)
    result=snapshot(db,sid,cid);db.commit();return result
@router.post('/courses/{cid}/tutor')
async def tutor(cid:int,data:TutorInput,user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid)
    from starlette.concurrency import run_in_threadpool
    if data.resource_ids or data.chapters or data.page_from or data.page_to:
        from app.services.materials import MaterialScope,resolve
        chunks=resolve(db,cid,MaterialScope(resource_ids=data.resource_ids,chapters=data.chapters,page_from=data.page_from,page_to=data.page_to))[:8];retrieval_status='Explicit book/chapter/page scope'
    else:
        import re
        chapter=re.search(r'chapter\s+(\d+)',data.question,re.I);page=re.search(r'page\s+(\d+)',data.question,re.I)
        if chapter or page:
            from app.services.materials import MaterialScope,resolve
            chunks=resolve(db,cid,MaterialScope(chapters=[chapter[1]] if chapter else [],page_from=int(page[1]) if page else None,page_to=int(page[1]) if page else None))[:8];retrieval_status='Book location extracted from query'
        else:chunks,retrieval_status=await run_in_threadpool(HybridStore().search,db,user,cid,data.question)
    if not chunks:return {'answer':'The provided course material does not contain enough information to answer this confidently. Ask your teacher to upload notes for this topic, then ask again. New uploads are searched immediately; a missing match does not mean the entire document is unavailable.','sources':[],'mode':'No evidence','provider_status':'No retrieval result'}
    answer='';status='DEMO-SIMULATED' if DEMO_MODE else 'EXTRACTIVE FALLBACK'
    source_ids=[c['id'] for c in chunks]
    if not DEMO_MODE and os.getenv('LLM_API_KEY'):
        try:
            result=await CompatibleLLM().answer(data.question,chunks,data.mode)
            answer=result['answer'];source_ids=result['source_ids'];status='LIVE PROVIDER'
            if db.get(Course,cid).material_only:
                from app.ai.grounded import GroundingVerdict
                from app.ai.providers import structured_generation
                verdict=await structured_generation('Verify that every substantive claim in this tutor answer is supported by the provided sources. Reject external facts. Answer: '+answer,chunks,GroundingVerdict)
                if not verdict.supported or not set(verdict.source_ids)<={c['id'] for c in chunks}:answer='';raise ValueError('Answer support check failed.')
        except Exception:answer='';status='EXTRACTIVE FALLBACK — provider unavailable or invalid output'
    if not answer:
        if data.mode=='Socratic Mode':answer='Read the excerpt below. Which rule applies, and why? Explain your reasoning before checking a worked solution.\n\n'+chunks[0]['text']
        elif data.mode=='Roman Urdu':answer='Yeh aap ke accessible course material ka relevant hissa hai. Offline mode mein nayi translation generate nahi hoti; sample bilingual notes hon to neeche dikhayi jati hain.\n\n'+chunks[0]['text']
        else:answer='From your course material:\n\n'+'\n\n'.join(c['text'] for c in chunks[:2])
    db.add(Conversation(student_id=user.id,course_id=cid,mode='tutor',question=data.question,answer=answer))
    profile=dict(user.profile or {});profile['mode']=data.mode;user.profile=profile;db.commit()
    return {'answer':answer,'sources':[c for c in chunks if c['id'] in source_ids],'provider_status':status,'retrieval_status':retrieval_status,'mode':data.mode}
def quiz_payload(db,run):
    if run.finished or run.cursor>=len(run.question_ids) or run.expires<now():
        if not run.finished:run.finished=True;db.commit()
        from app.assessment.results import results
        return results(db,run)
    q=db.get(Question,run.question_ids[run.cursor])
    return {'id':run.id,'complete':False,'index':run.cursor,'total':len(run.question_ids),'expires':run.expires,'mode':run.mode,'coverage_notice':('Only '+str(len(run.question_ids))+' approved questions are available. This is a short practice check, not sufficient evidence of mastery. Ask your teacher to expand the bank.' if len(run.question_ids)<(run.settings or {}).get('requested_count',len(run.question_ids)) else ''),'question':{'id':q.id,'prompt':q.prompt,'options':q.options,'topic_id':q.topic_id,'difficulty':q.difficulty,'bloom':q.bloom}}
@router.post('/courses/{cid}/quiz',status_code=201)
def start(cid:int,data:StartQuiz,user=Depends(current_user),db=Depends(get_db)):
    role(user,'student');course_access(db,user,cid)
    query=select(Question).where(Question.course_id==cid,Question.approved.is_(True))
    if data.topic_id:query=query.where(Question.topic_id==data.topic_id)
    if data.topic_ids:query=query.where(Question.topic_id.in_(data.topic_ids))
    if data.difficulty:query=query.where(Question.difficulty==data.difficulty)
    questions=db.scalars(query.order_by(Question.difficulty,Question.id)).all()
    if db.get(Course,cid).material_only:
        from app.models import Chunk,Resource
        allowed=set(db.scalars(select(Chunk.id).join(Resource,Resource.id==Chunk.resource_id).where(Resource.course_id==cid,Resource.owner_id.is_(None))))
        questions=[q for q in questions if q.source_ids and set(q.source_ids)<=allowed]
    if not questions:raise HTTPException(409,'No approved questions are available for this selection.')
    if data.mode=='mock':
        from app.assessment.selection import select_mock
        topics={t.id:t for t in db.scalars(select(Topic).where(Topic.course_id==cid))}
        questions=select_mock(questions,topics,data)
    if data.mode=='adaptive':
        # Retain multiple difficulties in the issued pool so correct responses can progress.
        order=[x['id'] for x in snapshot(db,user.id,cid)['path']]
        counts={}
        for qid in db.scalars(select(Answer.question_id).where(Answer.student_id==user.id)):
            counts[qid]=counts.get(qid,0)+1
        questions.sort(key=lambda q:(counts.get(q.id,0),order.index(q.topic_id) if q.topic_id in order else len(order),q.difficulty,q.id))
    # Diagnostic uses interleaving across concepts before repeated topics.
    if data.mode=='diagnostic':
        seen=set();first=[];rest=[]
        for q in questions:
            (rest if q.topic_id in seen else first).append(q);seen.add(q.topic_id)
        questions=first+rest
    run=QuizRun(student_id=user.id,course_id=cid,mode=data.mode,question_ids=[q.id for q in questions[:data.count]],cursor=0,difficulty=1,settings={'total_marks':data.total_marks,'minutes':data.minutes,'requested_count':data.count,'available_count':len(questions),'bloom_distribution':data.bloom_distribution,'clo_distribution':data.clo_distribution},hint_ids=[],question_started=now(),expires=now()+timedelta(minutes=data.minutes))
    db.add(run);db.commit();return quiz_payload(db,run)
@router.get('/quiz/{rid}')
def get_quiz(rid:int,user=Depends(current_user),db=Depends(get_db)):
    run=db.get(QuizRun,rid)
    if not run or run.student_id!=user.id:raise HTTPException(404,'Assessment not found.')
    course_access(db,user,run.course_id)
    return quiz_payload(db,run)
@router.post('/quiz/{rid}/answer')
def answer(rid:int,data:AnswerInput,user=Depends(current_user),db=Depends(get_db)):
    role(user,'student');run=db.get(QuizRun,rid)
    if not run or run.student_id!=user.id:raise HTTPException(404,'Assessment not found.')
    course_access(db,user,run.course_id)
    if run.finished:raise HTTPException(409,'Assessment is already complete.')
    if run.expires<now():raise HTTPException(409,'Assessment time has expired. Start a new attempt.')
    if run.cursor>=len(run.question_ids) or data.question_id!=run.question_ids[run.cursor]:raise HTTPException(409,'This question was already answered or is not currently issued.')
    q=db.get(Question,data.question_id)
    if data.selected>=len(q.options):raise HTTPException(422,'Invalid answer option.')
    cursor=run.cursor
    claimed=db.execute(update(QuizRun).where(QuizRun.id==rid,QuizRun.cursor==cursor,QuizRun.finished.is_(False)).values(cursor=cursor+1))
    if claimed.rowcount!=1:db.rollback();raise HTTPException(409,'Answer already processed.')
    correct=data.selected==q.correct
    impact=observe(db,user,q,correct,run,data.selected)
    run.difficulty=next_difficulty(q.difficulty,correct)
    run.question_started=now()
    ids=list(run.question_ids)
    if run.mode=='adaptive':
        remaining=ids[cursor+1:]
        remaining.sort(key=lambda qid:abs(db.get(Question,qid).difficulty-run.difficulty))
        run.question_ids=ids[:cursor+1]+remaining
    try:db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,'Answer already processed.')
    if run.mode=='mock' and not run.finished and run.cursor<len(run.question_ids):
        return {'saved':True,'feedback_delayed':True,'next':quiz_payload(db,run)}
    return {'correct':correct,'correct_answer':q.options[q.correct],'explanation':teaching_feedback(db,q,data.selected),'possible_misconception':q.misconception if not correct else None,'mastery':impact,'next':quiz_payload(db,run)}
@router.post('/revisions/{rid}/complete')
def revision(rid:int,user=Depends(current_user),db=Depends(get_db)):
    role(user,'student');r=db.get(Revision,rid)
    if not r or r.student_id!=user.id:raise HTTPException(404,'Revision not found.')
    course_access(db,user,db.get(Topic,r.topic_id).course_id)
    r.done=True;db.commit();return {'ok':True,'message':'Revision marked complete. Take a quiz to provide new mastery evidence.'}
@router.post('/courses/{cid}/planner')
def plan(cid:int,data:PlanInput,user=Depends(current_user),db=Depends(get_db)):
    role(user,'student');course_access(db,user,cid)
    from app.services.planning import create_plan
    return create_plan(db,user,cid,data)
@router.get('/algorithm/{name}')
def algorithm(name:str,user=Depends(current_user)):
    try:return algorithm_steps(name)
    except ValueError as e:raise HTTPException(422,str(e))
@router.post('/courses/{cid}/viva')
def viva(cid:int,data:TextInput,user=Depends(current_user),db=Depends(get_db)):
    role(user,'student');course_access(db,user,cid)
    if not DEMO_MODE:raise HTTPException(404,'Legacy demonstration is disabled. Use the material-grounded viva workflow.')
    from sample_data.legacy_viva import evaluate_demo
    return evaluate_demo(db,user,cid,data)

@router.post('/quiz/{rid}/finish')
def finish_quiz(rid:int,user=Depends(current_user),db=Depends(get_db)):
    run=db.get(QuizRun,rid)
    if not run or run.student_id!=user.id:raise HTTPException(404,'Assessment not found.')
    course_access(db,user,run.course_id);run.finished=True;db.commit();return quiz_payload(db,run)
@router.post('/quiz/{rid}/hint')
def hint(rid:int,user=Depends(current_user),db=Depends(get_db)):
    run=db.get(QuizRun,rid)
    if not run or run.student_id!=user.id:raise HTTPException(404,'Assessment not found.')
    course_access(db,user,run.course_id)
    if run.mode=='mock':raise HTTPException(403,'Hints are unavailable during a mock exam.')
    if run.finished or run.expires<now() or run.cursor>=len(run.question_ids):raise HTTPException(409,'This assessment is no longer active.')
    qid=run.question_ids[run.cursor];q=db.get(Question,qid)
    run.hint_ids=list(set((run.hint_ids or [])+[qid]));db.commit()
    return {'hint':db.get(Topic,q.topic_id).description,'message':'This is assisted practice; a correct answer will have reduced weight in the knowledge model.'}
@router.get('/courses/{cid}/assessments')
def history(cid:int,user=Depends(current_user),db=Depends(get_db)):
    role(user,'student');course_access(db,user,cid)
    return [{'id':r.id,'mode':r.mode,'created':r.created,'expires':r.expires,'complete':r.finished or r.cursor>=len(r.question_ids) or r.expires<now(),'answered':r.cursor,'total':len(r.question_ids)} for r in db.scalars(select(QuizRun).where(QuizRun.student_id==user.id,QuizRun.course_id==cid).order_by(QuizRun.id.desc()).limit(30))]
