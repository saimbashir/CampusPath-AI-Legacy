"""Deterministic quota selection; reject impossible distributions rather than invent questions."""
from collections import Counter,defaultdict
from fastapi import HTTPException
BLOOM={'Remember','Understand','Apply','Analyze','Evaluate','Create'}
def quotas(distribution,n,available):
    if distribution:
        if any(not isinstance(v,int) or v<0 or v>100 for v in distribution.values()) or sum(distribution.values())!=100:
            raise HTTPException(422,'Assessment distributions must contain percentages totaling 100.')
        weights=distribution
    else:weights=available
    total=sum(weights.values())
    if not total:raise HTTPException(409,'No matching questions in this category.')
    raw={k:n*v/total for k,v in weights.items()};counts={k:int(v) for k,v in raw.items()}
    for k in sorted(raw,key=lambda k:(-(raw[k]-counts[k]),k))[:n-sum(counts.values())]:counts[k]+=1
    return counts

def select_mock(questions,topics,data):
    if data.bloom_distribution.keys()-BLOOM:raise HTTPException(422,'Unknown Bloom level.')
    if data.clo_distribution.keys()-{t.clo for t in topics.values()}:raise HTTPException(422,'Unknown CLO code.')
    if (data.bloom_distribution or data.clo_distribution) and len(questions)<data.count:
        raise HTTPException(409,'The approved bank is too small for that exact exam configuration.')
    n=min(data.count,len(questions));cells=defaultdict(list)
    for q in questions:cells[(topics[q.topic_id].clo,q.bloom)].append(q)
    # An unspecified axis is unconstrained, not an implicit proportional quota.
    cq=quotas(data.clo_distribution,n,{}) if data.clo_distribution else Counter(topics[q.topic_id].clo for q in questions)
    bq=quotas(data.bloom_distribution,n,{}) if data.bloom_distribution else Counter(q.bloom for q in questions)
    capacity=defaultdict(dict)
    def edge(a,b,c):capacity[a][b]=c;capacity[b].setdefault(a,0)
    for clo,count in cq.items():edge('source','C:'+clo,count)
    for bloom,count in bq.items():edge('B:'+bloom,'sink',count)
    for (clo,bloom),qs in cells.items():
        if clo in cq and bloom in bq:edge('C:'+clo,'B:'+bloom,len(qs))
    flow=0
    while flow<n:
        parents={'source':None};queue=['source']
        for node in queue:
            for child,c in capacity[node].items():
                if c>0 and child not in parents:parents[child]=node;queue.append(child)
            if 'sink' in parents:break
        if 'sink' not in parents:raise HTTPException(409,'The approved question bank cannot satisfy these CLO/Bloom percentages. Adjust the mix or add questions.')
        node='sink'
        while parents[node] is not None:
            parent=parents[node];capacity[parent][node]-=1;capacity[node][parent]+=1;node=parent
        flow+=1
    selected=[]
    for (clo,bloom),qs in cells.items():
        count=capacity.get('B:'+bloom,{}).get('C:'+clo,0);selected.extend(qs[:count])
    return selected
