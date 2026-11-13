from typing import Literal
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
class Login(Input):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)
class Register(Login):
    name: str = Field(min_length=2,max_length=120)
    university_id: str = Field(min_length=2,max_length=80)
    password: str = Field(min_length=12,max_length=128)
    confirm_password: str
    role: Literal['student','teacher'] = 'student'
    teacher_key: str = Field(default='',max_length=200)
    department: str = Field(default='',max_length=100)
    program: str = Field(default='',max_length=100)
    semester: str = Field(default='',max_length=30)
    campus: str = Field(default='',max_length=100)
    designation: str = Field(default='',max_length=100)
    @field_validator('email')
    @classmethod
    def valid_email(cls,v):
        import re
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', v):
            raise ValueError('Enter a valid email address')
        return v.lower()
    @model_validator(mode='after')
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError('Passwords do not match')
        return self
class CourseInput(Input):
    name: str = Field(min_length=2,max_length=140)
    code: str = Field(min_length=2,max_length=40)
    section: str = Field(min_length=1,max_length=40)
    semester: str = Field(default='',max_length=40)
    description: str = Field(default='',max_length=4000)
    clos: list[str] = Field(default_factory=list,max_length=20)
class TopicInput(Input):
    name: str = Field(min_length=1,max_length=140)
    description: str = Field(default='',max_length=6000)
    prerequisites: list[int] = Field(default_factory=list,max_length=40)
    clo: str = Field(default='CLO-1',max_length=40)
    difficulty: int = Field(default=1,ge=1,le=3)
class QuestionInput(Input):
    source_ids:list[int]=Field(default_factory=list,max_length=20)
    topic_id: int
    prompt: str = Field(min_length=8,max_length=4000)
    options: list[str] = Field(min_length=2,max_length=6)
    correct: int = Field(ge=0,le=5)
    explanation: str = Field(min_length=3,max_length=4000)
    misconception: str = Field(default='',max_length=1000)
    difficulty: int = Field(default=1,ge=1,le=3)
    bloom: Literal['Remember','Understand','Apply','Analyze','Evaluate','Create'] = 'Understand'
    source: str = Field(default='Teacher authored',max_length=200)
    @model_validator(mode='after')
    def validate_options(self):
        if self.correct >= len(self.options) or len(set(self.options)) != len(self.options) or any(not s.strip() or len(s)>1000 for s in self.options):
            raise ValueError('Distinct nonempty options and a valid answer index required')
        return self
class TutorInput(Input):
    question: str = Field(min_length=2,max_length=4000)
    resource_ids:list[int]=Field(default_factory=list,max_length=100)
    chapters:list[str]=Field(default_factory=list,max_length=100)
    page_from:int|None=Field(default=None,ge=1)
    page_to:int|None=Field(default=None,ge=1)
    mode: Literal['Simple English','Detailed','Roman Urdu','Step-by-step','Analogy','Worked Example','Code Example','Exam Focus','Socratic Mode'] = 'Simple English'
class StartQuiz(Input):
    mode: Literal['adaptive','diagnostic','mock'] = 'adaptive'
    topic_id: int | None = None
    count: int = Field(default=8,ge=1,le=30)
    total_marks:int=Field(default=100,ge=1,le=1000)
    topic_ids:list[int]=Field(default_factory=list,max_length=40)
    difficulty:int|None=Field(default=None,ge=1,le=3)
    bloom_distribution:dict[str,int]=Field(default_factory=dict)
    clo_distribution:dict[str,int]=Field(default_factory=dict)
    minutes: int = Field(default=20,ge=1,le=120)
class AnswerInput(Input):
    question_id: int
    selected: int = Field(ge=0,le=5)
class TextInput(Input):
    text: str = Field(min_length=1,max_length=12000)
class CodeInput(Input):
    code: str = Field(min_length=3,max_length=80)
class AssignmentInput(Input):
    source_ids:list[int]=Field(default_factory=list,max_length=30)
    title: str = Field(min_length=3,max_length=160)
    instructions: str = Field(min_length=3,max_length=8000)
    rubric: str = Field(min_length=3,max_length=4000)
    due: datetime
class GradeInput(Input):
    grade: float = Field(ge=0,le=100)
    feedback: str = Field(default='',max_length=4000)
class PlanInput(Input):
    exam_date: datetime
    hours: float = Field(ge=0.25,le=12)
    free_days: list[int] = Field(default_factory=lambda:list(range(7)),min_length=1,max_length=7)
    @field_validator('free_days')
    @classmethod
    def days(cls,v):
        if any(x<0 or x>6 for x in v): raise ValueError('Days must be 0 Monday through 6 Sunday')
        return sorted(set(v))
class ProfileInput(Input):
    mode: str = Field(max_length=50)
class ResetInput(Input):
    token: str = Field(min_length=20,max_length=200)
    password: str = Field(min_length=12,max_length=128)
class EmailInput(Input):
    email: str = Field(max_length=254)

class SubmissionInput(Input):
    text:str=Field(default='',max_length=12000)
    resource_id:int|None=None
    @model_validator(mode='after')
    def nonempty(self):
        if not self.text and self.resource_id is None:raise ValueError('Write an answer or attach a resource.')
        return self
class ProfileUpdate(Input):
    name:str=Field(min_length=2,max_length=120)
    department:str=Field(default='',max_length=100)
    program:str=Field(default='',max_length=100)
    semester:str=Field(default='',max_length=30)
    campus:str=Field(default='',max_length=100)
    designation:str=Field(default='',max_length=100)
class PasswordChange(Input):
    old_password:str=Field(min_length=1,max_length=128)
    new_password:str=Field(min_length=12,max_length=128)
class VivaStart(Input):
    topic_id:int|None=None
    count:int=Field(default=30,ge=1,le=30)
class VivaAnswer(Input):
    turn_index:int=Field(ge=0)
    text:str=Field(min_length=2,max_length=6000)
class VivaReview(Input):
    score:float=Field(ge=0,le=100)
    feedback:str=Field(min_length=3,max_length=4000)
class TaskState(Input):
    status:Literal['planned','done','skipped']
