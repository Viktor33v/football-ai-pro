import json,os,re
from urllib.request import urlopen
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from datetime import datetime,timezone
from bot import send

BASE="https://raw.githubusercontent.com/hudl/open-data/master/data/"
SETS=[(9,281),(43,106),(43,3),(55,282),(55,43)]
LABELS=["Гол 1Т","ТБ 1.5 1Т","ТБ 2.5","Угловые ТБ 8.5","Угловые ТБ 9.5","Угловые 1Т ТБ 3.5","ЖК ТБ 2.5","ЖК ТБ 3.5"]
def get(path):
    with urlopen(BASE+path,timeout=45) as r: return json.load(r)
def match(item):
    group,m=item
    try:
        ev=get("events/"+str(m["match_id"])+".json")
        home=m["home_team"]["home_team_id"]; away=m["away_team"]["away_team_id"]
        formations={e["team"]["id"]:str(e["tactics"]["formation"]) for e in ev if e["type"]["name"]=="Starting XI" and e.get("tactics",{}).get("formation")}
        if home not in formations or away not in formations: return None
        g=h=c=ch=y=0
        periods=set()
        for e in ev:
            p=e.get("period")
            if p not in (1,2): continue
            periods.add(p); t=e["type"]["name"]
            if (t=="Shot" and e.get("shot",{}).get("outcome",{}).get("name")=="Goal") or t=="Own Goal Against":
                g+=1; h+=p==1
            if t=="Pass" and e.get("pass",{}).get("type",{}).get("name")=="Corner":
                c+=1; ch+=p==1
            if t in ("Foul Committed","Bad Behaviour"):
                card=e.get("foul_committed",{}).get("card",{}) if t=="Foul Committed" else e.get("bad_behaviour",{}).get("card",{})
                y+=card.get("name") in ("Yellow Card","Second Yellow")
        if periods!={1,2}: return None
        if not m.get("match_status")=="available": return None
        return group,m["match_date"],formations[home],formations[away],[int(x) for x in (h>=1,h>=2,g>=3,c>=9,c>=10,ch>=4,y>=3,y>=4)]
    except Exception: return None
def run():
    jobs=[]
    for c,s in SETS:
        jobs.extend(((c,s),m) for m in get(f"matches/{c}/{s}.json"))
    with ThreadPoolExecutor(max_workers=6) as pool: rows=[r for r in pool.map(match,jobs) if r is not None]
    if not rows: raise RuntimeError("No usable historic matches")
    pairs=defaultdict(list); baseline=defaultdict(list); errors=[[],[]]; days=defaultdict(list)
    for group,day,a,b,y in rows: days[day].append((group,a,b,y))
    for day,rs in sorted(days.items()):
        for group,a,b,y in rs:
            hist=pairs[a,b]; base=baseline[group]
            if len(hist)>=10 and len(base)>=15:
                for i,v in enumerate(y):
                    q=(sum(z[i] for z in base)+1)/(len(base)+2)
                    p=(sum(z[i] for z in hist)+20*q)/(len(hist)+20)
                    errors[0].append((p-v)**2); errors[1].append((q-v)**2)
        for group,a,b,y in rs: pairs[a,b].append(y); baseline[group].append(y)
    lines=["⚽ V14 TACTICAL MASTER • ИССЛЕДОВАНИЕ","Источник: StatsBomb Open Data https://github.com/hudl/open-data","Исторические турниры и Бундеслига 2023/24; не текущие составы.",f"Матчей: {len(rows)}/{len(jobs)}; пропущено {len(jobs)-len(rows)}"]
    if errors[0]: lines.append(f"Хронологический тест: {len(errors[0])//len(LABELS)} матчей; Brier {sum(errors[0])/len(errors[0]):.3f} / базовый {sum(errors[1])/len(errors[1]):.3f}")
    def fmt(s): return "-".join(s)
    for (a,b),rs in sorted(pairs.items(),key=lambda kv:len(kv[1]),reverse=True)[:10]:
        if len(rs)<10: continue
        lines.append(f"\n{fmt(a)} — {fmt(b)} | n={len(rs)}")
        lines.extend(f"{label}: {sum(z[i] for z in rs)}/{len(rs)} ({sum(z[i] for z in rs)/len(rs):.0%})" for i,label in enumerate(LABELS))
    lines.append("Только основное время; ЖК по событиям, возможны отличия правил подсчёта. Частоты не прогнозы. Влияние схем не причинное; текущая модель не изменена.")
    chunk=""
    for line in lines:
        if len(chunk)+len(line)>3500: send(os.environ["TELEGRAM_CHAT_ID"],chunk); chunk=""
        chunk+=line+"\n"
    if chunk: send(os.environ["TELEGRAM_CHAT_ID"],chunk)
if __name__=="__main__": run()
