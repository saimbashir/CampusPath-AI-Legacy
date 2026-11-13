"""Transparent descriptive readiness, not a validated prediction of an exam grade."""
from datetime import timedelta
from sqlalchemy import select
from app.models import QuizRun,Answer,now

def calculate(db,student_id,course_id,probabilities,states,answers):
    n=len(probabilities)
    mastery=sum(probabilities.values())/n if n else 0
    coverage=sum(m.attempts>0 for m in states.values())/n if n else 0
    accuracy=sum(a.correct for a in answers)/len(answers) if answers else None
    recent_mocks=db.scalars(select(QuizRun).where(QuizRun.student_id==student_id,QuizRun.course_id==course_id,QuizRun.mode=='mock').order_by(QuizRun.created.desc())).all()
    complete=[r for r in recent_mocks if r.finished or r.cursor>=len(r.question_ids) or r.expires<now()][:3]
    mock_scores=[]
    for run in complete:
        correct=sum(db.scalars(select(Answer.correct).where(Answer.run_id==run.id)))
        if run.question_ids:mock_scores.append(correct/len(run.question_ids))
    mock=sum(mock_scores)/len(mock_scores) if mock_scores else None
    secure=sum(tid in states and states[tid].attempts>0 and p>=.6 for tid,p in probabilities.items())/n if n else 0
    recency=sum(max(0,1-max(0,(now()-m.last_practiced).total_seconds()/86400)/30) for m in states.values() if m.last_practiced and m.attempts>0)/n if n else 0
    parts=[('mastery','Estimated concept mastery',.40,mastery),('coverage','Topics with assessment evidence',.15,coverage),('accuracy','Recorded MCQ accuracy',.15,accuracy),('mock','Last three completed mock exams',.15,mock),('secure','Assessed topics at 60%+ mastery',.10,secure),('recency','Recent assessed practice (30-day decay)',.05,recency)]
    factors=[{'key':key,'label':label,'weight':weight,'value':round(value*100,1) if value is not None else None,'contribution':round(weight*(value or 0)*100,2)} for key,label,weight,value in parts]
    score=round(sum(weight*(value or 0)*100 for _,_,weight,value in parts))
    return {'score':score,'factors':factors,'missing_evidence':[label for _,label,_,value in parts if value is None],
            'methodology':'A planning indicator, not a predicted grade. Fixed weights sum to 100%; unavailable evidence contributes zero, not an invented assessment score. Practice recency decays over 30 days. Self-marked study/revision completion does not increase readiness. Parameters are uncalibrated; synthetic demo priors are not measured mastery.'}
