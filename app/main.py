from pathlib import Path
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import FileResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError,OperationalError
from app.api import auth,courses,learning,teaching,generation,speech,workflows,viva,attachments,admin,research,universal,formal_viva
from app.auth.security import current_user,role
from app.config import DEMO_MODE,MAX_UPLOAD
ROOT=Path(__file__).resolve().parent
app=FastAPI(title='CampusPath AI',version='0.5.0',docs_url='/api/docs' if DEMO_MODE else None,redoc_url=None)
from app.http_limits import BodyLimitMiddleware
app.add_middleware(BodyLimitMiddleware,limit=MAX_UPLOAD+1024*1024)
for router in (universal.router,formal_viva.router,workflows.router,viva.router,attachments.router,admin.router,research.router):app.include_router(router)
app.include_router(generation.router);app.include_router(speech.router);app.include_router(auth.router);app.include_router(courses.router);app.include_router(learning.router);app.include_router(teaching.router)
from app.voice.streaming import router as voice_router
app.include_router(voice_router)
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
@app.middleware('http')
async def security_headers(request:Request,call_next):
    origin=request.headers.get('origin')
    if request.method not in ('GET','HEAD','OPTIONS') and origin and origin!=str(request.base_url).rstrip('/'):
        return JSONResponse({'detail':'Cross-origin requests are not allowed.'},403)
    if request.method not in ('GET','HEAD','OPTIONS'):
        length=request.headers.get('content-length')
        if length and (not length.isdigit() or int(length)>MAX_UPLOAD+1024*1024):
            return JSONResponse({'detail':'Request exceeds the size limit.'},413)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['Permissions-Policy']='microphone=(self), camera=()'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; media-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    if request.url.path.startswith('/api'):response.headers['Cache-Control']='no-store'
    return response
@app.exception_handler(IntegrityError)
async def conflict(request,exc):
    return JSONResponse({'detail':'This operation conflicts with an existing record. Refresh and retry.'},409)
@app.get('/api/health')
def health():
    import os
    return {'max_upload_mib':MAX_UPLOAD//(1024*1024),'stt_configured':bool(os.getenv('SPEECH_API_KEY') and os.getenv('STT_MODEL')),'tts_configured':bool(os.getenv('SPEECH_API_KEY') and os.getenv('TTS_MODEL')),'status':'ok','demo_mode':DEMO_MODE,'version':'0.5.0','voice':'PCM WebSocket with energy VAD, per-turn STT and controlled playback'
        ,'voice_transport':'websocket-pcm-vad','retrieval':'Lexical index with optional Qdrant hybrid search'}
@app.get('/')
@app.get('/login')
@app.get('/register')
@app.get('/app')
def shell():return FileResponse(ROOT/'templates'/'index.html')
@app.get('/teacher/students')
def teacher_page(user=Depends(current_user)):
    role(user,'teacher');return FileResponse(ROOT/'templates'/'index.html')
@app.get('/student/{sid}')
def student_page(sid:int,user=Depends(current_user)):
    if user.role!='student' or user.id!=sid:raise HTTPException(403,'Student records are private.')
    return FileResponse(ROOT/'templates'/'index.html')

@app.exception_handler(OperationalError)
async def database_unavailable(request,exc):
    return JSONResponse({'detail':'The database is busy or needs setup. Retry shortly; if it persists, run python run.py --check.'},503)
@app.exception_handler(Exception)
async def unexpected_error(request,exc):
    import logging,secrets
    reference=secrets.token_hex(4)
    logging.getLogger('campuspath').error('Unhandled %s; reference=%s',type(exc).__name__,reference)
    return JSONResponse({'detail':'An unexpected error occurred. Your request was not confirmed. Refresh and retry. Reference: '+reference},500)
