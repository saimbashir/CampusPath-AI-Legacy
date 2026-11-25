import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
ROOT = Path(__file__).resolve().parent.parent
DATABASE_URL = os.getenv('DATABASE_URL', '').strip() or 'sqlite:///' + str(ROOT / 'campuspath.db')
for prefix in ('postgres://', 'postgresql://'):
    if DATABASE_URL.startswith(prefix):
        DATABASE_URL = 'postgresql+psycopg://' + DATABASE_URL[len(prefix):]
        break
DEMO_MODE = os.getenv('DEMO_MODE', 'true').lower() == 'true'
COOKIE_SECURE = os.getenv('COOKIE_SECURE', 'false').lower() == 'true'
SESSION_HOURS = 8
MAX_UPLOAD = max(1,min(64,int(os.getenv('MAX_UPLOAD_MIB','8')))) * 1024 * 1024
MAX_PDF_PAGES=max(1,min(2000,int(os.getenv('MAX_PDF_PAGES','1200'))))
MAX_EXTRACTED_CHARS=max(10000,min(10_000_000,int(os.getenv('MAX_EXTRACTED_CHARS','5000000'))))
