from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
import io,wave
import pytest
from sqlalchemy import select
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from app.main import app
from app.db import SessionLocal
from app.models import Question,QuizRun,Answer,StudyTask,Notification,Mastery,VivaTurn,User,now
from app.auth.security import throttle
from app.voice.streaming import EnergyVAD,ACTIVE

def accounts(clients):
    return [clients(e)[0] for e in ('saim@campuspath.demo','teacher@campuspath.demo','ahmed@campuspath.demo','other@campuspath.demo','admin@campuspath.demo')]
def good(response,status=200):
    assert response.status_code==status,response.text
    return response.json()

def test_saved_plan_completion_privacy_and_archive(clients):
    s,t,other,_,_=accounts(clients)
    assert good(s.get('/api/courses/1/planner'))['id'] is None
    body={'exam_date':(now()+timedelta(days=3)).isoformat(),'hours':.75,'free_days':list(range(7))}
    plan=good(s.post('/api/courses/1/planner',json=body));tid=plan['days'][0]['activities'][0]['id']
    assert all(sum(a['minutes'] for a in d['activities'])==45 for d in plan['days'])
    assert other.post(f'/api/study-tasks/{tid}',json={'status':'done'}).status_code==404
    before=good(s.get('/api/courses/1/students/2/progress'))['mastery']
    good(s.post(f'/api/study-tasks/{tid}',json={'status':'done'}))
    assert good(s.get('/api/courses/1/planner'))['days'][0]['activities'][0]['status']=='done'
    assert good(s.get('/api/courses/1/students/2/progress'))['mastery']==before
    good(s.post('/api/courses/1/planner',json=body))
    assert s.post(f'/api/study-tasks/{tid}',json={'status':'done'}).status_code==404
    assert t.post('/api/courses/1/planner',json=body).status_code==403

def test_reschedule_retains_complete_and_respects_capacity(clients):
    s,_=clients('saim@campuspath.demo')
    p=good(s.post('/api/courses/1/planner',json={'exam_date':(now()+timedelta(days=1)).isoformat(),'hours':1,'free_days':list(range(7))}))
    done=p['days'][0]['activities'][0]['id'];good(s.post(f'/api/study-tasks/{done}',json={'status':'done'}))
    with SessionLocal() as db:
        tasks=db.scalars(select(StudyTask).where(StudyTask.plan_id==p['id'])).all()
        for task in tasks:
            if task.id!=done:task.scheduled=now()-timedelta(days=2)
        # Add backlog exceeding all remaining capacity.
        db.add(StudyTask(plan_id=p['id'],topic_id=1,scheduled=now()-timedelta(days=2),minutes=30,reason='Backlog',status='planned'));db.commit()
    result=good(s.post('/api/courses/1/planner/reschedule'))
    assert result['unscheduled']==1
    assert all(sum(a['minutes'] for a in d['activities'] if a['status'] in ('planned','done'))<=60 for d in result['days'])
    assert next(a for d in result['days'] for a in d['activities'] if a['id']==done)['status']=='done'

def test_mock_delays_feedback_finishes_and_counts_unanswered(clients):
    s,_,other,_,_=accounts(clients)
    run=good(s.post('/api/courses/1/quiz',json={'mode':'mock','count':4,'total_marks':40}),201)
    assert s.post(f"/api/quiz/{run['id']}/hint").status_code==403
    with SessionLocal() as db:q=db.get(Question,run['question']['id']);correct=q.correct
    response=good(s.post(f"/api/quiz/{run['id']}/answer",json={'question_id':q.id,'selected':correct}))
    assert response['feedback_delayed'] and 'correct_answer' not in response and 'mastery' not in response
    assert other.get(f"/api/quiz/{run['id']}").status_code==404
    result=good(s.post(f"/api/quiz/{run['id']}/finish"))
    assert result['score']==25 and result['marks']==10 and result['unanswered']==3
    assert len(result['details'])==4 and result['details'][0]['correct']
    assert s.post(f"/api/quiz/{run['id']}/answer",json={'question_id':response['next']['question']['id'],'selected':0}).status_code==409
    assert good(s.get('/api/courses/1/assessments'))[0]['complete']

def test_hint_and_repeat_discount_evidence(clients):
    s,_=clients('saim@campuspath.demo');weights=[]
    for attempt in range(2):
        r=good(s.post('/api/courses/1/quiz',json={'mode':'diagnostic','topic_id':1,'count':1}),201)
        if not attempt:good(s.post(f"/api/quiz/{r['id']}/hint"))
        with SessionLocal() as db:q=db.get(Question,r['question']['id']);correct=q.correct
        answer=good(s.post(f"/api/quiz/{r['id']}/answer",json={'question_id':q.id,'selected':correct}))
        weights.append(answer['mastery']['evidence_weight'])
    assert weights==[.35,.5]
    with SessionLocal() as db:
        rows=db.scalars(select(Answer).order_by(Answer.id)).all();assert rows[0].hint_used and not rows[1].hint_used
        assert all(a.response_seconds>=0 for a in rows)

def test_mock_exact_joint_distribution_and_shortages(clients):
    s,_=clients('saim@campuspath.demo')
    with SessionLocal() as db:
        rows=db.scalars(select(Question).order_by(Question.id)).all()
        for q in rows:q.approved=False
        for i,q in enumerate(rows[:4]):q.approved=True;q.topic_id=1 if i<2 else 2;q.bloom='Remember' if i%2==0 else 'Apply'
        from app.models import Topic
        db.get(Topic,1).clo='CLO-X';db.get(Topic,2).clo='CLO-Y';db.commit()
    body={'mode':'mock','count':4,'bloom_distribution':{'Remember':50,'Apply':50},'clo_distribution':{'CLO-X':50,'CLO-Y':50}}
    r=good(s.post('/api/courses/1/quiz',json=body),201)
    with SessionLocal() as db:
        q=[db.get(Question,i) for i in db.get(QuizRun,r['id']).question_ids]
        assert sum(x.bloom=='Apply' for x in q)==2 and sum(x.topic_id==1 for x in q)==2
    body['bloom_distribution']={'Apply':100};assert s.post('/api/courses/1/quiz',json=body).status_code==409
    body['bloom_distribution']={'Apply':99};assert s.post('/api/courses/1/quiz',json=body).status_code==422

def test_viva_saved_sequential_and_review_once(clients):
    s,t,other,outside,_=accounts(clients)
    before=good(s.get('/api/courses/1/students/2/progress'))['mastery']
    run=good(s.post('/api/courses/1/viva/start',json={'topic_id':7,'count':2}))
    answer={'turn_index':0,'text':'A star selects the node with lowest g(n) plus h(n).'}
    r=good(s.post(f"/api/viva/{run['id']}/answer",json=answer))
    assert r['proposed_score'] is None and r['next']['index']==1 and not r['next']['complete']
    assert good(s.get('/api/courses/1/students/2/progress'))['mastery']==before
    assert s.post(f"/api/viva/{run['id']}/answer",json=answer).status_code==409
    assert other.get(f"/api/viva/{run['id']}").status_code==404
    assert outside.get('/api/courses/1/viva/review').status_code==404
    assert s.get('/api/courses/1/viva/review').status_code==404
    tid=r['next']['turns'][0]['id'];grade={'score':85,'feedback':'Correct rule. Add an admissibility condition next time.'}
    good(t.post(f'/api/viva/turns/{tid}/review',json=grade))
    assert t.post(f'/api/viva/turns/{tid}/review',json=grade).status_code==409
    p=good(s.get('/api/courses/1/students/2/progress'));assert p['viva_average']==85 and p['viva_reviewed_count']==1
    result=good(s.post(f"/api/viva/{run['id']}/answer",json={'turn_index':1,'text':'The heuristic should not overestimate remaining cost.'}))
    assert result['next']['complete']
    history=good(s.get('/api/courses/1/viva/history'));assert history[0]['turns'][0]['reviewed_score']==85

def test_notifications_private_deduplicated_read(clients):
    s,t,other,_,_=accounts(clients)
    due=(now()+timedelta(days=1)).isoformat()
    good(t.post('/api/courses/1/assignments',json={'title':'Soon due','instructions':'Explain search','rubric':'Correct rule','due':due}),201)
    rows=good(s.get('/api/notifications'));assert rows
    assert len(good(s.get('/api/notifications')))==len(rows)
    nid=rows[0]['id'];assert other.post(f'/api/notifications/{nid}/read').status_code==404
    good(s.post(f'/api/notifications/{nid}/read'));assert next(n for n in good(s.get('/api/notifications')) if n['id']==nid)['read']

def test_attachment_privacy_explicit_submission_and_grade_lock(clients):
    s,t,other,outside,_=accounts(clients)
    content=b'My private assignment on heuristic search.'
    upload=good(s.post('/api/courses/1/resources',files={'file':('private.txt',content,'text/plain')}),201)
    rid=upload['id'];url=f'/api/courses/1/resources/{rid}/download'
    assert s.get(url).content==content
    assert t.get(url).status_code in (403,404) and other.get(url).status_code in (403,404)
    a=good(t.post('/api/courses/1/assignments',json={'title':'Evidence attachment','instructions':'Explain heuristics','rubric':'Correct rule','due':(now()+timedelta(days=1)).isoformat()}),201)
    submission=good(s.post(f"/api/assignments/{a['id']}/submit",json={'resource_id':rid}))
    listing=good(t.get('/api/courses/1/assignments'));row=next(x for x in listing if x['id']==a['id'])['submissions'][0];sid=row['id']
    assert t.get(f'/api/submissions/{sid}/attachment').content==content
    assert other.get(f'/api/submissions/{sid}/attachment').status_code in (403,404)
    assert outside.get(f'/api/submissions/{sid}/attachment').status_code in (403,404)
    good(t.post(f'/api/submissions/{sid}/grade',json={'grade':90,'feedback':'Good explanation.'}))
    assert s.post(f"/api/assignments/{a['id']}/submit",json={'text':'overwrite'}).status_code==409

def test_admin_assignment_grants_then_revokes_course_access(clients):
    s,t,other,outside,admin=accounts(clients)
    with SessionLocal() as db:uid=db.scalar(select(User.id).where(User.email=='other@campuspath.demo'))
    assert outside.get('/api/courses/1/students').status_code==404
    good(admin.post('/api/admin/assignments',json={'teacher_id':uid,'course_id':1}))
    assert admin.post('/api/admin/assignments',json={'teacher_id':uid,'course_id':1}).status_code==409
    assert outside.get('/api/courses/1/students').status_code==200
    assert any(c['id']==1 for c in good(outside.get('/api/courses')))
    assigned=good(admin.get('/api/admin/assignments'))['assignments'][0]
    good(admin.delete(f"/api/admin/assignments/{assigned['id']}"))
    assert outside.get('/api/courses/1/students').status_code==404
    assert s.get('/api/admin/system').status_code==403

def test_account_suspend_revokes_existing_sessions(clients):
    s,_,_,_,a=accounts(clients)
    good(a.post('/api/admin/users/2/state',json={'active':False}))
    assert s.get('/api/auth/me').status_code==401
    assert TestClient(app).post('/api/auth/login',json={'email':'saim@campuspath.demo','password':'CampusPath-Demo!2026'}).status_code in (401,403)
    good(a.post('/api/admin/users/2/state',json={'active':True}))
    assert a.post('/api/admin/users/5/state',json={'active':False}).status_code==409

def test_profile_password_revokes_other_sessions(clients):
    s,_=clients('saim@campuspath.demo');s2,_=clients('saim@campuspath.demo')
    r=good(s.put('/api/profile',json={'name':'Saim Updated','department':'CS'}));assert r['user']['name']=='Saim Updated'
    assert s.put('/api/profile',json={'name':'Saim','role':'admin'}).status_code==422
    good(s.post('/api/profile/password',json={'old_password':'CampusPath-Demo!2026','new_password':'New-CampusPath!2026'}))
    assert s2.get('/api/auth/me').status_code==401 and s.get('/api/auth/me').status_code==401
    assert TestClient(app).post('/api/auth/login',json={'email':'saim@campuspath.demo','password':'New-CampusPath!2026'}).status_code==200

def test_atomic_rate_budget_under_concurrent_requests(setup):
    def attempt(i):
        with SessionLocal() as db:
            try:throttle(db,'atomic-test',5);return 200
            except HTTPException as exc:return exc.status_code
    with ThreadPoolExecutor(max_workers=8) as pool:result=list(pool.map(attempt,range(20)))
    assert result.count(200)==5 and result.count(429)==15

def test_research_labels_scoped_and_metrics_not_invented(clients):
    s,t,_,outside,_=accounts(clients)
    assert s.get('/api/courses/1/research').status_code==404
    assert outside.get('/api/courses/1/research').status_code==404
    r=good(t.get('/api/courses/1/research'));assert r['observations']==0 and r['viva_mean_absolute_error'] is None
    assert t.post('/api/courses/1/research/retrieval',json={'query':'A star','relevant_chunk_ids':[999999]}).status_code==422

def test_energy_vad_handles_speech_silence_and_wav():
    from array import array
    vad=EnergyVAD(16000);speech=array('h',[1000]*4096).tobytes();silence=b'\0'*8192
    assert not vad.feed(speech)
    for _ in range(3):assert not vad.feed(silence)
    assert vad.feed(silence)
    with wave.open(io.BytesIO(vad.wav(speech))) as f:assert f.getframerate()==16000 and f.getnchannels()==1 and f.getnframes()==4096
    with pytest.raises(ValueError):vad.feed(b'x')

def test_websocket_origin_auth_and_course_scope(clients):
    s,_,_,outside,_=accounts(clients)
    for c,origin,cid in [(s,'http://evil.test',1),(TestClient(app),'http://testserver',1),(outside,'http://testserver',1),(s,'http://testserver',2)]:
        with pytest.raises(WebSocketDisconnect):
            with c.websocket_connect(f'/ws/courses/{cid}/voice',headers={'origin':origin}):pass

def test_websocket_transcript_contract_and_cleanup(clients,monkeypatch):
    s,_=clients('saim@campuspath.demo');captured={}
    def transcribe(data,filename,mime):
        captured['data']=data;return [('Audio transcript','Heuristic estimates remaining cost.')]
    monkeypatch.setattr('app.voice.streaming.transcribe',transcribe)
    with s.websocket_connect('/ws/courses/1/voice',headers={'origin':'http://testserver'}) as ws:
        ws.send_json({'type':'start','csrf':s.headers['X-CSRF-Token'],'sample_rate':16000});assert ws.receive_json()['type']=='ready'
        ws.send_bytes(b'\0\x10'*4096);ws.send_json({'type':'finish'})
        assert ws.receive_json()['type']=='transcribing'
        result=ws.receive_json();assert result['review_required'] and result['raw_audio_stored'] is False and result['text'].startswith('Heuristic')
    assert not ACTIVE
    with wave.open(io.BytesIO(captured['data'])) as f:assert f.getnframes()==4096

@pytest.mark.parametrize('case',['csrf','rate','frame','empty','revoked','concurrent'])
def test_websocket_rejects_invalid_controls(clients,case):
    s,_=clients('saim@campuspath.demo')
    with s.websocket_connect('/ws/courses/1/voice',headers={'origin':'http://testserver'}) as ws:
        ws.send_json({'type':'start','csrf':'wrong' if case=='csrf' else s.headers['X-CSRF-Token'],'sample_rate':1 if case=='rate' else 16000})
        first=ws.receive_json()
        if case in ('csrf','rate'):assert first['type']=='error'
        else:
            assert first['type']=='ready'
            if case=='concurrent':
                with s.websocket_connect('/ws/courses/1/voice',headers={'origin':'http://testserver'}) as ws2:
                    ws2.send_json({'type':'start','csrf':s.headers['X-CSRF-Token'],'sample_rate':16000});assert ws2.receive_json()['type']=='error'
                ws.send_json({'type':'end'})
            else:
                if case=='frame':ws.send_bytes(b'x')
                elif case=='empty':ws.send_json({'type':'finish'})
                elif case=='revoked':
                    good(s.post('/api/auth/logout'));ws.send_bytes(b'\0\0'*10)
                assert ws.receive_json()['type']=='error'
    assert not ACTIVE

def test_readiness_six_factors_and_missing_evidence(clients):
    s,_=clients('saim@campuspath.demo')
    p=good(s.get('/api/courses/1/students/2/progress'));detail=p['readiness_detail']
    assert len(detail['factors'])==6 and sum(f['weight'] for f in detail['factors'])==pytest.approx(1)
    assert p['readiness']==round(sum(f['contribution'] for f in detail['factors']))
    assert next(f for f in detail['factors'] if f['key']=='mock')['value'] is None
    assert next(f for f in detail['factors'] if f['key']=='recency')['value']==0
    r=good(s.post('/api/courses/1/quiz',json={'mode':'mock','count':1}),201)
    with SessionLocal() as db:q=db.get(Question,r['question']['id']);correct=q.correct
    good(s.post(f"/api/quiz/{r['id']}/answer",json={'question_id':q.id,'selected':correct}))
    detail=good(s.get('/api/courses/1/students/2/progress'))['readiness_detail']
    assert next(f for f in detail['factors'] if f['key']=='mock')['value']==100
    assert next(f for f in detail['factors'] if f['key']=='recency')['value']>0

def test_answer_claim_under_concurrent_submission(clients):
    s,_=clients('saim@campuspath.demo');r=good(s.post('/api/courses/1/quiz',json={'count':2}),201)
    def send(_):
        c=TestClient(app);c.cookies.update(s.cookies);c.headers.update({'X-CSRF-Token':s.headers['X-CSRF-Token']})
        return c.post(f"/api/quiz/{r['id']}/answer",json={'question_id':r['question']['id'],'selected':0}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(send,range(2)))
    assert sorted(codes)==[200,409]
    with SessionLocal() as db:assert len(db.scalars(select(Answer).where(Answer.run_id==r['id'])).all())==1

def test_chunked_body_cannot_bypass_limit(setup):
    c=TestClient(app)
    def chunks():
        for _ in range(10):yield b'x'*1024*1024
    r=c.post('/api/auth/login',content=chunks(),headers={'Content-Type':'application/json'})
    assert r.status_code==413

def test_mock_unspecified_distribution_axis_is_unconstrained(clients):
    s,_=clients('saim@campuspath.demo')
    with SessionLocal() as db:
        rows=db.scalars(select(Question).order_by(Question.id)).all()
        for q in rows:q.approved=False
        for i,q in enumerate(rows[:4]):q.approved=True;q.topic_id=1 if i<3 else 2;q.bloom='Apply' if i<3 else 'Remember'
        from app.models import Topic
        db.get(Topic,1).clo='CLO-X';db.get(Topic,2).clo='CLO-Y';db.commit()
    good(s.post('/api/courses/1/quiz',json={'mode':'mock','count':3,'bloom_distribution':{'Apply':100}}),201)
