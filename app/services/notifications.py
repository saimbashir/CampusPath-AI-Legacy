from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from datetime import timedelta
from app.models import Notification,Enrollment,Revision,Topic,Assignment,Submission,Question,Course,now
from app.auth.security import teacher_courses

def notify(db,uid,cid,key,title,message,target):
    if db.scalar(select(Notification.id).where(Notification.user_id==uid,Notification.event_key==key)):return
    try:
        with db.begin_nested():db.add(Notification(user_id=uid,course_id=cid,event_key=key,title=title,message=message,target=target))
    except IntegrityError:pass

def refresh(db,user):
    if user.role=='student':
        cids=list(db.scalars(select(Enrollment.course_id).where(Enrollment.student_id==user.id)))
        due=db.execute(select(Revision,Topic).join(Topic,Revision.topic_id==Topic.id).where(Revision.student_id==user.id,Topic.course_id.in_(cids),Revision.done.is_(False),Revision.due<=now()+timedelta(days=1))).all()
        for r,t in due:notify(db,user.id,t.course_id,f'review:{r.id}:{r.due.isoformat()}',f'Review {t.name}','A scheduled revision is due within one day or is overdue.','planner')
        for a in db.scalars(select(Assignment).where(Assignment.course_id.in_(cids),Assignment.due<=now()+timedelta(days=3),Assignment.due>=now())):
            if not db.scalar(select(Submission.id).where(Submission.assignment_id==a.id,Submission.student_id==user.id)):
                notify(db,user.id,a.course_id,f'assignment:{a.id}','Assignment due soon',f'{a.title} is due {a.due.date().isoformat()}.','assignments')
    elif user.role=='teacher':
        for q in db.scalars(select(Question).where(Question.course_id.in_(teacher_courses(user)),Question.approved.is_(False))):
            notify(db,user.id,q.course_id,f'question:{q.id}','Question awaiting review',q.prompt[:180],'questions')
        from app.models import VivaSession,VivaTurn
        for turn,session in db.execute(select(VivaTurn,VivaSession).join(VivaSession,VivaSession.id==VivaTurn.session_id).where(VivaSession.course_id.in_(teacher_courses(user)),VivaTurn.reviewed_at.is_(None))):
            notify(db,user.id,session.course_id,f'viva:{turn.id}','Viva response awaiting review','Review the transcript and rubric before confirming the score.','viva-review')
        from app.models import OralSession,VivaExam
        for session,exam in db.execute(select(OralSession,VivaExam).join(VivaExam,VivaExam.id==OralSession.viva_id).where(VivaExam.course_id.in_(teacher_courses(user)),OralSession.status=='TEACHER_REVIEW_REQUIRED')):
            notify(db,user.id,exam.course_id,f'oral-review:{session.id}','Viva ready for marking',exam.title+' has a submitted session awaiting confirmation.','oral-review')
    db.commit()
