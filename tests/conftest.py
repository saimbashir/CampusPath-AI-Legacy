import os,tempfile
from pathlib import Path
os.environ['DATABASE_URL']='sqlite:///'+str(Path(tempfile.mkdtemp())/'test.db')
os.environ['DEMO_MODE']='true'
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.db import Base,engine,SessionLocal
from app.models import User,Course,Enrollment,TeacherKey,now
from app.auth.security import hasher,digest
from scripts.seed_demo import seed
from datetime import timedelta
@pytest.fixture()
def setup():
    Base.metadata.drop_all(engine);Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
        outsider=User(name='Other Faculty',email='other@campuspath.demo',university_id='FAC-OTHER',role='teacher',password=hasher.hash('Other-Teacher!2026'))
        db.add(outsider);db.flush()
        db.add(Course(teacher_id=outsider.id,name='Other Course',code='OTH',section='B',enrollment_code='OTHER-CODE'))
        admin=db.scalar(select(User).where(User.role=='admin'))
        for key,revoked,days in [('valid-key-for-testing',False,7),('revoked-key-for-testing',True,7),('expired-key-for-testing',False,-1)]:
            db.add(TeacherKey(digest=digest(key),created_by=admin.id,expires=now()+timedelta(days=days),revoked=revoked,limit=1,uses=0))
        db.commit()
    yield
@pytest.fixture()
def clients(setup):
    def make(email):
        c=TestClient(app)
        r=c.post('/api/auth/login',json={'email':email,'password':'Other-Teacher!2026' if email.startswith('other@') else 'CampusPath-Demo!2026'})
        assert r.status_code==200,r.text
        c.headers['X-CSRF-Token']=r.json()['csrf']
        return c,r.json()['user']
    return make
