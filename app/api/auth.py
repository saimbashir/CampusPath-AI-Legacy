import os, secrets, smtplib
from email.message import EmailMessage
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError
from app.db import get_db
from app.models import User, Session, TeacherKey, ResetToken, LoginThrottle, now
from app.schemas import Login, Register, EmailInput, ResetInput
from app.auth.security import current_user, hasher, check_password, digest, DUMMY, throttle, audit
from app.config import COOKIE_SECURE, SESSION_HOURS
router=APIRouter(prefix='/api/auth')
def public(user):
    return dict(id=user.id,name=user.name,email=user.email,university_id=user.university_id,role=user.role,profile=user.profile)
@router.post('/register',status_code=201)
def register(data:Register,request:Request,db=Depends(get_db)):
    throttle(db,'register:'+request.client.host,20)
    if data.role=='teacher':
        result=db.execute(update(TeacherKey).where(TeacherKey.digest==digest(data.teacher_key),TeacherKey.revoked.is_(False),TeacherKey.expires>now(),TeacherKey.uses<TeacherKey.limit).values(uses=TeacherKey.uses+1))
        if result.rowcount!=1:
            db.rollback()
            raise HTTPException(403,'Invalid, expired, revoked or exhausted faculty invite.')
    user=User(name=data.name,email=data.email,university_id=data.university_id,password=hasher.hash(data.password),role=data.role,profile=data.model_dump(include={'department','program','semester','campus','designation'}))
    db.add(user)
    try: db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,'Email or university ID is already registered.')
    return public(user)
@router.post('/login')
def login(data:Login,request:Request,response:Response,db=Depends(get_db)):
    throttle(db,'login-ip:'+request.client.host,60)
    throttle(db,'login-user:'+data.email.lower(),8)
    user=db.scalar(select(User).where(User.email==data.email.lower()))
    valid=check_password(user.password if user else DUMMY,data.password)
    if not user or not user.active or not valid: raise HTTPException(401,'Invalid email or password.')
    db.execute(delete(LoginThrottle).where(LoginThrottle.key==digest('login-user:'+data.email.lower())))
    old=request.cookies.get('campus_session')
    if old: db.execute(delete(Session).where(Session.digest==digest(old)))
    token,csrf=secrets.token_urlsafe(32),secrets.token_urlsafe(32)
    db.add(Session(digest=digest(token),user_id=user.id,csrf=csrf,expires=now()+timedelta(hours=SESSION_HOURS)))
    audit(db,user,'login','session')
    db.commit()
    response.set_cookie('campus_session',token,httponly=True,secure=COOKIE_SECURE,samesite='strict',max_age=SESSION_HOURS*3600,path='/')
    return {'user':public(user),'csrf':csrf}
@router.get('/me')
def me(request:Request,user=Depends(current_user)):
    return {'user':public(user),'csrf':request.state.session.csrf}
@router.post('/logout')
def logout(request:Request,response:Response,user=Depends(current_user),db=Depends(get_db)):
    db.execute(delete(Session).where(Session.digest==request.state.session.digest));db.commit()
    response.delete_cookie('campus_session',path='/')
    return {'ok':True}
@router.post('/forgot')
def forgot(data:EmailInput,request:Request,db=Depends(get_db)):
    throttle(db,'reset:'+request.client.host,8)
    host=os.getenv('SMTP_HOST')
    if not host: raise HTTPException(503,'Password recovery email is not configured. Ask the administrator.')
    user=db.scalar(select(User).where(User.email==data.email.lower()))
    if user:
        token=secrets.token_urlsafe(32)
        db.execute(delete(ResetToken).where(ResetToken.user_id==user.id))
        db.add(ResetToken(digest=digest(token),user_id=user.id,expires=now()+timedelta(minutes=30)))
        message=EmailMessage();message['Subject']='CampusPath password reset';message['From']=os.environ['SMTP_FROM'];message['To']=user.email
        message.set_content('Your one-time reset token (valid for 30 minutes):\n'+token+'\nOpen CampusPath > Forgot password > Reset with token.')
        try:
            with smtplib.SMTP(host,int(os.getenv('SMTP_PORT','587')),timeout=10) as smtp:
                smtp.starttls()
                if os.getenv('SMTP_USER'): smtp.login(os.environ['SMTP_USER'],os.environ['SMTP_PASSWORD'])
                smtp.send_message(message)
            db.commit()
        except Exception:
            db.rollback()
            raise HTTPException(503,'Recovery email is temporarily unavailable.')
    return {'message':'If that account exists, a recovery message has been sent.'}
@router.post('/reset')
def reset(data:ResetInput,request:Request,db=Depends(get_db)):
    throttle(db,'reset-use:'+request.client.host,10)
    token=db.get(ResetToken,digest(data.token))
    if not token or token.expires<now(): raise HTTPException(400,'Invalid or expired token.')
    uid=token.user_id
    claimed=db.execute(delete(ResetToken).where(ResetToken.digest==digest(data.token),ResetToken.expires>now()))
    if claimed.rowcount!=1:
        db.rollback()
        raise HTTPException(400,'Invalid or already-used token.')
    db.get(User,uid).password=hasher.hash(data.password)
    db.execute(delete(ResetToken).where(ResetToken.user_id==uid))
    db.execute(delete(Session).where(Session.user_id==uid));db.commit()
    return {'message':'Password reset. Sign in with your new password.'}
