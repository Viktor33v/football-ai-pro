import json, os
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from bot import api, prob, send, MAX_GAMES, MIN_GAMES

LABELS=["ТБ 0.5 1Т","ТБ 1.5 1Т","ТБ 2.5","Обе забьют","ТБ 0.5 2Т"]
def run():
    today=datetime.now(timezone.utc).date()
    past={}
    for offset in range(1,211,7):
        for m in api("matches?dateFrom="+str(today-timedelta(days=offset+6))+"&dateTo="+str(today-timedelta(days=offset)))["matches"]:
            if m["status"]=="FINISHED": past[m["id"]]=m
    days=defaultdict(list)
    for m in past.values():
        if m["score"].get("duration") not in (None,"REGULAR"): continue
        f=m["score"]["fullTime"]; h=m["score"]["halfTime"]
        if any(v is None for v in [f["home"],f["away"],h["home"],h["away"]]): continue
        if f["home"]<h["home"] or f["away"]<h["away"]: continue
        days[m["utcDate"][:10]].append(m)
    stats=defaultdict(list); venue=defaultdict(list); records=[]; prior=[]
    def avg(team,side,j):
        allgames=stats[team][-MAX_GAMES:]; specific=venue[team,side][-10:]
        base=sum(v[j] for v in allgames)/len(allgames)
        return (sum(v[j] for v in specific)+4*base)/(len(specific)+4)
    for day,matches in sorted(days.items()):
        outcomes=[]
        for m in matches:
            a=m["homeTeam"]["id"]; b=m["awayTeam"]["id"]
            f=m["score"]["fullTime"]; h=m["score"]["halfTime"]
            ft=f["home"]+f["away"]; ht=h["home"]+h["away"]
            y=[int(ht>=1),int(ht>=2),int(ft>=3),int(min(f.values())>=1),int(ft-ht>=1)]
            outcomes.append(y)
            if min(len(stats[a]),len(stats[b]))<MIN_GAMES: continue
            home=(avg(a,"home",0)+avg(b,"away",1))/2
            away=(avg(b,"away",0)+avg(a,"home",1))/2
            half=(avg(a,"home",2)+avg(b,"away",3)+avg(a,"home",3)+avg(b,"away",2))/2
            p=[prob(half,1),prob(half,2),prob(home+away,3),prob(home,1)*prob(away,1),prob(max(0,home+away-half),1)]
            baseline=[(sum(z[i] for z in prior)+1)/(len(prior)+2) for i in range(5)]
            records.append({"id":m["id"],"date":day,"p":p,"y":y,"baseline":baseline})
        for m in matches:
            f=m["score"]["fullTime"]; h=m["score"]["halfTime"]
            for side,opp in (("home","away"),("away","home")):
                team=m[side+"Team"]["id"]; v=(f[side],f[opp],h[side],h[opp])
                stats[team].append(v); venue[team,side].append(v)
        prior.extend(outcomes)
    lines=["⚽ FOOTBALL AI PRO V4 • BACKTEST","Историческая проверка V3. Только результаты предыдущих UTC-дней используются для расчёта.","Матчей с прогнозом: "+str(len(records))]
    for i,label in enumerate(LABELS):
        n=len(records)
        if not n: break
        bs=sum((r["p"][i]-r["y"][i])**2 for r in records)/n
        base=sum((r["baseline"][i]-r["y"][i])**2 for r in records)/n
        lines.append(f"{label}: Brier {bs:.3f} / базовый {base:.3f}")
        for lo,hi in [(0.5,0.7),(0.7,0.8),(0.8,1.00001)]:
            group=[r for r in records if lo<=r["p"][i]<hi]
            if not group: continue
            wins=sum(r["y"][i] for r in group); count=len(group)
            mean=sum(r["p"][i] for r in group)/count
            lines.append(f"  {lo:.0%}–{min(hi,1):.0%}: {wins}/{count} ({wins/count:.0%}), средний прогноз {mean:.0%}")
    lines.append("Brier: меньше — лучше. Без исторических коэффициентов доходность неизвестна. Ретроспективный тест, не реальные ставки.")
    with open("backtest.json","w",encoding="utf-8") as f: json.dump({"labels":LABELS,"records":records},f,ensure_ascii=False,indent=2)
    send(os.environ["TELEGRAM_CHAT_ID"],"\n".join(lines))
if __name__=="__main__": run()
