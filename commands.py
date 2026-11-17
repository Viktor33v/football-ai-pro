import os,json,unicodedata
from urllib.request import urlopen,Request
from datetime import datetime,timezone,timedelta
from snapshot import load
from backtest import LABELS

def telegram(method,**params):
    try:
        url="https://api.telegram.org/bot"+os.environ["TELEGRAM_BOT_TOKEN"]+"/"+method
        with urlopen(Request(url,data=json.dumps(params).encode(),headers={"Content-Type":"application/json"}),timeout=20) as r:
            out=json.load(r)
        if not out.get("ok"): raise RuntimeError()
        return out["result"]
    except Exception: raise RuntimeError("Telegram API request failed") from None
def norm(s):
    return "".join(c for c in unicodedata.normalize("NFKD",s.casefold()) if not unicodedata.combining(c))
def answer(msg):
    local=timezone(timedelta(hours=6)); now=datetime.now(timezone.utc)
    cmd,_,arg=msg.strip().partition(" "); cmd=cmd.split("@")[0].lower()
    helptext="⚽ V11 SMART FILTER • ДЕМО\n/today — сегодня\n/tomorrow — завтра\n/top — 10 по вероятности\n/goals — голы\n/corners — угловые\n/cards — ЖК\n/stats — журнал\n/match Arsenal — поиск по названию (латиницей)\nОтветы при очередном запуске обработчика."
    if cmd in ("/start","/help"): return helptext
    if cmd=="/stats":
        rows=list(load("state/extra_journal.json",{}).values())
        for r in load("state/journal.json",{}).values():
            rows.append(dict(market=LABELS[r["market"]],date=r["kickoff"][:10],result=r["result"]))
        lines=["📊 Демо-журнал: первый сохранённый прогноз"]
        for d in (7,30,90):
            start=(now.date()-timedelta(days=d-1)).isoformat()
            lines.append(f"За {d} дней (UTC):")
            for market in sorted({r["market"] for r in rows}):
                rs=[r for r in rows if r["market"]==market and start<=r["date"]<=now.date().isoformat()]
                done=[r for r in rs if r["result"] is not None]
                lines.append(f"{market}: {sum(r['result'] for r in done)}/{len(done)}; ожидают {len(rs)-len(done)}")
        return "\n".join(lines)
    snap=load("state/snapshot.json",{})
    if not snap: return "База ещё не создана. Запусти V10 для обновления."
    def day(r):
        return datetime.fromisoformat(r["kickoff"]).astimezone(local).date().isoformat() if r.get("kickoff") else r["date"]
    rs=[r for r in snap["rows"] if (datetime.fromisoformat(r["kickoff"])>now if r.get("kickoff") else r["date"]>now.date().isoformat())]
    if cmd=="/match" or not cmd.startswith("/"):
        q=arg.strip() if cmd=="/match" else msg.strip()
        if not q: return "Пример: /match Bayern"
        rs=[r for r in rs if norm(q) in norm(r["home"]+" — "+r["away"])]
    elif cmd in ("/today","/tomorrow"):
        target=(now.astimezone(local).date()+timedelta(days=cmd=="/tomorrow")).isoformat()
        rs=[r for r in rs if day(r)==target and r["selected"]]
    elif cmd in ("/goals","/corners","/cards"):
        rs=[r for r in rs if r["group"]==cmd[1:] and r["selected"]]
    elif cmd=="/top":
        rs=[r for r in rs if r["selected"]]
    else: return helptext
    lines=["⚽ V11 • ДЕМО","Снимок: "+snap["created"]+" UTC","Вероятности не являются доказательством прибыльности."]
    for r in sorted(rs,key=lambda r:r["p"],reverse=True)[:(25 if cmd=="/match" else 10)]:
        lines.append(f'{day(r)} | {r["home"]} — {r["away"]}\n{r["market"]}: {r["p"]:.1%}')
    if not rs: lines.append("Нет подходящих будущих прогнозов в базе.")
    return "\n".join(lines)
def run():
    chat=int(os.environ["TELEGRAM_CHAT_ID"])
    offset=None
    # Telegram acknowledges updates on the next higher-offset request.
    for _ in range(5):
        args=dict(timeout=0,limit=100,allowed_updates=["message"])
        if offset is not None: args["offset"]=offset
        updates=telegram("getUpdates",**args)
        if not updates: break
        for u in updates:
            m=u.get("message",{})
            if m.get("chat",{}).get("id")==chat and m.get("chat",{}).get("type")=="private" and isinstance(m.get("text"),str):
                text=answer(m["text"])
                for i in range(0,len(text),3500): telegram("sendMessage",chat_id=chat,text=text[i:i+3500])
            offset=u["update_id"]+1
    if offset is not None: telegram("getUpdates",offset=offset,timeout=0,limit=1,allowed_updates=["message"])
if __name__=="__main__": run()
