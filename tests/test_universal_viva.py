"""Acceptance checks across unrelated curricula using the same production paths.
AI/STT responses are controlled test doubles, not live provider or microphone validation.
"""
import json
from datetime import timedelta
from sqlalchemy import select
import pytest
from app.db import SessionLocal
from app.models import Question,VivaQuestion,OralResponse,OralReview,Mastery,now
from app.ai import grounded
from app.ai.providers import structured_generation
from tests.test_workflows import good

MATERIALS=[
 ('Artificial Intelligence','Search methods','Heuristic search uses an estimated remaining cost. The estimate can guide exploration toward the goal. An admissible heuristic does not overestimate the optimal remaining cost.'),
 ('Linear Algebra','Determinants','A square matrix is invertible if and only if its determinant is nonzero. A zero determinant means the columns are linearly dependent. The determinant measures signed volume scaling.'),
 ('Computer Networks','TCP','TCP provides a reliable ordered byte stream between endpoints. Sequence numbers allow a receiver to order bytes. Acknowledgments and retransmissions recover lost data.'),
 ('Environmental Science','Ecosystems','Producers convert light energy into stored chemical energy. Consumers obtain energy by eating other organisms. Decomposers recycle nutrients from dead organic material.')]

def course_flow(clients,title,heading,body):
    t,_=clients('teacher@campuspath.demo');s,u=clients('saim@campuspath.demo')
    course=good(t.post('/api/courses',json={'name':title,'code':'TEST-'+str(len(title)),'section':'Acceptance'}),201)
    cid=course['id'];good(s.post('/api/courses/join',json={'code':course['enrollment_code']}))
    text=f'Chapter 2: {heading}\nSection 2.1: Main concept\n{body}\nChapter 3: Review\nExplain the key relationship using evidence from this chapter.'
    uploaded=good(t.post(f'/api/courses/{cid}/resources',files={'file':('teacher-notes.txt',text.encode(),'text/plain')}),201)
    draft=good(t.post(f'/api/courses/{cid}/structure/extract',json={'resource_ids':[uploaded['id']],'chapters':['2']}))
    assert draft['covered_chunks']==2
    good(t.post(f'/api/courses/{cid}/structure/approve',json=draft['draft']))
    catalog=good(t.get(f'/api/courses/{cid}/material-catalog'));assert catalog['topics'] and catalog['topics'][0]['structure']['source_ids']
    # Book-aware tutoring retrieves exactly the selected chapter.
    tutor=good(s.post(f'/api/courses/{cid}/tutor',json={'question':'Explain chapter 2'}));assert tutor['sources'] and all(x['structure']['chapter']=='2' for x in tutor['sources'])
    return t,s,cid,uploaded['id'],catalog

def create_exam(t,cid,rid,count=1,**changes):
    config={'count':count,'total_marks':5*count,'follow_up_depth':0,**changes}
    ex=good(t.post(f'/api/courses/{cid}/vivas',json={'title':'Course evidence viva','scope':{'resource_ids':[rid],'chapters':['2'],'sections':['2.1']},'config':config}),201)
    generated=good(t.post(f"/api/vivas/{ex['id']}/generate"))
    for q in generated['questions']:good(t.post(f"/api/vivas/{ex['id']}/questions/{q['id']}/review",json={'approved':True}))
    good(t.post(f"/api/vivas/{ex['id']}/publish"));return generated

async def structured_fake(instruction,context,schema):
    """Material-dependent evaluator contract; this is deliberately not called a real LLM."""
    if schema is grounded.EvaluatedAnswer:
        obj=context[0];source=obj['sources'][0]
        return schema.model_validate({'correctness':'partially_correct','correct_points':['Relevant core relationship identified.'],'incorrect_points':[],'missing_points':['Further justification.'],'misconceptions':[],'feedback':'The core point is supported; add justification.','confidence':.85,'criteria':[{'name':r['name'],'score_percent':80,'reason':'Supported core concept; justification incomplete.'} for r in obj['rubric']],'citations':[{'chunk_id':source['id'],'quote':source['text'][:80]}],'follow_up':'','follow_up_citations':[]})
    if schema is grounded.GroundingVerdict:return schema(supported=True,reason='The cited passage supports this question.',source_ids=[context[0]['id']])
    raise AssertionError('Unexpected schema '+schema.__name__)

@pytest.mark.parametrize('title,heading,body',MATERIALS)
def test_runtime_course_material_viva_audio_review_analytics(clients,monkeypatch,title,heading,body):
    t,s,cid,rid,catalog=course_flow(clients,title,heading,body)
    ex=create_exam(t,cid,rid);session=good(s.post(f"/api/vivas/{ex['id']}/start"));qid=session['question']['id']
    # Student payload cannot reveal expected answers or the private rubric.
    exposed=json.dumps(session);assert 'expected_concepts' not in exposed and 'acceptable_answer_points' not in exposed and 'rubric' not in exposed
    # Transport exercises PCM -> WAV -> STT -> editable text -> scoring with controlled STT output.
    monkeypatch.setattr('app.voice.streaming.transcribe',lambda *args:[('transcript',body.split('.')[0]+'.')])
    with s.websocket_connect(f'/ws/courses/{cid}/voice',headers={'origin':'http://testserver'}) as ws:
        ws.send_json({'type':'start','csrf':s.headers['X-CSRF-Token'],'sample_rate':16000});assert ws.receive_json()['type']=='ready'
        ws.send_bytes(b'\0\x10'*4096);ws.send_json({'type':'finish'});assert ws.receive_json()['type']=='transcribing';transcript=ws.receive_json();assert transcript['review_required'] and not transcript['raw_audio_stored']
    monkeypatch.setattr(grounded,'enabled',lambda:True);monkeypatch.setattr(grounded,'structured_generation',structured_fake)
    result=good(s.post(f"/api/oral-sessions/{session['id']}/answer",json={'turn':0,'transcript':transcript['text']}))
    assert result['status']=='TEACHER_REVIEW_REQUIRED' and result['ai_proposed_marks']==4 and result['confirmed_marks'] is None
    assert sum(c['marks'] for c in result['responses'][0]['evaluation']['scoring'])==4
    review=good(t.put(f"/api/oral-sessions/{session['id']}/questions/{qid}/review",json={'marks':4.5,'feedback':'Good answer with sufficient explanation.'}))
    assert review['confirmed_marks'] is None
    final=good(t.post(f"/api/oral-sessions/{session['id']}/finalize"));assert final['confirmed_marks']==4.5 and final['percentage']==90
    assert t.post(f"/api/oral-sessions/{session['id']}/finalize").status_code==409
    student=good(s.get(f"/api/oral-sessions/{session['id']}"));assert student['confirmed_marks']==4.5
    analytics=good(t.get(f'/api/courses/{cid}/viva-analytics'));assert analytics['class_average']==90 and analytics['finalized']==1
    directory=good(t.get(f'/api/courses/{cid}/students'));assert directory[0]['viva_average']==90
    assert any('4.5/5' in x['message'] for x in good(s.get('/api/notifications')))

def test_followup_context_and_marks_are_not_double_counted(clients,monkeypatch):
    t,s,cid,rid,_=course_flow(clients,*MATERIALS[2]);ex=create_exam(t,cid,rid,follow_up_depth=1,immediate_feedback=False)
    session=good(s.post(f"/api/vivas/{ex['id']}/start"));calls=[]
    async def evaluator(instruction,context,schema):
        if schema is grounded.EvaluatedAnswer:
            obj=context[0];calls.append(obj);r=await structured_fake(instruction,context,schema)
            if not obj['conversation']:
                r.follow_up='Explain the supporting relationship in the cited passage.';r.follow_up_citations=r.citations
            return r
        return await structured_fake(instruction,context,schema)
    monkeypatch.setattr(grounded,'enabled',lambda:True);monkeypatch.setattr(grounded,'structured_generation',evaluator)
    first=good(s.post(f"/api/oral-sessions/{session['id']}/answer",json={'turn':0,'transcript':'Sequence numbers order bytes.'}))
    assert first['question']['is_follow_up'] and not first['complete'] and 'evaluation' not in first['responses'][0]
    second=good(s.post(f"/api/oral-sessions/{session['id']}/answer",json={'turn':1,'transcript':'The receiver uses sequence numbers to assemble the ordered byte stream.'}))
    assert second['complete'] and second['ai_proposed_marks']==4 and len(second['responses'])==2
    assert calls[1]['conversation'][0]['answer']=='Sequence numbers order bytes.'
    assert s.post(f"/api/oral-sessions/{session['id']}/answer",json={'turn':1,'transcript':'replay'}).status_code==409

def test_scope_private_source_and_cross_student_guards(clients):
    t,s,cid,rid,_=course_flow(clients,*MATERIALS[1]);peer,_=clients('ahmed@campuspath.demo');outsider,_=clients('other@campuspath.demo')
    private=good(s.post(f'/api/courses/{cid}/resources',files={'file':('private.txt',b'Personal notes that are never teacher-provided material.')}),201)
    bad=t.post(f'/api/courses/{cid}/vivas',json={'title':'Bad scope','scope':{'resource_ids':[private['id']]}});assert bad.status_code==422
    ex=create_exam(t,cid,rid);session=good(s.post(f"/api/vivas/{ex['id']}/start"))
    assert peer.get(f"/api/oral-sessions/{session['id']}").status_code==404
    assert peer.post(f"/api/vivas/{ex['id']}/start").status_code==404
    assert outsider.get(f'/api/courses/{cid}/oral-review').status_code==404
    assert s.get(f'/api/courses/{cid}/oral-review').status_code==404
    assert s.put(f"/api/oral-sessions/{session['id']}/questions/{session['question']['id']}/review",json={'marks':5,'feedback':'forged'}).status_code==404
    assert 'expected_concepts' not in json.dumps(good(s.get(f"/api/vivas/{ex['id']}")))

def test_manual_citations_and_publication_guards(clients):
    t,s,cid,rid,_=course_flow(clients,*MATERIALS[0]);ex=good(t.post(f'/api/courses/{cid}/vivas',json={'title':'Grounding guards','scope':{'resource_ids':[rid]},'config':{'count':1,'total_marks':5}}),201)
    assert t.post(f"/api/vivas/{ex['id']}/publish").status_code==409
    assert s.get(f"/api/vivas/{ex['id']}").status_code==404
    evidence=good(t.post(f'/api/courses/{cid}/material-query',json={'resource_ids':[rid]}))[0]
    q={'question_text':'Explain the statement from this source.','marks':5,'expected_concepts':['The provided statement'],'acceptable_answer_points':['Accurate explanation'],'citations':[{'chunk_id':evidence['id'],'quote':'An invented quotation that is not present.'}]}
    assert t.post(f"/api/vivas/{ex['id']}/questions",json=q).status_code==422
    q['citations'][0]['quote']=evidence['text'];q['approved']=True
    v=good(t.post(f"/api/vivas/{ex['id']}/questions",json=q),201);good(t.post(f"/api/vivas/{ex['id']}/publish"))
    assert t.put(f"/api/vivas/{ex['id']}/questions/{v['questions'][0]['id']}",json=q).status_code==409

def test_evaluator_bad_citation_falls_back_without_marks(clients,monkeypatch):
    t,s,cid,rid,_=course_flow(clients,*MATERIALS[3]);ex=create_exam(t,cid,rid);session=good(s.post(f"/api/vivas/{ex['id']}/start"))
    async def invalid(instruction,context,schema):
        r=await structured_fake(instruction,context,schema);r.citations=[grounded.Citation(chunk_id=999999,quote='Invented outside-source evidence')];return r
    monkeypatch.setattr(grounded,'enabled',lambda:True);monkeypatch.setattr(grounded,'structured_generation',invalid)
    r=good(s.post(f"/api/oral-sessions/{session['id']}/answer",json={'turn':0,'transcript':'A sample explanation of producers.'}))
    assert r['complete'] and r['ai_proposed_marks'] is None and r['responses'][0]['provider']=='PROVIDER FALLBACK'

def test_flags_limits_and_finish_unanswered(clients):
    t,s,cid,rid,_=course_flow(clients,*MATERIALS[1]);ex=create_exam(t,cid,rid,count=2);session=good(s.post(f"/api/vivas/{ex['id']}/start"));sid=session['id']
    assert t.post(f'/api/oral-sessions/{sid}/finalize').status_code==409
    good(s.post(f'/api/oral-sessions/{sid}/finish'));questions=good(t.get(f'/api/courses/{cid}/oral-review'))[0]['questions']
    assert t.put(f"/api/oral-sessions/{sid}/questions/{questions[0]['id']}/review",json={'marks':6,'feedback':'too high'}).status_code==422
    for q in questions:good(t.put(f"/api/oral-sessions/{sid}/questions/{q['id']}/review",json={'marks':0,'feedback':'No answer submitted.','flagged':True}))
    assert t.post(f'/api/oral-sessions/{sid}/finalize').status_code==409
    for q in questions:good(t.put(f"/api/oral-sessions/{sid}/questions/{q['id']}/review",json={'marks':0,'feedback':'No answer submitted.'}))
    final=good(t.post(f'/api/oral-sessions/{sid}/finalize'));assert final['confirmed_marks']==0
    assert t.put(f"/api/oral-sessions/{sid}/questions/{questions[0]['id']}/review",json={'marks':5,'feedback':'late overwrite'}).status_code==409

def test_auto_finalize_only_explicit_and_no_unreviewed_mastery(clients,monkeypatch):
    t,s,cid,rid,_=course_flow(clients,*MATERIALS[3]);ex=create_exam(t,cid,rid,review_required=False);session=good(s.post(f"/api/vivas/{ex['id']}/start"))
    before=good(s.get(f'/api/courses/{cid}/students/2/progress'))['mastery']
    monkeypatch.setattr(grounded,'enabled',lambda:True);monkeypatch.setattr(grounded,'structured_generation',structured_fake)
    final=good(s.post(f"/api/oral-sessions/{session['id']}/answer",json={'turn':0,'transcript':'Producers store energy through conversion of sunlight.'}))
    assert final['status']=='FINALIZED' and final['confirmed_marks']==4
    assert good(s.get(f'/api/courses/{cid}/students/2/progress'))['mastery']==before
    assert 'AUTO-FINALIZED' in final['reviews'][0]['feedback']

def test_material_only_filters_private_retrieval_and_unlinked_mcqs(clients):
    t,s,cid,rid,_=course_flow(clients,*MATERIALS[3])
    good(s.post(f'/api/courses/{cid}/resources',files={'file':('private.txt',b'UnrelatedPrivateKeyword teaching statement.')}),201)
    good(t.put(f'/api/courses/{cid}/material-policy',json={'material_only':True}))
    r=good(s.post(f'/api/courses/{cid}/tutor',json={'question':'UnrelatedPrivateKeyword'}));assert not r['sources'] and 'does not contain enough' in r['answer']
    topic=good(t.get(f'/api/courses/{cid}/topics'))[0]['id']
    q=good(t.post(f'/api/courses/{cid}/questions',json={'topic_id':topic,'prompt':'Which statement is relevant?','options':['One','Two'],'correct':0,'explanation':'Teacher authored.'}),201)
    good(t.post(f"/api/courses/{cid}/questions/{q['id']}/approve"))
    assert s.post(f'/api/courses/{cid}/quiz',json={'count':1}).status_code==409

def test_window_and_specific_assignment(clients):
    t,s,cid,rid,_=course_flow(clients,*MATERIALS[2]);ex=create_exam(t,cid,rid,starts=(now()+timedelta(days=1)).isoformat(),ends=(now()+timedelta(days=2)).isoformat())
    assert s.post(f"/api/vivas/{ex['id']}/start").status_code==409
    bad=t.post(f'/api/courses/{cid}/vivas',json={'title':'Bad rubric','scope':{'resource_ids':[rid]},'config':{'rubric':[{'name':'Concepts','weight':50}]}});assert bad.status_code==422

def test_fractional_mark_allocation_and_generated_support_check(clients,monkeypatch):
    t,s,cid,rid,_=course_flow(clients,*MATERIALS[2])
    ex=good(t.post(f'/api/courses/{cid}/vivas',json={'title':'Fractional total','scope':{'resource_ids':[rid],'chapters':['2'],'sections':['2.1']},'config':{'count':3,'total_marks':10}}),201)
    v=good(t.post(f"/api/vivas/{ex['id']}/generate"));assert [q['marks'] for q in v['questions']]==[3.34,3.33,3.33]
    # The independent model review can reject a well-formed but unsupported question.
    evidence=good(t.post(f'/api/courses/{cid}/material-query',json={'resource_ids':[rid],'sections':['2.1']}))
    q=grounded.GroundedQuestion(question_text='Explain a claim absent from these sources.',expected_concepts=['Unsupported concept'],acceptable_answer_points=['Unsupported point'],citations=[grounded.Citation(chunk_id=evidence[0]['id'],quote=evidence[0]['text'][:60])])
    async def reject(*args):return grounded.GroundingVerdict(supported=False,reason='The question asks for an unsupported claim.',source_ids=[evidence[0]['id']])
    monkeypatch.setattr(grounded,'enabled',lambda:True);monkeypatch.setattr(grounded,'structured_generation',reject)
    import asyncio
    with pytest.raises(ValueError):asyncio.run(grounded.verify_question(q,evidence))

def test_uploaded_pdf_chapters_page_and_five_question_demo(clients):
    from pathlib import Path
    t,_=clients('teacher@campuspath.demo');s,_=clients('saim@campuspath.demo')
    c=good(t.post('/api/courses',json={'name':'Computer Networks PDF demonstration','code':'CN-PDF','section':'A'}),201);cid=c['id'];good(s.post('/api/courses/join',json={'code':c['enrollment_code']}));ids=[]
    for filename in ['CN_Lecture_01.pdf','CN_Lecture_02.pdf']:
        data=(Path(__file__).parents[1]/'sample_data'/'universal'/filename).read_bytes()
        ids.append(good(t.post(f'/api/courses/{cid}/resources',files={'file':(filename,data,'application/pdf')}),201)['id'])
    material=good(t.post(f'/api/courses/{cid}/material-query',json={'resource_ids':ids,'chapters':['1'],'page_from':1,'page_to':1}));assert material and all(x['structure']['chapter']=='1' and x['structure']['page']==1 for x in material)
    v=good(t.post(f'/api/courses/{cid}/vivas',json={'title':'Computer Networks Viva','scope':{'resource_ids':ids},'config':{'count':5,'total_marks':25}}),201)
    v=good(t.post(f"/api/vivas/{v['id']}/generate"));assert len(v['questions'])==5 and sum(q['marks'] for q in v['questions'])==25
    for q in v['questions']:assert all(x['resource_id'] in ids for x in q['sources'])

def test_material_only_assignment_requires_source_link(clients):
    t,s,cid,rid,_=course_flow(clients,*MATERIALS[3]);good(t.put(f'/api/courses/{cid}/material-policy',json={'material_only':True}))
    assignment={'title':'Source grounded response','instructions':'Explain the teacher material.','rubric':'Correct concepts and reasoning.','due':(now()+timedelta(days=1)).isoformat()}
    assert t.post(f'/api/courses/{cid}/assignments',json=assignment).status_code==422
    source=good(t.post(f'/api/courses/{cid}/material-query',json={'resource_ids':[rid]}))[0]
    assignment['source_ids']=[source['id']];good(t.post(f'/api/courses/{cid}/assignments',json=assignment),201)

def test_structure_covers_more_than_first_thirty_chunks(monkeypatch):
    import asyncio
    seen=[]
    evidence=[{'id':i,'resource_id':1,'text':f'Teacher passage {i}: A source-specific relationship is explained here.','filename':'Any course notes','location':f'Page {i}','structure':{}} for i in range(1,36)]
    async def generate(instruction,context,schema):
        seen.extend(x['id'] for x in context)
        return grounded.StructureDraft(topics=[grounded.Concept(name=f'Concept from {s["id"]}',description=s['text'],citations=[grounded.Citation(chunk_id=s['id'],quote=s['text'])]) for s in context])
    monkeypatch.setattr(grounded,'enabled',lambda:True);monkeypatch.setattr(grounded,'structured_generation',generate)
    result,status=asyncio.run(grounded.structure(evidence));assert len(result.topics)==35 and seen==list(range(1,36))

def test_environmental_quiz_provider_draft_to_student_result(clients,monkeypatch):
    from app.api import generation
    t,s,cid,rid,catalog=course_flow(clients,*MATERIALS[3])
    topic=catalog['topics'][0]['id']
    async def provider(instruction,context,schema):
        assert context and all(x['resource_id']==rid for x in context)
        return schema.model_validate({'question':{'topic_id':topic,'prompt':'What do producers convert into stored chemical energy?','options':['Light energy','Dead organic matter'],'correct':0,'explanation':'Producers convert light energy into stored chemical energy.','difficulty':1},'source_ids':[context[0]['id']]})
    monkeypatch.setattr(generation,'DEMO_MODE',False)
    monkeypatch.setattr(generation,'structured_generation',provider)
    draft=good(t.post(f'/api/courses/{cid}/questions/generate',json={'topic_id':topic,'resource_ids':[rid],'chapters':['2']}))
    assert draft['review_required'] and draft['draft']['source_ids']
    question=good(t.post(f'/api/courses/{cid}/questions',json=draft['draft']),201)
    good(t.post(f"/api/courses/{cid}/questions/{question['id']}/approve"))
    good(t.put(f'/api/courses/{cid}/material-policy',json={'material_only':True}))
    run=good(s.post(f'/api/courses/{cid}/quiz',json={'count':1}),201)
    result=good(s.post(f"/api/quiz/{run['id']}/answer",json={'question_id':run['question']['id'],'selected':0}))
    assert result['correct'] is True

def test_regeneration_preserves_draft_on_wrong_question_type(clients,monkeypatch):
    t,s,cid,rid,_=course_flow(clients,*MATERIALS[0])
    ex=good(t.post(f'/api/courses/{cid}/vivas',json={'title':'Regeneration validation','scope':{'resource_ids':[rid]},'config':{'count':1,'total_marks':5}}),201)
    generated=good(t.post(f"/api/vivas/{ex['id']}/generate"));q=generated['questions'][0]
    original=grounded.questions
    async def wrong_type(evidence,topics,config):
        drafts,provider=await original(evidence,topics,config)
        drafts[0].question_type='Definition'
        return drafts,provider
    monkeypatch.setattr(grounded,'questions',wrong_type)
    assert t.post(f"/api/vivas/{ex['id']}/questions/{q['id']}/regenerate").status_code==502
    after=good(t.get(f"/api/vivas/{ex['id']}"))['questions'][0]
    assert after['question_text']==q['question_text'] and after['question_type']==q['question_type']
