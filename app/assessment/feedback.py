from app.models import Topic

def teaching_feedback(db,q,selected):
    topic=db.get(Topic,q.topic_id)
    chosen=q.options[selected] if selected is not None else 'No answer submitted'
    expected=q.options[q.correct]
    correct=selected==q.correct
    parts=[('Your answer is correct: ' if correct else 'Your answer: ')+chosen,
           'Correct answer: '+expected,
           ('Why this is correct: '+q.explanation if correct else 'Why your choice is incorrect: the selected option, '+chosen+', does not satisfy the rule used here. '+(q.misconception or 'Compare it with the deciding rule below.'))]
    if not correct:
        if q.misconception:parts.append('Common confusion to check: '+q.misconception)
        parts.append('Why the correct answer fits: '+expected+' — '+q.explanation)
    if topic and topic.description:parts.append('The concept in context: '+topic.description)
    parts.append('Check your understanding: explain the deciding rule in your own words, then apply it to a different example before your next assessment.')
    return '\n\n'.join(parts)
