"""Small, reproducible retrieval benchmark. Does not claim research generalization."""
import sys,json,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select
from app.db import SessionLocal
from app.models import User,Course,Chunk,Resource
from app.ai.retrieval import LexicalStore
QUERIES=[('What does A* use for its priority?','A* selects'),('What structure does BFS use?','Breadth-first search expands'),('Explain minimax and the opponent','Minimax chooses')]
with SessionLocal() as db:
    user=db.scalar(select(User).where(User.email=='saim@campuspath.demo'))
    if not user:raise SystemExit('Seed the demo first.')
    course=db.scalar(select(Course).where(Course.code=='CS-301'))
    chunks=db.scalars(select(Chunk).join(Resource,Resource.id==Chunk.resource_id).where(Resource.course_id==course.id,Resource.owner_id.is_(None))).all()
    results=[]
    for question,label in QUERIES:
        relevant={c.id for c in chunks if label in c.text}
        start=time.perf_counter();found=LexicalStore().search(db,user,course.id,question,k=4);latency=(time.perf_counter()-start)*1000
        hits=len(relevant & {c['id'] for c in found})
        results.append({'query':question,'precision_at_4':hits/4,'recall_at_4':hits/len(relevant) if relevant else None,'latency_ms':round(latency,2),'relevant_count':len(relevant),'returned_count':len(found)})
    print(json.dumps({'methodology':'Three sample-course queries; relevance labels by exact subject passage, k=4. This is a tiny sanity benchmark, not a held-out educational evaluation. Missing results count against precision.','results':results},indent=2))
