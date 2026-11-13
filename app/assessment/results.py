from collections import defaultdict
from app.assessment.feedback import teaching_feedback
from sqlalchemy import select
from app.models import Answer,Question,Topic,now

def results(db,run):
    records={a.question_id:a for a in db.scalars(select(Answer).where(Answer.run_id==run.id))}
    questions=[db.get(Question,qid) for qid in run.question_ids];total=len(questions)
    correct=sum(a.correct for a in records.values());marks=(run.settings or {}).get('total_marks',100)
    topics=defaultdict(list);clos=defaultdict(list);blooms=defaultdict(list);details=[]
    for q in questions:
        t=db.get(Topic,q.topic_id);a=records.get(q.id);value=bool(a and a.correct)
        topics[t.name].append(value);clos[t.clo].append(value);blooms[q.bloom].append(value)
        details.append({'id':q.id,'prompt':q.prompt,'correct':value,'answered':a is not None,'your_answer':q.options[a.selected] if a else None,'correct_answer':q.options[q.correct],'explanation':teaching_feedback(db,q,a.selected if a else None),'topic':t.name,'clo':t.clo,'bloom':q.bloom,'seconds':a.response_seconds if a else None,'hint_used':bool(a and a.hint_used)})
    aggregate=lambda x:{k:round(sum(v)/len(v)*100) for k,v in x.items()}
    return {'id':run.id,'complete':True,'score':round(100*correct/total) if total else 0,'marks':round(marks*correct/total,2) if total else 0,'total_marks':marks,'total':total,'answered':len(records),'unanswered':total-len(records),'mode':run.mode,'topic_results':aggregate(topics),'clo_results':aggregate(clos),'bloom_results':aggregate(blooms),'details':details,'time_used_seconds':round(sum(a.response_seconds or 0 for a in records.values()),1)}
