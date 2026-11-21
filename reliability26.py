"""V26: descriptive calibration and conservative reliability diagnostics."""
import math

def wilson_interval(wins, n, z=1.959963984540054):
    if not isinstance(n,int) or n<=0 or not 0<=wins<=n:
        return None
    p=wins/n
    den=1+z*z/n
    center=(p+z*z/(2*n))/den
    margin=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return max(0,center-margin),min(1,center+margin)

def calibration_summary(records, lo, hi, min_n=30):
    valid=[]
    for item in records or []:
        try:
            p,y=item
            if type(p) not in (float,int) or type(y) not in (float,int):
                continue
            if math.isfinite(p) and 0<=p<=1 and y in (0,1) and lo<=p*100<=hi:
                valid.append((p,int(y)))
        except (TypeError,ValueError):
            continue
    n=len(valid)
    if n<min_n:
        return {"n":n,"sufficient":False}
    wins=sum(y for _,y in valid)
    mean=sum(p for p,_ in valid)/n
    observed=wins/n
    low,high=wilson_interval(wins,n)
    return dict(n=n,wins=wins,mean=mean,observed=observed,low=low,high=high,
                gap=observed-mean,sufficient=True)

def baseline_evidence(diagnostics, min_delta=0.002):
    """Practical Brier threshold; not a statistical significance test."""
    if not isinstance(diagnostics,dict) or type(diagnostics.get("n")) is not int or diagnostics["n"]<100:
        return {"status":"⚪ Недостаточно данных","delta":None}
    model=diagnostics.get("model")
    base=diagnostics.get("baseline")
    if not all(type(v) in (float,int) and math.isfinite(v) for v in (model,base)):
        return {"status":"⚪ Недостаточно данных","delta":None}
    delta=base-model
    if delta>=min_delta:
        status="🟢 Практическое улучшение Brier"
    elif delta<=-min_delta:
        status="🔴 Brier хуже базы"
    else:
        status="🟡 Преимущество не установлено"
    return {"status":status,"delta":delta}

def reliability(summary, diagnostics, sample, snapshot_created=None, now=None):
    """0-100 heuristic, not probability of a correct prediction."""
    if not summary or not summary.get("sufficient"):
        return {"score":None,"status":"⚪ Недостаточно данных","reason":"мало исторических прогнозов диапазона"}
    if not isinstance(diagnostics,dict):
        diagnostics={}
    n=diagnostics.get("n",0)
    model=diagnostics.get("model")
    base=diagnostics.get("baseline")
    if not isinstance(n,int) or n<100 or not all(type(x) in (float,int) and math.isfinite(x) for x in (model,base)):
        return {"score":None,"status":"⚪ Недостаточно данных","reason":"нет достаточного независимого теста модели"}
    if not isinstance(sample,(list,tuple)) or not sample or any(type(x) not in (int,float) or x<10 for x in sample):
        return {"score":None,"status":"⚪ Недостаточно данных","reason":"недостаточная выборка команд"}
    if snapshot_created is not None and now is not None:
        try:
            from datetime import datetime
            created=datetime.fromisoformat(snapshot_created)
            if created.tzinfo is None or (now-created).total_seconds()>108000 or created>now:
                return {"score":None,"status":"⚪ Недостаточно данных","reason":"устаревшая или некорректная база"}
        except (TypeError,ValueError):
            return {"score":None,"status":"⚪ Недостаточно данных","reason":"дата базы некорректна"}
    # Score components: coverage (25), interval width (25), calibration gap (30), Brier (20).
    coverage=25*min(1,summary["n"]/300)
    precision=25*max(0,1-(summary["high"]-summary["low"])/.35)
    calibration=30*max(0,1-abs(summary["gap"])/.15)
    evidence=baseline_evidence(diagnostics)
    skill=20 if evidence["delta"] is not None and evidence["delta"]>=.002 else 0
    score=round(max(0,min(100,coverage+precision+calibration+skill)))
    if evidence["delta"] is not None and evidence["delta"]<=-.002:
        status="🔴 Слабая надёжность"
        reason="Brier заметно хуже базовой модели"
    elif summary["mean"]<summary["low"] or summary["mean"]>summary["high"]:
        status="🔴 Слабая надёжность"
        reason="средний прогноз вне 95% интервала фактической частоты"
    elif evidence["delta"] is None or evidence["delta"]<.002:
        status="🟡 Преимущество не установлено"
        reason="улучшение Brier менее 0.002; зелёный статус запрещён"
    elif summary["n"]<100 or score<65:
        status="🟡 Ограниченная надёжность"
        reason="мало наблюдений или широкий интервал"
    else:
        status="🟢 Калибровка согласуется с историей"
        reason="средний прогноз внутри 95% интервала"
    return {"score":score,"status":status,"reason":reason}
