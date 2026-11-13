import os,subprocess,tempfile,shutil
from pathlib import Path
from io import BytesIO
import httpx
from PIL import Image

def transcribe(data,filename,mime='application/octet-stream'):
    base=os.getenv('SPEECH_BASE_URL','').rstrip('/')
    if not base.startswith('https://') or not os.getenv('SPEECH_API_KEY') or not os.getenv('STT_MODEL'):
        raise ValueError('Speech transcription is not configured. Upload a text transcript or type your answer.')
    response=httpx.post(base+'/audio/transcriptions',headers={'Authorization':'Bearer '+os.environ['SPEECH_API_KEY']},files={'file':(filename,data,mime)},data={'model':os.environ['STT_MODEL'],'response_format':'json'},timeout=60)
    response.raise_for_status();text=response.json().get('text')
    if not isinstance(text,str) or not text.strip() or len(text)>200000:raise ValueError('Invalid or empty transcription.')
    return [('Transcript (timestamps not supplied)',text.strip())]
def image_ocr(data):
    if not shutil.which('tesseract'):raise ValueError('Install Tesseract OCR or upload extracted text.')
    with Image.open(BytesIO(data)) as image:
        if image.width*image.height>20_000_000:raise ValueError('Image limit is 20 megapixels.')
        image.load()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'input.png';image.convert('RGB').save(path)
            result=subprocess.run(['tesseract',str(path),'stdout','-l',os.getenv('OCR_LANGUAGE','eng')],capture_output=True,timeout=25,check=True)
    text=result.stdout.decode('utf-8').strip()
    if not text:raise ValueError('OCR found no readable text. Try a clearer image or type a transcript.')
    return [('Image OCR (verify recognition)',text)]
def video_transcript(data,suffix):
    if not shutil.which('ffmpeg'):raise ValueError('Video requires FFmpeg and a configured STT provider. Upload a transcript instead.')
    with tempfile.TemporaryDirectory() as directory:
        source=Path(directory)/('input'+suffix);target=Path(directory)/'audio.wav';source.write_bytes(data)
        # Uploaded containers cannot open remote playlists or arbitrary protocols.
        subprocess.run(['ffmpeg','-nostdin','-v','error','-protocol_whitelist','file,pipe','-i',str(source),'-t','300','-vn','-ac','1','-ar','16000',str(target)],capture_output=True,check=True,timeout=45)
        return [(location+'; first 5 minutes only',text) for location,text in transcribe(target.read_bytes(),'audio.wav','audio/wav')]
