import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Chunk
from app.ai.vector import enabled,QdrantStore
if not enabled():raise SystemExit('Configure embedding and Qdrant settings first.')
with SessionLocal() as db:
    chunks=db.scalars(select(Chunk)).all();QdrantStore().index(chunks);print(f'Indexed {len(chunks)} chunks. Configure a separate collection for each database/environment.')
