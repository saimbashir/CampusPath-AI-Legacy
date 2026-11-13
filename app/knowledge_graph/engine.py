import heapq
from collections import deque

def validate_dag(topics):
    graph={t.id:list(t.prerequisites or []) for t in topics}
    visiting,done=set(),set()
    def visit(n):
        if n in visiting: raise ValueError('Prerequisites must not contain a cycle.')
        if n in done:return
        if n not in graph:raise ValueError('Prerequisite must belong to this course.')
        visiting.add(n)
        for p in graph[n]:visit(p)
        visiting.remove(n);done.add(n)
    for n in graph:visit(n)
def learning_order(topics,masteries):
    by_id={t.id:t for t in topics};order=[];visited=set()
    def visit(t):
        if t.id in visited:return
        visited.add(t.id)
        for p in t.prerequisites or []:
            if p in by_id and masteries.get(p,0.2)<0.8:visit(by_id[p])
        if masteries.get(t.id,0.2)<0.8:order.append(t)
    for t in sorted(topics,key=lambda t:masteries.get(t.id,0.2)):visit(t)
    return order

def algorithm_steps(algorithm):
    if algorithm not in ('BFS','DFS','UCS','A*'): raise ValueError('Unknown algorithm')
    graph={'S':[('A',2),('B',5)],'A':[('C',2),('D',5)],'B':[('D',1)],'C':[('G',5)],'D':[('G',2)],'G':[]}
    h={'S':7,'A':7,'B':3,'C':5,'D':2,'G':0}
    frontier=[(0,0,'S',['S'])];best={'S':0};visited=[];steps=[];seq=0
    while frontier:
        if algorithm in ('UCS','A*'): _,cost,node,path=heapq.heappop(frontier)
        else: _,cost,node,path=frontier.pop(0 if algorithm=='BFS' else -1)
        if node in visited:continue
        visited.append(node)
        if node!='G':
            edges=graph[node] if algorithm!='DFS' else list(reversed(graph[node]))
            for child,w in edges:
                new=cost+w
                if child in visited:continue
                if algorithm in ('UCS','A*') and new>=best.get(child,float('inf')):continue
                best[child]=new;seq+=1
                priority=new+(h[child] if algorithm=='A*' else 0)
                item=(priority,new,child,path+[child])
                if algorithm in ('UCS','A*'):heapq.heappush(frontier,item)
                else:frontier.append(item)
        ordered=sorted(frontier) if algorithm in ('UCS','A*') else frontier
        steps.append({'current':node,'visited':visited.copy(),'frontier':[x[2] for x in ordered],'path':path,'g':cost,'h':h[node],'f':cost+h[node],'explanation':f'Expand {node}. Path cost g={cost}; estimated remaining cost h={h[node]}. '+('Goal reached.' if node=='G' else 'Add eligible neighbors to the frontier.')})
        if node=='G':break
    return {'graph':graph,'heuristics':h,'steps':steps,'algorithm':algorithm}
