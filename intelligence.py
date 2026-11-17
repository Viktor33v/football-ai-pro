import os,json,math
from collections import defaultdict
from datetime import datetime,timezone,timedelta
from bot import api,prob,send
from backtest import LABELS

def run():
    today=datetime.now(timezone.utc).date()
    raw={}
    for offset in range(1,365,7):
        for m in api("matches?dateFrom="+str(today-timedelta(days=min(365,offset+6)))+"&dateTo="+str(today-timedelta(days=offset)))["matches"]:
            if m["status"]=="FINISHED": raw[m["id"]]=m
    days=defaultdict(list)
    for m in raw.values():
        if m["score"].get("duration") not in (None,"REGULAR"): continue
        f=m["score"]["fullTime"]; h=m["score"]["halfTime"]
        if any(v is None for v in [f["home"],f["away"],h["home"],h["away"]]): continue
        if f["home"]<h["home"] or f["away"]<h["away"]: continue
        days[m["utcDate"][:10]].append(m)
    teams=defaultdict(list); leagues=defaultdict(list); prior=[]; rows=[]
    def predictions(h,a,ht):
        return [prob(ht,1),prob(ht,2),prob(h+a,3),prob(h,1)*prob(a,1),prob(max(0,h+a-ht),1)]
    def mean(xs,j,n,weighted=False):
        xs=xs[-n:]
        w=[0.92**(len(xs)-1-i) if weighted else 1 for i in range(len(xs))]
        return sum(v[j]*z for v,z in zip(xs,w))/sum(w)
    for day,ms in sorted(days.items()):
        pending=[]
        for m in ms:
            a=m["homeTeam"]["id"]; b=m["awayTeam"]["id"]; l=m["competition"]["id"]
            f=m["score"]["fullTime"]; h=m["score"]["halfTime"]
            v=(f["home"],f["away"],h["home"],h["away"])
            ft=v[0]+v[1]; ht=v[2]+v[3]
            y=[int(ht>=1),int(ht>=2),int(ft>=3),int(min(v[:2])>=1),int(ft-ht>=1)]
            def strength(team):
                xs=teams[team][-20:]
                return (sum(z[0]-z[1] for z in xs)/(len(xs)+8))
            sa,sb=strength(a),strength(b)
            pending.append((a,b,l,v,y,sa,sb))
            if min(len(teams[a]),len(teams[b]))<12 or len(leagues[l])<20: continue
            base=[(sum(z[i] for z in prior)+2)/(len(prior)+4) for i in range(5)]
            league=[(sum(z[4][i] for z in leagues[l])+30*base[i])/(len(leagues[l])+30) for i in range(5)]
            def av(t,side,j,n=20,w=False):
                xs=teams[t]; spec=[z for z in xs if z[4]==side][-10:]
                g=mean(xs,j,n,w)
                return (sum(z[j] for z in spec)+4*g)/(len(spec)+4)
            def model(n,w):
                hh=(av(a,1,0,n,w)+av(b,0,1,n,w))/2
                aa=(av(b,0,0,n,w)+av(a,1,1,n,w))/2
                ht=(av(a,1,2,n,w)+av(b,0,3,n,w)+av(a,1,3,n,w)+av(b,0,2,n,w))/2
                return hh,aa,ht
            p20=predictions(*model(20,False))
            p5=predictions(*model(5,True)); p10=predictions(*model(10,True))
            hh,aa,th=model(20,True)
            # Opponent adjustment uses strength recorded before each past game.
            def adj(t,j,sign):
                xs=teams[t][-20:]
                return sum(z[j]*math.exp(max(-0.35,min(0.35,sign*0.12*z[5]))) for z in xs)/len(xs)
            hh=(hh+(adj(a,0,1)+adj(b,1,-1))/2)/2
            aa=(aa+(adj(b,0,1)+adj(a,1,-1))/2)/2
            pstrength=predictions(hh,aa,th)
            ensemble=[(p5[i]+p10[i]+pstrength[i]+2*league[i])/5 for i in range(5)]
            rows.append({"date":day,"id":m["id"],"y":y,"p":{"global":base,"league":league,"v3_like":p20,"recent5":p5,"recent10":p10,"strength":pstrength,"ensemble":ensemble}})
        for a,b,l,v,y,sa,sb in pending:
            teams[a].append((*v,1,sb)); teams[b].append((v[1],v[0],v[3],v[2],0,sa))
            leagues[l].append((*v,y)); prior.append(y)
    dates=sorted({r["date"] for r in rows})
    if len(dates)<10: raise RuntimeError("Insufficient historical dates")
    cut=dates[int(len(dates)*0.6)]
    train=[r for r in rows if r["date"]<cut]; test=[r for r in rows if r["date"]>=cut]
    names=list(rows[0]["p"])
    def brier(rs,i,fn): return sum((fn(r)-r["y"][i])**2 for r in rs)/len(rs)
    lines=["⚽ FOOTBALL AI PRO V5 • ДЕМО","История до 365 дней. Подбор на раннем периоде, проверка на позднем.",f"Подбор: {len(train)} | тест: {len(test)} | граница UTC: {cut}"]
    results=[]
    for i,label in enumerate(LABELS):
        candidates=[]
        for name in names:
            # Shrink calibration toward historical league prevalence; tune only on early period.
            for weight in (0,0.25,0.5,0.75,1):
                fn=lambda r,n=name,w=weight: w*r["p"][n][i]+(1-w)*r["p"]["league"][i]
                candidates.append((brier(train,i,fn),name,weight))
        _,name,w=min(candidates)
        fn=lambda r: w*r["p"][name][i]+(1-w)*r["p"]["league"][i]
        score=brier(test,i,fn); base=brier(test,i,lambda r:r["p"]["global"][i]); lg=brier(test,i,lambda r:r["p"]["league"][i])
        lines.append(f"{label}: {name}, вес {w:.2f}\nBrier тест: {score:.3f} | общий {base:.3f} | лига {lg:.3f}")
        for lo,hi in ((0.5,0.7),(0.7,0.8),(0.8,1.00001)):
            g=[r for r in test if lo<=fn(r)<hi]
            if g:
                wins=sum(r["y"][i] for r in g)
                lines.append(f"  {lo:.0%}–{min(hi,1):.0%}: {wins}/{len(g)} ({wins/len(g):.0%}), прогноз {sum(fn(r) for r in g)/len(g):.0%}")
        results.append(dict(market=label,model=name,weight=w,brier=score,global_brier=base,league_brier=lg))
    lines.append("Меньше Brier — лучше. Без коэффициентов прибыль неизвестна. V3 ежедневный прогноз не изменён.")
    with open("intelligence.json","w",encoding="utf-8") as f: json.dump(dict(cut=cut,results=results,rows=rows),f,ensure_ascii=False,indent=2)
    send(os.environ["TELEGRAM_CHAT_ID"],"\n".join(lines))
if __name__=="__main__": run()
