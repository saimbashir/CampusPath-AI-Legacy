from urllib.parse import quote
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import Response
from app.db import get_db
from app.auth.security import current_user,course_access,audit
from app.models import Resource,ResourceBlob,Submission,Assignment
router=APIRouter(prefix='/api')
def attachment_response(db,r):
    blob=db.get(ResourceBlob,r.id)
    if not blob:raise HTTPException(404,'Original file is unavailable for this older resource. Re-upload it if needed.')
    return Response(blob.data,media_type='application/octet-stream',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(r.filename,safe='')})
@router.get('/courses/{cid}/resources/{rid}/download')
def download(cid:int,rid:int,user=Depends(current_user),db=Depends(get_db)):
    course_access(db,user,cid);r=db.get(Resource,rid)
    if not r or r.course_id!=cid or r.owner_id not in (None,user.id):raise HTTPException(404,'Resource not found.')
    return attachment_response(db,r)
@router.get('/submissions/{sid}/attachment')
def submission_attachment(sid:int,user=Depends(current_user),db=Depends(get_db)):
    s=db.get(Submission,sid);a=db.get(Assignment,s.assignment_id) if s else None
    if not a or not s.resource_id:raise HTTPException(404,'Attachment not found.')
    course_access(db,user,a.course_id,teacher=user.role!='student')
    if user.role=='student' and s.student_id!=user.id:raise HTTPException(404,'Attachment not found.')
    r=db.get(Resource,s.resource_id)
    audit(db,user,'assignment attachment viewed',sid);db.commit();return attachment_response(db,r)
