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
if __name__=="__main__": probe()
