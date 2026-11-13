from datetime import timedelta
from sqlalchemy import select, delete, update
from fastapi import HTTPException
from app.models import Topic,Mastery,Answer,Question,Misconception,Revision,VivaTurn,VivaSession,StudyTask,StudyPlan,QuizRun,now
from app.mastery.engine import confidence,revision_dates,update_mastery
from app.knowledge_graph.engine import learning_order

def snapshot(db,student_id,course_id):
    topics=db.scalars(select(Topic).where(Topic.course_id==course_id)).all()
    states={m.topic_id:m for m in db.scalars(select(Mastery).join(Topic,Mastery.topic_id==Topic.id).where(Mastery.student_id==student_id,Topic.course_id==course_id))}
    answers=db.scalars(select(Answer).join(Question,Answer.question_id==Question.id).where(Answer.student_id==student_id,Question.course_id==course_id).order_by(Answer.created)).all()
    p={t.id:states[t.id].probability if t.id in states else .2 for t in topics}
    average=sum(p.values())/len(p) if p else 0
    coverage=sum(m.attempts>0 for m in states.values())/len(topics) if topics else 0
    accuracy=sum(a.correct for a in answers)/len(answers) if answers else 0
    from app.services.readiness import calculate
    readiness_detail=calculate(db,student_id,course_id,p,states,answers)
    readiness=readiness_detail['score']
    trend=round(100*sum(a.mastery_after-a.mastery_before for a in answers[-10:])/len(answers[-10:]),1) if answers else None
    clo={}
    topic_data=[]
    for t in topics:
        state=states.get(t.id);attempts=state.attempts if state else 0
        clo.setdefault(t.clo,[]).append(p[t.id])
        topic_data.append({'id':t.id,'name':t.name,'description':t.description,'prerequisites':t.prerequisites,'clo':t.clo,'mastery':round(100*p[t.id]),'attempts':attempts,'confidence':confidence(attempts),'last_practiced':state.last_practiced if state else None})
    order=learning_order(topics,p)
    path=[{'id':t.id,'name':t.name,'why':f'{round(p[t.id]*100)}% estimated mastery. '+('A prerequisite for later topics; revise before dependent concepts.' if any(t.id in (other.prerequisites or []) for other in topics) else 'Practice and recheck understanding.'),'confidence':confidence(states[t.id].attempts) if t.id in states else 0} for t in order]
    misconceptions=db.scalars(select(Misconception).join(Topic,Misconception.topic_id==Topic.id).where(Misconception.student_id==student_id,Topic.course_id==course_id).order_by(Misconception.created.desc()).limit(30)).all()
    revisions=db.scalars(select(Revision).join(Topic,Revision.topic_id==Topic.id).where(Revision.student_id==student_id,Topic.course_id==course_id,Revision.done.is_(False)).order_by(Revision.due)).all()
    status='HIGH PERFORMING' if average>=.85 and accuracy>=.8 and coverage>=.7 else 'PROFICIENT' if average>=.7 and coverage>=.5 else 'NEEDS SUPPORT' if answers and (average<.4 or accuracy<.4) else 'DEVELOPING'
    result={'mastery':round(average*100),'readiness':readiness,'readiness_factors':{'mastery_weight':.6,'coverage_weight':.2,'accuracy_weight':.2,'coverage':round(100*coverage),'accuracy':round(100*accuracy)},'quiz_average':round(100*accuracy) if answers else None,'attempts':len(answers),'trend':trend,'status':status,'topics':topic_data,'path':path,'clos':{k:round(100*sum(v)/len(v)) for k,v in clo.items()},'misconceptions':[{'topic_id':m.topic_id,'evidence':m.evidence,'created':m.created} for m in misconceptions],'revisions':[{'id':r.id,'topic_id':r.topic_id,'due':r.due} for r in revisions],'history':[{'created':a.created,'mastery':round(a.mastery_after*100),'topic_id':db.get(Question,a.question_id).topic_id} for a in answers[-30:]]}
    reviewed=db.scalars(select(VivaTurn).join(VivaSession,VivaSession.id==VivaTurn.session_id).where(VivaSession.student_id==student_id,VivaSession.course_id==course_id,VivaTurn.reviewed_score.is_not(None))).all()
    result['readiness_detail']=readiness_detail
    result['readiness_factors']={'components':readiness_detail['factors'],'coverage':round(100*coverage),'accuracy':round(100*accuracy),'methodology':readiness_detail['methodology']}
    from app.models import OralReview,OralSession,VivaExam,VivaQuestion
    formal=db.execute(select(OralReview,VivaQuestion).join(OralSession,OralSession.id==OralReview.session_id).join(VivaExam,VivaExam.id==OralSession.viva_id).join(VivaQuestion,VivaQuestion.id==OralReview.question_id).where(OralSession.student_id==student_id,VivaExam.course_id==course_id,OralSession.status=='FINALIZED',OralReview.finalized.is_(True))).all()
    totals={}
    for r,q in formal:
        earned,possible=totals.get(r.session_id,(0,0));totals[r.session_id]=(earned+r.marks,possible+q.marks)
    formal_percent=[100*earned/possible for earned,possible in totals.values() if possible]
    result['viva_average']=round(sum(t.reviewed_score for t in reviewed)/len(reviewed),1) if reviewed else None
    if formal_percent:
        values=[t.reviewed_score for t in reviewed]+formal_percent
        result['viva_average']=round(sum(values)/len(values),1)
    result['viva_reviewed_count']=len(reviewed)+len(formal)
    completed_tasks=db.scalars(select(StudyTask).join(StudyPlan,StudyPlan.id==StudyTask.plan_id).where(StudyPlan.student_id==student_id,StudyPlan.course_id==course_id,StudyTask.status=='done')).all()
    activity_dates={a.created.date() for a in answers}|{t.completed.date() for t in completed_tasks if t.completed}
    day=now().date();streak=0
    if day not in activity_dates:day-=timedelta(days=1)
    while day in activity_dates:streak+=1;day-=timedelta(days=1)
    result['study_streak']=streak
    result['bloom']={}
    grouped={}
    for a in answers:grouped.setdefault(db.get(Question,a.question_id).bloom,[]).append(a.correct)
    result['bloom']={k:round(100*sum(v)/len(v)) for k,v in grouped.items()}
    result['revision_completion']={'done':len(db.scalars(select(Revision.id).join(Topic,Topic.id==Revision.topic_id).where(Revision.student_id==student_id,Topic.course_id==course_id,Revision.done.is_(True))).all()),'pending':len(revisions)}
    return result

def observe(db,user,question,correct,run,selected):
    state=db.scalar(select(Mastery).where(Mastery.student_id==user.id,Mastery.topic_id==question.topic_id))
    if not state:
        state=Mastery(student_id=user.id,topic_id=question.topic_id,probability=.2,attempts=0,correct=0);db.add(state)
    db.flush()
    before=state.probability
    recent=db.scalars(select(Answer.id).where(Answer.student_id==user.id,Answer.question_id==question.id,Answer.created>now()-timedelta(days=1))).all()
    hint_used=question.id in (run.hint_ids or [])
    weight=max(.15,1/(1+len(recent)))*(.35 if hint_used and correct else 1)
    raw=update_mastery(before,correct,question.difficulty,guess=1/len(question.options))
    posterior=before+weight*(raw-before)
    history=db.execute(select(Answer,Question).join(Question,Answer.question_id==Question.id).where(Answer.student_id==user.id,Question.topic_id==question.topic_id)).all()
    distinct={q.id for a,q in history}|{question.id}
    sessions={a.run_id for a,q in history}|{run.id}
    days={a.created.date() for a,q in history}|{now().date()}
    # High mastery requires breadth plus reassessment on another day.
    ceiling=.79 if len(distinct)<12 or len(sessions)<3 else .89 if len(days)<2 else .97
    if posterior>before:posterior=min(posterior,max(before,ceiling))
    result=db.execute(update(Mastery).where(Mastery.id==state.id,Mastery.attempts==state.attempts,Mastery.probability==before).values(probability=posterior,attempts=Mastery.attempts+1,correct=Mastery.correct+int(correct),last_practiced=now()))
    if result.rowcount!=1:
        db.rollback()
        raise HTTPException(409,'Your progress changed in another session. Retry this answer.')
    db.refresh(state)
    db.add(Answer(run_id=run.id,question_id=question.id,student_id=user.id,selected=selected,correct=correct,mastery_before=before,mastery_after=state.probability,response_seconds=max(0,(now()-(run.question_started or run.created)).total_seconds()),hint_used=hint_used,evidence_weight=weight))
    if not correct:
        db.add(Misconception(student_id=user.id,topic_id=question.topic_id,evidence='Possible misconception: '+(question.misconception or 'Review the concept and explain your reasoning.')+' Selected: '+question.options[selected]))
    db.execute(delete(Revision).where(Revision.student_id==user.id,Revision.topic_id==question.topic_id,Revision.done.is_(False)))
    for due in revision_dates(now(),state.probability):db.add(Revision(student_id=user.id,topic_id=question.topic_id,due=due))
    if before<.8<=state.probability:
        from app.services.notifications import notify
        notify(db,user.id,question.course_id,f'mastery:{question.topic_id}:{state.attempts}','Mastery milestone',f'Your estimated mastery of {db.get(Topic,question.topic_id).name} has reached 80%. Keep checking retention.','analytics')
    return {'evidence_weight':round(weight,2),'before':round(before*100),'after':round(state.probability*100),'confidence':confidence(state.attempts)}
