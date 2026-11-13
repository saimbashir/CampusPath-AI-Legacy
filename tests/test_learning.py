from datetime import timedelta
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Question,QuizRun,Topic,now
from app.mastery.engine import update_mastery,next_difficulty
from app.knowledge_graph.engine import algorithm_steps,validate_dag
from app.documents.extract import extract
import pytest

def test_bkt_updates_and_boundaries():
    assert update_mastery(.5,True)>.5
    assert update_mastery(.5,False)<.5
    for p in (0,.01,.2,.5,.99,1):
        for correct in (True,False):
            assert .01<=update_mastery(p,correct)<=.99
    assert next_difficulty(3,True)==3 and next_difficulty(1,False)==1
    with pytest.raises(ValueError):update_mastery(1.1,True)

def test_algorithm_paths_and_costs():
    assert algorithm_steps('UCS')['steps'][-1]['g']==8
    assert algorithm_steps('A*')['steps'][-1]['g']==8
    assert algorithm_steps('BFS')['steps'][-1]['path']==['S','A','C','G']
    assert algorithm_steps('DFS')['steps'][-1]['current']=='G'

def test_complete_astar_journey(clients):
    c,u=clients('saim@campuspath.demo');base=f"/api/courses/1/students/{u['id']}/progress"
    initial=c.get(base).json();assert next(t for t in initial['topics'] if t['name']=='A*')['mastery']==39
    tutor=c.post('/api/courses/1/tutor',json={'question':'Explain A* in Roman Urdu according to Lecture 6','mode':'Roman Urdu'}).json()
    assert tutor['sources'] and all(s['filename']=='Lecture_6.pptx' for s in tutor['sources'])
    run=c.post('/api/courses/1/quiz',json={'topic_id':7,'count':3}).json()
    with SessionLocal() as db:q=db.get(Question,run['question']['id']);wrong=(q.correct+1)%len(q.options)
    body={'question_id':run['question']['id'],'selected':wrong}
    first=c.post(f"/api/quiz/{run['id']}/answer",json=body).json()
    assert first['possible_misconception'] and first['mastery']['after']<39
    assert c.post(f"/api/quiz/{run['id']}/answer",json=body).status_code==409
    run=first['next']
    while not run['complete']:
        with SessionLocal() as db:correct=db.get(Question,run['question']['id']).correct
        r=c.post(f"/api/quiz/{run['id']}/answer",json={'question_id':run['question']['id'],'selected':correct});assert r.status_code==200
        run=r.json()['next']
    final=c.get(base).json()
    assert final['attempts']==3 and len(final['revisions'])==3 and len(final['misconceptions'])==1
    assert next(t for t in final['topics'] if t['id']==7)['attempts']==3
    assert c.post(f"/api/revisions/{final['revisions'][0]['id']}/complete",json={}).status_code==200

def test_foreign_run_and_question_rejected(clients):
    a,_=clients('saim@campuspath.demo');b,_=clients('ahmed@campuspath.demo')
    run=a.post('/api/courses/1/quiz',json={}).json()
    assert b.get(f"/api/quiz/{run['id']}").status_code==404
    assert b.post(f"/api/quiz/{run['id']}/answer",json={'question_id':run['question']['id'],'selected':0}).status_code==404
    assert a.post(f"/api/quiz/{run['id']}/answer",json={'question_id':999,'selected':0}).status_code==409

def test_expired_quiz_rejected(clients):
    c,_=clients('saim@campuspath.demo');run=c.post('/api/courses/1/quiz',json={}).json()
    with SessionLocal() as db:db.get(QuizRun,run['id']).expires=now()-timedelta(seconds=1);db.commit()
    assert c.post(f"/api/quiz/{run['id']}/answer",json={'question_id':run['question']['id'],'selected':0}).status_code==409

def test_course_create_enroll_and_scope(clients):
    t,_=clients('teacher@campuspath.demo');s,_=clients('saim@campuspath.demo');o,_=clients('other@campuspath.demo')
    r=t.post('/api/courses',json={'name':'New AI','code':'AI-X','section':'B'});assert r.status_code==201;c=r.json()
    assert s.get(f"/api/courses/{c['id']}/topics").status_code==404
    assert s.post('/api/courses/join',json={'code':c['enrollment_code']}).status_code==200
    assert s.post('/api/courses/join',json={'code':c['enrollment_code']}).status_code==409
    assert s.get(f"/api/courses/{c['id']}/topics").status_code==200
    assert o.get(f"/api/courses/{c['id']}/students").status_code==404

def test_prerequisite_cycle_and_cross_course_rejected(clients):
    t,_=clients('teacher@campuspath.demo');data={'name':'Agents','description':'x','prerequisites':[7],'clo':'CLO-1','difficulty':1}
    assert t.put('/api/courses/1/topics/1',json=data).status_code==422
    data['prerequisites']=[999];assert t.put('/api/courses/1/topics/1',json=data).status_code==422
    assert t.get('/api/courses/1/topics').json()[0]['prerequisites']==[]

def test_assignment_grading_and_privacy(clients):
    t,_=clients('teacher@campuspath.demo');a,_=clients('saim@campuspath.demo');b,_=clients('ahmed@campuspath.demo')
    assert a.post('/api/assignments/1/submit',json={'text':'My private assignment answer'}).status_code==200
    assert b.get('/api/courses/1/assignments').json()[0]['submissions']==[]
    sid=t.get('/api/courses/1/assignments').json()[0]['submissions'][0]['id']
    assert a.post(f'/api/submissions/{sid}/grade',json={'grade':100}).status_code==404
    assert t.post(f'/api/submissions/{sid}/grade',json={'grade':85,'feedback':'Well reasoned.'}).status_code==200
    assert a.get('/api/courses/1/assignments').json()[0]['submissions'][0]['grade']==85
    assert a.post('/api/assignments/1/submit',json={'text':'overwrite'}).status_code==409

def test_safe_upload_and_real_location(clients):
    c,_=clients('saim@campuspath.demo')
    assert c.post('/api/courses/1/resources',files={'file':('fake.pdf',b'not-a-pdf')}).status_code==422
    assert c.post('/api/courses/1/resources',files={'file':('photo.png',b'image')}).status_code==422
    r=c.post('/api/courses/1/resources',files={'file':('../../notes.txt',b'Testing uniqueTermExample material.\nSecond line.')});assert r.status_code==201
    data=c.get(f"/api/courses/1/resources/{r.json()['id']}").json()
    assert data['filename']=='notes.txt' and data['chunks'][0]['location']=='Lines 1–2'

def test_question_review_gates_delivery(clients):
    t,_=clients('teacher@campuspath.demo');s,_=clients('saim@campuspath.demo')
    topic=t.post('/api/courses/1/topics',json={'name':'New topic'}).json()['id']
    data={'topic_id':topic,'prompt':'Which option is correct?','options':['Right','Wrong'],'correct':0,'explanation':'Right is correct.'}
    q=t.post('/api/courses/1/questions',json=data).json()['id']
    assert s.post('/api/courses/1/quiz',json={'topic_id':topic}).status_code==409
    assert t.post(f'/api/courses/1/questions/{q}/approve',json={}).status_code==200
    assert s.post('/api/courses/1/quiz',json={'topic_id':topic}).status_code==201
    assert t.put(f'/api/courses/1/questions/{q}',json=data).status_code==409

def test_empty_course_and_planner(clients):
    c,_=clients('saim@campuspath.demo')
    r=c.post('/api/courses/1/planner',json={'exam_date':(now()+timedelta(days=7)).isoformat(),'hours':1,'free_days':[0,1,2,3,4,5,6]})
    assert r.status_code==200 and r.json()['days']
    assert c.post('/api/courses/1/planner',json={'exam_date':(now()-timedelta(days=3)).isoformat(),'hours':1}).status_code==422

def test_viva_demo_does_not_fake_mastery(clients):
    c,u=clients('saim@campuspath.demo');path=f"/api/courses/1/students/{u['id']}/progress"
    before=c.get(path).json()['mastery']
    r=c.post('/api/courses/1/viva',json={'text':'It estimates the remaining cost to the goal.'}).json()
    assert r['concept_coverage'] and r['mastery_impact'] is None
    assert c.get(path).json()['mastery']==before

def test_adaptive_difficulty_increases_after_correct(clients):
    c,_=clients('saim@campuspath.demo');run=c.post('/api/courses/1/quiz',json={'count':6}).json()
    with SessionLocal() as db:correct=db.get(Question,run['question']['id']).correct
    r=c.post(f"/api/quiz/{run['id']}/answer",json={'question_id':run['question']['id'],'selected':correct}).json()
    assert r['next']['question']['difficulty']>run['question']['difficulty']

def test_plan_uses_requested_minutes(clients):
    c,_=clients('saim@campuspath.demo')
    r=c.post('/api/courses/1/planner',json={'exam_date':(now()+timedelta(days=1)).isoformat(),'hours':.75}).json()
    assert all(sum(a['minutes'] for a in d['activities'])==45 for d in r['days'])
