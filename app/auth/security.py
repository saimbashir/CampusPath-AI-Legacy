import hashlib, secrets
from datetime import timedelta
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select, update
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from app.db import get_db
from app.models import User, Session, Course, Enrollment, LoginThrottle, Audit, TeacherAssignment, now
hasher = PasswordHasher()
DUMMY = hasher.hash('dummy-not-an-account-password')
def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()
def check_password(stored, password):
    try: return hasher.verify(stored, password)
    except (VerificationError, InvalidHashError): return False
def audit(db,user,action,target):
    db.add(Audit(actor_id=user.id,action=action,target=str(target)))
def current_user(request: Request, db=Depends(get_db)):
    token=request.cookies.get('campus_session','')
    session=db.get(Session,digest(token)) if token else None
    if not session or session.expires < now(): raise HTTPException(401,'Please sign in again.')
    if request.method not in ('GET','HEAD','OPTIONS') and not secrets.compare_digest(session.csrf,request.headers.get('x-csrf-token','')):
        raise HTTPException(403,'Invalid request token. Refresh and retry.')
    request.state.session=session
    user=db.get(User,session.user_id)
    if not user or not user.active:raise HTTPException(401,'Account is inactive. Contact your administrator.')
    return user
def role(user,*roles):
    if user.role not in roles: raise HTTPException(403,'Access denied for this role.')
def course_access(db,user,course_id,teacher=False):
    course=db.get(Course,course_id)
    if not course: raise HTTPException(404,'Course not found.')
    if user.role=='teacher' and (course.teacher_id==user.id or db.scalar(select(TeacherAssignment.id).where(TeacherAssignment.course_id==course_id,TeacherAssignment.teacher_id==user.id))): return course
    if not teacher and user.role=='student' and db.scalar(select(Enrollment.id).where(Enrollment.course_id==course_id,Enrollment.student_id==user.id)):
        return course
    raise HTTPException(404,'Course not found or access denied.')
def student_access(db,user,course_id,student_id):
    course_access(db,user,course_id,teacher=user.role!='student')
    if user.role=='student' and user.id!=student_id: raise HTTPException(403,'Student records are private.')
    if not db.scalar(select(Enrollment.id).where(Enrollment.course_id==course_id,Enrollment.student_id==student_id)):
        raise HTTPException(404,'Student not enrolled in this course.')
    if user.role=='teacher': audit(db,user,'student record viewed',f'{course_id}:{student_id}')
def throttle(db,key,limit=8):
    from sqlalchemy import case
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    from sqlalchemy.dialects.postgresql import insert as postgres_insert
    key=digest(key);current=now();deadline=current+timedelta(minutes=15)
    insert=sqlite_insert if db.bind.dialect.name=='sqlite' else postgres_insert
    statement=insert(LoginThrottle).values(key=key,count=1,until=deadline)
    statement=statement.on_conflict_do_update(index_elements=[LoginThrottle.key],set_={
        'count':case((LoginThrottle.until<=current,1),else_=LoginThrottle.count+1),
        'until':case((LoginThrottle.until<=current,deadline),else_=LoginThrottle.until)
    },where=(LoginThrottle.until<=current)|(LoginThrottle.count<limit))
    result=db.execute(statement);db.commit()
    if result.rowcount!=1:raise HTTPException(429,'Too many attempts. Try again in 15 minutes.')

def teacher_courses(user):
    return select(Course.id).where((Course.teacher_id==user.id)|Course.id.in_(select(TeacherAssignment.course_id).where(TeacherAssignment.teacher_id==user.id)))
