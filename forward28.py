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
    lines.append("Без коэффициентов букмекеров: ROI не рассчитывается. Неподтверждённые исходы остаются открытыми.")
    return "\n".join(lines)
