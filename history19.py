"""CC0 OpenFootball historical results, separate from live predictions."""
import json, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
BASE="https://raw.githubusercontent.com/openfootball/football.json/master/"
def main():
    now=datetime.now(timezone.utc)
    rows=[]; errors=[]; coverage={}; seen=set()
    for season in ("2023-24","2024-25","2025-26","2026-27"):
        for league in ("en.1","de.1","es.1","it.1","fr.1","nl.1","pt.1","be.1","tr.1","gr.1"):
            key=f"{season}/{league}"
            try:
                with urllib.request.urlopen(BASE+key+".json",timeout=25) as f: data=json.load(f)
                count=0
                for m in data["matches"]:
                    d=m.get("date",""); h=m.get("team1"); a=m.get("team2"); s=m.get("score",{}).get("ft")
                    if not isinstance(h,str) or not isinstance(a,str) or not isinstance(s,list) or len(s)!=2 or not all(type(x)==int and x>=0 for x in s): continue
                    if not d or d>=now.date().isoformat(): continue
                    datetime.fromisoformat(d)
                    k=(league,d,h,a)
                    if k in seen: continue
                    seen.add(k); count+=1
                    rows.append(dict(date=d,home=h,away=a,ft=s,league=league))
                coverage[key]=count
            except Exception as e: errors.append(key+": "+type(e).__name__)
    if len(rows)<3000: raise RuntimeError("Insufficient historical coverage")
    rows.sort(key=lambda r:r["date"])
    Path("state").mkdir(exist_ok=True)
    Path("state/history.json").write_text(json.dumps(dict(created=now.isoformat(),source=BASE,coverage=coverage,errors=errors,rows=rows),ensure_ascii=False),encoding="utf-8")
    print("Historical matches:",len(rows),"files:",len(coverage),"errors:",errors)
if __name__=="__main__": main()
