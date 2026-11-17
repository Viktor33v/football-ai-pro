import os, math, json, time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from datetime import timedelta, datetime, timezone
from collections import defaultdict

MAX_GAMES=20
MIN_GAMES=12
_last_request=0.0

def api(path):
    req = Request("https://api.football-data.org/v4/"+path, headers={"X-Auth-Token":os.environ["FOOTBALL_API_KEY"].strip()})
    global _last_request
    for attempt in range(2):
        time.sleep(max(0,6.5-(time.monotonic()-_last_request)))
        _last_request=time.monotonic()
        try:
            with urlopen(req, timeout=30) as r: return json.load(r)
        except HTTPError as e:
            if e.code!=429 or attempt: raise RuntimeError(f"Football API HTTP {e.code}") from None
            time.sleep(65)

def prob(lam,k):
    return 1-sum(math.exp(-lam)*lam**i/math.factorial(i) for i in range(k))

def send(chat,text):
    req=Request("https://api.telegram.org/bot"+os.environ["TELEGRAM_BOT_TOKEN"].strip()+"/sendMessage",data=json.dumps({"chat_id":chat.strip(),"text":text}).encode(),headers={"Content-Type":"application/json"})
    try:
        with urlopen(req,timeout=30) as r: return json.load(r)
    except HTTPError as e:
        raise RuntimeError(f"Telegram HTTP {e.code}") from None

def report():
    now=datetime.now(timezone.utc)
    today=now.date()
    past=[]
    for offset in range(1,211,7):
        past.extend(api("matches?dateFrom="+str(today-timedelta(days=offset+6))+"&dateTo="+str(today-timedelta(days=offset)))["matches"])
    upcoming=api("matches?dateFrom="+str(today)+"&dateTo="+str(today+timedelta(days=6)))["matches"]
    stats=defaultdict(list)
    venue=defaultdict(list)
    for m in sorted({m["id"]:m for m in past}.values(),key=lambda m:m["utcDate"]):
        if m["status"]!="FINISHED": continue
        f=m["score"]["fullTime"]; h=m["score"]["halfTime"]
        if any(v is None for v in [f["home"],f["away"],h["home"],h["away"]]): continue
        for side,opp in (("home","away"),("away","home")):
            team=m[side+"Team"]["id"]
            v=(f[side],f[opp],h[side],h[opp])
            stats[team].append(v); venue[team,side].append(v)
    rows=[]
    for m in upcoming:
        if m["status"] not in ("TIMED","SCHEDULED"): continue
        kickoff=datetime.fromisoformat(m["utcDate"].replace("Z","+00:00"))
        if kickoff<=now: continue
        a=m["homeTeam"]["id"]; b=m["awayTeam"]["id"]
        if min(len(stats[a]),len(stats[b]))<MIN_GAMES: continue
        def avg(team,side,j):
            allgames=stats[team][-MAX_GAMES:]; specific=venue[team,side][-10:]
            base=sum(v[j] for v in allgames)/len(allgames)
            return (sum(v[j] for v in specific)+4*base)/(len(specific)+4)
        home=(avg(a,"home",0)+avg(b,"away",1))/2
        away=(avg(b,"away",0)+avg(a,"home",1))/2
        half=(avg(a,"home",2)+avg(b,"away",3)+avg(a,"home",3)+avg(b,"away",2))/2
        p=[prob(half,1),prob(half,2),prob(home+away,3),prob(home,1)*prob(away,1),prob(max(0,home+away-half),1)]
        rows.append((m,kickoff,p,min(MAX_GAMES,len(stats[a])),min(MAX_GAMES,len(stats[b])),home,away))
    rows.sort(key=lambda r:r[2][0],reverse=True)
    lines=["⚽ FOOTBALL AI PRO V3 • ДЕМО","Горизонт: 7 календарных дней UTC. История: 210 дней; до 20 матчей на команду, минимум 12. Сортировка по ТБ 0.5 1Т. Вероятности модели не откалиброваны; это не гарантия.",f"Матчей от API: {len(upcoming)} | с достаточной выборкой: {len(rows)}"]
    labels=["ТБ 0.5 1Т","ТБ 1.5 1Т","ТБ 2.5","Обе забьют","ТБ 0.5 2Т"]
    records=[]
    for m,k,p,na,nb,h,a in rows:
        records.append({"id":m["id"],"kickoff":m["utcDate"],"home":m["homeTeam"]["name"],"away":m["awayTeam"]["name"],"p":dict(zip(labels,p)),"generated":now.isoformat(),"sample_home":na,"sample_away":nb,"model":"V3"})
    for m,k,p,na,nb,h,a in rows[:15]:
        local=k.astimezone(timezone(timedelta(hours=6)))
        lines.append(f'{m["homeTeam"]["name"]} — {m["awayTeam"]["name"]}\n{local:%d.%m %H:%M} Бишкек\n'+" | ".join(f"{l}: {v:.0%}" for l,v in zip(labels,p))+f"\nРасчётные голы модели: {h:.2f} / {a:.2f}\nВыборка: {na}/{nb}")
    if not rows: lines.append("Нет матчей с достаточной выборкой.")
    with open("predictions.json","w",encoding="utf-8") as f: json.dump(records,f,ensure_ascii=False,indent=2)
    return lines

if __name__=="__main__":
    lines=report()
    chat=os.environ["TELEGRAM_CHAT_ID"]
    chunk=""
    for line in lines:
        if len(chunk)+len(line)>3500:
            send(chat,chunk); chunk=""
        chunk+=line+"\n\n"
    if chunk: send(chat,chunk)
