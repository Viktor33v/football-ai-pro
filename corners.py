import csv,io,os,json,math
from collections import defaultdict
from datetime import datetime,timezone,timedelta
from urllib.request import urlopen
from bot import prob,send

SOURCE="https://github.com/oladeeayo/open-matchday"
BASE="https://raw.githubusercontent.com/oladeeayo/open-matchday/master/data/"
LEAGUES=["ENG_1_premier-league","ESP_1_la-liga","GER_1_bundesliga","ITA_1_serie-a","FRA_1_ligue-1","NED_1_eredivisie","POR_1_primeira-liga","BEL_1_pro-league","TUR_1_super-lig","GRE_1_super-league","ENG_2_championship","GER_2_2-bundesliga","DEN_1_superliga","NOR_1_eliteserien","SWE_1_allsvenskan","SUI_1_super-league","AUT_1_bundesliga"]
MARKETS=[("Угловые ТБ 8.5",9,0),("Угловые ТБ 9.5",10,0),("Угловые 1Т ТБ 3.5",4,1)]
def read(league,kind):
    with urlopen(BASE+league+"/"+kind+"_2627.csv",timeout=30) as r:
        return list(csv.DictReader(io.StringIO(r.read().decode("utf-8-sig"))))
def valid_future_fixture(r,today,seen):
    """CSV dates are UTC calendar dates only; no trusted kickoff time."""
    try:
        d=datetime.strptime(r["date"],"%Y-%m-%d").date()
        home=r["home"].strip(); away=r["away"].strip()
        return bool(home and away and home!=away and today<d<=today+timedelta(days=7) and (r["date"],home,away) not in seen)
    except (KeyError,TypeError,ValueError,AttributeError):
        return False

def counts(r):
    try:
        a,b=int(r["home_corners"]),int(r["away_corners"])
        if min(a,b)<0: return None
    except (ValueError,KeyError,TypeError): return None
    try:
        c,d=int(r["home_corners_1h"]),int(r["away_corners_1h"])
        if not (0<=c<=a and 0<=d<=b): c=d=None
    except (ValueError,KeyError,TypeError): c=d=None
    return a,b,c,d

def run():
    today=datetime.now(timezone.utc).date()
    metrics=defaultdict(list); picks=defaultdict(list); coverage=[]; errors=[]; unavailable_stats=[]; fixture_counts={}
    for league in LEAGUES:
        try: history=read(league,"results"); fixtures=read(league,"fixtures")
        except Exception as e:
            errors.append(league+": "+type(e).__name__); continue
        days=defaultdict(list); seen=set()
        for r in history:
            key=(r["date"],r["home"],r["away"])
            if key in seen or r["date"]>=str(today): continue
            v=counts(r)
            if v is not None: days[r["date"]].append((r,v)); seen.add(key)
        stats=defaultdict(list); venue=defaultdict(list); totals=[[],[]]
        def forecast(r,market):
            label,k,half=market
            a,b=r["home"],r["away"]
            aa=stats[a,half][-20:]; bb=stats[b,half][-20:]
            if min(len(aa),len(bb))<6 or len(totals[half])<30: return None
            base=sum(totals[half])/len(totals[half])
            def av(t,side,j):
                xs=stats[t,half][-20:]; vs=venue[t,side,half][-10:]
                mean=sum(z[j] for z in xs)/len(xs)
                return (sum(z[j] for z in vs)+5*mean)/(len(vs)+5)
            lam=(av(a,1,0)+av(b,0,1)+av(b,0,0)+av(a,1,1))/2
            baseline=(sum(z>=k for z in totals[half])+1)/(len(totals[half])+2)
            p=(prob(.7*lam+.3*base,k)+baseline)/2
            return p,baseline,lam,len(aa),len(bb)
        for day,rs in sorted(days.items()):
            for r,v in rs:
                for i,market in enumerate(MARKETS):
                    k,half=market[1:]
                    pair=v[2:] if half else v[:2]
                    if None in pair: continue
                    f=forecast(r,market)
                    if f: metrics[i].append((f[0],f[1],int(sum(pair)>=k)))
            for r,v in rs:
                for half,pair in enumerate((v[:2],v[2:])):
                    if None in pair: continue
                    a,b=pair; h=r["home"]; t=r["away"]
                    stats[h,half].append((a,b)); stats[t,half].append((b,a))
                    venue[h,1,half].append((a,b)); venue[t,0,half].append((b,a))
                    totals[half].append(a+b)
        coverage.append(f"{league}: {len(totals[0])}/{len(totals[1])}")
        fixture_counts[league]=len(fixtures)
        if len(totals[0])<30: unavailable_stats.append(league+" (угловые: "+str(len(totals[0]))+")")
        used=set()
        for r in fixtures:
            key=(r["date"],r["home"],r["away"])
            if key in used or not valid_future_fixture(r,today,seen): continue
            used.add(key)
            for i,market in enumerate(MARKETS):
                f=forecast(r,market)
                if f:
                    p,baseline,lam,na,nb=f
                    picks[i].append(dict(league=league,date=r["date"],home=r["home"],away=r["away"],p=p,baseline=baseline,expected=lam,sample=[na,nb]))
    lines=["⚽ FOOTBALL AI PRO V7 • CORNERS • ДЕМО","Источник: open-matchday "+SOURCE,"Сезон 2026/27; минимум 6 матчей каждой команды. Прогнозы со следующего UTC-дня. Время не публикуем: источник использует неоднозначный часовой пояс.","История (матч / 1Т): "+str(sum(int(x.split(": ")[1].split("/")[0]) for x in coverage))+"/"+str(sum(int(x.split("/")[1]) for x in coverage))]
    for i,(label,k,half) in enumerate(MARKETS):
        rs=metrics[i]; n=len(rs)
        lines.append("\n"+label)
        if n:
            bs=sum((p-y)**2 for p,b,y in rs)/n; base=sum((b-y)**2 for p,b,y in rs)/n
            lines.append(f"Исторический тест: {n} | Brier {bs:.3f} / лига {base:.3f}")
            g=[y for p,b,y in rs if p>=.65]
            if g: lines.append(f"Прогнозы от 65%: {sum(g)}/{len(g)} ({sum(g)/len(g):.0%})")
        else: lines.append("Недостаточно истории для проверки")
        for r in sorted(picks[i],key=lambda r:r["p"],reverse=True)[:5]:
            lines.append(f'{r["home"]} — {r["away"]} | {r["date"]} | {r["p"]:.0%} | угл. модель {r["expected"]:.1f} | {r["sample"][0]}/{r["sample"][1]}')
        if not picks[i]: lines.append("Нет кандидатов")
    if unavailable_stats: lines.append("Нет достаточной статистики угловых (не активны для прогнозов): "+", ".join(unavailable_stats))
    if errors: lines.append("Недоступные лиги: "+", ".join(errors))
    lines.append("Не независимый финальный тест. Вероятности экспериментальные; пропуски не заменяются нулями.")
    with open("corners.json","w",encoding="utf-8") as f: json.dump(dict(source=SOURCE,coverage=coverage,errors=errors,unavailable_stats=unavailable_stats,fixture_counts=fixture_counts,picks=picks,metrics=metrics),f,ensure_ascii=False,indent=2)
    send(os.environ["TELEGRAM_CHAT_ID"],"\n".join(lines))
if __name__=="__main__": run()
