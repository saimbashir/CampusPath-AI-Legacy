"""Admin bootstrap and secure faculty invitation creation. Secrets never enter HTTP responses."""
import sys,secrets,getpass,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datetime import timedelta
from sqlalchemy import select
from app.db import SessionLocal
from app.models import User,TeacherKey,now
from app.auth.security import hasher,digest,audit
parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='command',required=True)
a=sub.add_parser('create-admin');a.add_argument('--email',required=True)
i=sub.add_parser('invite');i.add_argument('--admin-email',required=True);i.add_argument('--days',type=int,default=7);i.add_argument('--uses',type=int,default=1)
args=parser.parse_args()
with SessionLocal() as db:
    if args.command=='create-admin':
        if db.scalar(select(User.id).where(User.email==args.email.lower())):raise SystemExit('Account already exists.')
        password=getpass.getpass('New admin password (12+ characters): ')
        if len(password)<12:raise SystemExit('Password is too short.')
        db.add(User(email=args.email.lower(),name='Administrator',university_id='ADMIN-'+secrets.token_hex(4),role='admin',password=hasher.hash(password)));db.commit();print('Administrator created.')
    else:
        admin=db.scalar(select(User).where(User.email==args.admin_email.lower(),User.role=='admin'))
        if not admin:raise SystemExit('Administrator not found.')
        from app.auth.security import check_password
        if not check_password(admin.password,getpass.getpass('Admin password: ')):raise SystemExit('Authentication failed.')
        if not 1<=args.days<=90 or not 1<=args.uses<=100:raise SystemExit('Days 1–90; uses 1–100.')
        token=secrets.token_urlsafe(32)
        key=TeacherKey(digest=digest(token),created_by=admin.id,expires=now()+timedelta(days=args.days),limit=args.uses,uses=0);db.add(key);db.flush();audit(db,admin,'teacher key generated',key.id);db.commit()
        print('Faculty invite — shown once, deliver privately. Never add it to source or logs:\n'+token)
