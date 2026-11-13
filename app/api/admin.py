import os,shutil
from fastapi import APIRouter,Depends,HTTPException
from pydantic import Field
from sqlalchemy import select,delete,text
from app.db import get_db
from app.models import User,Course,TeacherAssignment,Session
from app.schemas import Input
from app.auth.security import current_user,role,audit
router=APIRouter(prefix='/api/admin')
class AssignmentInput(Input):
    course_id:int
    teacher_id:int
class AccountState(Input):
    active:bool
@router.get('/system')
def system(user=Depends(current_user),db=Depends(get_db)):
    role(user,'admin');db.execute(text('SELECT 1'))
    def configured(*names):return all(bool(os.getenv(n)) for n in names)
    return {'database':'connected','database_type':db.bind.dialect.name,'ocr_available':bool(shutil.which('tesseract')),'video_available':bool(shutil.which('ffmpeg')),'providers':{'llm':configured('LLM_BASE_URL','LLM_API_KEY','LLM_MODEL'),'stt':configured('SPEECH_BASE_URL','SPEECH_API_KEY','STT_MODEL'),'tts':configured('SPEECH_BASE_URL','SPEECH_API_KEY','TTS_MODEL','TTS_VOICE'),'semantic':configured('EMBEDDING_BASE_URL','EMBEDDING_API_KEY','EMBEDDING_MODEL','QDRANT_URL'),'email':configured('SMTP_HOST','SMTP_FROM')},'message':'Configuration presence is not a live connectivity test. API keys are never returned.'}
@router.get('/assignments')
def assignments(user=Depends(current_user),db=Depends(get_db)):
    role(user,'admin')
    return {'courses':[{'id':c.id,'name':c.name,'code':c.code,'section':c.section,'owner_id':c.teacher_id} for c in db.scalars(select(Course))],
            'teachers':[{'id':t.id,'name':t.name,'university_id':t.university_id} for t in db.scalars(select(User).where(User.role=='teacher',User.active.is_(True)))],
            'assignments':[{'id':a.id,'course_id':a.course_id,'teacher_id':a.teacher_id} for a in db.scalars(select(TeacherAssignment))]}
@router.post('/assignments')
def assign(data:AssignmentInput,user=Depends(current_user),db=Depends(get_db)):
    role(user,'admin');course=db.get(Course,data.course_id);teacher=db.get(User,data.teacher_id)
    if not course or not teacher or teacher.role!='teacher' or not teacher.active:raise HTTPException(422,'Select an active teacher and an existing course.')
    if course.teacher_id==teacher.id:raise HTTPException(409,'This teacher already owns the course.')
    db.add(TeacherAssignment(course_id=course.id,teacher_id=teacher.id,assigned_by=user.id));audit(db,user,'co-teacher assigned',f'{course.id}:{teacher.id}');db.commit();return {'ok':True}
@router.delete('/assignments/{aid}')
def unassign(aid:int,user=Depends(current_user),db=Depends(get_db)):
    role(user,'admin');assignment=db.get(TeacherAssignment,aid)
    if not assignment:raise HTTPException(404,'Assignment not found.')
    db.delete(assignment);audit(db,user,'co-teacher removed',aid);db.commit();return {'ok':True}
@router.post('/users/{uid}/state')
def state(uid:int,data:AccountState,user=Depends(current_user),db=Depends(get_db)):
    role(user,'admin');target=db.get(User,uid)
    if not target:raise HTTPException(404,'User not found.')
    if target.role=='admin':raise HTTPException(409,'Administrator suspension is not allowed through this interface.')
    target.active=data.active
    if not data.active:db.execute(delete(Session).where(Session.user_id==uid))
    audit(db,user,'account enabled' if data.active else 'account suspended',uid);db.commit();return {'ok':True}
