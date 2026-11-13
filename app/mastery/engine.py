from datetime import timedelta

def update_mastery(prior:float,correct:bool,difficulty:int=1,guess:float=.25):
    """BKT observation update followed by a learning transition; not a grade."""
    if not 0<=prior<=1 or difficulty not in (1,2,3): raise ValueError('Invalid BKT input')
    slip=0.08+0.04*(difficulty-1)
    if not 0<guess<1:raise ValueError('Guess probability must be between 0 and 1')
    if correct:
        posterior=prior*(1-slip)/(prior*(1-slip)+(1-prior)*guess)
    else:
        posterior=prior*slip/(prior*slip+(1-prior)*(1-guess))
    target=posterior+(1-posterior)*0.08
    # One observation is weak evidence: cap positive movement at 3 percentage points.
    return min(.97,max(.01,prior+max(-.05,min(.03,(target-prior)*.15))))
def next_difficulty(current,correct):
    return max(1,min(3,current+(1 if correct else -1)))
def revision_dates(now,mastery):
    return [now+timedelta(days=d) for d in ([1,3,7] if mastery<0.8 else [3,7,14])]
def confidence(attempts):
    return round(min(0.95,attempts/(attempts+8)),2)
