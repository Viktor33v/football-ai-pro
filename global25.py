"""Read-only coverage test; no predictions or ledger changes."""
import json
import time
from urllib.request import urlopen, Request
from urllib.parse import urlencode
BASE="https://www.thesportsdb.com/api/v1/json/123/"
COUNTRIES=["Uruguay","Argentina","Brazil","Chile","Colombia","Japan","South Korea"]
def get(endpoint, **params):
    with urlopen(Request(BASE+endpoint+".php?"+urlencode(params),headers={"User-Agent":"FootballAI-Demo/1.0"}),timeout=15) as f:
        return json.load(f)
def probe():
    rows=[]
    for country in COUNTRIES:
        try:
            data=get("search_all_leagues",c=country,s="Soccer")
            leagues=data.get("countries") or data.get("leagues") or []
            rows.append({"country":country,"leagues":[{"id":x.get("idLeague"),"name":x.get("strLeague")} for x in leagues if x.get("idLeague")]})
        except Exception as e:
            rows.append({"country":country,"error":type(e).__name__})
        time.sleep(3)
    print(json.dumps(rows,ensure_ascii=False,indent=2))
def test_events():
    from datetime import datetime, timezone
    now=datetime.now(timezone.utc)
    for league in ("4432","4627","4497","4633","4689"):
        for endpoint in ("eventspastleague","eventsnextleague","eventsseason"):
            try:
                params={"id":league}
                if endpoint=="eventsseason": params["s"]=str(now.year)
                data=get(endpoint,**params)
                events=data.get("events") or []
                print(json.dumps({"league":league,"endpoint":endpoint,"count":len(events),"scored":sum(e.get("intHomeScore") is not None and e.get("intAwayScore") is not None for e in events),"samples":[{k:e.get(k) for k in ("idEvent","strHomeTeam","strAwayTeam","dateEvent","strTimestamp","strStatus","intHomeScore","intAwayScore")} for e in events[:3]]},ensure_ascii=False))
            except Exception as e:
                print(json.dumps({"league":league,"endpoint":endpoint,"error":type(e).__name__}))
            time.sleep(3)
if __name__=="__main__": test_events()
