"""Authenticated live PCM transport with energy VAD and per-turn transcription.

This is not provider-token streaming: transcription happens after detected silence/finish.
"""
import asyncio,json,secrets,wave,io,math,sys
from array import array
from fastapi import APIRouter,WebSocket,WebSocketDisconnect,HTTPException
from app.db import SessionLocal
from app.models import Session,User,now
from app.auth.security import digest,course_access,throttle
from app.documents.multimodal import transcribe
router=APIRouter()
ACTIVE={}
class EnergyVAD:
    def __init__(self,rate,threshold=450,silence_seconds=.8):
        self.rate=rate;self.threshold=threshold;self.silence_seconds=silence_seconds
        self.speech_samples=0;self.silence_samples=0;self.total=0
    def feed(self,data):
        if not data or len(data)%2 or len(data)>32768:raise ValueError('Send mono PCM16 frames of at most 16,384 samples.')
        samples=array('h');samples.frombytes(data)
        if sys.byteorder!='little':samples.byteswap()
        rms=math.sqrt(sum(x*x for x in samples)/len(samples))
        self.total+=len(samples)
        if rms>=self.threshold:self.speech_samples+=len(samples);self.silence_samples=0
        elif self.speech_samples:self.silence_samples+=len(samples)
        return self.speech_samples/self.rate>=.25 and self.silence_samples/self.rate>=self.silence_seconds
    def wav(self,data):
        out=io.BytesIO()
        with wave.open(out,'wb') as writer:writer.setnchannels(1);writer.setsampwidth(2);writer.setframerate(self.rate);writer.writeframes(data)
        return out.getvalue()

def authorize(ws,cid,csrf=None):
    with SessionLocal() as db:
        token=ws.cookies.get('campus_session','');session=db.get(Session,digest(token)) if token else None
        if not session or session.expires<now():raise HTTPException(401,'Session expired.')
        user=db.get(User,session.user_id)
        if not user or not user.active:raise HTTPException(401,'Account unavailable.')
        course_access(db,user,cid)
        if csrf is not None:
            if not isinstance(csrf,str) or not secrets.compare_digest(session.csrf,csrf):raise HTTPException(403,'Invalid request token.')
            throttle(db,'voice-stream:'+str(user.id),30)
        return user.id

@router.websocket('/ws/courses/{cid}/voice')
async def voice(ws:WebSocket,cid:int):
    uid=None;registered=False
    origin=ws.headers.get('origin');expected=('https' if ws.url.scheme=='wss' else 'http')+'://'+ws.headers.get('host','')
    if origin!=expected:
        await ws.close(code=1008);return
    try:uid=authorize(ws,cid)
    except HTTPException:
        await ws.close(code=1008);return
    await ws.accept()
    try:
        start=await asyncio.wait_for(ws.receive_text(),timeout=10)
        if len(start)>2048:raise ValueError('Start message is too large.')
        data=json.loads(start)
        if not isinstance(data,dict) or set(data)-{'type','csrf','sample_rate'} or data.get('type')!='start':raise ValueError('Expected a start message.')
        uid=authorize(ws,cid,data.get('csrf',''))
        rate=data.get('sample_rate')
        if type(rate) is not int or rate not in (16000,22050,24000,32000,44100,48000):raise ValueError('Unsupported PCM sample rate.')
        if uid in ACTIVE:raise ValueError('Another microphone session is active for your account. Stop it first.')
        ACTIVE[uid]=ws;registered=True
        vad=EnergyVAD(rate);audio=bytearray();messages=0
        await ws.send_json({'type':'ready','max_seconds':60,'vad':'energy','message':'Speak, then pause or press Finish answer.'})
        while True:
            message=await asyncio.wait_for(ws.receive(),timeout=15);messages+=1
            if messages>5000:raise ValueError('Too many audio frames.')
            if message['type']=='websocket.disconnect':return
            # Re-check revocation and expiration during a long-lived stream.
            authorize(ws,cid)
            if 'bytes' in message and message['bytes'] is not None:
                frame=message['bytes'];done=vad.feed(frame);audio.extend(frame)
                if len(audio)>8*1024*1024 or vad.total/rate>60:done=True
                if not done:continue
            elif 'text' in message and message['text'] is not None:
                if len(message['text'])>200:raise ValueError('Control message too large.')
                control=json.loads(message['text'])
                if not isinstance(control,dict) or set(control)!={'type'}:raise ValueError('Only finish/end controls are accepted.')
                if control['type']=='end':return
                if control['type']!='finish':raise ValueError('Unknown control message.')
            else:raise ValueError('Unsupported frame.')
            if not audio:raise ValueError('No audio received. Type an answer or try again.')
            await ws.send_json({'type':'transcribing','duration_seconds':round(vad.total/rate,2)})
            try:
                parts=await asyncio.to_thread(transcribe,vad.wav(bytes(audio)),'recording.wav','audio/wav')
                authorize(ws,cid)
                await ws.send_json({'type':'transcript','text':parts[0][1],'review_required':True,'raw_audio_stored':False})
            except Exception:
                await ws.send_json({'type':'error','message':'Transcription is unavailable. Your raw audio was not saved; type your answer to continue.'})
            return
    except (WebSocketDisconnect,RuntimeError):pass
    except (ValueError,HTTPException,asyncio.TimeoutError) as exc:
        try:await ws.send_json({'type':'error','message':str(exc.detail) if isinstance(exc,HTTPException) else 'Recording timed out.' if isinstance(exc,asyncio.TimeoutError) else str(exc)})
        except Exception:pass
    finally:
        if registered and ACTIVE.get(uid) is ws:ACTIVE.pop(uid,None)
        try:await ws.close()
        except Exception:pass
