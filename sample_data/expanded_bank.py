"""Faculty-authored demonstration questions; no subject-specific runtime logic."""
EXTRA=[
(0,'A thermostat senses room temperature. Which component changes the environment?','The heater actuator','The temperature sensor','The heater changes the room temperature; the sensor only observes it.'),
(0,'Why does an agent need a performance measure?','To compare how well its actions achieve the goal','To count source-code lines','A performance measure defines successful behavior, so actions can be evaluated against a goal.'),
(0,'A robot receives an obstacle reading. What is this incoming observation called?','A percept','An actuator','A percept is information received from the environment through a sensor.'),
(0,'Two agents take the same action but receive different random outcomes. Must one be irrational?','No, rationality depends on available evidence','Yes, the worse outcome proves irrationality','A rational decision maximizes expected performance before the uncertain outcome is known.'),
(0,'Which sequence describes a basic agent interaction cycle?','Perceive, choose an action, act','Act forever without observing','Sensors provide evidence, the agent selects an action and actuators carry it out.'),
(1,'The BFS queue contains B, C; expanding B discovers D. What is the new queue?','C, D','D, C','Newly discovered D is appended to the FIFO queue, after C.'),
(1,'BFS finds a goal at depth 3 with unit edge costs. What is the path cost?','3','It must equal the heuristic','Three unit-cost edges give cost 3; BFS does not use a heuristic.'),
(1,'Why can BFS require substantial memory on a wide tree?','It stores a broad frontier at each depth','It stores only one root-to-leaf path','The frontier can contain many nodes from the current and next levels.'),
(1,'A direct edge costs 20 while a two-edge route costs 2. Which route can BFS prefer?','The direct one-edge route','Always the cost-2 route','BFS prioritizes shallow depth, not the sum of edge costs.'),
(1,'What does a visited set prevent in graph BFS?','Repeated expansion of already visited states','All storage of frontier nodes','Tracking visited states avoids cycles and redundant expansion while retaining the FIFO frontier.'),
(2,'The DFS stack has A then B pushed on top. Which is popped first?','B','A','A stack is last-in, first-out; B was pushed most recently.'),
(2,'Why might DFS reach a deep goal before a shallow goal on another branch?','It follows its current branch before alternatives','It always orders nodes by depth ascending','DFS extends a branch until it must backtrack; it does not explore complete levels.'),
(2,'What happens when DFS reaches a dead end?','It backtracks to an unexplored alternative','It becomes uniform-cost search','Backtracking resumes from an ancestor with unexplored successors.'),
(2,'What additional rule prevents unbounded descent in depth-limited DFS?','Stop expanding at a chosen depth limit','Sort the frontier by path cost','A depth limit bounds how far the current search can descend.'),
(2,'Can changing successor order change the first solution found by DFS?','Yes','No, DFS always finds the same first goal','Successor order changes which branch is explored first, so the first solution may differ.'),
(3,'UCS expands a node at g=4 through an edge of cost 6. What is the child cost?','10','6','Accumulated cost includes both the existing path and the new edge: 4+6=10.'),
(3,'Which frontier structure naturally supports UCS?','A priority queue ordered by g(n)','A stack ordered only by discovery','UCS repeatedly removes the state with the smallest accumulated path cost.'),
(3,'A cheaper route reaches an existing frontier state. What should UCS do?','Update that state to the cheaper cost','Keep the old cost regardless','Keeping the best known path cost preserves the least-cost search ordering.'),
(3,'Why are positive lower-bounded costs relevant to UCS completeness?','They prevent infinitely many ever-cheaper steps before a finite-cost goal','They make heuristics exact','A positive lower bound limits the number of steps in paths below a fixed finite cost.'),
(3,'With identical positive edge costs, how do UCS and BFS compare?','They prioritize equivalent depth levels','UCS must follow the deepest branch','Path cost is proportional to depth when each edge has the same positive cost.'),
(4,'A heuristic gives h=0 everywhere. Is it admissible for nonnegative remaining costs?','Yes','No, admissible estimates must be positive','Zero never overestimates a nonnegative true remaining cost, though it gives little guidance.'),
(4,'Why is an exact remaining-cost estimate admissible?','Equality does not overestimate','It ignores the remaining path','Admissibility permits equality with the true optimal remaining cost.'),
(4,'Which quantity includes costs already paid along the path?','g(n)','h(n)','g is accumulated path cost; h estimates the future cost to a goal.'),
(4,'If h=4 and the true remaining cost is 9, is this estimate an overestimate?','No','Yes','4 is less than 9; this particular estimate respects the lower-bound requirement.'),
(4,'Does one valid estimate prove a heuristic is admissible for every state?','No, it must never overestimate at any relevant state','Yes, one example is sufficient','Admissibility is a global property; an untested state may still have an overestimate.'),
(5,'GBFS frontier has A: g=20,h=2 and B: g=1,h=5. Which is chosen?','A','B','Greedy Best-First Search compares only h: 2 is smaller than 5, regardless of g.'),
(5,'GBFS reaches a node through an expensive path. Does its ranking include that expense?','No, ranking uses h(n)','Yes, ranking uses g(n)+h(n)','Ignoring accumulated g can lead Greedy toward a costly complete route.'),
(5,'Two GBFS nodes have equal h values. What decides their order?','The implementation tie-breaking rule','The heuristic alone uniquely decides','Equal heuristic values give equal Greedy priority; a separate tie-break rule is needed.'),
(5,'Does an admissible heuristic alone make GBFS optimal?','No','Yes','Greedy ignores accumulated cost, so admissibility alone cannot guarantee a least-cost complete path.'),
(5,'What distinction separates GBFS priority from A* priority?','GBFS uses h; A* uses g+h','Both always use only g','A* considers cost already incurred as well as the estimated remaining cost.'),
(6,'A* frontier contains A: g=2,h=6 and B: g=5,h=1. Which has lower f?','B','A','f(A)=8 and f(B)=6, so B has lower A* priority.'),
(6,'A* uses h=0 on every node. Which search priority does it become?','Uniform-cost priority','Depth-first priority','f=g+0=g, so priority is the accumulated path cost.'),
(6,'Why might A* graph search reopen a state with an admissible but inconsistent heuristic?','A cheaper route may be discovered after the state was closed','A* never stores path costs','Reopening lets the search propagate the improved g value instead of retaining a worse route.'),
(6,'For a consistent heuristic, what relation holds across an edge of cost c to a successor?','h(n) <= c + h(successor)','h(n) must always exceed c + h(successor)','Consistency is a triangle-inequality condition linking neighboring estimates.'),
(6,'At a goal with h=0, what does the A* f value equal?','The complete path cost g','Always zero','The remaining estimated cost is zero, but the cost already paid remains in g.'),
(7,'At a MAX node, children have utilities 3, 7 and 2. Which value is backed up?','7','2','MAX selects the greatest utility among the available child values.'),
(7,'At a MIN node, children have utilities 3, 7 and 2. Which value is backed up?','2','7','MIN selects the smallest utility, modeling the opponent acting against MAX.'),
(7,'MAX can choose branches with worst-case utilities 4 and 1. Which is preferred?','The branch with worst-case utility 4','The branch with worst-case utility 1','Minimax maximizes the guaranteed value against an optimal opponent.'),
(7,'Why does minimax alternate MAX and MIN levels?','The players take turns with opposing objectives','Both players maximize the same utility','One player maximizes the stated utility while the opponent minimizes it.'),
(7,'What assumption underlies the classical minimax game model?','Deterministic two-player zero-sum play','Random outcomes and unrelated player rewards','Classical minimax assumes adversarial zero-sum utilities and deterministic transitions.'),
]

def extend_demo(db,course,topics):
    from sqlalchemy import select
    from app.models import Question
    existing=set(db.scalars(select(Question.prompt).where(Question.course_id==course.id)))
    for i,(tid,prompt,right,wrong,explanation) in enumerate(EXTRA):
        if prompt in existing:continue
        options=[right,wrong] if i%2==0 else [wrong,right]
        db.add(Question(course_id=course.id,topic_id=topics[tid].id,prompt=prompt,options=options,correct=options.index(right),explanation=explanation,misconception='',difficulty=1+i%3,bloom='Understand' if i%2==0 else 'Analyze',approved=True,source='CampusPath faculty-authored supplemental demo bank'))
