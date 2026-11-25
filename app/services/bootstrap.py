"""Create the first accounts from environment variables.

Free hosting plans have no shell, so the interactive scripts/manage.py commands cannot
run there. Set these once in the host's environment settings, deploy, log in, then
delete the variables. Existing accounts are never changed. Passwords are stored hashed.

  ADMIN_EMAIL, ADMIN_PASSWORD                       -> administrator
  TEACHER_EMAIL, TEACHER_PASSWORD, TEACHER_NAME     -> first teacher (optional)
"""
import os,secrets,logging
from sqlalchemy import select
log=logging.getLogger('campuspath.bootstrap')

def ensure_accounts():
    from app.db import SessionLocal
    from app.models import User
    from app.auth.security import hasher
    wanted=[('admin',os.getenv('ADMIN_EMAIL'),os.getenv('ADMIN_PASSWORD'),'Administrator'),
            ('teacher',os.getenv('TEACHER_EMAIL'),os.getenv('TEACHER_PASSWORD'),os.getenv('TEACHER_NAME') or 'Teacher')]
    try:
        with SessionLocal() as db:
            for role,email,password,name in wanted:
                if not email or not password:continue
                email=email.strip().lower()
                if len(password)<12:
                    log.warning('%s account not created: password must have at least 12 characters.',role);continue
                if db.scalar(select(User.id).where(User.email==email)):continue
                db.add(User(email=email,name=name[:120],university_id=role.upper()+'-'+secrets.token_hex(4),role=role,password=hasher.hash(password)))
                db.commit();log.warning('Created %s account %s from environment variables. Remove the password variable now.',role,email)
    except Exception as exc:
        log.error('Account bootstrap skipped (%s). Run database migrations first.',type(exc).__name__)
