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
ALIASES={"бавария":"bayern","кёльн":"koln","кельн":"koln","барселона":"barcelona","реал мадрид":"real madrid","реал":"real","атлетико":"atletico","арсенал":"arsenal","челси":"chelsea","ливерпуль":"liverpool","манчестер сити":"manchester city","манчестер юнайтед":"manchester united","тоттенхэм":"tottenham","псж":"paris saint","боруссия":"borussia","дортмунд":"dortmund","ювентус":"juventus","интер":"inter","милан":"milan","наполи":"napoli","псв":"psv","аякс":"ajax","фейеноорд":"feyenoord","утрехт":"utrecht","вильярреал":"villarreal","бетис":"betis","гетафе":"getafe","валенсия":"valencia","севилья":"sevilla","лейпциг":"leipzig","байер":"leverkusen","штутгарт":"stuttgart","аугсбург":"augsburg","майнц":"mainz","эвертон":"everton","брентфорд":"brentford"}
MENU={"Сегодня":"/today","Завтра":"/tomorrow","Топ-10":"/top","Голы":"/goals","Угловые":"/corners","Карточки":"/cards","Статистика":"/stats","Помощь":"/help","Форма":"/form","Тактика":"/tactic","Анализ матча":"/analyze"}
def keyboard():
    return {"keyboard":[[{"text":x} for x in row] for row in [("Сегодня","Завтра","Топ-10"),("Голы","Угловые","Карточки"),("Статистика","Форма","Тактика"),("Анализ матча","Помощь")]],"resize_keyboard":True}
def canonical(s):
    return " ".join(norm(s).split())
def query_match(q,r):
    q=canonical(q)
    parts=q.replace(" — "," - ").replace(" – "," - ").split(" - ")
    names=canonical(r["home"]+" — "+r["away"])
    return all(canonical(ALIASES.get(x.strip(),x.strip())) in names for x in parts)
def reconcile(rows):
    # Exact ordered team names only. A unique nearby goal fixture supplies kickoff.
    index={}
    for r in rows:
        if r.get("kickoff"):
            key=(canonical(r["home"]),canonical(r["away"]))
            index.setdefault(key,set()).add(r["kickoff"])
    result=[]
    for row in rows:
        r=dict(row)
        if not r.get("kickoff"):
            key=(canonical(r["home"]),canonical(r["away"]))
            options=[k for k in index.get(key,set()) if abs((datetime.fromisoformat(k).date()-datetime.fromisoformat(r["date"]).date()).days)<=1]
            if len(options)==1:
                r["kickoff"]=options[0]; r["matched"]=True
        result.append(r)
    return result
def team_form(q):
    data=load("state/form.json",{})
    if not data: return "База формы ещё не создана. Запусти V10."
    q=canonical(q); q=canonical(ALIASES.get(q,q))
    if not q: return "Пример: /form Бавария"
    teams=[t for t in data["teams"] if q in canonical(t["name"])]
    lines=["⚽ V13 • Форма команды","Источник: "+data["source"],"Данные на "+data["created"][:10]+" UTC. Только завершённые матчи лиги."]
    for t in teams[:5]:
        rs=t["matches"]; n=len(rs)
        lines.append("\n"+t["name"]+" | "+t["league"])
        lines.append(f"Последние {n}: "+ " ".join("В" if r["g"]>r["c"] else "Н" if r["g"]==r["c"] else "П" for r in rs))
        for r in rs:
            lines.append(f'{r["date"]} | {r["opponent"]} | {r["g"]}:{r["c"]} ({ "дома" if r["venue"]=="home" else "в гостях"})')
        for key,label in [("g","Голы"),("c","Пропущено"),("shots","Удары"),("target","В створ"),("corners","Угловые"),("yellow","ЖК")]:
            vals=[r[key] for r in rs if r[key] is not None]
            lines.append(f"{label}: "+(f"{sum(vals)/len(vals):.1f} ({len(vals)}/{n})" if vals else "нет данных"))
    if not teams: lines.append("Команда не найдена. Попробуй латиницей.")
    if len(teams)>5: lines.append("Уточни название команды.")
    lines.append("Схемы, травмы и судьи пока недоступны. Форма не меняет вероятности модели.")
    return "\n".join(lines)
def tactic(q):
    data=load("state/tactical.json",{})
    if not data: return "База тактики ещё не создана. Запусти V15."
    lines=["⚽ V15 • История схем",f"Матчей в базе: {data['n']}","StatsBomb Open Data https://github.com/hudl/open-data","Частоты, не прогнозы. Порядок хозяева/гости."]
    if not q:
        lines.append("Пример: /tactic 4-3-3 4-2-3-1")
        for r in sorted(data["pairs"],key=lambda r:r["n"],reverse=True)[:10]:
            lines.append(f"{'-'.join(r['home'])} — {'-'.join(r['away'])}: {r['n']} матчей")
        return "\n".join(lines)
    parts=[x.replace("-","") for x in q.split()]
    if len(parts)!=2 or any(not x.isascii() or not x.isdigit() or sum(map(int,x))!=10 for x in parts): return "Пример: /tactic 4-3-3 4-2-3-1"
    rs=[r for r in data["pairs"] if [r["home"],r["away"]]==parts]
    if not rs: return "\n".join(lines+["Нет наблюдений для этой пары."])
    r=rs[0]; n=r["n"]
    lines.append(f"{q} | n={n}")
    if n<30: lines.append("Малая выборка: менее 30 матчей.")
    for l,h in zip(data["labels"],r["hits"]):
        lines.append(f"{l}: {h}/{n} ({h/n:.0%})")
    return "\n".join(lines)
def analyze(arg):
    q,_,schemes=arg.partition(";")
    q=q.strip(); schemes=schemes.strip()
    if not q: return "Пример: /analyze Бавария - Кёльн; 4-3-3 4-2-3-1"
    snap=load("state/snapshot.json",{})
    if not snap: return "База отсутствует. Запусти V10."
    now=datetime.now(timezone.utc); local=timezone(timedelta(hours=6))
    groups={}
    for r in reconcile(snap["rows"]):
        if not query_match(q,r): continue
        k=r.get("kickoff")
        if k and datetime.fromisoformat(k)<=now: continue
        if not k and r["date"]<=now.date().isoformat(): continue
        key=(canonical(r["home"]),canonical(r["away"]),k or r["date"])
        groups.setdefault(key,[]).append(r)
    if not groups: return "Будущий матч не найден в снимке. Проверь названия или обнови V10."
    if len(groups)>1:
        return "Уточни матч:\n"+"\n".join(f"{rs[0]['home']} — {rs[0]['away']} | {key[2]}" for key,rs in list(groups.items())[:12])
    key,rs=next(iter(groups.items())); a=rs[0]
    stamp=datetime.fromisoformat(a["kickoff"]).astimezone(local).strftime("%d.%m %H:%M Бишкек") if a.get("kickoff") else a["date"]+" (время неизвестно)"
    lines=["⚽ V16 MATCH ANALYZER • ДЕМО",a["home"]+" — "+a["away"],stamp,"Снимок: "+snap["created"],"Расписание независимо не проверено.","","ФОРМА: последние 5 матчей лиги"]
    form=load("state/form.json",{})
    for side in ("home","away"):
        teams=[t for t in form.get("teams",[]) if canonical(t["name"])==canonical(a[side])]
        leagues={r["league"] for r in rs if r.get("league")}
        if leagues: teams=[t for t in teams if t["league"] in leagues]
        lines.append(a[side])
        if len(teams)!=1:
            lines.append("Нет однозначных данных"); continue
        ms=teams[0]["matches"]; n=len(ms)
        lines.append(" ".join(f"{'В' if m['g']>m['c'] else 'Н' if m['g']==m['c'] else 'П'} {m['g']}:{m['c']}" for m in ms))
        for field,label in [("g","Голы"),("c","Пропущено"),("shots","Удары"),("target","В створ"),("corners","Угловые"),("yellow","ЖК")]:
            v=[m[field] for m in ms if m.get(field) is not None]
            lines.append(f"{label}: {sum(v)/len(v):.1f} ({len(v)}/{n})" if v else label+": нет данных")
    lines.append("\nРЫНКИ: вероятности отдельных моделей")
    by={}
    for r in rs: by.setdefault((r["group"],r["market"]),[]).append(r)
    clean=[]
    for (g,m), rr in by.items():
        if len(rr)!=1: lines.append(m+": неоднозначные данные"); continue
        r=rr[0]; clean.append(r)
        sample=r.get("sample")
        lines.append(f"{m}: {r['p']:.1%}"+(f" | выборка {sample}" if sample else ""))
    lines.append(f"Покрытие: {len(clean)}/13. Это полнота данных, не гарантия точности.")
    lines.append("\nТРИ РЫНКА ДЛЯ ДЕМО-НАБЛЮДЕНИЯ (по p, не по доходности)")
    for r in sorted([r for r in clean if r["selected"]],key=lambda r:r["p"],reverse=True)[:3]:
        lines.append(f"{r['market']}: {r['p']:.1%}")
    if not any(r["selected"] for r in clean): lines.append("Нет рынков выше порогов.")
    lines.append("\nТАКТИКА")
    lines.append("Схемы введены вручную, не подтверждены." if schemes else "Составы не подключены. Добавь после точки с запятой две схемы хозяев/гостей.")
    if schemes: lines.append(tactic(schemes))
    lines.append("Нет учёта судей, травм или букмекерских коэффициентов. Тактика и форма не изменяют p. Не экспресс.")
    return "\n".join(lines)
def answer(msg):
    msg=MENU.get(msg.strip(),msg)
    local=timezone(timedelta(hours=6)); now=datetime.now(timezone.utc)
    cmd,_,arg=msg.strip().partition(" "); cmd=cmd.split("@")[0].lower()
    helptext="⚽ V16 MATCH ANALYZER • ДЕМО\n/today — сегодня\n/tomorrow — завтра\n/top — 10 по вероятности\n/goals — голы\n/corners — угловые\n/cards — ЖК\n/stats — журнал\n/match Arsenal — поиск по названию (русский или латиница)\nОтветы при очередном запуске обработчика."
    if cmd in ("/start","/help"): return helptext+"\n/form Бавария — последние 5 матчей\n/tactic 4-3-3 4-2-3-1 — история схем\n/analyze Бавария - Кёльн — полный анализ"
    if cmd=="/analyze": return analyze(arg)
    if cmd=="/tactic": return tactic(arg.strip())
    if cmd=="/form": return team_form(arg.strip())
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
    rs=[r for r in reconcile(snap["rows"]) if (datetime.fromisoformat(r["kickoff"])>now if r.get("kickoff") else r["date"]>now.date().isoformat())]
    if cmd=="/match" or not cmd.startswith("/"):
        q=arg.strip() if cmd=="/match" else msg.strip()
        if not q: return "Пример: /match Bayern"
        rs=[r for r in rs if query_match(q,r)]
    elif cmd in ("/today","/tomorrow"):
        target=(now.astimezone(local).date()+timedelta(days=cmd=="/tomorrow")).isoformat()
        rs=[r for r in rs if r.get("kickoff") and day(r)==target and r["selected"]]
    elif cmd in ("/goals","/corners","/cards"):
        rs=[r for r in rs if r["group"]==cmd[1:] and r["selected"]]
    elif cmd=="/top":
        rs=[r for r in rs if r["selected"]]
    else: return helptext
    lines=["⚽ V13 • ДЕМО","Снимок: "+snap["created"]+" UTC","Вероятности не являются доказательством прибыльности.","Время Бишкек для совпавших матчей; остальные даты из CSV не подтверждены."]
    for r in sorted(rs,key=lambda r:r["p"],reverse=True)[:(25 if cmd=="/match" else 10)]:
        stamp=datetime.fromisoformat(r["kickoff"]).astimezone(local).strftime("%d.%m %H:%M") if r.get("kickoff") else r["date"]+" (время неизвестно)"
        lines.append(f'{stamp} | {r["home"]} — {r["away"]}\n{r["market"]}: {r["p"]:.1%}')
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
                for i in range(0,len(text),3500): telegram("sendMessage",chat_id=chat,text=text[i:i+3500],reply_markup=keyboard())
            offset=u["update_id"]+1
    if offset is not None: telegram("getUpdates",offset=offset,timeout=0,limit=1,allowed_updates=["message"])
if __name__=="__main__": run()
