"""JSON-line bridge for DOM integration QA: real FastAPI/SQLite, no network server."""
import json,os,sys,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root));os.chdir(root)
with tempfile.TemporaryDirectory(prefix='campuspath-ui-') as tmp:
    os.environ['DATABASE_URL']='sqlite:///'+str(Path(tmp)/'ui.db');os.environ['DEMO_MODE']='true'
    from alembic import command
    from alembic.config import Config
    command.upgrade(Config(str(root/'alembic.ini')),'head')
    from scripts.seed_demo import seed
    from app.db import SessionLocal
    with SessionLocal() as db:seed(db)
    from fastapi.testclient import TestClient
    from app.main import app
    clients={}
    for line in sys.stdin:
        try:
            req=json.loads(line);client=clients.setdefault(req['client'],TestClient(app,raise_server_exceptions=False))
            response=client.request(req.get('method','GET'),req['url'],headers=req.get('headers',{}),content=req.get('body'))
            try:body=response.json()
            except ValueError:body={'raw':response.text}
            print(json.dumps({'id':req['id'],'status':response.status_code,'data':body}),flush=True)
        except Exception as exc:print(json.dumps({'id':req.get('id'),'error':type(exc).__name__+': '+str(exc)}),flush=True)
