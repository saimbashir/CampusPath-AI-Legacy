from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, ForeignKey, DateTime, JSON, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase
class Base(DeclarativeBase):
    pass

def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String(254), unique=True, nullable=False)
    name = Column(String(120), nullable=False)
    university_id = Column(String(80), unique=True, nullable=False)
    password = Column(Text, nullable=False)
    role = Column(String(12), nullable=False)
    profile = Column(JSON, default=dict)
    active = Column(Boolean, default=True, nullable=False)
    created = Column(DateTime, default=now)
class Session(Base):
    __tablename__ = 'sessions'
    digest = Column(String(64), primary_key=True)
    user_id = Column(ForeignKey('users.id'), nullable=False)
    csrf = Column(String(64), nullable=False)
    expires = Column(DateTime, nullable=False)
class TeacherKey(Base):
    __tablename__ = 'teacher_keys'
    id = Column(Integer, primary_key=True)
    digest = Column(String(64), unique=True, nullable=False)
    created_by = Column(ForeignKey('users.id'), nullable=False)
    created = Column(DateTime, default=now)
    expires = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False)
    limit = Column(Integer, default=1)
    uses = Column(Integer, default=0)
class ResetToken(Base):
    __tablename__ = 'reset_tokens'
    digest = Column(String(64), primary_key=True)
    user_id = Column(ForeignKey('users.id'), nullable=False)
    expires = Column(DateTime, nullable=False)
class LoginThrottle(Base):
    __tablename__ = 'login_throttle'
    key = Column(String(64), primary_key=True)
    count = Column(Integer, default=0)
    until = Column(DateTime, nullable=False)
class Course(Base):
    __tablename__ = 'courses'
    id = Column(Integer, primary_key=True)
    teacher_id = Column(ForeignKey('users.id'), nullable=False)
    name = Column(String(140), nullable=False)
    code = Column(String(40), nullable=False)
    section = Column(String(40), nullable=False)
    semester = Column(String(40), default='')
    description = Column(Text, default='')
    clos = Column(JSON, default=list)
    enrollment_code = Column(String(40), unique=True, nullable=False)
class Enrollment(Base):
    __tablename__ = 'enrollments'
    id = Column(Integer, primary_key=True)
    course_id = Column(ForeignKey('courses.id'), nullable=False)
    student_id = Column(ForeignKey('users.id'), nullable=False)
    __table_args__ = (UniqueConstraint('course_id', 'student_id'),)
class Topic(Base):
    __tablename__ = 'topics'
    id = Column(Integer, primary_key=True)
    course_id = Column(ForeignKey('courses.id'), nullable=False)
    name = Column(String(140), nullable=False)
    description = Column(Text, default='')
    prerequisites = Column(JSON, default=list)
    clo = Column(String(40), default='CLO-1')
    difficulty = Column(Integer, default=1)
class Resource(Base):
    __tablename__ = 'resources'
    id = Column(Integer, primary_key=True)
    course_id = Column(ForeignKey('courses.id'), nullable=False)
    owner_id = Column(ForeignKey('users.id'), nullable=True)
    filename = Column(String(200), nullable=False)
    kind = Column(String(30), nullable=False)
    created = Column(DateTime, default=now)
class Chunk(Base):
    __tablename__ = 'chunks'
    id = Column(Integer, primary_key=True)
    resource_id = Column(ForeignKey('resources.id'), nullable=False)
    location = Column(String(80), nullable=False)
    text = Column(Text, nullable=False)
class Question(Base):
    __tablename__ = 'questions'
    id = Column(Integer, primary_key=True)
    course_id = Column(ForeignKey('courses.id'), nullable=False)
    topic_id = Column(ForeignKey('topics.id'), nullable=False)
    prompt = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)
    correct = Column(Integer, nullable=False)
    explanation = Column(Text, nullable=False)
    misconception = Column(Text, default='')
    difficulty = Column(Integer, default=1)
    bloom = Column(String(40), default='Understand')
    approved = Column(Boolean, default=False)
    source = Column(String(200), default='Teacher authored')
class QuizRun(Base):
    __tablename__ = 'quiz_runs'
    id = Column(Integer, primary_key=True)
    student_id = Column(ForeignKey('users.id'), nullable=False)
    course_id = Column(ForeignKey('courses.id'), nullable=False)
    mode = Column(String(20), default='adaptive')
    settings = Column(JSON, default=dict)
    finished = Column(Boolean, default=False, nullable=False)
    hint_ids = Column(JSON, default=list)
    question_started = Column(DateTime, default=now)
    question_ids = Column(JSON, default=list)
    cursor = Column(Integer, default=0)
    difficulty = Column(Integer, default=1)
    created = Column(DateTime, default=now)
    expires = Column(DateTime, nullable=False)
class Answer(Base):
    __tablename__ = 'answers'
    id = Column(Integer, primary_key=True)
    run_id = Column(ForeignKey('quiz_runs.id'), nullable=False)
    question_id = Column(ForeignKey('questions.id'), nullable=False)
    student_id = Column(ForeignKey('users.id'), nullable=False)
    selected = Column(Integer, nullable=False)
    response_seconds = Column(Float, default=0)
    hint_used = Column(Boolean, default=False)
    evidence_weight = Column(Float, default=1)
    correct = Column(Boolean, nullable=False)
    mastery_before = Column(Float, nullable=False)
    mastery_after = Column(Float, nullable=False)
    created = Column(DateTime, default=now)
    __table_args__ = (UniqueConstraint('run_id', 'question_id'),)
class Mastery(Base):
    __tablename__ = 'mastery'
    id = Column(Integer, primary_key=True)
    student_id = Column(ForeignKey('users.id'), nullable=False)
    topic_id = Column(ForeignKey('topics.id'), nullable=False)
    probability = Column(Float, default=0.2)
    attempts = Column(Integer, default=0)
    correct = Column(Integer, default=0)
    last_practiced = Column(DateTime, nullable=True)
    __table_args__ = (UniqueConstraint('student_id', 'topic_id'),)
class Misconception(Base):
    __tablename__ = 'misconceptions'
    id = Column(Integer, primary_key=True)
    student_id = Column(ForeignKey('users.id'), nullable=False)
    topic_id = Column(ForeignKey('topics.id'), nullable=False)
    evidence = Column(Text, nullable=False)
    created = Column(DateTime, default=now)
class Revision(Base):
    __tablename__ = 'revisions'
    id = Column(Integer, primary_key=True)
    student_id = Column(ForeignKey('users.id'), nullable=False)
    topic_id = Column(ForeignKey('topics.id'), nullable=False)
    due = Column(DateTime, nullable=False)
    done = Column(Boolean, default=False)
class Assignment(Base):
    __tablename__ = 'assignments'
    id = Column(Integer, primary_key=True)
    course_id = Column(ForeignKey('courses.id'), nullable=False)
    title = Column(String(160), nullable=False)
    instructions = Column(Text, nullable=False)
    rubric = Column(Text, nullable=False)
    due = Column(DateTime, nullable=False)
class Submission(Base):
    __tablename__ = 'submissions'
    id = Column(Integer, primary_key=True)
    assignment_id = Column(ForeignKey('assignments.id'), nullable=False)
    resource_id = Column(ForeignKey('resources.id'), nullable=True)
    student_id = Column(ForeignKey('users.id'), nullable=False)
    text = Column(Text, nullable=False)
    grade = Column(Float, nullable=True)
    feedback = Column(Text, default='')
    created = Column(DateTime, default=now)
    __table_args__ = (UniqueConstraint('assignment_id','student_id'),)
class Note(Base):
    __tablename__ = 'notes'
    id = Column(Integer, primary_key=True)
    teacher_id = Column(ForeignKey('users.id'), nullable=False)
    student_id = Column(ForeignKey('users.id'), nullable=False)
    course_id = Column(ForeignKey('courses.id'), nullable=False)
    text = Column(Text, nullable=False)
class Conversation(Base):
    __tablename__ = 'conversations'
    id = Column(Integer, primary_key=True)
    student_id = Column(ForeignKey('users.id'), nullable=False)
    course_id = Column(ForeignKey('courses.id'), nullable=False)
    mode = Column(String(20), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    created = Column(DateTime, default=now)
class Audit(Base):
    __tablename__ = 'audit'
    id = Column(Integer, primary_key=True)
    actor_id = Column(ForeignKey('users.id'), nullable=False)
    action = Column(String(60), nullable=False)
    target = Column(String(100), nullable=False)
    created = Column(DateTime, default=now)

# Release 0.2 additions. Existing tables are upgraded by migration 0002.
class StudyPlan(Base):
    __tablename__ = 'study_plans'
    id = Column(Integer, primary_key=True)
    student_id = Column(ForeignKey('users.id'), nullable=False)
    course_id = Column(ForeignKey('courses.id'), nullable=False)
    exam_date = Column(DateTime, nullable=False)
    daily_minutes = Column(Integer, nullable=False)
    free_days = Column(JSON, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created = Column(DateTime, default=now)
class StudyTask(Base):
    __tablename__ = 'study_tasks'
    id = Column(Integer, primary_key=True)
    plan_id = Column(ForeignKey('study_plans.id'), nullable=False)
    topic_id = Column(ForeignKey('topics.id'), nullable=False)
    scheduled = Column(DateTime, nullable=False)
    minutes = Column(Integer, nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String(20), default='planned', nullable=False)
    completed = Column(DateTime, nullable=True)
class Notification(Base):
    __tablename__ = 'notifications'
    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey('users.id'), nullable=False)
    course_id = Column(ForeignKey('courses.id'), nullable=True)
    event_key = Column(String(180), nullable=False)
    title = Column(String(180), nullable=False)
    message = Column(Text, nullable=False)
    target = Column(String(30), default='dashboard', nullable=False)
    read = Column(Boolean, default=False, nullable=False)
    created = Column(DateTime, default=now)
    __table_args__ = (UniqueConstraint('user_id','event_key'),)
class ResourceBlob(Base):
    __tablename__ = 'resource_blobs'
    resource_id = Column(ForeignKey('resources.id'), primary_key=True)
    data = Column(__import__('sqlalchemy').LargeBinary, nullable=False)
    content_type = Column(String(100), default='application/octet-stream')
class TeacherAssignment(Base):
    __tablename__ = 'teacher_assignments'
    id = Column(Integer, primary_key=True)
    course_id = Column(ForeignKey('courses.id'), nullable=False)
    teacher_id = Column(ForeignKey('users.id'), nullable=False)
    assigned_by = Column(ForeignKey('users.id'), nullable=False)
    __table_args__ = (UniqueConstraint('course_id','teacher_id'),)
class VivaSession(Base):
    __tablename__ = 'viva_sessions'
    id = Column(Integer, primary_key=True)
    student_id = Column(ForeignKey('users.id'), nullable=False)
    course_id = Column(ForeignKey('courses.id'), nullable=False)
    topic_ids = Column(JSON, nullable=False)
    cursor = Column(Integer, default=0, nullable=False)
    created = Column(DateTime, default=now)
    expires = Column(DateTime, nullable=False)
class VivaTurn(Base):
    __tablename__ = 'viva_turns'
    id = Column(Integer, primary_key=True)
    session_id = Column(ForeignKey('viva_sessions.id'), nullable=False)
    turn_index = Column(Integer, nullable=False)
    topic_id = Column(ForeignKey('topics.id'), nullable=False)
    prompt = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    evaluation = Column(JSON, nullable=False)
    provider = Column(String(40), nullable=False)
    proposed_score = Column(Float, nullable=True)
    reviewed_score = Column(Float, nullable=True)
    teacher_feedback = Column(Text, default='')
    reviewed_by = Column(ForeignKey('users.id'), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    mastery_before = Column(Float, nullable=True)
    mastery_after = Column(Float, nullable=True)
    created = Column(DateTime, default=now)
    __table_args__ = (UniqueConstraint('session_id','turn_index'),)

metadata = Base.metadata
