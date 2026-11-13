from datetime import datetime,time,timedelta,timezone
from sqlalchemy import select
from fastapi import HTTPException
from app.models import StudyPlan,StudyTask,Topic,now
from app.services.learning import snapshot

def utc_naive(value):
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value

def serialize_plan(db,plan):
    if not plan:return {'id':None,'days':[],'message':'Create a study plan to save your schedule.'}
    groups={}
    tasks=db.scalars(select(StudyTask).where(StudyTask.plan_id==plan.id).order_by(StudyTask.scheduled,StudyTask.id)).all()
    for t in tasks:
        groups.setdefault(t.scheduled.date().isoformat(),[]).append({'id':t.id,'topic_id':t.topic_id,'topic':db.get(Topic,t.topic_id).name,'minutes':t.minutes,'why':t.reason,'status':t.status,'overdue':t.status=='planned' and t.scheduled.date()<now().date()})
    return {'id':plan.id,'exam_date':plan.exam_date,'daily_minutes':plan.daily_minutes,'free_days':plan.free_days,'days':[{'date':d,'activities':a} for d,a in groups.items()],'message':'Saved plan. Complete tasks as you study; move missed work into available time before the exam. Dates use UTC.'}

def create_plan(db,user,cid,data):
    end=utc_naive(data.exam_date)
    if end.date()<now().date() or end>now()+timedelta(days=365):raise HTTPException(422,'Choose an exam date within the next year.')
    progress=snapshot(db,user.id,cid);path=progress['path'] or [{'id':t['id'],'name':t['name'],'why':'Retention check for a previously mastered concept.'} for t in progress['topics']]
    if not path:raise HTTPException(409,'Your teacher needs to add course topics first.')
    for old in db.scalars(select(StudyPlan).where(StudyPlan.student_id==user.id,StudyPlan.course_id==cid,StudyPlan.active.is_(True))):old.active=False
    plan=StudyPlan(student_id=user.id,course_id=cid,exam_date=end,daily_minutes=round(data.hours*60),free_days=data.free_days,active=True)
    db.add(plan);db.flush();day=now().date();index=0
    while day<=end.date():
        if day.weekday() in data.free_days:
            budget=plan.daily_minutes
            while budget>0:
                minutes=min(30,budget);topic=path[index%len(path)];index+=1;budget-=minutes
                db.add(StudyTask(plan_id=plan.id,topic_id=topic['id'],scheduled=datetime.combine(day,time(12)),minutes=minutes,reason=topic['why'],status='planned'))
        day+=timedelta(days=1)
    db.flush()
    if not db.scalar(select(StudyTask.id).where(StudyTask.plan_id==plan.id)):
        db.rollback();raise HTTPException(422,'No selected study day falls before the exam. Choose another weekday or date.')
    db.commit();return serialize_plan(db,plan)

def reschedule(db,plan):
    """Preserve completed work and move backlog without increasing daily time budgets."""
    today=now().date();tasks=db.scalars(select(StudyTask).where(StudyTask.plan_id==plan.id).order_by(StudyTask.scheduled,StudyTask.id)).all()
    movable=[t for t in tasks if t.status in ('planned','skipped','unscheduled')]
    completed=[t for t in tasks if t.status=='done'];capacities={};day=today
    while day<=plan.exam_date.date():
        if day.weekday() in plan.free_days:capacities[day]=max(0,plan.daily_minutes-sum(t.minutes for t in completed if t.scheduled.date()==day))
        day+=timedelta(days=1)
    placed=0;unscheduled=0
    for task in movable:
        destination=next((d for d,capacity in capacities.items() if capacity>=task.minutes),None)
        if destination is None:
            task.status='unscheduled';unscheduled+=1
        else:
            task.scheduled=datetime.combine(destination,time(12));task.status='planned';capacities[destination]-=task.minutes;placed+=1
    db.commit();result=serialize_plan(db,plan)
    result['message']=f'Rescheduled {placed} tasks within your daily budget. {unscheduled} tasks could not fit before the exam; increase available time or regenerate a shorter plan.'
    result['unscheduled']=unscheduled
    return result
