import os,json
from collections import defaultdict
from datetime import datetime,timezone
from functools import lru_cache
import smart,corners,cards
from bot import send

def run():
    reports={}; errors=[]; data={}
    # Both CSV models use the same snapshot during a run.
    reader=lru_cache(maxsize=None)(corners.read)
    corners.read=reader; cards.read=reader
    for name,mod,filename in [("ГОЛЫ",smart,None),("УГЛОВЫЕ",corners,"corners.json"),("КАРТОЧКИ",cards,"cards.json")]:
        parts=[]
        mod.send=lambda chat,msg: parts.append(msg)
        try:
            mod.run()
            reports[name]="".join(parts).splitlines()
            if filename:
                with open(filename,encoding="utf-8") as f: data[name]=json.load(f)
        except Exception as e:
            errors.append(name+": "+type(e).__name__)
    lines=["⚽ FOOTBALL AI PRO V10 ULTIMATE • ДЕМО",datetime.now(timezone.utc).isoformat(timespec="minutes"),"13 рынков: 5 голов, 3 угловых, 5 ЖК. Вероятности отдельных моделей, не совместные. Тактика и судьи не учтены.","Модулей успешно: "+str(len(reports))+"/3"]
    if errors: lines.append("Ошибки: "+", ".join(errors))
    for name,report in reports.items():
        lines.extend(["","━━ "+name+" ━━"]+report[1:])
    # Exact source match only, avoiding ambiguous cross-provider joins.
    groups=defaultdict(list)
    for name,d in data.items():
        markets=corners.MARKETS if name=="УГЛОВЫЕ" else cards.MARKETS
        for i,rs in d["picks"].items():
            for r in rs:
                if r["p"]>=.65:
                    key=(r["league"],r["date"],r["home"],r["away"])
                    groups[key].append((name,markets[int(i)][0],r["p"]))
    lines.extend(["","━━ Совпадения рынков ━━","Только точные совпадения матчей угловых и ЖК; не экспресс и не общая вероятность."])
    matches=[(k,v) for k,v in groups.items() if len({x[0] for x in v})>1]
    for k,v in sorted(matches,key=lambda x:max(z[2] for z in x[1]),reverse=True)[:5]:
        lines.append(k[2]+" — "+k[3]+" | "+k[1])
        lines.append(" | ".join(f"{label}: {p:.0%}" for _,label,p in v))
    if not matches: lines.append("Нет совпадений выше 65%")
    lines.append("Порог совпадений экспериментальный; преимущества над букмекером не доказано.")
    with open("ultimate.json","w",encoding="utf-8") as f: json.dump(dict(reports=reports,errors=errors),f,ensure_ascii=False,indent=2)
    chunk=""
    for line in lines:
        if len(chunk)+len(line)+1>3500:
            if os.environ.get("COMPACT_REPORT")!="1": send(os.environ["TELEGRAM_CHAT_ID"],chunk)
            chunk=""
        chunk+=line+"\n"
    if chunk and os.environ.get("COMPACT_REPORT")!="1": send(os.environ["TELEGRAM_CHAT_ID"],chunk)
    if errors: raise RuntimeError("One or more modules failed")
if __name__=="__main__": run()
