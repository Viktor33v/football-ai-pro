"""V28 forward-only forecast audit. Never backfill outcomes for predictions not archived before kickoff."""
import hashlib,json,math
from datetime import datetime,timezone,timedelta

GOAL_MARKETS={"ТБ 0.5 1Т":lambda ht,ft:ht>=1,
              "ТБ 1.5 1Т":lambda ht,ft:ht>=2,
              "ТБ 2.5":lambda ht,ft:ft>=3,
              "Обе забьют":lambda ht,ft:None,
              "ТБ 0.5 2Т":lambda ht,ft:ft-ht>=1}

def key(row):
    return hashlib.sha256(json.dumps([row.get("fixture_id"),row.get("market")],ensure_ascii=False).encode()).hexdigest()[:20]

def archive(journal,rows,now):
    """First prediction only; no editing archived probability."""
    for r in rows:
        if r.get("group")!="goals" or r.get("market") not in GOAL_MARKETS:continue
        fixture=r.get("fixture_id")
        if type(fixture) is not int or type(r.get("p")) not in (int,float) or not math.isfinite(r["p"]) or not 0<=r["p"]<=1:continue
        try:kickoff=datetime.fromisoformat(r["kickoff"])
        except (ValueError,TypeError,KeyError):continue
        if kickoff.tzinfo is None or kickoff<=now:continue
        k=key(r)
        if k not in journal:
            journal[k]=dict(fixture_id=fixture,market=r["market"],home=r["home"],away=r["away"],kickoff=r["kickoff"],p=r["p"],created=now.isoformat(),result=None,result_source=None)
    return journal

def settle(journal,results,now):
    """Only FINISHED regular-time API results, unique fixture id, archived pre-kickoff."""
    count=0
    for r in journal.values():
        if r.get("result") is not None:continue
        fixture=results.get(str(r.get("fixture_id")))
        if not isinstance(fixture,dict) or fixture.get("status")!="FINISHED":continue
        score=fixture.get("score") or {}
        if score.get("duration") not in (None,"REGULAR"):continue
        ft=score.get("fullTime") or {};ht=score.get("halfTime") or {}
        nums=[ft.get("home"),ft.get("away"),ht.get("home"),ht.get("away")]
        if any(type(x) is not int or x<0 for x in nums):continue
        if nums[0]<nums[2] or nums[1]<nums[3]:continue
        try:
            created=datetime.fromisoformat(r["created"])
            kickoff=datetime.fromisoformat(r["kickoff"])
            actual_kickoff=datetime.fromisoformat(fixture["utcDate"].replace("Z","+00:00"))
        except (ValueError,TypeError,KeyError,AttributeError):continue
        if any(x.tzinfo is None for x in (created,kickoff,actual_kickoff)) or created>=kickoff or created>=actual_kickoff or actual_kickoff>now:continue
        if abs((actual_kickoff-kickoff).total_seconds())>3600*12:continue
        market=r["market"]
        if market not in GOAL_MARKETS:continue
        if market=="Обе забьют":y=int(nums[0]>0 and nums[1]>0)
        else:y=int(GOAL_MARKETS[market](nums[2]+nums[3],nums[0]+nums[1]))
        r["result"]=y;r["result_source"]="football-data.org/v4";r["settled_at"]=now.isoformat()
        count+=1
    return count

def report(journal,now):
    lines=["📊 V28 • Проверка новых прогнозов (демо)","Только прогнозы, сохранённые ДО начала матча. Не ретроспективный бэктест."]
    for days in (7,30,90):
        start=now-timedelta(days=days)
        rs=[]
        for r in journal.values():
            try:k=datetime.fromisoformat(r["kickoff"])
            except (KeyError,TypeError,ValueError):continue
            if k.tzinfo and start<=k<=now:rs.append(r)
        done=[r for r in rs if r.get("result") in (0,1)]
        lines.append(f"\nЗа {days} дней: завершено {len(done)}, ожидают {len(rs)-len(done)}")
        for market in sorted({r["market"] for r in rs}):
            m=[r for r in done if r["market"]==market]
            if not m:continue
            hits=sum(r["result"] for r in m)
            brier=sum((r["p"]-r["result"])**2 for r in m)/len(m)
            lines.append(f"{market}: {hits}/{len(m)} ({hits/len(m):.1%}), Brier {brier:.4f}")
            if len(m)>=30:
                mean_p=sum(x["p"] for x in m)/len(m)
                gap=hits/len(m)-mean_p
                lines.append(f"  Калибровка: средний прогноз {mean_p:.1%}, факт {hits/len(m):.1%}, отклонение {gap*100:+.1f} п.п.")
                for low,high in ((0.0,0.5),(0.5,0.6),(0.6,0.7),(0.7,0.8),(0.8,1.000001)):
                    bucket=[x for x in m if low<=x["p"]<high]
                    if len(bucket)<20: continue
                    observed=sum(x["result"] for x in bucket)/len(bucket)
                    expected=sum(x["p"] for x in bucket)/len(bucket)
                    lines.append(f"  {low:.0%}–{min(high,1):.0%}: {len(bucket)} прогнозов, ожидалось {expected:.1%}, произошло {observed:.1%}")
            else:
                lines.append("  Калибровка: недостаточно завершённых прогнозов (минимум 30).")
    lines.append("Без коэффициентов букмекеров: ROI не рассчитывается. Неподтверждённые исходы остаются открытыми.")
    return "\n".join(lines)

def extra_market_report(journal,now):
    """CSV audit: distinguish pending by date; kickoff is not verified."""
    lines=["\n📐 Угловые и карточки • отдельный журнал",
           "CSV содержит дату без подтверждённого времени начала. Это НЕ независимая forward-проверка до стартового свистка."]
    for days in (7,30,90):
        start=(now-timedelta(days=days)).date()
        records=[]
        for r in journal.values():
            if r.get("group") not in ("corners","cards"):continue
            try:
                match_date=datetime.fromisoformat(r["date"]).date()
                created=datetime.fromisoformat(r["created"])
            except (KeyError,ValueError,TypeError):continue
            if created.tzinfo is None or not start<=match_date<=now.date()+timedelta(days=7):continue
            records.append((r,match_date))
        done=[r for r,d in records if type(r.get("result")) is int and r["result"] in (0,1) and d<=now.date() and d>=start]
        pending=[(r,d) for r,d in records if r.get("result") is None]
        future=sum(d>now.date() for r,d in pending)
        today=sum(d==now.date() for r,d in pending)
        overdue=sum(d<now.date() for r,d in pending)
        lines.append(f"\nЗа {days} дней: завершено {len(done)}, ожидают {len(pending)} (будущие {future}, сегодня {today}, прошлые без результата {overdue})")
        if overdue:
            lines.append("  ⚠️ Прошлые без результата: проверь CSV results, доступность лиги и совпадение названий команд.")
            reasons={"source_unavailable":"источник недоступен",
                     "fixture_not_found":"матч не найден",
                     "missing_corner_stats":"нет статистики угловых",
                     "missing_first_half_corners":"нет угловых 1Т",
                     "missing_card_stats":"нет статистики карточек",
                     "not_checked":"причина ещё не определена"}
            counts={}
            leagues={}
            for r,d in pending:
                if d>=now.date():continue
                issue=r.get("settlement_issue") or "not_checked"
                counts[issue]=counts.get(issue,0)+1
                league=r.get("league") or "неизвестная лига"
                leagues[league]=leagues.get(league,0)+1
            lines.append("  Причины: "+", ".join(f"{reasons.get(k,k)} — {v}" for k,v in sorted(counts.items(),key=lambda x:-x[1])))
            lines.append("  Лиги с незакрытыми записями: "+", ".join(f"{k} — {v}" for k,v in sorted(leagues.items(),key=lambda x:-x[1])[:5]))
        for market in sorted({r.get("market","") for r in done}):
            matches=[r for r in done if r.get("market")==market and type(r.get("p")) in (int,float) and math.isfinite(r["p"]) and 0<=r["p"]<=1]
            if not matches:continue
            hits=sum(r["result"] for r in matches)
            brier=sum((r["p"]-r["result"])**2 for r in matches)/len(matches)
            lines.append(f"{market}: {hits}/{len(matches)} ({hits/len(matches):.1%}), Brier {brier:.4f}")
            if len(matches)>=30:
                expected=sum(r["p"] for r in matches)/len(matches)
                actual=hits/len(matches)
                lines.append(f"  Калибровка: прогноз {expected:.1%}, факт {actual:.1%}, разница {(actual-expected)*100:+.1f} п.п.")
            else:
                lines.append("  Мало наблюдений для калибровки (минимум 30).")
    lines.append("Результаты CSV не подтверждены независимым источником; время начала не проверено.")
    return "\n".join(lines)
