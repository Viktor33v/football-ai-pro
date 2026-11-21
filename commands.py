import os,json,unicodedata,html,time
from urllib.request import urlopen,Request
from datetime import datetime,timezone,timedelta
from snapshot import load
from backtest import LABELS
from reliability26 import calibration_summary, reliability, baseline_evidence

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
MENU={"Сегодня":"/today","Завтра":"/tomorrow","Топ-10":"/top","Голы":"/goals","Угловые":"/corners","Карточки":"/cards","Статистика":"/stats","Помощь":"/help","Форма":"/form","Тактика":"/tactic","Анализ матча":"/analyze","Лучшие сегодня":"/best","Все прогнозы":"/all","Лучшие прогнозы":"/best","Состояние":"/status"}
def keyboard():
    return {"keyboard":[[{"text":x} for x in row] for row in [("Сегодня","Завтра","Топ-10"),("Голы","Угловые","Карточки"),("Статистика","Форма","Тактика"),("Анализ матча","Все прогнозы","Лучшие прогнозы"),("Состояние","Помощь")]],"resize_keyboard":True}
def canonical(s):
    return " ".join(norm(s).split())
def query_match(q,r):
    import re
    q=canonical(q)
    parts=[x.strip() for x in re.split(r"\s*[-‐‑‒–—−]\s*",q) if x.strip()]
    aliases={canonical(k):canonical(v) for k,v in ALIASES.items()}
    names=canonical(r["home"]+" — "+r["away"])
    return bool(parts) and all(aliases.get(x,x) in names for x in parts)
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
    q,_,window=canonical(q).partition(";"); q=q.strip()
    q={canonical(k):v for k,v in ALIASES.items()}.get(q,q)
    if window.strip() not in ("","5","10","20"): return "Пример: /form Бавария; 10"
    limit=int(window.strip() or "5")
    if not q: return "Пример: /form Бавария"
    teams=[t for t in data["teams"] if q in canonical(t["name"])]
    lines=["⚽ V13 • Форма команды","Источник: "+data["source"],"Данные на "+data["created"][:10]+" UTC. Только завершённые матчи лиги."]
    for t in teams[:5]:
        rs=t["matches"][-limit:]; n=len(rs)
        lines.append("\n"+t["name"]+" | "+t["league"])
        lines.append(f"Доступно {n} из {limit}: "+ " ".join("В" if r["g"]>r["c"] else "Н" if r["g"]==r["c"] else "П" for r in rs))
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
def reasons(r,snap):
    d=snap.get("diagnostics",{}).get(r["market"],{})
    out=[]
    if not r["selected"]: out.append("ниже порога p")
    if min(r.get("sample") or [0])<10: out.append("выборка <10 или неизвестна")
    if d.get("n",0)<100: out.append("мало тестов или нет метрик")
    elif d["model"]>=d["baseline"]: out.append("Brier не лучше базы")
    return out
def eligible(r,snap):
    return not reasons(r,snap)
def odds(arg):
    try:
        p,k=map(float,arg.replace(",",".").split())
        if not (0<p<=100 and 1<k<=1000): raise ValueError()
    except ValueError: return "Пример: /odds 73.5 1.50"
    p/=100
    return f"ДЕМО: p={p:.1%}; коэффициент {k:.2f}\nБезубыточный коэффициент {1/p:.2f}\nРасчётное ожидание {p*k-1:+.1%}\nВероятность введена вручную, преимущество не подтверждено."
def half_report():
    d=load("state/half_shadow.json",{})
    if not d: return "Запусти V10 для расчёта V17."
    lines=["V17 • эксперимент первого тайма",d["created"]]
    for label,m in zip(LABELS[:2],d["metrics"]):
        lines.append(f"{label}: Brier {m['model']:.3f} / {m['baseline']:.3f}; n={m['n']}" if m["n"] else label+": нет теста")
    lines.append("Исследовательский тест. Основная модель не изменена.")
    return "\n".join(lines)

def history_summary(a):
    hist=load("state/history.json",{})
    rows=hist.get("rows",[])
    lines=["ИСТОРИЯ V20 • только результаты OpenFootball"]
    for side in ("home","away"):
        name=canonical(a[side])
        games=[]
        for r in rows:
            h,v=canonical(r["home"]),canonical(r["away"])
            if h==name: games.append((r["date"],"home",*r["ft"]))
            elif v==name: games.append((r["date"],"away",*reversed(r["ft"])))
        games.sort()
        lines.append(a[side])
        for n in (5,10,20):
            ms=games[-n:]
            if ms: lines.append(f"Последние {len(ms)}/{n}: голы {sum(m[2] for m in ms)/len(ms):.2f}, пропущено {sum(m[3] for m in ms)/len(ms):.2f}")
        ms=[m for m in games if m[1]==side][-10:]
        if ms: lines.append(f"На нужном поле ({len(ms)}): голы {sum(m[2] for m in ms)/len(ms):.2f}, пропущено {sum(m[3] for m in ms)/len(ms):.2f}")
        if games: lines.append("Последняя дата архива: "+games[-1][0])
        else: lines.append("Нет точного совпадения названия.")
    matches=[r for r in rows if {canonical(r["home"]),canonical(r["away"])}=={canonical(a["home"]),canonical(a["away"])}][-10:]
    lines.append(f"Очные встречи: {len(matches)}")
    if matches:
        lines.append(f"Средний тотал: {sum(sum(r['ft']) for r in matches)/len(matches):.2f}; ТБ 2.5: {sum(sum(r['ft'])>=3 for r in matches)}/{len(matches)}")
    lines.append("Архив неполный; статистика не меняет вероятности.")
    return "\n".join(lines)

def analyze(arg):
    q,_,schemes=arg.partition(";")
    q=q.strip(); schemes=schemes.strip()
    if not q: return "Пример: /analyze Бавария - Кёльн; 4-3-3 4-2-3-1"
    snap=load("state/snapshot.json",{})
    if not snap: return "База отсутствует. Запусти V10."
    now=datetime.now(timezone.utc); local=timezone(timedelta(hours=6))
    if (now-datetime.fromisoformat(snap["created"])).total_seconds()>108000: return "Снимок старше 30 часов. Обнови базу."
    groups={}
    for r in reconcile(snap["rows"]):
        if not query_match(q,r): continue
        k=r.get("kickoff")
        if k and datetime.fromisoformat(k)<=now: continue
        if not k and r["date"]<=now.date().isoformat(): continue
        key=(canonical(r["home"]),canonical(r["away"]),k or r["date"])
        groups.setdefault(key,[]).append(r)
    if not groups: return "Матч не найден среди доступных будущих встреч. Возможные причины: чемпионат не поддерживается источником, матч вне горизонта прогноза или название не распознано. /status — состояние базы."
    if len(groups)>1:
        return "Уточни матч:\n"+"\n".join(f"{rs[0]['home']} — {rs[0]['away']} | {key[2]}" for key,rs in list(groups.items())[:12])
    key,rs=next(iter(groups.items())); a=rs[0]
    stamp=datetime.fromisoformat(a["kickoff"]).astimezone(local).strftime("%d.%m %H:%M Бишкек") if a.get("kickoff") else a["date"]+" (время неизвестно)"
    lines=["⚽ Football AI PRO • Подробный анализ • ДЕМО",a["home"]+" — "+a["away"],stamp,"Снимок: "+snap["created"],"Расписание независимо не проверено.","","ФОРМА: последние 5 матчей лиги"]
    form=load("state/form.json",{})
    for side in ("home","away"):
        teams=[t for t in form.get("teams",[]) if canonical(t["name"])==canonical(a[side])]
        leagues={r["league"] for r in rs if r.get("league")}
        if leagues: teams=[t for t in teams if t["league"] in leagues]
        lines.append(a[side])
        if len(teams)!=1:
            lines.append("Нет однозначных данных"); continue
        ms=teams[0]["matches"][-5:]; n=len(ms)
        lines.append(" ".join(f"{'В' if m['g']>m['c'] else 'Н' if m['g']==m['c'] else 'П'} {m['g']}:{m['c']}" for m in ms))
        for field,label in [("g","Голы"),("c","Пропущено"),("shots","Удары"),("target","В створ"),("corners","Угловые"),("yellow","ЖК")]:
            v=[m[field] for m in ms if m.get(field) is not None]
            lines.append(f"{label}: {sum(v)/len(v):.1f} ({len(v)}/{n})" if v else label+": нет данных")
    lines.append("\n"+history_summary(a))
    lines.append("\nРЫНКИ: вероятности отдельных моделей")
    by={}
    for r in rs: by.setdefault((r["group"],r["market"]),[]).append(r)
    clean=[]
    descriptions=[
        ("goals","ТБ 0.5 1Т","1+ гол до перерыва"),
        ("goals","ТБ 1.5 1Т","2+ гола до перерыва"),
        ("goals","ТБ 2.5","3+ гола за матч"),
        ("goals","Обе забьют","Каждая команда забьёт"),
        ("goals","ТБ 0.5 2Т","1+ гол после перерыва"),
        ("corners","Угловые ТБ 8.5","9+ угловых за матч"),
        ("corners","Угловые ТБ 9.5","10+ угловых за матч"),
        ("corners","Угловые 1Т ТБ 3.5","4+ угловых до перерыва"),
        ("cards","ЖК ТБ 2.5","3+ ЖК за матч"),
        ("cards","ЖК ТБ 3.5","4+ ЖК за матч"),
        ("cards","ЖК ТБ 4.5","5+ ЖК за матч"),
        ("cards","ЖК хозяев ТБ 1.5","2+ ЖК хозяев"),
        ("cards","ЖК гостей ТБ 1.5","2+ ЖК гостей")]
    lines.append("Рынок | Вероятность | Фильтр")
    for g,m,meaning in descriptions:
        rr=by.get((g,m),[])
        if len(rr)!=1:
            lines.append(f"{m} | — | —")
            lines.append("↳ "+meaning+"; "+("нет данных" if not rr else "неоднозначные данные"))
            continue
        r=rr[0]; clean.append(r)
        sample=r.get("sample")
        why=reasons(r,snap)
        lines.append(f"{m} | {r['p']:.1%} | "+("нет" if why else "да"))
        if g=="goals" and m=="ТБ 2.5":
            under=1-r["p"]
            lines.append(f"ТМ 2.5 | {under:.1%} | обзор (0–2 гола)")
            side="ТБ 2.5" if r["p"]>0.5 else "ТМ 2.5" if under>0.5 else "равные вероятности"
            lines.append(f"Более вероятный исход модели: {side}; не сигнал доходности.")
        lines.append("↳ "+meaning+(f"; выборка {sample}" if sample else ""))
        if why: lines.append("Причина: "+"; ".join(why))
    lines.append(f"Покрытие: {len(clean)}/13. Это полнота данных, не гарантия точности.")
    lines.append("\nФИЛЬТР ДЕМО: 10 матчей каждой команды, 100 тестовых, Brier лучше базы")
    for r in sorted([r for r in clean if eligible(r,snap)],key=lambda r:r["p"],reverse=True)[:3]:
        lines.append(f"{r['market']}: {r['p']:.1%}")
    if not any(eligible(r,snap) for r in clean): lines.append("Нет рынков, прошедших фильтр.")
    for r in clean:
        d=snap.get("diagnostics",{}).get(r["market"],{})
        if d: lines.append(f"{r['market']}: Brier {d['model']:.4f}/{d['baseline']:.4f}; n={d['n']}")
    for row in load("state/half_shadow.json",{}).get("rows",[]):
        if row["kickoff"]==a.get("kickoff") and canonical(row["home"])==canonical(a["home"]) and canonical(row["away"])==canonical(a["away"]):
            lines.append(f"Эксперимент 1Т: {row['p'][0]:.1%} / {row['p'][1]:.1%}")
    lines.append("\nТАКТИКА")
    lines.append("Схемы введены вручную, не подтверждены." if schemes else "Составы не подключены. Добавь после точки с запятой две схемы хозяев/гостей.")
    if schemes: lines.append(tactic(schemes))
    lines.append("Нет учёта судей, травм или букмекерских коэффициентов. Тактика и форма не изменяют p. Не экспресс.")
    return "\n".join(lines)
def status_report():
    s=load("state/snapshot.json",{}); f=load("state/form.json",{})
    if not s: return "База отсутствует."
    age=(datetime.now(timezone.utc)-datetime.fromisoformat(s["created"])).total_seconds()/3600
    return "\n".join(["Football AI PRO • статус",f"Снимок: {s['created']}",f"Возраст: {age:.1f} ч",f"Рынков с метриками: {len(s.get('diagnostics',{}))}/13",f"Команд с формой: {len(f.get('teams',[]))}","ВНИМАНИЕ: данные старше 30 часов" if age>30 else "Возраст снимка в пределах 30 часов","Даты матчей независимо не подтверждены. Демо."])
def h2h_local(q):
    if not q.strip(): return "Пример: /h2h Бавария - Кёльн"
    f=load("state/form.json",{}); found={}
    for t in f.get("teams",[]):
        for m in t["matches"]:
            if m["venue"]!="home": continue
            r=dict(home=t["name"],away=m["opponent"])
            if query_match(q,r): found[(t["league"],m["date"],r["home"],r["away"])]=m
    lines=["Очные встречи: только доступная история лиги (до 20 игр каждой команды)."]
    for k,m in sorted(found.items(),key=lambda x:x[0][1],reverse=True)[:5]:
        lines.append(f"{k[1]} | {k[2]} — {k[3]} | {m['g']}:{m['c']}")
    if not found: lines.append("Нет встреч в доступной истории; это не означает, что их не было.")
    return "\n".join(lines)

def h2h(q):
    import re
    parts=[canonical(x) for x in re.split(r"\s*[-–—]\s*",q) if x.strip()]
    if len(parts)!=2: return "Пример: /h2h Бавария - Кёльн"
    aliases={canonical(k):canonical(v) for k,v in ALIASES.items()}
    a,b=[aliases.get(x,x) for x in parts]
    if a==b: return "Укажи две разные команды."
    hist=load("state/history.json",{})
    if not hist.get("rows"): return h2h_local(q)
    found=[]
    for r in hist["rows"]:
        h,v=canonical(r["home"]),canonical(r["away"])
        if (a in h and b in v) or (b in h and a in v): found.append(r)
    lines=["V19 • Очные встречи OpenFootball (неполное покрытие)"]
    for r in sorted(found,key=lambda x:x["date"],reverse=True)[:10]:
        lines.append("{} | {} — {} | {}:{}".format(r["date"],r["home"],r["away"],*r["ft"]))
    lines.append("Найдено: "+str(len(found))+". История не меняет прогнозы.")
    return "\n".join(lines)

def filter_predictions(arg):
    import re,math
    from corners import MARKETS as CORNER_MARKETS
    from cards import MARKETS as CARD_MARKETS
    aliases={"оз":"Обе забьют","btts":"Обе забьют","обе забьют":"Обе забьют",
             "тм 2.5":"ТМ 2.5","тм 2,5":"ТМ 2.5"}
    markets=LABELS+[m[0] for m in CORNER_MARKETS+CARD_MARKETS]
    for name in markets:
        aliases[name.casefold()]=name
        aliases[name.casefold().replace(".",",")]=name
    usage=("Примеры:\n/filter обе забьют 60-80\n/filter тб 2.5 до 70\n"
           "/filter тб 1.5 1т от 60\n/filter тм 2.5 60-80\n"
           "По умолчанию: сегодня (Бишкек), все прогнозы, по убыванию вероятности.")
    arg=" ".join(arg.casefold().replace("–","-").replace("—","-").split())
    m=re.fullmatch(r"(.+?)\s+(?:(от|до)\s+)?(\d{1,3})(?:\s*-\s*(\d{1,3}))?\s*%?",arg)
    if not m: return usage
    market=aliases.get(m.group(1))
    if not market: return "Рынок не распознан.\n"+usage
    a=int(m.group(3)); b=int(m.group(4)) if m.group(4) else None
    if a>100 or (b is not None and (b>100 or a>b or m.group(2))):
        return "Неверный диапазон: укажи от 0 до 100, например 60-80."
    lo,hi=(a,b) if b is not None else ((0,a) if m.group(2)=="до" else (a,100))
    snap=load("state/snapshot.json",{})
    if not snap: return "База прогнозов отсутствует."
    now=datetime.now(timezone.utc); local=timezone(timedelta(hours=6))
    try:
        created=datetime.fromisoformat(snap["created"])
        if created.tzinfo is None or (now-created).total_seconds()>108000:
            return "База старше 30 часов. Обнови прогнозы."
    except (ValueError,TypeError,KeyError):
        return "Дата базы некорректна."
    today=now.astimezone(local).date()
    found={}
    for r in reconcile(snap.get("rows",[])):
        if not r.get("kickoff"): continue
        try: k=datetime.fromisoformat(r["kickoff"])
        except (ValueError,TypeError): continue
        if k.tzinfo is None or k<=now or k.astimezone(local).date()!=today: continue
        if market=="ТМ 2.5":
            if r.get("group")!="goals" or r.get("market")!="ТБ 2.5": continue
            p=1-r.get("p",float("nan"))
        else:
            if r.get("market")!=market: continue
            p=r.get("p")
        if not isinstance(p,(int,float)) or not math.isfinite(p) or not 0<=p<=1: continue
        if not lo<=p*100<=hi: continue
        key=(canonical(r["home"]),canonical(r["away"]),k.isoformat(),market)
        if key not in found or p>found[key][0]: found[key]=(p,r)
    ranked=sorted(found.values(),key=lambda t:t[0],reverse=True)
    lines=[f"🔎 {market} | {lo}–{hi}% | сегодня, Бишкек",
           "Все прогнозы; сортировка по вероятности.",
           "Расписание независимо не подтверждено; оценка не гарантия."]
    if market=="ТМ 2.5":
        lines.append("ТМ 2.5 = 1 − P(ТБ 2.5). Отдельного теста ТМ нет.")
    calibration=snap.get("calibration",{}).get("markets",{}).get("ТБ 2.5" if market=="ТМ 2.5" else market)
    if market=="ТМ 2.5" and calibration is not None:
        calibration=[[1-p,1-y] for p,y in calibration]
    summary=calibration_summary(calibration,lo,hi)
    if summary["sufficient"]:
        lines.append(f"📊 Исторически в диапазоне {lo}–{hi}%: {summary['wins']}/{summary['n']} ({summary['observed']:.1%}) событий; средний прогноз {summary['mean']:.1%}; разница {100*summary['gap']:+.1f} п.п.")
        lines.append(f"95% интервал частоты (Уилсон): {summary['low']:.1%}–{summary['high']:.1%}.")
        lines.append("Это общая историческая частота диапазона, не точность отдельного матча.")
    else:
        lines.append(f"📊 Для диапазона {lo}–{hi}% недостаточно исторических записей: {summary['n']} (минимум 30).")
    history=snap.get("history_comparison",{})
    if history.get("markets") and market in history["markets"]:
        h=history["markets"][market]
        lines.append(f"📚 Изменение базы тестов: {h['previous']} → {h['current']} ({h['current']-h['previous']:+d}). Причина изменения автоматически не установлена.")
    for p,r in ranked[:20]:
        sample=r.get("sample") or []
        d=snap.get("diagnostics",{}).get(r["market"],{})
        n=d.get("n",0)
        reasons_list=reasons(r,snap)
        if market=="ТМ 2.5":
            status="⚪ Недостаточно данных"
            why="нет отдельной исторической проверки ТМ 2.5"
        elif not sample or min(sample)<10 or n<100 or not all(isinstance(d.get(k),(int,float)) and math.isfinite(d[k]) for k in ("model","baseline")):
            status="⚪ Недостаточно данных"
            why="выборка команд <10 или тестов <100, либо нет метрик"
        elif reasons_list:
            status="🟡 Не прошёл фильтр"
            why="; ".join(reasons_list)
        else:
            status="🟢 Прошёл фильтр"
            why="выполнены текущие критерии отбора"
        quality=reliability(summary,d,r.get("sample"),snap.get("created"),now) if market!="ТМ 2.5" else {"score":None,"status":"⚪ Недостаточно данных","reason":"отдельная оценка ТМ не валидирована"}
        quality_text=(f"{quality['score']}/100" if quality['score'] is not None else "н/д")
        evidence=baseline_evidence(d) if market!="ТМ 2.5" else {"status":"⚪ Нет отдельного теста","delta":None}
        stamp=datetime.fromisoformat(r["kickoff"]).astimezone(local).strftime("%d.%m %H:%M")
        lines.append(f"\n{stamp} | {r['home']} — {r['away']}\n"
                     f"{market}: {p:.1%} | {status}\nПричина: {why}\n"
                     f"Индекс V26.1: {quality_text} | {quality['status']}\nОснование: {quality['reason']}\nПреимущество над базой: {evidence['status']}\nИсторических тестов: {n if market!='ТМ 2.5' and n else 'нет отдельного теста'}"
                     + (f" | Brier модель/база: {d['model']:.3f}/{d['baseline']:.3f}"
                        if market!="ТМ 2.5" and isinstance(d.get("model"),(int,float)) and isinstance(d.get("baseline"),(int,float)) else ""))
    if not ranked: lines.append("На сегодня подходящих матчей нет. Попробуй другой диапазон.")
    if len(ranked)>20: lines.append(f"Показано 20 из {len(ranked)}.")
    lines.append("V26.1: порог улучшения Brier 0.002 — эвристический, не проверка статистической значимости.")
    lines.append("V26: индекс — эвристика качества данных и калибровки, не вероятность выигрыша. 95% интервал описывает частоту, не отдельный матч.")
    lines.append("Brier — историческая ошибка вероятностей, не процент выигрышей и не ROI.")
    return "\n".join(lines)


def all_predictions(arg):
    snap=load("state/snapshot.json",{})
    if not snap: return "Нет базы прогнозов. Запусти обновление."
    now=datetime.now(timezone.utc); local=timezone(timedelta(hours=6))
    if (now-datetime.fromisoformat(snap["created"])).total_seconds()>108000:
        return "Снимок старше 30 часов. Обнови базу."
    rows=[]
    for r in reconcile(snap["rows"]):
        if r.get("kickoff"):
            k=datetime.fromisoformat(r["kickoff"])
            if not now<k<=now+timedelta(days=7): continue
        else:
            if not now.date().isoformat()<r["date"]<=(now+timedelta(days=7)).date().isoformat(): continue
        if arg.strip() and not query_match(arg,r): continue
        rows.append(r)
    groups={}
    for r in rows:
        key=(canonical(r["home"]),canonical(r["away"]),r.get("kickoff") or r["date"])
        groups.setdefault(key,[]).append(r)
    if not groups:
        return "Нет будущих матчей в базе для этого запроса. Пример: /all Бавария - Кёльн"
    lines=["⚽ Все прогнозы • обзор, БЕЗ фильтра качества","Снимок: "+snap["created"],"⚠️ Низкие вероятности и непрошедшие тесты НЕ рекомендации.","Расписание независимо не подтверждено."]
    for key,rs in sorted(groups.items(),key=lambda item:item[0][2])[:(1 if arg.strip() else 3)]:
        a=rs[0]; stamp=datetime.fromisoformat(a["kickoff"]).astimezone(local).strftime("%d.%m %H:%M Бишкек") if a.get("kickoff") else a["date"]+" (время не проверено)"
        lines.append("\n"+a["home"]+" — "+a["away"]+" | "+stamp)
        markets={}
        for r in rs:
            if r["market"] not in markets or r["p"]>markets[r["market"]]["p"]: markets[r["market"]]=r
        for r in sorted(markets.values(),key=lambda r:(("ТБ 0.5 1Т","ТБ 1.5 1Т","ТБ 2.5","Обе забьют","ТБ 0.5 2Т").index(r["market"]) if r["market"] in ("ТБ 0.5 1Т","ТБ 1.5 1Т","ТБ 2.5","Обе забьют","ТБ 0.5 2Т") else 20,r["market"])):
            status="фильтр пройден" if eligible(r,snap) else "не прошёл фильтр"
            lines.append(f"{r['market']}: {r['p']:.1%} ({status})")
            if r["group"]=="goals" and r["market"]=="ТБ 2.5":
                lines.append(f"ТМ 2.5: {1-r['p']:.1%} (дополнение, не тестировалось отдельно)")
        lines.append(f"Рынков в базе: {len(markets)}/13")
    if len(groups)>(1 if arg.strip() else 3): lines.append("Другие матчи: /all НАЗВАНИЕ КОМАНДЫ")
    return "\n".join(lines)

def best_today():
    snap=load("state/snapshot.json",{})
    if not snap: return "Нет снимка. Обнови V10."
    now=datetime.now(timezone.utc); local=timezone(timedelta(hours=6))
    if (now-datetime.fromisoformat(snap["created"])).total_seconds()>108000: return "Снимок старше 30 часов. Обнови базу."
    rows=[]
    for r in reconcile(snap["rows"]):
        if not r.get("kickoff"): continue
        k=datetime.fromisoformat(r["kickoff"])
        if k>now and k.astimezone(local).date()==now.astimezone(local).date() and eligible(r,snap): rows.append(r)
    lines=["V18 • кандидаты сегодня (Бишкек) • ДЕМО","Снимок: "+snap["created"]]
    for r in sorted(rows,key=lambda x:x["p"],reverse=True)[:10]:
        lines.append(f"{r['home']} — {r['away']} | {r['market']} {r['p']:.1%}")
    if not rows: lines.append("Нет кандидатов с известным временем, прошедших фильтр.")
    lines.append("Ранжирование по p, не доходности. Расписание не проверено независимо.")
    return "\n".join(lines)

def shortlist():
    snap=load("state/snapshot.json",{})
    if not snap: return "Нет снимка."
    now=datetime.now(timezone.utc)
    local=timezone(timedelta(hours=6))
    if (now-datetime.fromisoformat(snap["created"])).total_seconds()>108000:
        return "V23: снимок устарел; кандидаты скрыты."
    selected={}
    for r in reconcile(snap["rows"]):
        if not r.get("kickoff") or not eligible(r,snap): continue
        k=datetime.fromisoformat(r["kickoff"])
        if not now<k<=now+timedelta(days=7): continue
        key=(r["market"],canonical(r["home"]),canonical(r["away"]),k)
        if key not in selected or r["p"]>selected[key]["p"]: selected[key]=r
    lines=["⚽ V23 • Кандидаты на 7 дней • ДЕМО","Расписание независимо не проверено."]
    used=set(); chosen=[]; counts={}
    for group,limit in (("goals",4),("corners",3),("cards",3)):
        for r in sorted(selected.values(),key=lambda x:x["p"],reverse=True):
            if r["group"]!=group: continue
            key=(canonical(r["home"]),canonical(r["away"]),r["kickoff"])
            if key in used or counts.get(r["market"],0)>=2: continue
            chosen.append(r); used.add(key); counts[r["market"]]=counts.get(r["market"],0)+1
            if sum(x["group"]==group for x in chosen)>=limit: break
    for r in chosen:
        stamp=datetime.fromisoformat(r["kickoff"]).astimezone(local).strftime("%d.%m %H:%M")
        lines.append(f"{stamp} | {r['home']} — {r['away']} | {r['market']}: {r['p']:.1%} | 1/p {1/r['p']:.2f}")
    if not chosen: lines.append("Нет кандидатов, прошедших фильтр.")
    lines.append("Время Бишкек. Один рынок на матч; до 4 голов, 3 угловых, 3 ЖК; до 2 на рынок. Сортировка по p внутри группы, не по доходности. 1/p не является котировкой букмекера.")
    return "\n".join(lines)


def performance():
    now=datetime.now(timezone.utc)
    rows=list(load("state/extra_journal.json",{}).values())
    for r in load("state/journal.json",{}).values():
        rows.append(dict(market=LABELS[r["market"]],date=r["kickoff"][:10],result=r["result"]))
    markets=list(dict.fromkeys(list(LABELS)+[r["market"] for r in load("state/snapshot.json",{}).get("rows",[])]))
    lines=["V24 • Статистика демопрогнозов","Все сохранённые прогнозы, не только shortlist."]
    for days in (7,30,90):
        start=(now.date()-timedelta(days=days-1)).isoformat()
        lines.append(f"За {days} дней (UTC):")
        for market in markets:
            rs=[r for r in rows if r["market"]==market and start<=r["date"]<=now.date().isoformat()]
            done=[r for r in rs if r["result"] in (0,1)]
            wins=sum(r["result"] for r in done)
            rate=f"{wins/len(done):.1%}" if done else "нет результатов"
            lines.append(f"{market}: В {wins} / П {len(done)-wins}; {rate}; ждут {len(rs)-len(done)}")
    lines.append(f"Будущие прогнозы: {sum(r['date']>now.date().isoformat() and r['result'] is None for r in rows)}")
    lines.append("ROI не рассчитан: отсутствуют зафиксированные букмекерские коэффициенты. Источники результатов независимо не проверены.")
    return "\n".join(lines)

def paper_id(r):
    import hashlib
    key="|".join(str(r[x]) for x in ("home","away","kickoff","market"))
    return hashlib.sha256(key.encode()).hexdigest()[:12]

def paper_candidates():
    snap=load("state/snapshot.json",{})
    now=datetime.now(timezone.utc)
    if not snap or (now-datetime.fromisoformat(snap["created"])).total_seconds()>108000:
        return {}
    return {paper_id(r):r for r in reconcile(snap["rows"]) if r.get("kickoff")
            and now<datetime.fromisoformat(r["kickoff"])<=now+timedelta(days=7)
            and eligible(r,snap)}

def paper_settle(bank):
    # Only exact, unique records from the published result journal.
    # Goal entries require stable fixture IDs, not yet available.
    import json
    from urllib.request import urlopen
    pending=[e for e in bank["entries"] if e["result"] is None and e["group"] in ("corners","cards") and datetime.fromisoformat(e["kickoff"])+timedelta(hours=3)<datetime.now(timezone.utc)]
    if not pending: return 0
    url="https://raw.githubusercontent.com/Viktor33v/football-ai-pro/main/state/extra_journal.json"
    with urlopen(url,timeout=10) as f:
        journal=json.load(f)
    count=0
    for e in pending:
        rows=[r for r in journal.values() if all(r.get(k)==e.get(k) for k in ("group","market","date","home","away"))]
        if len(rows)!=1: continue
        row=rows[0]
        if type(row.get("result")) is not int or row["result"] not in (0,1): continue
        if not row.get("created") or datetime.fromisoformat(row["created"])>=datetime.fromisoformat(e["kickoff"]): continue
        e["result"]=row["result"]
        e["settled_at"]=datetime.now(timezone.utc).isoformat()
        e["result_source"]="extra_journal_unverified"
        count+=1
    return count

def paper_commands(cmd,arg):
    from paper24 import load_bank,save_bank,calculate
    from decimal import Decimal
    path=os.environ.get("FOOTBALL_BANK_PATH")
    if not path: return "Хранилище не настроено."
    try:
        bank=load_bank(path)
        if cmd=="/paper_settle":
            n=paper_settle(bank)
            if n: save_bank(path,bank)
            return f"Рассчитано: {n}. Только однозначные записи угловых и ЖК. Источник независимо не проверен. Голы пока не рассчитываются."
        if cmd=="/paper_list":
            rows=sorted(paper_candidates().items(),key=lambda x:x[1]["p"],reverse=True)[:15]
            lines=["Учебные кандидаты; расписание не проверено."]
            for key,r in rows:
                lines.append(f"{key} | {r['home']} — {r['away']} | {r['market']} {r['p']:.1%}")
            return "\n".join(lines+["Запись: /paper_add ID коэффициент. Только виртуальные $10."])
        if cmd=="/paper_open":
            return "\n".join(["Открытые учебные записи:"]+[f"{e['id']} | {e['home']} — {e['away']} | {e['market']} | {e['odds']}" for e in bank["entries"] if e["result"] is None]) if any(e["result"] is None for e in bank["entries"]) else "Открытых записей нет."
        parts=arg.split()
        if len(parts)!=2: return "Формат: /paper_add ID 1.80"
        key,odd=parts
        odds=Decimal(odd.replace(",","."))
        if not odds.is_finite() or not Decimal("1")<odds<=Decimal("1000"): return "Недопустимый коэффициент."
        r=paper_candidates().get(key)
        if not r: return "Кандидат отсутствует или устарел. /paper_list"
        if any(e["id"]==key or (canonical(e["home"])==canonical(r["home"]) and canonical(e["away"])==canonical(r["away"]) and e["kickoff"]==r["kickoff"]) for e in bank["entries"]): return "Этот матч уже записан."
        if calculate(bank["entries"])["available"]<10: return "Недостаточно виртуальных средств."
        if datetime.now(timezone.utc)>=datetime.fromisoformat(r["kickoff"]): return "Матч уже начался."
        bank["entries"].append(dict(id=key,home=r["home"],away=r["away"],kickoff=r["kickoff"],market=r["market"],group=r["group"],date=r["date"],p=r["p"],odds=str(odds),result=None,created=datetime.now(timezone.utc).isoformat(),odds_source="manual_unverified"))
        save_bank(path,bank)
        return f"Учебная запись {key} сохранена: $10, коэффициент {odds}. Расписание и коэффициент не проверены. Расчёт угловых и ЖК: /paper_settle; голы пока отключены."
    except (OSError,ValueError,KeyError,TypeError,ArithmeticError):
        return "Ошибка данных или хранилища; проверьте /paper_open."

def bank_report():
    from paper24 import calculate, load_bank, save_bank, new_bank
    path=os.environ.get("FOOTBALL_BANK_PATH")
    if not path:
        return "💰 V24 • Демобанк\nСтартовый капитал: $1000.00\nПостоянное хранилище не настроено. Учёт операций отключён."
    try:
        bank=load_bank(path)
        if "storage_marker" not in bank:
            import uuid
            bank["storage_marker"]=uuid.uuid4().hex[:12]
            save_bank(path,bank)
        s=calculate(bank["entries"])
    except (OSError,ValueError,KeyError,TypeError):
        return "Ошибка хранилища демобанка. Баланс не сброшен."
    roi="—" if s["roi"] is None else f"{s['roi']:.2f}%"
    return "\n".join(["💰 V24 • Демобанк",f"Цикл: {bank['cycle']}",f"Метка хранения: {bank['storage_marker']}",f"Баланс: ${s['balance']:.2f}",f"Свободно: ${s['available']:.2f}",f"Прибыль: ${s['profit']:.2f}",f"ROI: {roi}",f"Открыто: {s['pending']} | Рассчитано: {s['settled']}","Файл банка доступен. Сохранность при Redeploy ещё не проверена.","Учебные записи: /paper_list, /paper_open, /paper_settle. Автоматический расчёт ещё отключён."])
def bank_admin(cmd,arg):
    from paper24 import load_bank,save_bank,calculate,reset_bank
    path=os.environ.get("FOOTBALL_BANK_PATH")
    if not path: return "Хранилище не настроено."
    try:
        bank=load_bank(path)
        stats=calculate(bank["entries"])
        if cmd=="/bank_history":
            lines=["История демобанка"]
            for old in bank["history"][-20:]:
                v=calculate(old["entries"])
                lines.append(f"Цикл {old['cycle']}: прибыль ${v['profit']:.2f}, операций {v['settled']}")
            return "\n".join(lines) if len(lines)>1 else "Завершённых циклов пока нет."
        if stats["pending"]: return "Сброс невозможен: есть открытые операции."
        token=f"{bank['cycle']}-{bank['storage_marker']}"
        if cmd=="/bank_reset":
            return f"Новый цикл с $1000, прежняя история сохраняется. Для подтверждения: /bank_confirm {token}"
        if arg.strip()!=token: return "Сначала отправьте /bank_reset и скопируйте команду подтверждения."
        new=reset_bank(bank,True)
        new["storage_marker"]=bank["storage_marker"]
        save_bank(path,new)
        return f"Демобанк: новый цикл {new['cycle']}, баланс $1000. История сохранена."
    except (OSError,ValueError,KeyError,TypeError,ArithmeticError):
        return "Ошибка хранилища. Сброс не выполнен."

def answer(msg):
    msg=MENU.get(msg.strip(),msg)
    local=timezone(timedelta(hours=6)); now=datetime.now(timezone.utc)
    cmd,_,arg=msg.strip().partition(" "); cmd=cmd.split("@")[0].lower()
    helptext="⚽ Football AI PRO V24 • ДЕМО\n/today — сегодня\n/tomorrow — завтра\n/top — 10 по вероятности\n/goals — голы\n/corners — угловые\n/cards — ЖК\n/stats — журнал\n/match Arsenal — поиск по названию (русский или латиница)\nРежим ДЕМО. /bank — виртуальный банк.\n/bank_reset — новый цикл\n/bank_history — история циклов"
    if cmd in ("/start","/help"): return helptext+"\n/form Бавария — последние 5 матчей\n/tactic 4-3-3 4-2-3-1 — история схем\n/analyze Бавария - Кёльн — полный анализ\n/performance — проходимость 7/30/90 дней\n/shortlist — кандидаты на 7 дней\n/best — фильтр на сегодня\n/status — состояние базы\n/h2h Бавария - Кёльн — доступные очные встречи\n/form Бавария; 20 — форма до 20 матчей\n/half — тест 1Т\n/odds 73.5 1.50 — демо расчёт"
    if cmd=="/bank": return bank_report()
    if cmd in ("/paper_list","/paper_add","/paper_open","/paper_settle"): return paper_commands(cmd,arg)
    if cmd in ("/bank_reset","/bank_confirm","/bank_history"): return bank_admin(cmd,arg)
    if cmd=="/performance": return performance()
    if cmd=="/shortlist": return shortlist()
    if cmd=="/best": return best_today()
    if cmd=="/all": return all_predictions(arg)
    if cmd=="/filter": return filter_predictions(arg)
    if cmd=="/status": return status_report()
    if cmd=="/h2h": return h2h(arg)
    if cmd=="/odds": return odds(arg)
    if cmd=="/half": return half_report()
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
    lines=["⚽ Football AI PRO V23 • ДЕМО","Снимок: "+snap["created"]+" UTC","Вероятности не являются доказательством прибыльности.","Время Бишкек для совпавших матчей; остальные даты из CSV не подтверждены."]
    for r in sorted(rs,key=lambda r:r["p"],reverse=True)[:(25 if cmd=="/match" else 10)]:
        stamp=datetime.fromisoformat(r["kickoff"]).astimezone(local).strftime("%d.%m %H:%M") if r.get("kickoff") else r["date"]+" (время неизвестно)"
        lines.append(f'{stamp} | {r["home"]} — {r["away"]}\n{r["market"]}: {r["p"]:.1%}')
    if not rs:
        lines.append("Нет подходящих будущих прогнозов в базе.")
        if cmd in ("/today","/tomorrow"):
            dates=sorted({day(r) for r in reconcile(snap["rows"]) if r.get("kickoff") and datetime.fromisoformat(r["kickoff"])>now and r["selected"] and day(r)>target})
            if dates: lines.append("Ближайшая дата в базе: "+dates[0]+" (расписание независимо не проверено).")
            lines.append("Используй /shortlist для обзора ближайших 7 дней.")
    return "\n".join(lines)
def run():
    chat=int(os.environ["TELEGRAM_CHAT_ID"])
    offset=None
    received=0; accepted=0; sent=0
    info=telegram("getMe")
    print("Bot username:",info.get("username","unknown"))
    webhook=telegram("getWebhookInfo")
    print("Webhook active:",bool(webhook.get("url")),"pending:",webhook.get("pending_update_count",0))
    # Telegram acknowledges updates on the next higher-offset request.
    for _ in range(5):
        args=dict(timeout=0,limit=100,allowed_updates=["message"])
        if offset is not None: args["offset"]=offset
        updates=telegram("getUpdates",**args)
        if not updates: break
        for u in updates:
            received+=1
            m=u.get("message",{})
            if m.get("chat",{}).get("id")==chat and m.get("chat",{}).get("type")=="private" and isinstance(m.get("text"),str):
                accepted+=1
                text=html.unescape(answer(m["text"]))
                for i in range(0,len(text),3500):
                    telegram("sendMessage",chat_id=chat,text=text[i:i+3500],reply_markup=keyboard())
                    sent+=1
            offset=u["update_id"]+1
    if offset is not None: telegram("getUpdates",offset=offset,timeout=0,limit=1,allowed_updates=["message"])
    print(f"Updates received={received}; authorized={accepted}; messages sent={sent}")
    if os.environ.get("TELEGRAM_DIAGNOSTIC")=="1":
        telegram("sendMessage",chat_id=chat,text="Football AI PRO: проверка связи Telegram успешна.",reply_markup=keyboard())
        print("Diagnostic message delivered to Telegram API")
def serve():
    while True:
        try:
            run()
        except Exception as e:
            print("Polling error:",type(e).__name__,flush=True)
            time.sleep(15)
        else:
            time.sleep(2)
if __name__=="__main__":
    if os.environ.get("TELEGRAM_CONTINUOUS")=="1": serve()
    else: run()

