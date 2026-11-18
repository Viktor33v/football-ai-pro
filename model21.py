import json, math
from collections import defaultdict
from itertools import groupby
from pathlib import Path
rows=json.loads(Path("state/history.json").read_text())["rows"]
teams=defaultdict(list)
leagues=defaultdict(list)
metrics=[[0.,0.,0] for _ in range(2)]
for date,group in groupby(sorted(rows,key=lambda r:r["date"]),key=lambda r:r["date"]):
    day=list(group)
    for r in day:
        l=r["league"]; h=r["home"]; a=r["away"]
        hs=teams[l,h][-20:]; vs=teams[l,a][-20:]; ls=leagues[l]
        if min(len(hs),len(vs))<10 or len(ls)<50 or date<"2025-07-01": continue
        def avg(ms,i):
            weights=[0.94**(len(ms)-1-j) for j in range(len(ms))]
            return sum(w*m[i] for w,m in zip(weights,ms))/sum(weights)
        def rate(x,y,prior):
            return max(.05,(x+y+prior)/3)
        x=rate(avg(hs,0),avg(vs,1),sum(m[0] for m in ls)/len(ls))
        y=rate(avg(vs,0),avg(hs,1),sum(m[1] for m in ls)/len(ls))
        z=x+y
        probs=[1-math.exp(-z)*(1+z+z*z/2),(1-math.exp(-x))*(1-math.exp(-y))]
        g,c=r["ft"]
        outcomes=[g+c>=3,g>0 and c>0]
        bases=[sum(u+v>=3 for u,v in ls)/len(ls),sum(u>0 and v>0 for u,v in ls)/len(ls)]
        for i in range(2):
            metrics[i][0]+=(probs[i]-outcomes[i])**2
            metrics[i][1]+=(bases[i]-outcomes[i])**2
            metrics[i][2]+=1
    for r in day:
        l=r["league"];g,c=r["ft"]
        teams[l,r["home"]].append((g,c))
        teams[l,r["away"]].append((c,g))
        leagues[l].append((g,c))
result={k:{"model":m[0]/m[2],"baseline":m[1]/m[2],"n":m[2]} for k,m in zip(["over25","btts"],metrics) if m[2]}
print(json.dumps(result,indent=2))
Path("state/model21.json").write_text(json.dumps(result,indent=2))
