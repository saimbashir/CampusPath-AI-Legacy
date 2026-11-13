"""Safe local setup and launch. Does not reset an existing database."""
import argparse,os,sys,sqlite3,shutil
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent

def prepare(backup=False):
    os.chdir(ROOT)
    if not (ROOT/'.env').exists():shutil.copyfile(ROOT/'.env.example',ROOT/'.env')
    from app.config import DEMO_MODE,DATABASE_URL
    from app.db import engine,SessionLocal
    from sqlalchemy import text,select
    from alembic.config import Config
    from alembic import command
    from alembic.migration import MigrationContext
    from alembic.script import ScriptDirectory
    config=Config(str(ROOT/'alembic.ini'));config.set_main_option('script_location',str(ROOT/'migrations'))
    with engine.connect() as connection:current=MigrationContext.configure(connection).get_current_revision()
    head=ScriptDirectory.from_config(config).get_current_head()
    if engine.dialect.name=='sqlite' and engine.url.database and engine.url.database!=':memory:':
        path=Path(engine.url.database)
        with sqlite3.connect(path) as source:
            if source.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise RuntimeError('Database integrity check failed. Restore a verified backup before continuing.')
            # A snapshot of real data precedes any schema change. Backups can also be requested explicitly.
            if backup or (current and current!=head):
                folder=ROOT/'backups';folder.mkdir(exist_ok=True)
                target=folder/('campuspath-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.db')
                with sqlite3.connect(target) as dest:source.backup(dest)
                if os.name!='nt':target.chmod(0o600)
                print('Backup saved:',target.name)
    elif current and current!=head:
        print('External database: take an operator-managed backup before production schema upgrades.')
    command.upgrade(config,'head')
    with SessionLocal() as db:
        from app.models import User
        if DEMO_MODE:
            # Do not introduce demo accounts into a populated real-user database.
            count=db.scalar(select(User.id).limit(1));existing=db.scalar(select(User.id).where(User.email=='saim@campuspath.demo'))
            if not count or existing:
                from scripts.seed_demo import seed
                seed(db)
            else:print('Existing non-demo accounts detected; sample data was not inserted.')
        db.execute(text('SELECT 1'))
    if engine.dialect.name=='sqlite':
        with engine.connect() as c:
            if c.exec_driver_sql('PRAGMA foreign_key_check').fetchone():raise RuntimeError('Database relationship check failed; contact the administrator.')
    print('Database ready. Schema:',head)
    print('Mode:', 'local demonstration' if DEMO_MODE else 'live / teacher-authored')
    for label,names in [('LLM',('LLM_BASE_URL','LLM_API_KEY','LLM_MODEL')),('speech input',('SPEECH_BASE_URL','SPEECH_API_KEY','STT_MODEL')),('speech output',('SPEECH_BASE_URL','SPEECH_API_KEY','TTS_MODEL','TTS_VOICE'))]:
        print(label+':', 'configured (not connectivity-tested)' if all(os.getenv(n) for n in names) else 'not configured; fallback available')
    print('OCR:', 'available' if shutil.which('tesseract') else 'optional Tesseract not installed')
    if DEMO_MODE:print('Local demo login: saim@campuspath.demo / CampusPath-Demo!2026')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true',help='Set up/check the database and exit without launching a server');parser.add_argument('--backup',action='store_true',help='Make an additional SQLite backup');parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8000)
    args=parser.parse_args()
    if not 1<=args.port<=65535:parser.error('Port must be between 1 and 65535.')
    try:
        prepare(args.backup)
        if args.check:return 0
        import socket,uvicorn
        with socket.socket() as check:check.bind((args.host,args.port))
        print(f'Open http://{args.host}:{args.port} in your browser. Keep this terminal open; Ctrl+C stops the app.')
        uvicorn.run('app.main:app',host=args.host,port=args.port,workers=1,proxy_headers=False,log_level='info')
        return 0
    except ImportError as exc:
        print('A required package is missing. Run: python -m pip install -r requirements.lock.txt',file=sys.stderr);return 1
    except OSError as exc:
        print('Unable to open the database, files, or server port. Check folder permissions and whether the selected port is in use. Try --port 8001 for a busy port.',file=sys.stderr);return 1
    except Exception as exc:
        print(f'Setup stopped ({type(exc).__name__}). Your existing database was not reset. Check .env, migration setup and backup availability. Run the verification instructions in docs/deployment.md.',file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
