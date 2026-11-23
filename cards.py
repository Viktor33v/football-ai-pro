import os,json
from collections import defaultdict
from datetime import datetime,timezone,timedelta
from corners import read,LEAGUES,SOURCE,valid_future_fixture
from bot import prob,send

MARKETS=[("ЖК ТБ 2.5",3,0),("ЖК ТБ 3.5",4,0),("ЖК ТБ 4.5",5,0),("ЖК хозяев ТБ 1.5",2,1),("ЖК гостей ТБ 1.5",2,2)]
def pair(r,field):
    try:
        a,b=int(r["home_"+field]),int(r["away_"+field])
        return (a,b) if min(a,b)>=0 else None
    except (ValueError,TypeError,KeyError): return None
def run():
    today=datetime.now(timezone.utc).date()
    metrics=defaultdict(list); picks=defaultdict(list); coverage={}; errors=[]; unavailable_stats=[]; fixture_counts={}
    for league in LEAGUES:
        try: history=read(league,"results"); fixtures=read(league,"fixtures")
        except Exception as e:
            errors.append(league+": "+type(e).__name__); continue
        days=defaultdict(list); seen=set()
        for r in history:
            key=(r["date"],r["home"],r["away"])
            if key in seen or r["date"]>=str(today): continue
            v=pair(r,"yellow")
            if v is None: continue
            seen.add(key); days[r["date"]].append((r,v,pair(r,"fouls")))
        stats=defaultdict(list); venue=defaultdict(list); fouls=defaultdict(list); league_fouls=[]; totals=[]
        def forecast(r,market):
            label,k,side=market; a,b=r["home"],r["away"]
            aa=stats[a][-20:]; bb=stats[b][-20:]
            if min(len(aa),len(bb))<6 or len(totals)<30: return None
            def av(t,s,j):
                xs=stats[t][-20:]; vs=venue[t,s][-10:]
                mean=sum(z[j] for z in xs)/len(xs)
                return (sum(z[j] for z in vs)+5*mean)/(len(vs)+5)
            h=av(a,1,0); t=av(b,0,0)
            lh=sum(z[0] for z in totals)/len(totals); la=sum(z[1] for z in totals)/len(totals)
            fm=None
            if len(fouls[a])>=6 and len(fouls[b])>=6 and len(league_fouls)>=30:
                fa=fouls[a][-20:]; fb=fouls[b][-20:]
                fm=sum(fa)/len(fa)+sum(fb)/len(fb)
                avg=sum(league_fouls)/len(league_fouls)
                ratio=max(.8,min(1.2,fm/avg)) if avg>0 else 1
                h*=.8+.2*ratio; t*=.8+.2*ratio
            h=.7*h+.3*lh; t=.7*t+.3*la
            lam=[h+t,h,t][side]
            baseline=(sum([sum(z),z[0],z[1]][side]>=k for z in totals)+1)/(len(totals)+2)
            return (prob(lam,k)+baseline)/2,baseline,lam,len(aa),len(bb),fm
        for day,rs in sorted(days.items()):
            for r,v,fou in rs:
                for i,market in enumerate(MARKETS):
                    f=forecast(r,market)
                    if f: metrics[i].append((f[0],f[1],int([sum(v),v[0],v[1]][market[2]]>=market[1])))
            for r,v,fou in rs:
                a,b=v; h=r["home"]; t=r["away"]
                stats[h].append((a,b)); stats[t].append((b,a))
                venue[h,1].append((a,b)); venue[t,0].append((b,a)); totals.append(v)
                if fou is not None:
                    fouls[h].append(fou[0]); fouls[t].append(fou[1]); league_fouls.append(sum(fou))
        coverage[league]=[len(totals),len(league_fouls)]
        fixture_counts[league]=len(fixtures)
        if len(totals)<30: unavailable_stats.append(league+" (ЖК: "+str(len(totals))+")")
        used=set()
        for r in fixtures:
            key=(r["date"],r["home"],r["away"])
            if key in used or not valid_future_fixture(r,today,seen): continue
            used.add(key)
            for i,market in enumerate(MARKETS):
                f=forecast(r,market)
                if f:
                    p,base,lam,na,nb,fm=f
                    picks[i].append(dict(league=league,date=r["date"],home=r["home"],away=r["away"],p=p,baseline=base,expected=lam,sample=[na,nb],fouls=fm))
    lines=["⚽ FOOTBALL AI PRO V8 • ЖК • ДЕМО","Источник: open-matchday "+SOURCE,"История ЖК / фолов: "+str(sum(v[0] for v in coverage.values()))+"/"+str(sum(v[1] for v in coverage.values())),"Минимум 6 матчей на команду. Только исходные жёлтые карточки; правила расчёта букмекеров могут отличаться."]
    for i,(label,k,side) in enumerate(MARKETS):
        rs=metrics[i]; n=len(rs); lines.append("\n"+label)
        if n:
            bs=sum((p-y)**2 for p,b,y in rs)/n; base=sum((b-y)**2 for p,b,y in rs)/n
            lines.append(f"Тест: {n} | Brier {bs:.3f} / лига {base:.3f}")
            g=[y for p,b,y in rs if p>=.65]
            if g: lines.append(f"От 65%: {sum(g)}/{len(g)} ({sum(g)/len(g):.0%})")
        else: lines.append("Недостаточно истории")
        for r in sorted(picks[i],key=lambda r:r["p"],reverse=True)[:5]:
            fm="нет" if r["fouls"] is None else f'{r["fouls"]:.1f}'
            lines.append(f'{r["home"]} — {r["away"]} | {r["date"]} | {r["p"]:.0%} | ЖК {r["expected"]:.1f} | фолы {fm} | {r["sample"][0]}/{r["sample"][1]}')
        if not picks[i]: lines.append("Нет кандидатов")
    if unavailable_stats: lines.append("Нет достаточной статистики ЖК (не активны для прогнозов): "+", ".join(unavailable_stats))
    if errors: lines.append("Недоступные лиги: "+", ".join(errors))
    lines.append("Исторический последовательный тест, не независимый финальный тест. Судьи не учтены. Демо.")
    with open("cards.json","w",encoding="utf-8") as f: json.dump(dict(source=SOURCE,coverage=coverage,errors=errors,unavailable_stats=unavailable_stats,fixture_counts=fixture_counts,picks=picks,metrics=metrics),f,ensure_ascii=False,indent=2)
    chunk=""
    for line in lines:
        if len(chunk)+len(line)>3500:
            send(os.environ["TELEGRAM_CHAT_ID"],chunk); chunk=""
        chunk+=line+"\n"
    if chunk: send(os.environ["TELEGRAM_CHAT_ID"],chunk)
if __name__=="__main__": run()
