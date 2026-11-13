from datetime import timedelta
import csv,io,secrets
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select,update
from app.db import get_db
from app.models import User,Enrollment,Course,Topic,Assignment,Submission,Note,Audit,TeacherKey,Resource,ResourceBlob,VivaTurn,VivaSession,now
from app.schemas import AssignmentInput,TextInput,GradeInput,SubmissionInput
from app.auth.security import current_user,role,course_access,student_access,audit
from app.services.learning import snapshot
router=APIRouter(prefix='/api')
@router.get('/courses/{cid}/students')
def students(cid:int,q:str='',user=Depends(current_user),db=Depends(get_db)):
    course=course_access(db,user,cid,True)
    users=db.scalars(select(User).join(Enrollment,Enrollment.student_id==User.id).where(Enrollment.course_id==cid)).all()
    result=[]
    for student in users:
        if q.lower() not in (student.name+' '+student.university_id+' '+student.email).lower():continue
        state=snapshot(db,student.id,cid)
        grades=db.scalars(select(Submission.grade).join(Assignment,Submission.assignment_id==Assignment.id).where(Assignment.course_id==cid,Submission.student_id==student.id,Submission.grade.is_not(None))).all()
        result.append({'id':student.id,'name':student.name,'university_id':student.university_id,'email':student.email,'section':course.section,'mastery':state['mastery'],'quiz_average':state['quiz_average'],'assignment_average':round(sum(grades)/len(grades)) if grades else None,'viva_average':state.get('viva_average'),'readiness':state['readiness'],'trend':state['trend'],'status':state['status'],'weakest_topic':min(state['topics'],key=lambda t:t['mastery'])['name'] if state['topics'] else None})
    audit(db,user,'student directory viewed',cid);db.commit();return result
@router.get('/courses/{cid}/analytics')
def analytics(cid:int,user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid,True)
    ids=db.scalars(select(Enrollment.student_id).where(Enrollment.course_id==cid)).all()
    states=[snapshot(db,sid,cid) for sid in ids]
    topics=db.scalars(select(Topic).where(Topic.course_id==cid)).all()
    from app.models import Answer,Question
    answers=db.execute(select(Answer,Question).join(Question,Question.id==Answer.question_id).where(Question.course_id==cid)).all()
    bloom={}
    for a,q in answers:bloom.setdefault(q.bloom,[]).append(a.correct)
    return {'students':len(ids),'mastery':round(sum(s['mastery'] for s in states)/len(states)) if states else None,'support_count':sum(s['status']=='NEEDS SUPPORT' for s in states),'topics':[{'id':t.id,'name':t.name,'mastery':round(sum(next((v['mastery'] for v in s['topics'] if v['id']==t.id),20) for s in states)/len(states)) if states else None} for t in topics],'clos':{clo:round(sum(s['clos'].get(clo,0) for s in states)/len(states)) for clo in {t.clo for t in topics}} if states else {},'bloom':{k:round(100*sum(v)/len(v)) for k,v in bloom.items()},'misconceptions':[m for s in states for m in s['misconceptions']],'methodology':'Mastery is a model estimate. Bloom uses submitted question accuracy; CLO uses topic mastery. Empty evidence is shown as unavailable.'}
@router.post('/courses/{cid}/copilot')
def copilot(cid:int,data:TextInput,user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid,True)
    rows=students(cid,'',user,db)
    text=data.text.lower()
    topics=db.scalars(select(Topic).where(Topic.course_id==cid)).all()
    matches=[t for t in topics if t.name.lower() in text]
    target=matches[0] if matches else None
    affected=[]
    for r in rows:
        state=snapshot(db,r['id'],cid)
        weak=[t for t in state['topics'] if t['mastery']<60 and (target is None or t['id']==target.id)]
        if weak:affected.append({'name':r['name'],'university_id':r['university_id'],'evidence':[f"{t['name']}: {t['mastery']}% estimated mastery" for t in weak]})
    title=target.name if target else 'the weakest concepts'
    activity=f'15-minute activity for {title}: 3 minutes recall prerequisites; 4 minutes model a worked example; 4 minutes guided practice; 3 minutes independent check; 1 minute collect exit tickets.'
    return {'answer':f'{len(affected)} enrolled students have estimated mastery below 60% for '+title+'.','students':affected,'activity':activity,'status':'Deterministic course-data copilot. Activity is a teaching template, not LLM generation.'}
@router.get('/courses/{cid}/students/{sid}/notes')
def notes(cid:int,sid:int,user=Depends(current_user),db=Depends(get_db)):
    role(user,'teacher');student_access(db,user,cid,sid)
    rows=db.scalars(select(Note).where(Note.course_id==cid,Note.student_id==sid,Note.teacher_id==user.id)).all();db.commit()
    return [{'id':n.id,'text':n.text} for n in rows]
@router.post('/courses/{cid}/students/{sid}/notes')
def note(cid:int,sid:int,data:TextInput,user=Depends(current_user),db=Depends(get_db)):
    role(user,'teacher');student_access(db,user,cid,sid)
    db.add(Note(course_id=cid,student_id=sid,teacher_id=user.id,text=data.text));audit(db,user,'teacher note added',f'{cid}:{sid}');db.commit();return {'ok':True}
@router.get('/courses/{cid}/assignments')
def assignments(cid:int,user=Depends(current_user),db=Depends(get_db)):
    course=course_access(db,user,cid)
    result=[]
    for a in db.scalars(select(Assignment).where(Assignment.course_id==cid)):
        if user.role=='student' and course.material_only and not a.source_ids:continue
        query=select(Submission).where(Submission.assignment_id==a.id)
        if user.role=='student':query=query.where(Submission.student_id==user.id)
        submissions=db.scalars(query).all()
        result.append({'id':a.id,'title':a.title,'instructions':a.instructions,'rubric':a.rubric,'source_ids':a.source_ids or [],'due':a.due,'submissions':[{'id':s.id,'student_id':s.student_id,'name':db.get(User,s.student_id).name,'university_id':db.get(User,s.student_id).university_id,'text':s.text,'grade':s.grade,'feedback':s.feedback,'resource_id':s.resource_id,'attachment_filename':db.get(Resource,s.resource_id).filename if s.resource_id else None} for s in submissions]})
    return result
@router.post('/courses/{cid}/assignments',status_code=201)
def assignment(cid:int,data:AssignmentInput,user=Depends(current_user),db=Depends(get_db)):
    course=course_access(db,user,cid,True)
    if course.material_only and not data.source_ids:raise HTTPException(422,'Link assignment instructions to teacher source chunks in material-only mode.')
    if data.source_ids:
        from app.services.materials import resolve,MaterialScope
        resolve(db,cid,MaterialScope(chunk_ids=data.source_ids))
    from app.services.planning import utc_naive
    values=data.model_dump();values['due']=utc_naive(values['due'])
    a=Assignment(course_id=cid,**values);db.add(a);db.commit();return {'id':a.id}
@router.post('/assignments/{aid}/submit')
def submit(aid:int,data:SubmissionInput,user=Depends(current_user),db=Depends(get_db)):
    role(user,'student');a=db.get(Assignment,aid)
    if not a:raise HTTPException(404,'Assignment not found.')
    course=course_access(db,user,a.course_id)
    if course.material_only and not a.source_ids:raise HTTPException(409,'This assignment needs teacher source links under the current material policy.')
    if now()>a.due:raise HTTPException(409,'The submission deadline has passed.')
    if data.resource_id:
        r=db.get(Resource,data.resource_id)
        if not r or r.owner_id!=user.id or r.course_id!=a.course_id or not db.get(ResourceBlob,r.id):raise HTTPException(422,'Attach one of your uploaded resources from this course.')
    s=db.scalar(select(Submission).where(Submission.assignment_id==aid,Submission.student_id==user.id))
    if s and s.grade is not None:raise HTTPException(409,'Graded work cannot be overwritten.')
    if not s:
        s=Submission(assignment_id=aid,student_id=user.id,text=data.text,resource_id=data.resource_id);db.add(s)
    else:
        changed=db.execute(update(Submission).where(Submission.id==s.id,Submission.grade.is_(None)).values(text=data.text,created=now(),resource_id=data.resource_id))
        if changed.rowcount!=1:db.rollback();raise HTTPException(409,'Your teacher has graded this work. Refresh to view feedback.')
    db.commit();return {'ok':True}
@router.post('/submissions/{sid}/grade')
def grade(sid:int,data:GradeInput,user=Depends(current_user),db=Depends(get_db)):
    s=db.get(Submission,sid)
    if not s:raise HTTPException(404,'Submission not found.')
    a=db.get(Assignment,s.assignment_id);course_access(db,user,a.course_id,True)
    s.grade=data.grade;s.feedback=data.feedback;audit(db,user,'marks changed',sid)
    from app.services.notifications import notify
    notify(db,s.student_id,a.course_id,f'grade:{sid}:{data.grade}','Assignment graded',a.title+' has teacher feedback.','assignments')
    db.commit();return {'ok':True}
@router.get('/courses/{cid}/report.csv')
def report(cid:int,user=Depends(current_user),db=Depends(get_db)):
    rows=students(cid,'',user,db)
    stream=io.StringIO();writer=csv.writer(stream)
    keys=['name','university_id','section','mastery','quiz_average','assignment_average','readiness','status']
    writer.writerow(keys)
    def safe(v):
        s='' if v is None else str(v)
        return "'"+s if s.lstrip().startswith(('=','+','-','@')) or s.startswith(('\t','\r')) else s
    for row in rows:writer.writerow([safe(row[k]) for k in keys])
    audit(db,user,'report exported',cid);db.commit()
    return Response(stream.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename=campuspath-report.csv'})
@router.get('/admin/overview')
def admin_overview(user=Depends(current_user),db=Depends(get_db)):
    role(user,'admin')
    return {'users':[{'id':u.id,'name':u.name,'role':u.role,'university_id':u.university_id,'active':u.active} for u in db.scalars(select(User))],'keys':[{'id':k.id,'expires':k.expires,'revoked':k.revoked,'uses':k.uses,'limit':k.limit,'created_by':k.created_by} for k in db.scalars(select(TeacherKey))],'audit':[{'action':a.action,'actor_id':a.actor_id,'target':a.target,'created':a.created} for a in db.scalars(select(Audit).order_by(Audit.created.desc()).limit(100))]}
@router.post('/admin/keys/{kid}/revoke')
def revoke(kid:int,user=Depends(current_user),db=Depends(get_db)):
    role(user,'admin');k=db.get(TeacherKey,kid)
    if not k:raise HTTPException(404,'Invite not found.')
    k.revoked=True;audit(db,user,'teacher key revoked',kid);db.commit();return {'ok':True}
