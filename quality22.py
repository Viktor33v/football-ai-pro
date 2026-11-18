import json
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
def main():
    h=json.loads(Path("state/history.json").read_text())
    rows=h["rows"]
    keys=Counter((r["league"],r["date"],r["home"],r["away"]) for r in rows)
    latest={}
    for r in rows:
        latest[r["league"]]=max(latest.get(r["league"],""),r["date"])
    today=datetime.now(timezone.utc).date()
    ages={k:(today-datetime.fromisoformat(v).date()).days for k,v in latest.items()}
    report={"created":datetime.now(timezone.utc).isoformat(),"rows":len(rows),"duplicate_keys":sum(n-1 for n in keys.values()),"latest":latest,"age_days":ages,"stale_leagues":[k for k,v in ages.items() if v>14],"source_errors":h.get("errors",[]),"independent_verification":False}
    Path("state/quality22.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
if __name__=="__main__": main()
