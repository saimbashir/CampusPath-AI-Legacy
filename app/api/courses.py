import secrets
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError
from app.db import get_db
from app.models import Course,Enrollment,Topic,Resource,ResourceBlob,Chunk,Question
from app.schemas import CourseInput,CodeInput,TopicInput,QuestionInput
from app.auth.security import current_user,role,course_access,audit,teacher_courses
from app.documents.extract import extract
from app.knowledge_graph.engine import validate_dag
from app.config import MAX_UPLOAD
router=APIRouter(prefix='/api')
def course_dict(c,user):
    result={k:getattr(c,k) for k in ('id','name','code','section','semester','description','clos','material_only')}
    if user.role=='teacher':result['enrollment_code']=c.enrollment_code
    return result
@router.get('/courses')
def courses(user=Depends(current_user),db=Depends(get_db)):
    if user.role=='teacher':q=select(Course).where(Course.id.in_(teacher_courses(user)))
    elif user.role=='student':q=select(Course).join(Enrollment,Enrollment.course_id==Course.id).where(Enrollment.student_id==user.id)
    else:return []
    return [course_dict(c,user) for c in db.scalars(q)]
@router.post('/courses',status_code=201)
def create(data:CourseInput,user=Depends(current_user),db=Depends(get_db)):
    role(user,'teacher')
    c=Course(**data.model_dump(),teacher_id=user.id,enrollment_code=secrets.token_urlsafe(9));db.add(c);db.flush();audit(db,user,'course created',c.id);db.commit()
    return course_dict(c,user)
@router.post('/courses/join')
def join(data:CodeInput,user=Depends(current_user),db=Depends(get_db)):
    role(user,'student')
    c=db.scalar(select(Course).where(Course.enrollment_code==data.code))
    if not c:raise HTTPException(404,'Invalid enrollment code.')
    db.add(Enrollment(course_id=c.id,student_id=user.id))
    try:db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,'Already enrolled.')
    return course_dict(c,user)
@router.get('/courses/{cid}/topics')
def topics(cid:int,user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid)
    return [{k:getattr(t,k) for k in ('id','name','description','prerequisites','clo','difficulty')} for t in db.scalars(select(Topic).where(Topic.course_id==cid))]
@router.post('/courses/{cid}/topics',status_code=201)
def add_topic(cid:int,data:TopicInput,user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid,True)
    t=Topic(course_id=cid,**data.model_dump());db.add(t);db.flush()
    try:validate_dag(db.scalars(select(Topic).where(Topic.course_id==cid)).all())
    except ValueError as e:db.rollback();raise HTTPException(422,str(e))
    audit(db,user,'topic created',t.id);db.commit();return {'id':t.id}
@router.put('/courses/{cid}/topics/{tid}')
def edit_topic(cid:int,tid:int,data:TopicInput,user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid,True)
    t=db.get(Topic,tid)
    if not t or t.course_id!=cid:raise HTTPException(404,'Topic not found.')
    for k,v in data.model_dump().items():setattr(t,k,v)
    try:validate_dag(db.scalars(select(Topic).where(Topic.course_id==cid)).all())
    except ValueError as e:db.rollback();raise HTTPException(422,str(e))
    audit(db,user,'topic edited',t.id);db.commit();return {'ok':True}
@router.get('/courses/{cid}/resources')
def resources(cid:int,user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid)
    rows=db.scalars(select(Resource).where(Resource.course_id==cid,or_(Resource.owner_id.is_(None),Resource.owner_id==user.id))).all()
    return [{'id':r.id,'filename':r.filename,'kind':r.kind,'created':r.created,'download_available':db.get(ResourceBlob,r.id) is not None} for r in rows]
@router.post('/courses/{cid}/resources',status_code=201)
def upload(cid:int,file:UploadFile=File(...),user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid)
    data=file.file.read(MAX_UPLOAD+1)
    if len(data)>MAX_UPLOAD:raise HTTPException(413,f'File limit is {MAX_UPLOAD//(1024*1024)} MiB.')
    filename=Path((file.filename or 'upload.txt').replace('\\','/')).name[:200]
    try:parts=extract(filename,data)
    except Exception as e:
        message=str(e) if isinstance(e,ValueError) else 'Could not parse this document. Check its format and encryption.'
        raise HTTPException(422,message)
    r=Resource(course_id=cid,owner_id=user.id if user.role=='student' else None,filename=filename,kind='PERSONAL MATERIAL' if user.role=='student' else 'COURSE MATERIAL')
    db.add(r);db.flush()
    db.add(ResourceBlob(resource_id=r.id,data=data,content_type='application/octet-stream'))
    from app.services.materials import annotated
    for location,text,structure in annotated(parts,filename):db.add(Chunk(resource_id=r.id,location=location,text=text,structure=structure))
    audit(db,user,'resource indexed',r.id);db.commit()
    from app.ai.vector import enabled,QdrantStore
    vector_status='Lexical index ready'
    if enabled():
        try:
            QdrantStore().index(db.scalars(select(Chunk).where(Chunk.resource_id==r.id)).all())
            vector_status='Lexical and semantic indexes ready'
        except Exception:vector_status='Lexical index ready; semantic indexing failed. Administrator can reindex.'
    return {'id':r.id,'chunks':len(parts),'message':'Text indexed. Source locations retained.','vector_status':vector_status}
@router.get('/courses/{cid}/resources/{rid}')
def read_resource(cid:int,rid:int,user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid)
    r=db.get(Resource,rid)
    if not r or r.course_id!=cid or r.owner_id not in (None,user.id):raise HTTPException(404,'Resource not found.')
    return {'filename':r.filename,'chunks':[{'id':c.id,'location':c.location,'text':c.text,'structure':c.structure or {}} for c in db.scalars(select(Chunk).where(Chunk.resource_id==rid))]}
@router.get('/courses/{cid}/questions')
def questions(cid:int,user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid,True)
    return [{k:getattr(q,k) for k in ('id','topic_id','prompt','options','correct','explanation','misconception','difficulty','bloom','approved','source','source_ids')} for q in db.scalars(select(Question).where(Question.course_id==cid))]
@router.post('/courses/{cid}/questions',status_code=201)
def question_create(cid:int,data:QuestionInput,user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid,True)
    t=db.get(Topic,data.topic_id)
    if not t or t.course_id!=cid:raise HTTPException(422,'Select a topic from this course.')
    if db.scalar(select(Question.id).where(Question.course_id==cid,Question.prompt==data.prompt)):raise HTTPException(409,'Duplicate question.')
    if data.source_ids:
        from app.services.materials import resolve,MaterialScope
        resolve(db,cid,MaterialScope(chunk_ids=data.source_ids))
    q=Question(course_id=cid,**data.model_dump());db.add(q);db.commit();return {'id':q.id}
@router.put('/courses/{cid}/questions/{qid}')
def question_edit(cid:int,qid:int,data:QuestionInput,user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid,True)
    q=db.get(Question,qid);t=db.get(Topic,data.topic_id)
    if not q or q.course_id!=cid or not t or t.course_id!=cid:raise HTTPException(404,'Question/topic not found.')
    # Preserve evidence: question versions with answers cannot be overwritten.
    from app.models import Answer,QuizRun
    if db.scalar(select(Answer.id).where(Answer.question_id==qid)) or any(qid in r.question_ids for r in db.scalars(select(QuizRun).where(QuizRun.course_id==cid))):
        raise HTTPException(409,'Question has been issued. Create a new version instead.')
    if data.source_ids:
        from app.services.materials import resolve,MaterialScope
        resolve(db,cid,MaterialScope(chunk_ids=data.source_ids))
    for k,v in data.model_dump().items():setattr(q,k,v)
    q.approved=False;db.commit();return {'ok':True}
@router.post('/courses/{cid}/questions/{qid}/{action}')
def review(cid:int,qid:int,action:str,user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid,True)
    q=db.get(Question,qid)
    if not q or q.course_id!=cid:raise HTTPException(404,'Question not found.')
    if action not in ('approve','reject'):raise HTTPException(400,'Unknown review action.')
    q.approved=action=='approve';audit(db,user,'question '+action,qid);db.commit();return {'ok':True}
@router.get('/courses/{cid}/search')
def search(cid:int,q:str='',user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid)
    if not 2<=len(q)<=200:raise HTTPException(422,'Search needs 2–200 characters.')
    from app.ai.retrieval import LexicalStore
    return {'topics':[{'id':t.id,'name':t.name} for t in db.scalars(select(Topic).where(Topic.course_id==cid)) if q.lower() in t.name.lower()],'resources':LexicalStore().search(db,user,cid,q)}
