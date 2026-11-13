import os
import httpx
from fastapi import APIRouter,Depends,HTTPException,UploadFile,File
from fastapi.responses import Response
from pydantic import BaseModel,Field
from app.db import get_db
from app.auth.security import current_user,course_access,throttle
from app.documents.multimodal import transcribe
router=APIRouter(prefix='/api/courses')
class SpeechInput(BaseModel):
    text:str=Field(min_length=1,max_length=4000)
@router.post('/{cid}/speech/transcribe')
def stt(cid:int,file:UploadFile=File(...),user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid);throttle(db,'speech:'+str(user.id),60)
    data=file.file.read(8*1024*1024+1)
    if len(data)>8*1024*1024:raise HTTPException(413,'Audio must be under 8 MiB.')
    try:parts=transcribe(data,'recording.webm',file.content_type or 'audio/webm')
    except ValueError as exc:raise HTTPException(503,str(exc))
    except Exception:raise HTTPException(503,'Speech provider is unavailable. Type your answer instead.')
    return {'text':parts[0][1],'raw_audio_stored':False,'review_required':True}
@router.post('/{cid}/speech/synthesize')
def tts(cid:int,data:SpeechInput,user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid);throttle(db,'speech:'+str(user.id),60)
    base=os.getenv('SPEECH_BASE_URL','').rstrip('/')
    if not base.startswith('https://') or not all(os.getenv(k) for k in ['SPEECH_API_KEY','TTS_MODEL','TTS_VOICE']):raise HTTPException(503,'Speech output is not configured. Use browser playback or read the text.')
    try:
        r=httpx.post(base+'/audio/speech',headers={'Authorization':'Bearer '+os.environ['SPEECH_API_KEY']},json={'model':os.environ['TTS_MODEL'],'voice':os.environ['TTS_VOICE'],'input':data.text,'response_format':'mp3'},timeout=45);r.raise_for_status()
        if not r.content or len(r.content)>15*1024*1024:raise ValueError('Invalid speech result')
    except Exception:raise HTTPException(503,'Speech output is unavailable. Read the text instead.')
    return Response(r.content,media_type='audio/mpeg')
