"""Subject-independent scope resolution and source metadata. No subject-specific templates."""
import re
from sqlalchemy import select
from fastapi import HTTPException
from app.models import Chunk,Resource,Topic
from app.schemas import Input
from pydantic import Field
class MaterialScope(Input):
    resource_ids:list[int]=Field(default_factory=list,max_length=100)
    chunk_ids:list[int]=Field(default_factory=list,max_length=300)
    topic_ids:list[int]=Field(default_factory=list,max_length=100)
    chapters:list[str]=Field(default_factory=list,max_length=100)
    units:list[str]=Field(default_factory=list,max_length=100)
    sections:list[str]=Field(default_factory=list,max_length=100)
    clos:list[str]=Field(default_factory=list,max_length=40)
    page_from:int|None=Field(default=None,ge=1)
    page_to:int|None=Field(default=None,ge=1)

def annotated(parts,filename):
    state={'book':filename}
    for location,text in parts:
        page=re.match(r'Page (\d+)',location);state['page']=int(page[1]) if page else None
        segments=[];current=[]
        for line in text.splitlines():
            title=line.strip().lstrip('#').strip()
            match=re.match(r'^(chapter|unit|section)\s+([\w.\-]+)(?:\s*[:—\-]?\s*)(.*)$',title,re.I)
            if match:
                if current:segments.append((dict(state),'\n'.join(current)));current=[]
                kind=match[1].lower();state[kind]=match[2];state[kind+'_title']=title
                if kind in ('unit','chapter'):
                    state.pop('section',None);state.pop('section_title',None)
                if kind=='unit':state.pop('chapter',None);state.pop('chapter_title',None)
            current.append(line)
        if current:segments.append((dict(state),'\n'.join(current)))
        for meta,body in segments:
            if body.strip():yield location,body.strip(),meta

def resolve(db,cid,scope,limit=300):
    """All selectors combine by intersection; omitted selectors mean all teacher material."""
    if isinstance(scope,dict):scope=MaterialScope.model_validate(scope)
    rows=db.execute(select(Chunk,Resource).join(Resource,Resource.id==Chunk.resource_id).where(Resource.course_id==cid,Resource.owner_id.is_(None)).order_by(Resource.id,Chunk.id)).all()
    valid_resources={r.id for c,r in rows};valid_chunks={c.id for c,r in rows}
    if not set(scope.resource_ids)<=valid_resources or not set(scope.chunk_ids)<=valid_chunks:raise HTTPException(422,'Scope contains inaccessible or unindexed teacher material.')
    topics=db.scalars(select(Topic).where(Topic.course_id==cid)).all()
    if not set(scope.topic_ids)<={t.id for t in topics}:raise HTTPException(422,'Topics must belong to this course.')
    selected=[t for t in topics if (not scope.topic_ids or t.id in scope.topic_ids) and (not scope.clos or t.clo in scope.clos)]
    if scope.topic_ids or scope.clos:
        source_ids=set(i for t in selected for i in (t.structure or {}).get('source_ids',[]))
        if not source_ids:raise HTTPException(422,'Selected topics/CLOs need source links. Extract the digital twin or edit the topic source mapping first.')
    else:source_ids=None
    result=[]
    for c,r in rows:
        m=c.structure or {}
        if scope.resource_ids and r.id not in scope.resource_ids:continue
        if scope.chunk_ids and c.id not in scope.chunk_ids:continue
        if source_ids is not None and c.id not in source_ids:continue
        if any(values and str(m.get(key,'')) not in values for key,values in [('chapter',scope.chapters),('unit',scope.units),('section',scope.sections)]):continue
        if scope.page_from and (not m.get('page') or m['page']<scope.page_from):continue
        if scope.page_to and (not m.get('page') or m['page']>scope.page_to):continue
        result.append({'id':c.id,'resource_id':r.id,'filename':r.filename,'location':c.location,'text':c.text,'structure':m})
    if not result:raise HTTPException(409,'The provided course material does not contain enough information to answer this confidently. No excerpts match the selected scope.')
    if len(result)>limit:raise HTTPException(422,f'Scope contains {len(result)} excerpts; select a chapter or documents with at most {limit} excerpts for this operation.')
    return result

def validate_citations(citations,evidence):
    mapping={s['id']:s for s in evidence}
    if not citations:raise ValueError('At least one source citation is required.')
    for c in citations:
        c=c.model_dump() if hasattr(c,'model_dump') else c
        if c['chunk_id'] not in mapping:raise ValueError('Citation falls outside selected material.')
        normalized=lambda s:' '.join(s.split()).casefold()
        if len(c['quote'].strip())<8 or normalized(c['quote']) not in normalized(mapping[c['chunk_id']]['text']):raise ValueError('Evidence quotation is not present in the cited source.')
    return [mapping[c.chunk_id if hasattr(c,'chunk_id') else c['chunk_id']] for c in citations]
