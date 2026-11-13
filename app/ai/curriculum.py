from pydantic import BaseModel,Field,model_validator,ConfigDict
from app.schemas import QuestionInput
class DraftTopic(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(min_length=1,max_length=140)
    description:str=Field(min_length=1,max_length=6000)
    prerequisites:list[str]=Field(default_factory=list,max_length=30)
    clo:str=Field(default='CLO-1',max_length=40)
    difficulty:int=Field(default=1,ge=1,le=3)
class CurriculumDraft(BaseModel):
    model_config=ConfigDict(extra='forbid')
    topics:list[DraftTopic]=Field(min_length=1,max_length=40)
    @model_validator(mode='after')
    def unique_and_acyclic(self):
        names=[t.name for t in self.topics]
        if len(set(names))!=len(names):raise ValueError('Duplicate topic names.')
        graph={t.name:t.prerequisites for t in self.topics};seen=set();visiting=set()
        def visit(n):
            if n in visiting:raise ValueError('Prerequisite cycle.')
            if n in seen or n not in graph:return
            visiting.add(n)
            for p in graph[n]:visit(p)
            visiting.remove(n);seen.add(n)
        for n in graph:visit(n)
        return self
class QuestionDraft(BaseModel):
    model_config=ConfigDict(extra='forbid')
    question:QuestionInput
    source_ids:list[int]=Field(min_length=1,max_length=5)
