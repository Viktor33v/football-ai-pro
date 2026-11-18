from collections import defaultdict
from datetime import datetime,timezone
from corners import read,LEAGUES,SOURCE
from snapshot import save

def number(x):
    try:
        n=int(x)
        return n if n>=0 else None
    except (TypeError,ValueError): return None

def run():
    today=datetime.now(timezone.utc).date().isoformat()
    teams=defaultdict(list); errors=[]
    for league in LEAGUES:
        try: rows=read(league,"results")
        except Exception: errors.append(league); continue
        seen=set()
        for r in sorted(rows,key=lambda r:r["date"]):
            key=(r["date"],r["home"],r["away"])
            if key in seen or r["date"]>=today: continue
            h,a=number(r.get("ft_home")),number(r.get("ft_away"))
            if h is None or a is None: continue
            seen.add(key)
            for side,opp,g,c in [("home","away",h,a),("away","home",a,h)]:
                teams[(league,r[side])].append(dict(date=r["date"],opponent=r[opp],venue=side,g=g,c=c,shots=number(r.get(side+"_shots")),target=number(r.get(side+"_target")),corners=number(r.get(side+"_corners")),yellow=number(r.get(side+"_yellow"))))
    save("state/form.json",dict(created=datetime.now(timezone.utc).isoformat(),source=SOURCE,errors=errors,teams=[dict(league=l,name=t,matches=rs[-20:]) for (l,t),rs in teams.items()]))
if __name__=="__main__": run()
