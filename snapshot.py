import json,os
from datetime import datetime,timezone,timedelta
import corners,cards
from backtest import LABELS
from smart import LIMITS

def load(path,default):
    if not os.path.exists(path): return default
    with open(path,encoding="utf-8") as f: return json.load(f)
def save(path,obj):
    with open(path,"w",encoding="utf-8") as f: json.dump(obj,f,ensure_ascii=False,indent=2)
def run():
    now=datetime.now(timezone.utc); today=now.date().isoformat()
    os.makedirs("state",exist_ok=True)
    previous=load("state/snapshot.json",{})
    rows=[]; diagnostics=load('goal_metrics.json',{}); journal=load("state/extra_journal.json",{})
    for r in load("goals.json",[]):
        for i,p in enumerate(r["p"]):
            rows.append(dict(home=r["home"],away=r["away"],date=r["date"],kickoff=r["kickoff"],group="goals",sample=r.get("sample"),market=LABELS[i],p=p,selected=p>=LIMITS[i]))
    for group,mod in [("corners",corners),("cards",cards)]:
        d=load(group+".json",{})
        for i,rr in d.get("metrics",{}).items():
            if rr: diagnostics[mod.MARKETS[int(i)][0]]=dict(n=len(rr),model=sum((p-y)**2 for p,b,y in rr)/len(rr),baseline=sum((b-y)**2 for p,b,y in rr)/len(rr))
        for i,rs in d.get("picks",{}).items():
            i=int(i)
            for r in rs:
                row=dict(r,group=group,market=mod.MARKETS[i][0],selected=r["p"]>=.65)
                rows.append(row)
                if row["selected"] and r["date"]>today:
                    key=json.dumps([group,r["league"],r["date"],r["home"],r["away"],i],ensure_ascii=False)
                    journal.setdefault(key,dict(row,index=i,created=now.isoformat(),result=None))
    pending={}
    for r in journal.values():
        if r["result"] is None and r["date"]<today: pending.setdefault(r["league"],[]).append(r)
    for league,rs in pending.items():
        try: history=corners.read(league,"results")
        except Exception: continue
        actual={}
        for x in history:
            if x["date"]<today and x.get("ft_home","").isdigit() and x.get("ft_away","").isdigit():
                actual[(x["date"],x["home"],x["away"])]=x
        for r in rs:
            x=actual.get((r["date"],r["home"],r["away"]))
            if x is None: continue
            if r["group"]=="corners":
                _,k,half=corners.MARKETS[r["index"]]; v=corners.counts(x)
                if v is None: continue
                pair=v[2:] if half else v[:2]
                if None in pair: continue
                value=sum(pair)
            else:
                _,k,side=cards.MARKETS[r["index"]]; v=cards.pair(x,"yellow")
                if v is None: continue
                value=[sum(v),v[0],v[1]][side]
            r["result"]=int(value>=k)
    save("state/extra_journal.json",journal)
    changes={}
    for market,d in diagnostics.items():
        old=previous.get("diagnostics",{}).get(market,{})
        if isinstance(d,dict) and isinstance(old,dict) and type(d.get("n")) is int and type(old.get("n")) is int and d["n"]!=old["n"]:
            changes[market]={"previous":old["n"],"current":d["n"]}
    save("state/snapshot.json",dict(created=now.isoformat(),rows=rows,diagnostics=diagnostics,calibration=load("state/goal_calibration.json",{}),history_comparison={"previous_created":previous.get("created"),"markets":changes}))
if __name__=="__main__": run()
