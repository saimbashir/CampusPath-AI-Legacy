from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from app.db import get_db
from app.models import StudyPlan,StudyTask,Notification,Session,Enrollment,now
from app.schemas import PlanInput,TaskState,ProfileUpdate,PasswordChange
from app.auth.security import current_user,role,course_access,check_password,hasher,audit,teacher_courses
from app.services.planning import create_plan,serialize_plan,reschedule
from app.services.notifications import refresh
router=APIRouter(prefix='/api')
@router.get('/courses/{cid}/planner')
def read_plan(cid:int,user=Depends(current_user),db=Depends(get_db)):
    role(user,'student');course_access(db,user,cid)
    p=db.scalar(select(StudyPlan).where(StudyPlan.student_id==user.id,StudyPlan.course_id==cid,StudyPlan.active.is_(True)).order_by(StudyPlan.id.desc()))
    return serialize_plan(db,p)
@router.post('/courses/{cid}/planner/reschedule')
def move_plan(cid:int,user=Depends(current_user),db=Depends(get_db)):
    role(user,'student');course_access(db,user,cid)
    p=db.scalar(select(StudyPlan).where(StudyPlan.student_id==user.id,StudyPlan.course_id==cid,StudyPlan.active.is_(True)).order_by(StudyPlan.id.desc()))
    if not p:raise HTTPException(404,'Create a study plan first.')
    return reschedule(db,p)
@router.post('/study-tasks/{tid}')
def set_task(tid:int,data:TaskState,user=Depends(current_user),db=Depends(get_db)):
    role(user,'student');t=db.get(StudyTask,tid);p=db.get(StudyPlan,t.plan_id) if t else None
    if not p or p.student_id!=user.id or not p.active:raise HTTPException(404,'Study task not found.')
    course_access(db,user,p.course_id);t.status=data.status;t.completed=now() if data.status=='done' else None;db.commit()
    return {'ok':True,'message':'Study activity updated. Assessment evidence determines mastery.'}
@router.get('/notifications')
def notifications(user=Depends(current_user),db=Depends(get_db)):
    refresh(db,user)
    query=select(Notification).where(Notification.user_id==user.id)
    if user.role!='admin':
        accessible=teacher_courses(user) if user.role=='teacher' else select(Enrollment.course_id).where(Enrollment.student_id==user.id)
        query=query.where(Notification.course_id.is_(None)|Notification.course_id.in_(accessible))
    rows=db.scalars(query.order_by(Notification.created.desc()).limit(100)).all()
    return [{'id':n.id,'course_id':n.course_id,'title':n.title,'message':n.message,'target':n.target,'read':n.read,'created':n.created} for n in rows]
@router.post('/notifications/{nid}/read')
def read_notification(nid:int,user=Depends(current_user),db=Depends(get_db)):
    n=db.get(Notification,nid)
    if not n or n.user_id!=user.id:raise HTTPException(404,'Notification not found.')
    n.read=True;db.commit();return {'ok':True}
@router.put('/profile')
def profile(data:ProfileUpdate,user=Depends(current_user),db=Depends(get_db)):
    user.name=data.name;user.profile={**(user.profile or {}),**data.model_dump(exclude={'name'})};db.commit()
    from app.api.auth import public
    return {'user':public(user)}
@router.post('/profile/password')
def password(data:PasswordChange,user=Depends(current_user),db=Depends(get_db)):
    from sqlalchemy import delete
    if not check_password(user.password,data.old_password):raise HTTPException(403,'Current password is incorrect.')
    user.password=hasher.hash(data.new_password);db.execute(delete(Session).where(Session.user_id==user.id));audit(db,user,'password changed','own account');db.commit()
    return {'message':'Password changed. Sign in again on each device.'}
