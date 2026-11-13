import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from fastapi.testclient import TestClient
from app.main import app
out={}
for email in ['saim@campuspath.demo','teacher@campuspath.demo','admin@campuspath.demo']:
 c=TestClient(app)
 login=c.post('/api/auth/login',json={'email':email,'password':'CampusPath-Demo!2026'}).json();c.headers['X-CSRF-Token']=login['csrf'];role=login['user']['role']
 paths=['/api/health','/api/auth/me','/api/courses','/api/notifications']
 if role!='admin':paths+=['/api/courses/1/topics','/api/courses/1/resources','/api/courses/1/assignments','/api/algorithm/A*']
 if role=='student':paths+=['/api/courses/1/students/2/progress','/api/courses/1/planner','/api/courses/1/assessments','/api/courses/1/viva/history']
 if role=='teacher':paths+=['/api/courses/1/students','/api/courses/1/questions','/api/courses/1/analytics','/api/courses/1/viva/review','/api/courses/1/research']
 if role=='admin':paths+=['/api/admin/overview','/api/admin/system','/api/admin/assignments']
 out[role]={p:c.get(p).json() for p in paths}
Path(__file__).with_name('fixtures.json').write_text(json.dumps(out))
