from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from app.db import get_db
from app.auth.security import current_user,course_access,audit,throttle
from app.models import Chunk,Resource,Topic
from app.schemas import Input
from app.services.materials import MaterialScope,resolve,validate_citations
from app.ai.grounded import Concept,StructureDraft,structure
from app.knowledge_graph.engine import validate_dag
router=APIRouter(prefix='/api/courses')
class Policy(Input):material_only:bool
@router.put('/{cid}/material-policy')
def policy(cid:int,data:Policy,user=Depends(current_user),db=Depends(get_db)):
    c=course_access(db,user,cid,True);c.material_only=data.material_only;audit(db,user,'material policy changed',cid);db.commit();return {'material_only':c.material_only}
@router.get('/{cid}/material-catalog')
def catalog(cid:int,user=Depends(current_user),db=Depends(get_db)):
    c=course_access(db,user,cid)
    rows=db.execute(select(Chunk,Resource).join(Resource,Resource.id==Chunk.resource_id).where(Resource.course_id==cid,Resource.owner_id.is_(None))).all()
    return {'material_only':c.material_only,'resources':[{'id':r.id,'filename':r.filename,'chunks':[{'id':ch.id,'location':ch.location,'structure':ch.structure or {}} for ch,rr in rows if rr.id==r.id]} for r in {r.id:r for ch,r in rows}.values()],
            'topics':[{'id':t.id,'name':t.name,'clo':t.clo,'structure':t.structure or {}} for t in db.scalars(select(Topic).where(Topic.course_id==cid))]}
@router.post('/{cid}/material-query')
def query(cid:int,data:MaterialScope,user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid);return resolve(db,cid,data)
class LocationEdit(Input):
    book:str=''
    unit:str=''
    chapter:str=''
    section:str=''
    page:int|None=None
@router.put('/{cid}/chunks/{chunk_id}/location')
def location(cid:int,chunk_id:int,data:LocationEdit,user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid,True);chunk=db.get(Chunk,chunk_id);r=db.get(Resource,chunk.resource_id) if chunk else None
    if not r or r.course_id!=cid or r.owner_id is not None:raise HTTPException(404,'Course excerpt not found.')
    chunk.structure=data.model_dump();audit(db,user,'source location corrected',chunk_id);db.commit();return {'ok':True}
@router.post('/{cid}/structure/extract')
async def extract_structure(cid:int,data:MaterialScope,user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid,True);throttle(db,'structure:'+str(user.id),15);evidence=resolve(db,cid,data)
    try:draft,status=await structure(evidence)
    except Exception as exc:raise HTTPException(502,'Structure generation failed validation. Narrow the scope or retry; no curriculum was changed.')
    return {'draft':draft.model_dump(),'status':status,'sources':evidence,'covered_chunks':len(evidence),'review_required':True}
@router.post('/{cid}/structure/approve')
def approve(cid:int,data:StructureDraft,user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid,True)
    ids=list({c.chunk_id for t in data.topics for c in t.citations});sources=resolve(db,cid,MaterialScope(chunk_ids=ids))
    topics=db.scalars(select(Topic).where(Topic.course_id==cid)).all();mapping={t.name.casefold():t for t in topics};new=[]
    if len({t.name.casefold() for t in data.topics})!=len(data.topics):raise HTTPException(422,'Duplicate topic names.')
    for t in data.topics:
        try:validate_citations(t.citations,sources)
        except ValueError as exc:raise HTTPException(422,str(exc))
        if t.name.casefold() in mapping:raise HTTPException(409,'A topic already exists. Rename the proposed topic or remove it from this draft.')
        row=Topic(course_id=cid,name=t.name,description=t.description,clo=t.clo,difficulty=t.difficulty,prerequisites=[],structure={**t.model_dump(exclude={'name','description','clo','difficulty','prerequisites'}),'source_ids':[c.chunk_id for c in t.citations]})
        db.add(row);db.flush();mapping[t.name.casefold()]=row;new.append(row)
    for t,row in zip(data.topics,new):
        if any(p.casefold() not in mapping for p in t.prerequisites):db.rollback();raise HTTPException(422,'Unknown prerequisite. Edit the proposed relationship before approving.')
        row.prerequisites=[mapping[p.casefold()].id for p in t.prerequisites]
    try:validate_dag(list(mapping.values()))
    except ValueError as exc:db.rollback();raise HTTPException(422,str(exc))
    audit(db,user,'material structure approved',cid);db.commit();return {'created':len(new)}

@router.put('/{cid}/topics/{tid}/structure')
def update_structure(cid:int,tid:int,data:Concept,user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid,True);topic=db.get(Topic,tid)
    if not topic or topic.course_id!=cid:raise HTTPException(404,'Topic not found.')
    sources=resolve(db,cid,MaterialScope(chunk_ids=[c.chunk_id for c in data.citations]))
    try:validate_citations(data.citations,sources)
    except ValueError as exc:raise HTTPException(422,str(exc))
    topics=list(db.scalars(select(Topic).where(Topic.course_id==cid)))
    names={t.name.casefold():t.id for t in topics if t.id!=tid}
    if data.name.casefold() in names:raise HTTPException(409,'Another topic uses this name.')
    names[data.name.casefold()]=tid
    if any(p.casefold() not in names for p in data.prerequisites):raise HTTPException(422,'Unknown prerequisite name.')
    topic.name=data.name;topic.description=data.description;topic.clo=data.clo;topic.difficulty=data.difficulty;topic.prerequisites=[names[p.casefold()] for p in data.prerequisites]
    topic.structure={**data.model_dump(exclude={'name','description','clo','difficulty','prerequisites'}),'source_ids':[c.chunk_id for c in data.citations]}
    try:validate_dag(topics)
    except ValueError as exc:db.rollback();raise HTTPException(422,str(exc))
    audit(db,user,'source-linked topic edited',tid);db.commit();return {'ok':True}
