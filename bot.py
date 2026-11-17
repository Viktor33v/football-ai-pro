import os, math, json
from urllib.request import Request, urlopen
from datetime import date, timedelta, datetime, timezone
from collections import defaultdict
def api(path):
    req = Request("https://api.football-data.org/v4/"+path, headers={"X-Auth-Token":os.environ["FOOTBALL_API_KEY"]})
    with urlopen(req,timeout=30) as r: return json.load(r)
def prob(lam,k):
    return 1-sum(math.exp(-lam)*lam**i/math.factorial(i) for i in range(k))
def send(chat,text):
    req=Request("https://api.telegram.org/bot"+os.environ["TELEGRAM_BOT_TOKEN"]+"/sendMessage",data=json.dumps({"chat_id":chat,"text":text}).encode(),headers={"Content-Type":"application/json"})
    with urlopen(req,timeout=30) as r: return json.load(r)
def report():
    today=date.today()
    past=api("matches?dateFrom="+str(today-timedelta(days=90))+"&dateTo="+str(today-timedelta(days=1)))["matches"]
    upcoming=api("matches?dateFrom="+str(today)+"&dateTo="+str(today+timedelta(days=1)))["matches"]
    stats=defaultdict(list)
    for m in past:
        if m["status"]!="FINISHED": continue
        f=m["score"]["fullTime"]; h=m["score"]["halfTime"]
        if any(v is None for v in [f["home"],f["away"],h["home"],h["away"]]): continue
        stats[m["homeTeam"]["id"]].append((f["home"],f["away"],h["home"],h["away"]))
        stats[m["awayTeam"]["id"]].append((f["away"],f["home"],h["away"],h["home"]))
    lines=["⚽ FOOTBALL AI PRO V1 • ДЕМО","Базовая модель Пуассона. Не проверена на истории."]
    for m in upcoming:
        if m["status"] not in ("TIMED","SCHEDULED"): continue
        if datetime.fromisoformat(m["utcDate"].replace("Z","+00:00")) <= datetime.now(timezone.utc): continue
        a=stats[m["homeTeam"]["id"]]; b=stats[m["awayTeam"]["id"]]
        if min(len(a),len(b))<5: continue
        avg=lambda x,j:sum(v[j] for v in x)/len(x)
        full=(sum(avg(a,j)+avg(b,j) for j in (0,1)))/2
        half=(sum(avg(a,j)+avg(b,j) for j in (2,3)))/2
        lines.append(f'{m["homeTeam"]["name"]} — {m["awayTeam"]["name"]}\nТБ 0.5 1Т: {prob(half,1):.0%} | ТБ 1.5 1Т: {prob(half,2):.0%} | ТБ 2.5: {prob(full,3):.0%}\nМатчей в выборке: {len(a)}/{len(b)}')
    if len(lines)==2: lines.append("Нет матчей с достаточной выборкой.")
    return lines
if __name__=="__main__":
    lines=report()
    chat=os.environ.get("TELEGRAM_CHAT_ID")
    if not chat:
        print("Football API: OK; set TELEGRAM_CHAT_ID to enable delivery.")
    else:
        chunk=""
        for line in lines:
            if len(chunk)+len(line)>3500:
                send(chat,chunk); chunk=""
            chunk+=line+"\n\n"
        if chunk: send(chat,chunk)
