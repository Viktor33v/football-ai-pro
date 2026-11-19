"""Read-only demo accounting calculation; no real bets."""
from decimal import Decimal, InvalidOperation
def calculate(entries):
    profit=Decimal("0")
    pending=0
    settled=0
    wins=0
    for e in entries:
        odds=Decimal(str(e["odds"]))
        if not odds.is_finite() or not Decimal("1")<odds<=Decimal("1000"):
            raise ValueError("invalid odds")
        result=e["result"]
        if result is None:
            pending+=1
        elif result in (0,1):
            settled+=1
            wins+=result
            profit+=(Decimal("10")*(odds-1) if result else Decimal("-10"))
        else:
            raise ValueError("invalid result")
    return dict(profit=profit,balance=Decimal("1000")+profit,available=Decimal("1000")+profit-10*pending,pending=pending,settled=settled,wins=wins,roi=profit/(10*settled)*100 if settled else None)
def selftest():
    a=calculate([dict(odds="1.80",result=1),dict(odds="2",result=0),dict(odds="1.50",result=None)])
    assert a["profit"]==Decimal("-2") and a["available"]==Decimal("988") and a["roi"]==Decimal("-10")
    assert calculate([])["roi"] is None
    for o in ("NaN","Infinity","1","0"):
        try: calculate([dict(odds=o,result=None)])
        except ValueError: continue
        raise AssertionError("invalid odds accepted")
def new_bank():
    return {"version":1,"cycle":1,"entries":[],"history":[]}
def reset_bank(bank, confirmed=False):
    if not confirmed:
        raise ValueError("confirmation required")
    stats=calculate(bank["entries"])
    if stats["pending"]:
        raise ValueError("pending entries")
    return {"version":1,"cycle":bank["cycle"]+1,"entries":[],
            "history":bank["history"]+[{"cycle":bank["cycle"],"entries":bank["entries"]}]}
def reset_test():
    b=new_bank()
    b["entries"]=[dict(odds="2",result=0)]
    try: reset_bank(b)
    except ValueError: pass
    else: raise AssertionError("confirmation missing")
    a=reset_bank(b,True)
    assert a["cycle"]==2 and calculate(a["entries"])["balance"]==1000
    assert a["history"][0]["entries"]==b["entries"]
    b["entries"].append(dict(odds="2",result=None))
    try: reset_bank(b,True)
    except ValueError: pass
    else: raise AssertionError("pending reset")
if __name__=="__main__":
    selftest()
    reset_test()


def save_bank(path, bank):
    import os, json, tempfile
    calculate(bank["entries"])
    folder=os.path.dirname(os.path.abspath(path))
    os.makedirs(folder,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=".bank-",dir=folder)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            json.dump(bank,f,ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def load_bank(path):
    import json
    with open(path,encoding="utf-8") as f:
        bank=json.load(f)
    if bank.get("version")!=1 or not isinstance(bank["history"],list) or not isinstance(bank["cycle"],int):
        raise ValueError("invalid bank")
    calculate(bank["entries"])
    return bank

def storage_test():
    import tempfile, os
    with tempfile.TemporaryDirectory() as folder:
        path=os.path.join(folder,"bank.json")
        b=new_bank()
        save_bank(path,b)
        assert load_bank(path)==b
        b["entries"].append(dict(odds="1.8",result=1))
        save_bank(path,b)
        assert calculate(load_bank(path)["entries"])["balance"]==1008

if __name__=="__main__": storage_test()
