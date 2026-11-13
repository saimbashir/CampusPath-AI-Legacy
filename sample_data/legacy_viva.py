"""Isolated legacy demonstration; not used by the universal viva engine."""
from app.models import Conversation
def evaluate_demo(db,user,cid,data):
    # This is a narrowly scoped demo evaluator, explicitly not a general semantic judge.
    text=data.text.lower()
    confusion=any(s in text for s in ('already travelled','already traveled','accumulated','cost so far','travelled cost'))
    covered=any(s in text for s in ('estimate','estimated','andaza','heuristic')) and any(s in text for s in ('goal','remaining','baqi','manzil')) and not confusion
    feedback='Correct concept coverage: h(n) estimates remaining cost to the goal.' if covered else 'Possible g(n)/h(n) confusion. h(n) estimates remaining cost; g(n) is accumulated path cost.' if confusion else 'Your answer needs an estimate of the remaining cost to the goal. Rephrase it or ask your teacher to review.'
    db.add(Conversation(student_id=user.id,course_id=cid,mode='viva-demo',question=data.text,answer=feedback));db.commit()
    return {'feedback':feedback,'concept_coverage':covered,'follow_up':'How does A* combine g(n) and h(n)?','status':'DEMO-SIMULATED: keyword feedback only; no grade or mastery update.','mastery_impact':None}
