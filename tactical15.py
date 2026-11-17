import json,os,re,math
from urllib.request import urlopen
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from datetime import datetime,timezone
from bot import send
from snapshot import save

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
    jobs=[]; seen=set(); sets=[]
    for x in get("competitions.json"):
        if x.get("competition_gender")!="male": continue
        if int(x["season_name"][:4])<2015: continue
        c,s=x["competition_id"],x["season_id"]
        ms=get(f"matches/{c}/{s}.json")
        sets.append([c,s,x["competition_name"],x["season_name"],len(ms)])
        for m in ms:
            if m["match_id"] not in seen:
                seen.add(m["match_id"]); jobs.append(((c,s),m))
    with ThreadPoolExecutor(max_workers=8) as pool: rows=[r for r in pool.map(match,jobs) if r is not None]
    if not rows: raise RuntimeError("No usable historic matches")
    pairs=defaultdict(list); baseline=defaultdict(list); days=defaultdict(list)
    errors=[[] for _ in LABELS]
    for group,day,a,b,y in rows: days[day].append((group,a,b,y))
    for day,rs in sorted(days.items()):
        for group,a,b,y in rs:
            hist=pairs[a,b]; base=baseline[group[0]]
            if len(hist)>=10 and len(base)>=15:
                for i,v in enumerate(y):
                    q=(sum(z[i] for z in base)+1)/(len(base)+2)
                    p=(sum(z[i] for z in hist)+20*q)/(len(hist)+20)
                    errors[i].append(((p-v)**2,(q-v)**2))
        for group,a,b,y in rs: pairs[a,b].append(y); baseline[group[0]].append(y)
    metrics=[dict(n=len(es),model=sum(x[0] for x in es)/len(es),baseline=sum(x[1] for x in es)/len(es)) if es else dict(n=0) for es in errors]
    data=dict(created=datetime.now(timezone.utc).isoformat(),n=len(rows),attempted=len(jobs),sets=sets,labels=LABELS,metrics=metrics,pairs=[dict(home=a,away=b,n=len(rs),hits=[sum(z[i] for z in rs) for i in range(len(LABELS))]) for (a,b),rs in pairs.items()])
    os.makedirs("state",exist_ok=True); save("state/tactical.json",data)
    lines=["⚽ V15 TACTICAL INTELLIGENCE • ИССЛЕДОВАНИЕ","StatsBomb Open Data https://github.com/hudl/open-data",f"Матчей {len(rows)}/{len(jobs)}; турниров/сезонов {len(sets)}.","Мужские турниры с 2015 года; доступные матчи, не обязательно полные сезоны.","Brier: схема / базовый по соревнованию"]
    for label,m in zip(LABELS,metrics):
        lines.append(f"{label}: {m['model']:.3f} / {m['baseline']:.3f} | n={m['n']}" if m["n"] else label+": мало данных")
    for r in sorted(data["pairs"],key=lambda r:r["n"],reverse=True)[:10]:
        lines.append(f"\n{'-'.join(r['home'])} — {'-'.join(r['away'])} | n={r['n']}")
        lines.extend(f"{l}: {h}/{r['n']} ({h/r['n']:.0%})" for l,h in zip(LABELS,r["hits"]))
    lines.append("Порядок хозяева/гости по протоколу, включая нейтральные поля. Частоты не прогнозы; поправки отключены.")
    chunk=""
    for line in lines:
        if len(chunk)+len(line)>3500: send(os.environ["TELEGRAM_CHAT_ID"],chunk); chunk=""
        chunk+=line+"\n"
    if chunk: send(os.environ["TELEGRAM_CHAT_ID"],chunk)
if __name__=="__main__": run()
