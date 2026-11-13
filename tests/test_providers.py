import pytest
from io import BytesIO
from PIL import Image,ImageDraw,ImageFont
from sqlalchemy import select
from app.db import SessionLocal
from app.models import User,Question
from app.ai.curriculum import CurriculumDraft,QuestionDraft
from app.ai.vector import QdrantStore,CompatibleEmbeddings
from app.ai.providers import TutorOutput
from app.documents.extract import extract

class Reply:
    def __init__(self,data,status=200):self.data=data;self.status_code=status
    def json(self):return self.data
    def raise_for_status(self):
        if self.status_code>=400:raise RuntimeError('Unavailable')

def test_vector_query_authorizes_before_and_after_remote_search(monkeypatch):
    monkeypatch.setenv('QDRANT_URL','http://localhost:6333')
    monkeypatch.setattr(CompatibleEmbeddings,'embed',lambda self,text:[[.1,.2]])
    calls=[]
    def fake_post(url,**kwargs):
        calls.append(kwargs['json']);return Reply({'result':{'points':[{'id':1},{'id':999}]}})
    monkeypatch.setattr('app.ai.vector.httpx.post',fake_post)
    assert QdrantStore().search('example',[1,2],4)==[1]
    assert calls[0]['filter']=={'must':[{'has_id':[1,2]}]}

def test_embedding_validation(monkeypatch):
    monkeypatch.setenv('EMBEDDING_BASE_URL','https://provider.example/v1');monkeypatch.setenv('EMBEDDING_API_KEY','fake-test-key');monkeypatch.setenv('EMBEDDING_MODEL','test')
    monkeypatch.setattr('app.ai.vector.httpx.post',lambda *a,**k:Reply({'data':[{'index':0,'embedding':[float('nan')]}]}))
    with pytest.raises(ValueError):CompatibleEmbeddings().embed(['text'])

def test_structured_output_validation():
    with pytest.raises(ValueError):CurriculumDraft.model_validate({'topics':[{'name':'A','description':'A','prerequisites':['B']},{'name':'B','description':'B','prerequisites':['A']}]})
    with pytest.raises(ValueError):TutorOutput.model_validate({'answer':'','source_ids':[]})

def test_image_ocr_actual_tool():
    import shutil
    if not shutil.which('tesseract'):pytest.skip('Tesseract not installed')
    image=Image.new('RGB',(1000,200),'white');draw=ImageDraw.Draw(image)
    try:font=ImageFont.truetype('DejaVuSans.ttf',42)
    except OSError:pytest.skip('Test font unavailable')
    draw.text((25,60),'Heuristic estimates remaining cost.',fill='black',font=font)
    output=BytesIO();image.save(output,format='PNG')
    parts=extract('notes.png',output.getvalue())
    assert 'remaining cost' in parts[0][1]
    assert 'OCR' in parts[0][0]

def test_validated_generation_stays_unpublished(clients,monkeypatch):
    t,_=clients('teacher@campuspath.demo')
    monkeypatch.setattr('app.api.generation.DEMO_MODE',False)
    from app.models import Chunk
    with SessionLocal() as db:source_id=db.scalar(select(Chunk.id))
    async def fake(*args):return QuestionDraft.model_validate({'question':{'topic_id':7,'prompt':'A new source-grounded test question?','options':['One','Two'],'correct':0,'explanation':'A reviewed explanation.'},'source_ids':[source_id]})
    monkeypatch.setattr('app.api.generation.structured_generation',fake)
    result=t.post('/api/courses/1/questions/generate',json={'topic_id':7})
    assert result.status_code==200 and result.json()['review_required']
    with SessionLocal() as db:assert not db.scalar(select(Question.id).where(Question.prompt=='A new source-grounded test question?'))

def test_generated_foreign_citation_rejected(clients,monkeypatch):
    t,_=clients('teacher@campuspath.demo');monkeypatch.setattr('app.api.generation.DEMO_MODE',False)
    async def fake(*args):return QuestionDraft.model_validate({'question':{'topic_id':7,'prompt':'A source-grounded test question?','options':['One','Two'],'correct':0,'explanation':'An explanation.'},'source_ids':[999999]})
    monkeypatch.setattr('app.api.generation.structured_generation',fake)
    assert t.post('/api/courses/1/questions/generate',json={'topic_id':7}).status_code==502

def test_curriculum_approval_and_rollback(clients):
    t,_=clients('teacher@campuspath.demo');s,_=clients('saim@campuspath.demo')
    body={'topics':[{'name':'Advanced Search','description':'Advanced search methods','prerequisites':['A*']}]}
    assert s.post('/api/courses/1/curriculum/approve',json=body).status_code==404
    assert t.post('/api/courses/1/curriculum/approve',json=body).status_code==200
    body={'topics':[{'name':'Invalid Search','description':'Invalid dependency','prerequisites':['UNKNOWN']}]}
    assert t.post('/api/courses/1/curriculum/approve',json=body).status_code==422
    assert all(x['name']!='Invalid Search' for x in t.get('/api/courses/1/topics').json())

def test_unconfigured_speech_falls_back_safely(clients,monkeypatch):
    monkeypatch.delenv('SPEECH_API_KEY',raising=False)
    c,_=clients('saim@campuspath.demo')
    assert c.post('/api/courses/1/speech/transcribe',files={'file':('test.webm',b'audio')}).status_code==503
    assert c.post('/api/courses/1/speech/synthesize',json={'text':'A test'}).status_code==503

def test_speech_provider_receives_only_audio_and_returns_editable_text(clients,monkeypatch):
    c,_=clients('saim@campuspath.demo');monkeypatch.setenv('SPEECH_BASE_URL','https://provider.example/v1');monkeypatch.setenv('SPEECH_API_KEY','fake');monkeypatch.setenv('STT_MODEL','test')
    calls=[]
    def fake(*args,**kwargs):calls.append(kwargs);return Reply({'text':'Estimated remaining cost.'})
    monkeypatch.setattr('app.documents.multimodal.httpx.post',fake)
    r=c.post('/api/courses/1/speech/transcribe',files={'file':('test.webm',b'audio')})
    assert r.status_code==200 and r.json()['review_required'] and not r.json()['raw_audio_stored']
    assert 'cookie' not in {k.lower() for k in calls[0]['headers']}
