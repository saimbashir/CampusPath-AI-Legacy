from sqlalchemy import select
from app.db import SessionLocal
from app.models import Question,Mastery
from app.mastery.engine import update_mastery
from tests.test_workflows import good
from tests.test_universal_viva import course_flow,MATERIALS

def test_gradual_mastery_and_small_bank_cannot_certify(clients):
    s,u=clients('saim@campuspath.demo')
    for prior in [.2,.4,.6,.79,.9]:assert update_mastery(prior,True)-prior<=.030001
    with SessionLocal() as db:
        m=db.scalar(select(Mastery).where(Mastery.student_id==u['id'],Mastery.topic_id==1));m.probability=.77;db.commit()
    for _ in range(4):
        run=good(s.post('/api/courses/1/quiz',json={'topic_id':1,'count':8}),201)
        while not run['complete']:
            with SessionLocal() as db:q=db.get(Question,run['question']['id']);correct=q.correct
            answer=good(s.post(f"/api/quiz/{run['id']}/answer",json={'question_id':q.id,'selected':correct}))
            assert answer['mastery']['after']-answer['mastery']['before']<=3
            run=answer['next']
    with SessionLocal() as db:assert db.scalar(select(Mastery).where(Mastery.student_id==u['id'],Mastery.topic_id==1)).probability<=.79

def test_acronym_and_new_teacher_upload_available_immediately(clients):
    t,s,cid,rid,_=course_flow(clients,*MATERIALS[3])
    assert not good(s.post(f'/api/courses/{cid}/tutor',json={'question':'GBFS'}))['sources']
    uploaded=good(t.post(f'/api/courses/{cid}/resources',files={'file':('search.txt',b'Greedy Best-First Search selects the node with the smallest estimated remaining cost. It ignores accumulated path cost.')}),201)
    reply=good(s.post(f'/api/courses/{cid}/tutor',json={'question':'Explain GBFS'}))
    assert any(x['filename']=='search.txt' for x in reply['sources'])
    assert 'smallest estimated' in reply['answer']

def test_expanded_demo_and_detailed_wrong_feedback(clients):
    s,_=clients('saim@campuspath.demo')
    with SessionLocal() as db:
        for tid in range(1,9):assert len(db.scalars(select(Question).where(Question.topic_id==tid,Question.approved.is_(True))).all())>=8
    run=good(s.post('/api/courses/1/quiz',json={'topic_id':6,'count':8}),201);assert run['total']==8
    with SessionLocal() as db:q=db.get(Question,run['question']['id']);wrong=(q.correct+1)%len(q.options)
    result=good(s.post(f"/api/quiz/{run['id']}/answer",json={'question_id':q.id,'selected':wrong}))
    for label in ['Your answer:','Correct answer:','Why your choice is incorrect:','Why the correct answer fits:','The concept in context:','Check your understanding:']:assert label in result['explanation']

def test_grounded_batch_saves_only_reviewable_questions(clients,monkeypatch):
    from app.ai import grounded
    t,s,cid,rid,catalog=course_flow(clients,*MATERIALS[3]);topic=catalog['topics'][0]['id']
    monkeypatch.setattr(grounded,'enabled',lambda:True)
    async def provider(instruction,context,schema):
        if schema is grounded.GroundingVerdict:return schema(supported=True,reason='Supported by the supplied notes.',source_ids=[context[0]['id']])
        return schema(questions=[grounded.GroundedQuestion(question_text=f'Which statement describes producers, example {i}?',topic_id=topic,question_type='MCQ',options=['Convert light energy','Create light from nutrients'],correct_option=0,expected_concepts=['Energy conversion'],acceptable_answer_points=['Producers convert light into stored chemical energy.'],citations=[grounded.Citation(chunk_id=context[-1]['id'],quote=context[-1]['text'])]) for i in range(4)])
    monkeypatch.setattr(grounded,'structured_generation',provider)
    result=good(t.post(f'/api/courses/{cid}/questions/generate-batch',json={'topic_id':topic,'count':4,'resource_ids':[rid],'chapters':['2']}),201)
    assert result['created']==4
    qs=good(t.get(f'/api/courses/{cid}/questions'));assert len(qs)==4 and all(not q['approved'] and q['source_ids'] for q in qs)
    assert s.post(f'/api/courses/{cid}/quiz',json={'count':4}).status_code==409
    assert t.post(f'/api/courses/{cid}/questions/generate-batch',json={'topic_id':topic,'count':4,'resource_ids':[rid],'chapters':['2']}).status_code==502
    assert len(good(t.get(f'/api/courses/{cid}/questions')))==4

def test_viva_does_not_repeat_current_question(clients,monkeypatch):
    from app.ai import grounded
    from tests.test_universal_viva import create_exam,structured_fake
    t,s,cid,rid,_=course_flow(clients,*MATERIALS[2]);exam=create_exam(t,cid,rid,follow_up_depth=3)
    session=good(s.post(f"/api/vivas/{exam['id']}/start"))
    async def repeating(question,transcript,history,rubric,evidence):
        return {'correctness':'partially_correct','feedback':'A relevant point was made.','confidence':.8,'marks':3,'scoring':[],'correct_points':[],'incorrect_points':[],'missing_points':[],'misconceptions':[],'follow_up':question['current_prompt'],'follow_up_citations':[]},'AI PROVISIONAL'
    monkeypatch.setattr(grounded,'evaluate',repeating)
    result=good(s.post(f"/api/oral-sessions/{session['id']}/answer",json={'turn':0,'transcript':'Sequence numbers support ordered delivery.'}))
    assert result['complete'] and result['ai_proposed_marks']==3
    from app.models import OralResponse
    with SessionLocal() as db:
        saved=db.scalar(select(OralResponse).where(OralResponse.session_id==session['id']))
        assert saved.evaluation['follow_up']==''
