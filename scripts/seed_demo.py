import sys,random
from io import BytesIO
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select
from datetime import timedelta
from app.config import DEMO_MODE,ROOT
from app.db import SessionLocal
from app.models import User,Course,Enrollment,Topic,Mastery,Question,Resource,ResourceBlob,Chunk,Assignment,now
from app.auth.security import hasher
from app.documents.extract import extract
from sample_data.course import TOPICS,QUESTIONS

def seed(db):
    if db.scalar(select(User.id).where(User.email=='saim@campuspath.demo')):
        course=db.scalar(select(Course).where(Course.enrollment_code=='AI-FALL26-DEMO'))
        if course:
            from sample_data.expanded_bank import extend_demo
            topics=db.scalars(select(Topic).where(Topic.course_id==course.id).order_by(Topic.id)).all()
            if len(topics)==len(TOPICS) and all(t.name==expected[0] for t,expected in zip(topics,TOPICS)):
                extend_demo(db,course,topics);db.commit()
        return
    users=[]
    for name,uid,email,role in [('Faculty Demo','FAC-001','teacher@campuspath.demo','teacher'),('Saim Bashir','23F-1234','saim@campuspath.demo','student'),('Ahmed Khan','23F-4123','ahmed@campuspath.demo','student'),('Ayesha Ali','23F-2056','ayesha@campuspath.demo','student'),('Demo Administrator','ADMIN-DEMO','admin@campuspath.demo','admin')]:
        u=User(name=name,university_id=uid,email=email,role=role,password=hasher.hash('CampusPath-Demo!2026'),profile={'department':'Computing','program':'BS Software Engineering','semester':'5','campus':'Lahore','synthetic_demo':True});db.add(u);db.flush();users.append(u)
    c=Course(teacher_id=users[0].id,name='Artificial Intelligence',code='CS-301',section='A',semester='Fall 2026',description='Search, knowledge and intelligent decision-making. Synthetic demonstration course.',clos=['CLO-1: Explain agents','CLO-2: Apply uninformed search','CLO-3: Compare heuristic search','CLO-4: Apply minimax'],enrollment_code='AI-FALL26-DEMO');db.add(c);db.flush()
    for u in users[1:4]:db.add(Enrollment(course_id=c.id,student_id=u.id))
    topics=[]
    for name,desc,parents,clo in TOPICS:
        t=Topic(course_id=c.id,name=name,description=desc,prerequisites=[topics[i].id for i in parents],clo=clo);db.add(t);db.flush();topics.append(t)
    rng=random.Random(42)
    for idx,(tid,prompt,options,correct,explanation,misconception) in enumerate(QUESTIONS):
        pairs=list(enumerate(options));rng.shuffle(pairs)
        db.add(Question(course_id=c.id,topic_id=topics[tid].id,prompt=prompt,options=[v for _,v in pairs],correct=next(i for i,(old,_) in enumerate(pairs) if old==correct),explanation=explanation,misconception=misconception,difficulty=idx%3+1,bloom=['Remember','Understand','Apply'][idx%3],approved=True,source='CampusPath sample course; faculty-authored demo bank'))
    priors=[[.72,.90,.85,.64,.48,.52,.39,.30],[.50,.65,.55,.45,.39,.35,.34,.25],[.92,.93,.87,.84,.81,.80,.82,.76]]
    for u,values in zip(users[1:4],priors):
        for t,p in zip(topics,values):db.add(Mastery(student_id=u.id,topic_id=t.id,probability=p,attempts=0,correct=0))
    # A real sample slide deck makes 'Slide 18' a verifiable location.
    from pptx import Presentation
    ppt=Presentation()
    for i in range(18):
        slide=ppt.slides.add_slide(ppt.slide_layouts[1])
        topic=TOPICS[6] if i==17 else (TOPICS[:6]+TOPICS[7:])[i%7]
        slide.shapes.title.text=f'{topic[0]} — Course notes'
        slide.placeholders[1].text=topic[1]
    # Each seed owns its bytes; concurrent database setups must not rewrite a shared ZIP.
    buffer=BytesIO();ppt.save(buffer);deck=buffer.getvalue()
    r=Resource(course_id=c.id,filename='Lecture_6.pptx',owner_id=None,kind='COURSE MATERIAL');db.add(r);db.flush()
    db.add(ResourceBlob(resource_id=r.id,data=deck,content_type='application/octet-stream'))
    for loc,text in extract('Lecture_6.pptx',deck):db.add(Chunk(resource_id=r.id,location=loc,text=text))
    db.add(Assignment(course_id=c.id,title='Compare A* and Greedy',instructions='Use a weighted graph to explain why Greedy and A* can choose different nodes. Include g, h and f calculations.',rubric='Concept correctness 40%; worked example 40%; clarity 20%.',due=now()+timedelta(days=14)))
    from sample_data.expanded_bank import extend_demo
    extend_demo(db,c,topics)
    db.commit()
if __name__=='__main__':
    if not DEMO_MODE:raise SystemExit('Demo seed is disabled unless DEMO_MODE=true.')
    with SessionLocal() as db:seed(db)
    print('Demo ready. Login: saim@campuspath.demo or teacher@campuspath.demo; password: CampusPath-Demo!2026. Local demo only.')
