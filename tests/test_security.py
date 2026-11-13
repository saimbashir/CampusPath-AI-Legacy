from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.db import SessionLocal
from app.models import TeacherKey,Session,ResetToken,User,now
from app.auth.security import digest

@pytest.mark.parametrize('path',['/api/courses','/api/admin/overview','/api/courses/1/students','/api/courses/1/students/2/progress','/teacher/students'])
def test_unauthenticated_sensitive_routes(setup,path):
    assert TestClient(app).get(path).status_code==401

def test_student_isolation_and_teacher_routes(clients):
    a,ua=clients('saim@campuspath.demo');b,ub=clients('ahmed@campuspath.demo')
    assert a.get(f"/api/courses/1/students/{ua['id']}/progress").status_code==200
    assert a.get(f"/api/courses/1/students/{ub['id']}/progress").status_code==403
    assert a.get(f"/student/{ub['id']}").status_code==403
    for path in ['/teacher/students','/api/courses/1/students','/api/courses/1/questions','/api/admin/overview','/api/courses/1/analytics']:
        assert a.get(path).status_code in (403,404)

def test_teacher_course_boundaries(clients):
    teacher,_=clients('teacher@campuspath.demo');other,_=clients('other@campuspath.demo')
    assert teacher.get('/api/courses/1/students').status_code==200
    assert other.get('/api/courses/1/students').status_code==404
    assert teacher.get('/api/courses/2/students').status_code==404
    assert other.get('/api/courses/1/students/2/progress').status_code==404
    assert teacher.post('/api/courses/2/copilot',json={'text':'Who needs help?'}).status_code==404

def registration(**overrides):
    return dict(name='New Person',email='new@example.com',university_id='NEW-1',password='Long-Safe-Pass!2026',confirm_password='Long-Safe-Pass!2026',**overrides)
@pytest.mark.parametrize('key',['wrong-key','revoked-key-for-testing','expired-key-for-testing',''])
def test_teacher_invites_fail_closed(setup,key):
    c=TestClient(app)
    assert c.post('/api/auth/register',json=registration(role='teacher',teacher_key=key)).status_code==403

def test_single_use_invite_and_no_privilege_escalation(setup):
    c=TestClient(app)
    assert c.post('/api/auth/register',json=registration(role='admin')).status_code==422
    body=registration(role='teacher',teacher_key='valid-key-for-testing')
    assert c.post('/api/auth/register',json=body).status_code==201
    body.update(email='another@example.com',university_id='NEW-2')
    assert c.post('/api/auth/register',json=body).status_code==403

def test_duplicate_registration_does_not_burn_invite(setup):
    c=TestClient(app);data=registration(role='teacher',teacher_key='valid-key-for-testing');data['email']='saim@campuspath.demo'
    assert c.post('/api/auth/register',json=data).status_code==409
    data['email']='new@example.com'
    assert c.post('/api/auth/register',json=data).status_code==201

def test_csrf_origin_and_logout(clients):
    c,_=clients('saim@campuspath.demo');token=c.headers.pop('X-CSRF-Token')
    assert c.post('/api/courses/join',json={'code':'OTHER-CODE'}).status_code==403
    c.headers['X-CSRF-Token']=token
    assert c.post('/api/auth/logout',headers={'Origin':'https://evil.example'},json={}).status_code==403
    assert c.post('/api/auth/logout',json={}).status_code==200
    assert c.get('/api/auth/me').status_code==401

def test_expired_session(clients):
    c,u=clients('saim@campuspath.demo')
    with SessionLocal() as db:
        s=db.scalar(select(Session).where(Session.user_id==u['id']));s.expires=now()-timedelta(seconds=1);db.commit()
    assert c.get('/api/auth/me').status_code==401

def test_login_rate_limit(setup):
    c=TestClient(app)
    codes=[c.post('/api/auth/login',json={'email':'not-real@example.com','password':'wrong'}).status_code for _ in range(9)]
    assert codes[:8]==[401]*8 and codes[8]==429

def test_personal_resource_not_visible_to_students_or_teacher(clients):
    a,_=clients('saim@campuspath.demo');b,_=clients('ahmed@campuspath.demo');t,_=clients('teacher@campuspath.demo')
    r=a.post('/api/courses/1/resources',files={'file':('private.txt',b'ConfidentialNebula is my private learning note.')})
    assert r.status_code==201;rid=r.json()['id']
    for c in [b,t]:
        assert c.get(f'/api/courses/1/resources/{rid}').status_code==404
        assert all(x['id']!=rid for x in c.get('/api/courses/1/resources').json())
        assert c.post('/api/courses/1/tutor',json={'question':'ConfidentialNebula'}).json()['sources']==[]
    assert a.post('/api/courses/1/tutor',json={'question':'ConfidentialNebula'}).json()['sources']

def test_no_answer_key_or_course_code_to_student(clients):
    c,_=clients('saim@campuspath.demo')
    assert 'enrollment_code' not in c.get('/api/courses').json()[0]
    r=c.post('/api/courses/1/quiz',json={}).json()
    assert 'correct' not in r['question'] and 'explanation' not in r['question']

def test_reset_revokes_sessions_and_is_single_use(clients):
    c,u=clients('saim@campuspath.demo');token='random-reset-token-for-this-test-only'
    with SessionLocal() as db:db.add(ResetToken(digest=digest(token),user_id=u['id'],expires=now()+timedelta(minutes=20)));db.commit()
    body={'token':token,'password':'MyNewPassword!2026'}
    assert c.post('/api/auth/reset',json=body).status_code==200
    assert c.get('/api/auth/me').status_code==401
    assert c.post('/api/auth/reset',json=body).status_code==400

def test_teacher_private_notes(clients):
    t,_=clients('teacher@campuspath.demo');s,u=clients('saim@campuspath.demo');o,_=clients('other@campuspath.demo')
    path=f"/api/courses/1/students/{u['id']}/notes"
    assert t.post(path,json={'text':'Private faculty observation.'}).status_code==200
    assert s.get(path).status_code==403
    assert o.get(path).status_code==404
    assert len(t.get(path).json())==1

def test_repeated_successful_login_does_not_exhaust_failure_budget(clients):
    c,_=clients('saim@campuspath.demo')
    for _ in range(9):
        assert c.post('/api/auth/login',json={'email':'saim@campuspath.demo','password':'CampusPath-Demo!2026'}).status_code==200
