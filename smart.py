import os,json,math
from collections import defaultdict
from datetime import datetime,timezone,timedelta
from bot import api,prob,send
from backtest import LABELS

LIMITS=[.70,.50,.60,.60,.80]
def run():
    now=datetime.now(timezone.utc); today=now.date()
    raw={}
    for offset in range(0,365,7):
        end=today-timedelta(days=offset)
        start=max(today-timedelta(days=364),end-timedelta(days=6))
        for m in api("matches?dateFrom="+str(start)+"&dateTo="+str(end))["matches"]:
            raw[m["id"]]=m
    upcoming=api("matches?dateFrom="+str(today)+"&dateTo="+str(today+timedelta(days=6)))["matches"]
    days=defaultdict(list); actual={}
    for m in raw.values():
        if m["status"]!="FINISHED" or m["score"].get("duration") not in (None,"REGULAR"): continue
        f=m["score"]["fullTime"]; h=m["score"]["halfTime"]
        if any(v is None for v in [f["home"],f["away"],h["home"],h["away"]]): continue
        v=(f["home"],f["away"],h["home"],h["away"])
        if v[0]<v[2] or v[1]<v[3]: continue
        ft=v[0]+v[1]; ht=v[2]+v[3]
        y=[int(ht>=1),int(ht>=2),int(ft>=3),int(min(v[:2])>=1),int(ft-ht>=1)]
        actual[str(m["id"])]=y
        if m["utcDate"][:10]<str(today): days[m["utcDate"][:10]].append((m,v,y))
    teams=defaultdict(list); leagues=defaultdict(list); prior=[]; half_test=[[],[]]
    def half_candidate(a,b,l):
        if min(len(teams[a]),len(teams[b]))<12 or len(leagues[l])<20: return None
        base=[(sum(z[i] for z in prior)+2)/(len(prior)+4) for i in range(2)]
        lg=[(sum(z[i] for z in leagues[l])+30*base[i])/(len(leagues[l])+30) for i in range(2)]
        def avg(t,side,j):
            xs=teams[t][-20:]; vs=[z for z in teams[t] if z[4]==side][-10:]
            return (sum(z[j] for z in vs)+5*sum(z[j] for z in xs)/len(xs))/(len(vs)+5)
        lam=(avg(a,1,2)+avg(b,0,3)+avg(a,1,3)+avg(b,0,2))/2
        old=[(base[0]+lg[0])/2,lg[1]]
        return [(prob(lam,i+1)+old[i])/2 for i in range(2)],old
    def strength(t):
        xs=teams[t][-20:]
        return sum(z[0]-z[1] for z in xs)/(len(xs)+8)
    for day,ms in sorted(days.items()):
        pending=[]
        for m,v,y in ms:
            a=m["homeTeam"]["id"]; b=m["awayTeam"]["id"]
            l=m["competition"]["id"]; f=half_candidate(a,b,l)
            if f:
                for i in range(2): half_test[i].append((f[0][i],f[1][i],y[i]))
            pending.append((a,b,l,v,y,strength(a),strength(b)))
        for a,b,l,v,y,sa,sb in pending:
            teams[a].append((*v,1,sb)); teams[b].append((v[1],v[0],v[3],v[2],0,sa))
            leagues[l].append(y); prior.append(y)
    def av(t,side,j):
        xs=teams[t][-20:]; spec=[z for z in teams[t] if z[4]==side][-10:]
        w=[.92**(len(xs)-1-i) for i in range(len(xs))]
        g=sum(z[j]*q for z,q in zip(xs,w))/sum(w)
        return (sum(z[j] for z in spec)+4*g)/(len(spec)+4)
    def adj(t,j,sign):
        xs=teams[t][-20:]
        return sum(z[j]*math.exp(max(-.35,min(.35,sign*.12*z[5]))) for z in xs)/len(xs)
    candidates=[]; shadow=[]
    for m in upcoming:
        if m["status"] not in ("TIMED","SCHEDULED"): continue
        k=datetime.fromisoformat(m["utcDate"].replace("Z","+00:00"))
        if k<=now: continue
        a=m["homeTeam"]["id"]; b=m["awayTeam"]["id"]; l=m["competition"]["id"]
        if min(len(teams[a]),len(teams[b]))<12 or len(leagues[l])<20: continue
        base=[(sum(z[i] for z in prior)+2)/(len(prior)+4) for i in range(5)]
        lg=[(sum(z[i] for z in leagues[l])+30*base[i])/(len(leagues[l])+30) for i in range(5)]
        hh=(av(a,1,0)+av(b,0,1))/2; aa=(av(b,0,0)+av(a,1,1))/2
        ht=(av(a,1,2)+av(b,0,3)+av(a,1,3)+av(b,0,2))/2
        hh=(hh+(adj(a,0,1)+adj(b,1,-1))/2)/2
        aa=(aa+(adj(b,0,1)+adj(a,1,-1))/2)/2
        p=[(base[0]+lg[0])/2,lg[1],(prob(hh+aa,3)+lg[2])/2,(prob(hh,1)*prob(aa,1)+lg[3])/2,(prob(max(0,hh+aa-ht),1)+lg[4])/2]
        candidates.append((m,k,p))
        f=half_candidate(a,b,l)
        if f: shadow.append(dict(home=m["homeTeam"]["name"],away=m["awayTeam"]["name"],kickoff=k.isoformat(),p=f[0],old=f[1],sample=[min(20,len(teams[a])),min(20,len(teams[b]))]))
    os.makedirs("state",exist_ok=True)
    with open("goals.json","w",encoding="utf-8") as f:
        json.dump([dict(home=m["homeTeam"]["name"],away=m["awayTeam"]["name"],date=k.date().isoformat(),kickoff=k.isoformat(),p=p) for m,k,p in candidates],f,ensure_ascii=False)
    with open("state/half_shadow.json","w",encoding="utf-8") as f: json.dump(dict(created=now.isoformat(),rows=shadow,metrics=[dict(n=len(rs),model=sum((p-y)**2 for p,b,y in rs)/len(rs),baseline=sum((b-y)**2 for p,b,y in rs)/len(rs)) if rs else dict(n=0) for rs in half_test]),f,ensure_ascii=False)
    path="state/journal.json"
    if os.path.exists(path):
        with open(path,encoding="utf-8") as f: journal=json.load(f)
    else: journal={}
    for r in journal.values():
        if int(r["id"]) in raw and raw[int(r["id"])].get("utcDate"):
            r["kickoff"]=datetime.fromisoformat(raw[int(r["id"])]["utcDate"].replace("Z","+00:00")).isoformat()
        if r["id"] in actual and r["result"] is None: r["result"]=actual[r["id"]][r["market"]]
    lines=["⚽ FOOTBALL AI PRO V6 • ДЕМО","Фиксированные модели V5; пороги экспериментальные. Коэффициент 1/p — расчётный, не букмекерский.",f"Матчей с выборкой: {len(candidates)}"]
    for i,label in enumerate(LABELS):
        picks=sorted([r for r in candidates if r[2][i]>=LIMITS[i]],key=lambda r:r[2][i],reverse=True)[:5]
        lines.append(f"\n{label} | порог {LIMITS[i]:.0%}")
        if not picks: lines.append("Нет кандидатов")
        for m,k,p in picks:
            if k<=datetime.now(timezone.utc): continue
            key=str(m["id"])+":"+str(i)
            name=m["homeTeam"]["name"]+" — "+m["awayTeam"]["name"]
            local=k.astimezone(timezone(timedelta(hours=6)))
            lines.append(f"{name} | {local:%d.%m %H:%M} | {p[i]:.1%} | 1/p: {1/p[i]:.2f}")
            journal.setdefault(key,dict(id=str(m["id"]),market=i,p=p[i],kickoff=k.isoformat(),created=now.isoformat(),result=None))
    future=sum(r["result"] is None and datetime.fromisoformat(r["kickoff"])>now for r in journal.values())
    lines.append(f"\nЖурнал V6: первый прогноз на матч/рынок. Предстоящих прогнозов: {future}")
    for n in (7,30,90):
        lines.append(f"За {n} дней:")
        for i,label in enumerate(LABELS):
            rs=[r for r in journal.values() if r["market"]==i and now-timedelta(days=n)<=datetime.fromisoformat(r["kickoff"])<=now]
            done=[r for r in rs if r["result"] is not None]; wins=sum(r["result"] for r in done)
            rate=f" ({wins/len(done):.0%})" if done else ""
            lines.append(f"{label}: {wins}/{len(done)}{rate}; без результата {len(rs)-len(done)}")
    with open(path,"w",encoding="utf-8") as f: json.dump(journal,f,ensure_ascii=False,indent=2)
    chunk=""
    for line in lines:
        if len(chunk)+len(line)>3500:
            send(os.environ["TELEGRAM_CHAT_ID"],chunk); chunk=""
        chunk+=line+"\n"
    if chunk: send(os.environ["TELEGRAM_CHAT_ID"],chunk)
if __name__=="__main__": run()
