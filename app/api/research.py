from time import perf_counter
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from app.db import get_db
from app.auth.security import current_user,course_access
from app.models import Answer,Question,Topic,VivaSession,VivaTurn
from app.ai.retrieval import LexicalStore
from app.schemas import Input
from pydantic import Field
router=APIRouter(prefix='/api/courses')
class RetrievalCase(Input):
    query:str=Field(min_length=2,max_length=1000)
    relevant_chunk_ids:list[int]=Field(min_length=1,max_length=100)
    k:int=Field(default=4,ge=1,le=20)
@router.post('/{cid}/research/retrieval')
def evaluate_retrieval(cid:int,data:RetrievalCase,user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid,True)
    from app.models import Chunk,Resource
    valid=set(db.scalars(select(Chunk.id).join(Resource,Resource.id==Chunk.resource_id).where(Resource.course_id==cid,Resource.owner_id.is_(None))))
    if not set(data.relevant_chunk_ids)<=valid:raise HTTPException(422,'All relevance labels must reference chunks of this course material.')
    started=perf_counter();result=LexicalStore().search(db,user,cid,data.query,k=data.k);latency=(perf_counter()-started)*1000
    relevant=set(data.relevant_chunk_ids);returned={r['id'] for r in result};hits=len(relevant&returned)
    return {'precision_at_k':hits/data.k,'recall_at_k':hits/len(relevant),'latency_ms':round(latency,2),'k':data.k,'results':result,'methodology':'Teacher-provided relevant chunk labels, local lexical retrieval. Missing result slots count against precision. One query is not a generalization benchmark.'}
@router.get('/{cid}/research')
def research(cid:int,user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid,True)
    rows=db.scalars(select(Answer).join(Question,Question.id==Answer.question_id).where(Question.course_id==cid)).all()
    questions=db.scalars(select(Question).where(Question.course_id==cid)).all()
    generated=[q for q in questions if q.source.startswith('AI GENERATED')]
    deltas=[a.mastery_after-a.mastery_before for a in rows]
    turns=db.scalars(select(VivaTurn).join(VivaSession,VivaSession.id==VivaTurn.session_id).where(VivaSession.course_id==cid)).all()
    matched=[t for t in turns if t.proposed_score is not None and t.reviewed_score is not None]
    return {'observations':len(rows),'mean_mastery_change_pp':round(100*sum(deltas)/len(deltas),2) if deltas else None,
            'generated_questions':len(generated),'current_approval_rate':round(100*sum(q.approved for q in generated)/len(generated),1) if generated else None,
            'reviewed_ai_viva_pairs':len(matched),'viva_mean_absolute_error':round(sum(abs(t.proposed_score-t.reviewed_score) for t in matched)/len(matched),2) if matched else None,
            'methodology':'Descriptive metrics from saved course evidence. Mastery change is a model update, not proof of learning or a causal remediation effect. Current approval rate is not a historical approval experiment. Viva error compares AI proposals to teacher scores only where both exist.'}
