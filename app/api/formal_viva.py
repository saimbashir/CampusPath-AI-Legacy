"""Material-grounded formal oral/written assessments with immutable publication and review."""
from datetime import datetime,timedelta
from collections import defaultdict,Counter
from secrets import SystemRandom
from itertools import combinations
from fastapi import APIRouter,Depends,HTTPException
from pydantic import Field,model_validator
from sqlalchemy import select,update
from app.db import get_db
from app.models import VivaExam,VivaQuestion,OralSession,OralResponse,OralReview,Topic,User,Mastery,Revision,Enrollment,now
from app.schemas import Input
from app.auth.security import current_user,course_access,role,audit,throttle
from app.services.materials import MaterialScope,resolve,validate_citations
from app.services.planning import utc_naive
from app.services.notifications import notify
from app.ai import grounded
from app.mastery.engine import update_mastery,revision_dates
router=APIRouter(prefix='/api')
class VivaConfig(Input):
    count:int=Field(default=5,ge=1,le=30)
    total_marks:float=Field(default=25,gt=0,le=1000)
    minutes:int=Field(default=20,ge=1,le=180)
    difficulty:str=Field(default='Mixed',pattern='^(Mixed|1|2|3)$')
    follow_up_depth:int=Field(default=1,ge=0,le=3)
    immediate_feedback:bool=True
    review_required:bool=True
    question_review_required:bool=True
    show_topic:bool=True
    personalize_questions:bool=True
    starts:datetime|None=None
    ends:datetime|None=None
    student_ids:list[int]=Field(default_factory=list,max_length=1000)
    bloom_distribution:dict[str,int]=Field(default_factory=dict)
    question_types:list[str]=Field(default_factory=lambda:['Oral Viva'],max_length=14)
    rubric:list[grounded.RubricCriterion]=Field(default_factory=lambda:[grounded.RubricCriterion(**c) for c in grounded.DEFAULT_RUBRIC],min_length=1,max_length=12)
    @model_validator(mode='after')
    def valid(self):
        if abs(self.total_marks*100-round(self.total_marks*100))>.0001 or self.total_marks*100<self.count:raise ValueError('Use marks with at most two decimal places and at least 0.01 per question.')
        if abs(sum(r.weight for r in self.rubric)-100)>.001 or len({r.name for r in self.rubric})!=len(self.rubric):raise ValueError('Distinct rubric criteria must total 100%.')
        if self.starts:self.starts=utc_naive(self.starts)
        if self.ends:self.ends=utc_naive(self.ends)
        if self.starts and self.ends and self.ends<=self.starts:raise ValueError('End must be after start.')
        levels={'Remember','Understand','Apply','Analyze','Evaluate','Create'}
        if self.bloom_distribution and (set(self.bloom_distribution)-levels or sum(self.bloom_distribution.values())!=100 or any(v<0 for v in self.bloom_distribution.values())):raise ValueError('Known Bloom percentages must total 100.')
        allowed={'Oral Viva','MCQ','True/False','Short Answer','Long Answer','Numerical','Problem Solving','Scenario-Based','Conceptual','Definition','Comparison','Programming Question','Application Question','Analysis Question'}
        if not self.question_types or not set(self.question_types)<=allowed:raise ValueError('Select supported question types.')
        return self
class CreateViva(Input):
    title:str=Field(min_length=3,max_length=180)
    scope:MaterialScope=Field(default_factory=MaterialScope)
    config:VivaConfig=Field(default_factory=VivaConfig)
class AddQuestion(grounded.GroundedQuestion):
    approved:bool=False
class PublishQuestion(Input):approved:bool
class OralAnswer(Input):
    turn:int=Field(ge=0)
    transcript:str=Field(min_length=2,max_length=12000)
class ReviewMarks(Input):
    marks:float=Field(ge=0,le=1000)
    feedback:str=Field(min_length=3,max_length=4000)
    flagged:bool=False

def exam_access(db,user,eid,teacher=False):
    ex=db.get(VivaExam,eid)
    if not ex:raise HTTPException(404,'Viva not found.')
    course_access(db,user,ex.course_id,teacher)
    if user.role=='student' and (ex.status!='PUBLISHED' or (ex.config.get('student_ids') and user.id not in ex.config['student_ids'])):raise HTTPException(404,'Viva not assigned.')
    return ex

def session_access(db,user,sid,teacher=False):
    s=db.get(OralSession,sid)
    if not s:raise HTTPException(404,'Session not found.')
    ex=exam_access(db,user,s.viva_id,teacher)
    if not teacher and s.student_id!=user.id:raise HTTPException(404,'Session not found.')
    return s,ex

def evidence_for(db,ex):
    return resolve(db,ex.course_id,MaterialScope.model_validate(ex.scope))

def teacher_question(q):return {'id':q.id,'approved':q.approved,**{k:v for k,v in q.content.items() if k!='sources'},'question_text':q.prompt,'marks':q.marks,'topic_id':q.topic_id,'sources':q.content.get('sources',[])}

def exam_payload(db,ex,teacher=False):
    conf=ex.config
    result={'id':ex.id,'course_id':ex.course_id,'title':ex.title,'status':ex.status,'count':conf['count'],'total_marks':conf['total_marks'],'minutes':conf['minutes'],'starts':conf.get('starts'),'ends':conf.get('ends'),'review_required':conf['review_required'],'immediate_feedback':conf['immediate_feedback'],'personalize_questions':conf.get('personalize_questions',False),'created':ex.created}
    if teacher:result.update(scope=ex.scope,config=conf,questions=[teacher_question(q) for q in db.scalars(select(VivaQuestion).where(VivaQuestion.viva_id==ex.id).order_by(VivaQuestion.id))])
    return result

def latest_responses(db,s):
    records=db.scalars(select(OralResponse).where(OralResponse.session_id==s.id).order_by(OralResponse.turn)).all()
    return records,{r.question_id:r for r in records}

def finish_expired(db,s):
    if s.status=='IN_PROGRESS' and s.expires<=now():s.status='TEACHER_REVIEW_REQUIRED';s.submitted=now();db.commit()

def session_payload(db,s,ex,teacher=False):
    finish_expired(db,s);records,latest=latest_responses(db,s);questions=[db.get(VivaQuestion,qid) for qid in s.question_ids]
    reviews={r.question_id:r for r in db.scalars(select(OralReview).where(OralReview.session_id==s.id))}
    complete=s.status!='IN_PROGRESS';feedback=teacher or complete or ex.config['immediate_feedback']
    proposed=[latest[q.id].proposed_marks if q.id in latest else (0 if complete else None) for q in questions]
    total_ai=round(sum(proposed),2) if complete and all(v is not None for v in proposed) else None
    confirmed=round(sum(r.marks for r in reviews.values()),2) if s.status=='FINALIZED' else None
    result={'id':s.id,'viva_id':ex.id,'title':ex.title,'course_id':ex.course_id,'status':s.status,'index':s.cursor,'turn':s.turn,'total':len(questions),'total_marks':ex.config['total_marks'],'expires':s.expires,'created':s.created,'complete':complete,'follow_up_depth':s.follow_depth,'immediate_feedback':ex.config['immediate_feedback'],'ai_proposed_marks':total_ai,'confirmed_marks':confirmed,'percentage':round(100*confirmed/ex.config['total_marks'],1) if confirmed is not None else None,'review_required':ex.config['review_required']}
    result['responses']=[{'id':r.id,'question_id':r.question_id,'prompt':r.prompt,'transcript':r.transcript,'depth':r.depth,'created':r.created,**({'evaluation':{k:v for k,v in r.evaluation.items() if k not in ('follow_up','follow_up_citations')},'proposed_marks':r.proposed_marks,'provider':r.provider} if feedback else {})} for r in records]
    result['reviews']=[{'question_id':r.question_id,'marks':r.marks,'feedback':r.feedback,'flagged':r.flagged,'finalized':r.finalized} for r in reviews.values()] if teacher or complete else []
    if not complete:
        q=questions[s.cursor];prompt=s.next_prompt['text'] if s.next_prompt else q.prompt
        result['question']={'id':q.id,'question_text':prompt,'marks':q.marks,'type':q.content['question_type'],'topic':db.get(Topic,q.topic_id).name if q.topic_id and ex.config['show_topic'] else None,'is_follow_up':s.follow_depth>0,'options':q.content.get('options',[])}
    if teacher:
        u=db.get(User,s.student_id);result.update(student_id=u.id,name=u.name,university_id=u.university_id,questions=[teacher_question(q) for q in questions],rubric=ex.config['rubric'],scope=ex.scope)
    return result

@router.get('/courses/{cid}/vivas')
def list_vivas(cid:int,user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid);teacher=user.role=='teacher'
    exams=db.scalars(select(VivaExam).where(VivaExam.course_id==cid).order_by(VivaExam.id.desc())).all()
    return [exam_payload(db,e,teacher) for e in exams if teacher or e.status=='PUBLISHED' and (not e.config.get('student_ids') or user.id in e.config['student_ids'])]
@router.post('/courses/{cid}/vivas',status_code=201)
def create(cid:int,data:CreateViva,user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid,True);resolve(db,cid,data.scope)
    enrolled=set(db.scalars(select(Enrollment.student_id).where(Enrollment.course_id==cid)))
    if not set(data.config.student_ids)<=enrolled:raise HTTPException(422,'Assigned students must be enrolled in this section.')
    ex=VivaExam(course_id=cid,teacher_id=user.id,title=data.title,config=data.config.model_dump(mode='json'),scope=data.scope.model_dump(),status='DRAFT');db.add(ex);audit(db,user,'viva created',cid);db.commit();return exam_payload(db,ex,True)
@router.get('/vivas/{eid}')
def get_exam(eid:int,user=Depends(current_user),db=Depends(get_db)):
    ex=exam_access(db,user,eid);return exam_payload(db,ex,user.role=='teacher')

def mutable(ex):
    if ex.status!='DRAFT':raise HTTPException(409,'Published viva is immutable. Create a new draft for changes.')

def lock_draft(db,ex):
    changed=db.execute(update(VivaExam).where(VivaExam.id==ex.id,VivaExam.status=='DRAFT').values(status='DRAFT'))
    if changed.rowcount!=1:db.rollback();raise HTTPException(409,'Viva has already been published.')

def store_question(db,ex,data,approved=False,sources=None,provider='MANUAL'):
    values=data.model_dump();q=VivaQuestion(viva_id=ex.id,topic_id=data.topic_id,prompt=data.question_text,marks=data.marks,approved=approved,content={**values,'sources':sources or [],'provider':provider});db.add(q);return q

def validate_topic(db,ex,q):
    if q.topic_id:
        topic=db.get(Topic,q.topic_id)
        if not topic or topic.course_id!=ex.course_id:raise HTTPException(422,'Question topic is outside the course.')
        if ex.scope.get('topic_ids') and q.topic_id not in ex.scope['topic_ids']:raise HTTPException(422,'Question topic is outside the selected scope.')
        if ex.scope.get('clos') and topic.clo not in ex.scope['clos']:raise HTTPException(422,'Question CLO is outside scope.')

@router.post('/vivas/{eid}/generate')
async def generate(eid:int,user=Depends(current_user),db=Depends(get_db)):
    ex=exam_access(db,user,eid,True);mutable(ex);throttle(db,'formal-generation:'+str(user.id),15)
    if db.scalar(select(VivaQuestion.id).where(VivaQuestion.viva_id==eid)):raise HTTPException(409,'Delete draft questions before regenerating the full set, or add a manual question.')
    context=evidence_for(db,ex);topics=[{'id':t.id,'name':t.name,'clo':t.clo,'source_ids':(t.structure or {}).get('source_ids',[])} for t in db.scalars(select(Topic).where(Topic.course_id==ex.course_id))]
    try:
        qs,provider=await grounded.questions(context,topics,ex.config)
        for q in qs:
            validate_topic(db,ex,q)
            if q.question_type not in ex.config['question_types']:raise ValueError('Question type does not match the requested configuration.')
        if ex.config['difficulty']!='Mixed' and any(q.difficulty!=int(ex.config['difficulty']) for q in qs):raise ValueError('Generated difficulty does not match the configuration.')
        if ex.config['bloom_distribution']:
            from app.assessment.selection import quotas
            expected=quotas(ex.config['bloom_distribution'],len(qs),{})
            actual=Counter(q.bloom for q in qs)
            if any(actual.get(k,0)!=v for k,v in expected.items()) or set(actual)-set(expected):raise ValueError('Generated Bloom distribution does not match the configuration.')
        lock_draft(db,ex)
        if db.scalar(select(VivaQuestion.id).where(VivaQuestion.viva_id==eid)):raise HTTPException(409,'Another request added questions. Refresh the draft.')
        for q in qs:store_question(db,ex,q,approved=not ex.config['question_review_required'],sources=validate_citations(q.citations,context),provider=provider)
    except HTTPException:raise
    except Exception as exc:db.rollback();raise HTTPException(502,str(exc) if isinstance(exc,ValueError) else 'Question generation unavailable. Add supported questions manually or try again.')
    audit(db,user,'viva questions generated',eid);db.commit();return exam_payload(db,ex,True)
class GenerateMore(Input):
    count:int=Field(default=10,ge=1,le=30)

@router.post('/vivas/{eid}/generate-more')
async def generate_more(eid:int,data:GenerateMore,user=Depends(current_user),db=Depends(get_db)):
    """Extend a draft question bank, retaining teacher approval and source checks."""
    ex=exam_access(db,user,eid,True);mutable(ex)
    if not ex.config.get('personalize_questions',False):
        raise HTTPException(409,'Enable personalized questions before expanding the bank.')
    throttle(db,'formal-generation:'+str(user.id),15)
    existing=db.scalars(select(VivaQuestion).where(VivaQuestion.viva_id==eid)).all()
    unit=round(ex.config['total_marks']/ex.config['count'],2)
    if abs(ex.config['count']*unit-ex.config['total_marks'])>.001:
        raise HTTPException(409,'Expanded banks need equal per-question marks. Adjust the exam total or count.')
    if existing and any(abs(q.marks-unit)>.001 for q in existing):
        raise HTTPException(409,'All bank questions must have the same marks for per-student selection.')
    context=evidence_for(db,ex)
    topics=[{'id':t.id,'name':t.name,'clo':t.clo,'source_ids':(t.structure or {}).get('source_ids',[])} for t in db.scalars(select(Topic).where(Topic.course_id==ex.course_id))]
    temp={**ex.config,'count':data.count,'total_marks':round(unit*data.count,2)}
    try:
        qs,provider=await grounded.questions(context,topics,temp,existing_prompts=[q.prompt for q in existing])
        seen={q.prompt.strip().casefold() for q in existing}
        if len(qs)!=data.count:raise ValueError('The requested number of distinct questions was not produced.')
        for q in qs:
            validate_topic(db,ex,q)
            if q.question_type not in ex.config['question_types']:raise ValueError('Question type is outside the configured mix.')
            if abs(q.marks-unit)>.001:raise ValueError('Question marks do not match the pool allocation.')
            if q.question_text.strip().casefold() in seen:raise ValueError('A generated question repeats an existing question.')
            seen.add(q.question_text.strip().casefold())
        lock_draft(db,ex)
        for q in qs:store_question(db,ex,q,approved=not ex.config['question_review_required'],sources=validate_citations(q.citations,context),provider=provider)
    except HTTPException:raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(502,str(exc) if isinstance(exc,ValueError) else 'Unable to expand the bank. Add questions manually or retry.')
    audit(db,user,'viva question pool expanded',eid);db.commit()
    return exam_payload(db,ex,True)

@router.post('/vivas/{eid}/questions',status_code=201)
async def add_question(eid:int,data:AddQuestion,user=Depends(current_user),db=Depends(get_db)):
    ex=exam_access(db,user,eid,True);mutable(ex);lock_draft(db,ex);validate_topic(db,ex,data)
    try:sources=validate_citations(data.citations,evidence_for(db,ex))
    except ValueError as exc:raise HTTPException(422,str(exc))
    store_question(db,ex,grounded.GroundedQuestion.model_validate(data.model_dump(exclude={'approved'})),data.approved,sources);db.commit();return exam_payload(db,ex,True)
@router.put('/vivas/{eid}/questions/{qid}')
def edit_question(eid:int,qid:int,data:AddQuestion,user=Depends(current_user),db=Depends(get_db)):
    ex=exam_access(db,user,eid,True);mutable(ex);lock_draft(db,ex);q=db.get(VivaQuestion,qid)
    if not q or q.viva_id!=eid:raise HTTPException(404,'Question not found.')
    validate_topic(db,ex,data)
    try:sources=validate_citations(data.citations,evidence_for(db,ex))
    except ValueError as exc:raise HTTPException(422,str(exc))
    q.prompt=data.question_text;q.topic_id=data.topic_id;q.marks=data.marks;q.approved=data.approved;q.content={**data.model_dump(exclude={'approved'}),'sources':sources,'provider':'TEACHER EDITED'};db.commit();return exam_payload(db,ex,True)
@router.delete('/vivas/{eid}/questions/{qid}')
def delete_question(eid:int,qid:int,user=Depends(current_user),db=Depends(get_db)):
    ex=exam_access(db,user,eid,True);mutable(ex);lock_draft(db,ex);q=db.get(VivaQuestion,qid)
    if not q or q.viva_id!=eid:raise HTTPException(404,'Question not found.')
    db.delete(q);db.commit();return {'ok':True}
@router.post('/vivas/{eid}/questions/{qid}/review')
def question_review(eid:int,qid:int,data:PublishQuestion,user=Depends(current_user),db=Depends(get_db)):
    ex=exam_access(db,user,eid,True);mutable(ex);lock_draft(db,ex);q=db.get(VivaQuestion,qid)
    if not q or q.viva_id!=eid:raise HTTPException(404,'Question not found.')
    q.approved=data.approved;db.commit();return {'ok':True}
@router.post('/vivas/{eid}/publish')
def publish(eid:int,user=Depends(current_user),db=Depends(get_db)):
    ex=exam_access(db,user,eid,True);mutable(ex);lock_draft(db,ex);qs=db.scalars(select(VivaQuestion).where(VivaQuestion.viva_id==eid,VivaQuestion.approved.is_(True))).all()
    count=ex.config['count']
    if ex.config.get('personalize_questions',False):
        if len(qs)<count:raise HTTPException(409,'Approve at least the requested number of questions to publish.')
        if len(qs)==count:
            if abs(sum(q.marks for q in qs)-ex.config['total_marks'])>.001:raise HTTPException(409,'Approved marks must total the exam marks.')
        else:
            unit=ex.config['total_marks']/count
            if any(abs(q.marks-unit)>.001 for q in qs):raise HTTPException(409,'An expanded pool needs equal per-question marks so every student receives the same total.')
    elif len(qs)!=count or abs(sum(q.marks for q in qs)-ex.config['total_marks'])>.001:
        raise HTTPException(409,'Approve exactly the configured question count, with marks adding to the configured total.')
    context=evidence_for(db,ex)
    for q in qs:
        try:validate_citations(q.content['citations'],context)
        except ValueError as exc:raise HTTPException(422,str(exc))
    ex.status='PUBLISHED';audit(db,user,'viva published',eid);db.commit();return exam_payload(db,ex,True)
@router.post('/vivas/{eid}/start')
def start(eid:int,user=Depends(current_user),db=Depends(get_db)):
    role(user,'student');ex=exam_access(db,user,eid)
    old=db.scalar(select(OralSession).where(OralSession.viva_id==eid,OralSession.student_id==user.id))
    if old:return session_payload(db,old,ex)
    for key in ('starts','ends'):
        value=ex.config.get(key)
        if value:
            date=utc_naive(datetime.fromisoformat(value))
            if (key=='starts' and now()<date) or (key=='ends' and now()>date):raise HTTPException(409,'Viva is outside its availability window.')
    ids=list(db.scalars(select(VivaQuestion.id).where(VivaQuestion.viva_id==eid,VivaQuestion.approved.is_(True)).order_by(VivaQuestion.id)))
    if len(ids)<ex.config['count']:raise HTTPException(409,'The question bank is too small. Ask your teacher to check this viva.')
    if ex.config.get('personalize_questions',False):
        # Select from approved questions, without reusing a complete question set
        # while unused combinations are still available. Older sessions stay fixed.
        rng=SystemRandom()
        prior={tuple(sorted(previous.question_ids)) for previous in db.scalars(select(OralSession).where(OralSession.viva_id==eid))}
        pool=list(ids)
        rng.shuffle(pool)
        selected=pool[:ex.config['count']]
        if len(pool)>ex.config['count'] and tuple(sorted(selected)) in prior:
            # Randomly shuffle first, then search a bounded number of alternatives.
            for candidate in combinations(pool,ex.config['count']):
                if tuple(sorted(candidate)) not in prior:
                    selected=list(candidate)
                    rng.shuffle(selected)
                    break
        ids=selected
    else:
        ids=ids[:ex.config['count']]
    expiry=now()+timedelta(minutes=ex.config['minutes'])
    if ex.config.get('ends'):expiry=min(expiry,utc_naive(datetime.fromisoformat(ex.config['ends'])))
    s=OralSession(viva_id=eid,student_id=user.id,question_ids=ids,cursor=0,turn=0,follow_depth=0,status='IN_PROGRESS',expires=expiry);db.add(s);db.commit();return session_payload(db,s,ex)
@router.get('/oral-sessions/{sid}')
def get_session(sid:int,user=Depends(current_user),db=Depends(get_db)):
    s,ex=session_access(db,user,sid);return session_payload(db,s,ex)
@router.post('/oral-sessions/{sid}/answer')
async def answer(sid:int,data:OralAnswer,user=Depends(current_user),db=Depends(get_db)):
    role(user,'student');s,ex=session_access(db,user,sid);throttle(db,'formal-answer:'+str(user.id),90)
    if s.status!='IN_PROGRESS' or s.expires<=now():raise HTTPException(409,'Session is complete or expired. Open the saved results.')
    if s.turn!=data.turn:raise HTTPException(409,'This turn is already saved or is not currently issued.')
    turn=s.turn;cursor=s.cursor;depth=s.follow_depth;q=db.get(VivaQuestion,s.question_ids[cursor]);prompt=s.next_prompt['text'] if s.next_prompt else q.prompt
    records,_=latest_responses(db,s);history=[{'question_id':r.question_id,'question':r.prompt,'answer':r.transcript,'feedback':r.evaluation.get('feedback','')} for r in records]
    sources=list({src['id']:src for question_id in s.question_ids for src in db.get(VivaQuestion,question_id).content['sources']}.values())
    try:evaluation,provider=await grounded.evaluate({**q.content,'question_text':q.prompt,'current_prompt':prompt,'question_id':q.id,'marks':q.marks},data.transcript,history,ex.config['rubric'],sources)
    except Exception:evaluation={'correctness':'insufficient_evidence','feedback':'Evaluation is unavailable or failed evidence validation. Your answer is saved for teacher review.','confidence':0,'marks':None,'scoring':[],'correct_points':[],'incorrect_points':[],'missing_points':[],'misconceptions':[],'follow_up':''};provider='PROVIDER FALLBACK'
    # Never accept output outside the current question's maximum.
    proposed=evaluation.get('marks')
    if proposed is not None and not 0<=proposed<=q.marks:raise HTTPException(502,'Evaluation marks failed validation.')
    follow=evaluation.get('follow_up','') if depth<ex.config['follow_up_depth'] else ''
    # Repeated prompts are not additional evidence: advance instead of trapping a student.
    normalize=lambda text:' '.join(text.casefold().split()).rstrip('?.!')
    prior_prompts={normalize(q.prompt),normalize(prompt)}|{normalize(r.prompt) for r in records if r.question_id==q.id}
    if follow and normalize(follow) in prior_prompts:
        follow='';evaluation['follow_up']='';evaluation['follow_up_citations']=[]
    newcursor=cursor if follow else cursor+1;newdepth=depth+1 if follow else 0
    complete=newcursor>=len(s.question_ids)
    claim=db.execute(update(OralSession).where(OralSession.id==sid,OralSession.turn==turn,OralSession.status=='IN_PROGRESS',OralSession.expires>now()).values(turn=turn+1,cursor=newcursor,follow_depth=newdepth,next_prompt={'text':follow,'citations':evaluation.get('follow_up_citations',[])} if follow else None,status='TEACHER_REVIEW_REQUIRED' if complete else 'IN_PROGRESS',submitted=now() if complete else None))
    if claim.rowcount!=1:db.rollback();raise HTTPException(409,'Session changed or time expired while evaluating. Refresh the saved session.')
    r=OralResponse(session_id=sid,question_id=q.id,turn=turn,depth=depth,prompt=prompt,transcript=data.transcript,evaluation=evaluation,proposed_marks=proposed,provider=provider);db.add(r);db.commit();db.refresh(s)
    if complete and not ex.config['review_required']:auto_finalize(db,s,ex)
    return session_payload(db,s,ex)
@router.post('/oral-sessions/{sid}/finish')
def finish(sid:int,user=Depends(current_user),db=Depends(get_db)):
    s,ex=session_access(db,user,sid)
    if s.status=='IN_PROGRESS':s.status='TEACHER_REVIEW_REQUIRED';s.submitted=now();db.commit()
    return session_payload(db,s,ex)
@router.get('/courses/{cid}/oral-history')
def history(cid:int,user=Depends(current_user),db=Depends(get_db)):
    role(user,'student');course_access(db,user,cid)
    rows=db.scalars(select(OralSession).join(VivaExam,VivaExam.id==OralSession.viva_id).where(VivaExam.course_id==cid,OralSession.student_id==user.id).order_by(OralSession.id.desc()).limit(100)).all()
    return [session_payload(db,s,db.get(VivaExam,s.viva_id)) for s in rows]
@router.get('/courses/{cid}/oral-review')
def queue(cid:int,q:str='',user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid,True)
    rows=db.scalars(select(OralSession).join(VivaExam,VivaExam.id==OralSession.viva_id).join(User,User.id==OralSession.student_id).where(VivaExam.course_id==cid).order_by(OralSession.created.desc()).limit(300)).all()
    return [session_payload(db,s,db.get(VivaExam,s.viva_id),True) for s in rows if q.lower() in (db.get(User,s.student_id).name+' '+db.get(User,s.student_id).university_id).lower()]
@router.put('/oral-sessions/{sid}/questions/{qid}/review')
def review(sid:int,qid:int,data:ReviewMarks,user=Depends(current_user),db=Depends(get_db)):
    s,ex=session_access(db,user,sid,True);finish_expired(db,s)
    if s.status in ('IN_PROGRESS','FINALIZED'):raise HTTPException(409,'Submit the session before review; finalized results cannot be overwritten.')
    claim=db.execute(update(OralSession).where(OralSession.id==sid,OralSession.status=='TEACHER_REVIEW_REQUIRED').values(status='TEACHER_REVIEW_REQUIRED'))
    if claim.rowcount!=1:db.rollback();raise HTTPException(409,'Session changed. Refresh before reviewing.')
    if qid not in s.question_ids:raise HTTPException(404,'Question not in this session.')
    question=db.get(VivaQuestion,qid)
    if data.marks>question.marks:raise HTTPException(422,'Marks exceed this question maximum.')
    r=db.scalar(select(OralReview).where(OralReview.session_id==sid,OralReview.question_id==qid))
    if not r:r=OralReview(session_id=sid,question_id=qid,teacher_id=user.id);db.add(r)
    r.marks=data.marks;r.feedback=data.feedback;r.flagged=data.flagged;r.teacher_id=user.id
    audit(db,user,'viva marks reviewed',f'{sid}:{qid}');db.commit();return session_payload(db,s,ex,True)

def finalize(db,s,ex,user,automated=False):
    claimed=db.execute(update(OralSession).where(OralSession.id==s.id,OralSession.status=='TEACHER_REVIEW_REQUIRED').values(status='FINALIZED'))
    if claimed.rowcount!=1:db.rollback();raise HTTPException(409,'This viva has already been finalized or is still active.')
    reviews=list(db.scalars(select(OralReview).where(OralReview.session_id==s.id)))
    if {r.question_id for r in reviews}!=set(s.question_ids):db.rollback();raise HTTPException(409,'Review every main question before finalizing.')
    if any(r.flagged for r in reviews):db.rollback();raise HTTPException(409,'Resolve flagged evaluations before finalizing.')
    for r in reviews:
        r.finalized=True;q=db.get(VivaQuestion,r.question_id)
        if q.topic_id and not automated:
            m=db.scalar(select(Mastery).where(Mastery.student_id==s.student_id,Mastery.topic_id==q.topic_id))
            if not m:m=Mastery(student_id=s.student_id,topic_id=q.topic_id,probability=.2,attempts=0,correct=0);db.add(m);db.flush()
            before=m.probability;correct=r.marks/q.marks>=.7;after=before+.35*(update_mastery(before,correct,q.content['difficulty'],guess=.1)-before)
            changed=db.execute(update(Mastery).where(Mastery.id==m.id,Mastery.attempts==m.attempts,Mastery.probability==before).values(probability=after,attempts=Mastery.attempts+1,correct=Mastery.correct+int(correct),last_practiced=now()))
            if changed.rowcount!=1:db.rollback();raise HTTPException(409,'Learning evidence changed concurrently. Retry finalization.')
            db.refresh(m);r.mastery_before=before;r.mastery_after=after
            for due in revision_dates(now(),after):db.add(Revision(student_id=s.student_id,topic_id=q.topic_id,due=due))
    total=round(sum(r.marks for r in reviews),2)
    notify(db,s.student_id,ex.course_id,f'oral-final:{s.id}',ex.title+' graded',f'{ex.title} graded: {total:g}/{ex.config["total_marks"]:g}. '+('Auto-finalized under the teacher-enabled policy.' if automated else 'Your teacher confirmed the final result.'),'formal-viva')
    audit(db,user,'viva auto-finalized' if automated else 'viva finalized',s.id);db.commit();db.refresh(s)

def auto_finalize(db,s,ex):
    _,latest=latest_responses(db,s)
    if any(qid not in latest or latest[qid].proposed_marks is None or latest[qid].evaluation.get('confidence',0)<.7 for qid in s.question_ids):return
    for qid in s.question_ids:
        r=latest[qid];db.add(OralReview(session_id=s.id,question_id=qid,teacher_id=ex.teacher_id,marks=r.proposed_marks,feedback='AUTO-FINALIZED: '+r.evaluation['feedback'],flagged=False))
    db.flush();finalize(db,s,ex,db.get(User,ex.teacher_id),automated=True)
@router.post('/oral-sessions/{sid}/finalize')
def confirm(sid:int,user=Depends(current_user),db=Depends(get_db)):
    s,ex=session_access(db,user,sid,True);finalize(db,s,ex,user);return session_payload(db,s,ex,True)
@router.get('/courses/{cid}/viva-analytics')
def analytics(cid:int,user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid,True)
    sessions=db.scalars(select(OralSession).join(VivaExam,VivaExam.id==OralSession.viva_id).where(VivaExam.course_id==cid)).all()
    scores=[];groups={'topics':defaultdict(list),'clos':defaultdict(list),'difficulty':defaultdict(list)};missing=Counter();mistakes=Counter();support=[]
    for s in sessions:
        records,latest=latest_responses(db,s)
        for r in latest.values():missing.update(r.evaluation.get('missing_points',[]));mistakes.update(r.evaluation.get('misconceptions',[]))
        if s.status!='FINALIZED':continue
        reviews=db.scalars(select(OralReview).where(OralReview.session_id==s.id)).all();ex=db.get(VivaExam,s.viva_id)
        pct=100*sum(r.marks for r in reviews)/ex.config['total_marks'];scores.append(pct)
        if pct<60:
            u=db.get(User,s.student_id);support.append({'name':u.name,'university_id':u.university_id,'percentage':round(pct,1),'viva':ex.title})
        for r in reviews:
            question=db.get(VivaQuestion,r.question_id);pct=100*r.marks/question.marks
            groups['topics'][db.get(Topic,question.topic_id).name if question.topic_id else 'Unmapped'].append(pct);groups['clos'][question.content.get('clo') or 'Unmapped'].append(pct);groups['difficulty'][str(question.content['difficulty'])].append(pct)
    return {'sessions':len(sessions),'finalized':len(scores),'class_average':round(sum(scores)/len(scores),1) if scores else None,'highest':round(max(scores),1) if scores else None,**{k:{key:round(sum(vals)/len(vals),1) for key,vals in mapping.items()} for k,mapping in groups.items()},'missing_concepts':missing.most_common(15),'misconceptions':mistakes.most_common(15),'support':support,'methodology':'Marks use finalized sessions. Missing-concept and misconception labels are provisional AI observations requiring teacher interpretation.'}

@router.post('/vivas/{eid}/questions/{qid}/regenerate')
async def regenerate(eid:int,qid:int,user=Depends(current_user),db=Depends(get_db)):
    ex=exam_access(db,user,eid,True);mutable(ex);q=db.get(VivaQuestion,qid)
    if not q or q.viva_id!=eid:raise HTTPException(404,'Question not found.')
    throttle(db,'formal-generation:'+str(user.id),15)
    evidence=evidence_for(db,ex)
    config={**ex.config,'count':1,'total_marks':q.marks,'bloom_distribution':{},'question_types':[q.content['question_type']]}
    topics=[{'id':t.id,'name':t.name,'clo':t.clo,'source_ids':(t.structure or {}).get('source_ids',[])} for t in db.scalars(select(Topic).where(Topic.course_id==ex.course_id))]
    try:
        generated,provider=await grounded.questions(evidence,topics,config);draft=generated[0];validate_topic(db,ex,draft);sources=validate_citations(draft.citations,evidence)
        if draft.question_type not in config['question_types'] or (config['difficulty']!='Mixed' and draft.difficulty!=int(config['difficulty'])):
            raise ValueError('Regenerated question does not match the requested type or difficulty.')
    except Exception:raise HTTPException(502,'Regeneration failed validation; the previous draft was preserved.')
    # Recheck publication after the provider call before changing the draft.
    claim=db.execute(update(VivaExam).where(VivaExam.id==eid,VivaExam.status=='DRAFT').values(status='DRAFT'))
    if claim.rowcount!=1:db.rollback();raise HTTPException(409,'Viva was published during generation.')
    q.prompt=draft.question_text;q.topic_id=draft.topic_id;q.content={**draft.model_dump(),'sources':sources,'provider':provider};q.approved=False
    db.commit();return exam_payload(db,ex,True)
