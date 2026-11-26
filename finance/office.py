"""Local financial office reports from an explicit, fictional snapshot.

All amounts are integer CAD cents. No external writes or financial advice.
"""
import hashlib
import json
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
from .worker import connect, event, now, read_limited

def strict_keys(obj, keys):
    if not isinstance(obj,dict) or set(obj)!=set(keys):
        raise ValueError("Unexpected fields; expected "+", ".join(keys))

def text(value):
    if not isinstance(value,str) or not value.strip() or len(value)>200:
        raise ValueError("Invalid text field")
    return value.strip()

def cents(value):
    if type(value) is not int or abs(value)>10**12:
        raise ValueError("Use integer cents, magnitude at most 10^12")
    return value

def day(value):
    if not isinstance(value,str):
        raise ValueError("Use ISO date")
    d=date.fromisoformat(value)
    if d.isoformat()!=value:
        raise ValueError("Use YYYY-MM-DD")
    return d

def records(value):
    if not isinstance(value,list) or len(value)>10000:
        raise ValueError("Expected list of at most 10,000 rows")
    return value

def unique(seen, key):
    if key in seen:
        raise ValueError("Duplicate record: "+key)
    seen.add(key)

def calculate(data, today):
    strict_keys(data,("company","currency","as_of","cash_cents","journal","receivables","payables","deadlines"))
    company=text(data["company"])
    if data["currency"]!="CAD":
        raise ValueError("Only CAD supported")
    asof=day(data["as_of"])
    if asof>today:
        raise ValueError("Snapshot is future dated")
    cash=cents(data["cash_cents"])
    accounts={}
    seen=set()
    for entry in records(data["journal"]):
        strict_keys(entry,("id","date","lines"))
        unique(seen,text(entry["id"]))
        if day(entry["date"])>asof:
            raise ValueError("Journal entry after snapshot")
        lines=records(entry["lines"])
        if len(lines)<2:
            raise ValueError("Journal entry must have at least two lines")
        debit=credit=0
        for line in lines:
            strict_keys(line,("account","debit_cents","credit_cents"))
            account=text(line["account"])
            d,c=cents(line["debit_cents"]),cents(line["credit_cents"])
            if d<0 or c<0 or (d>0)==(c>0):
                raise ValueError("Exactly one positive debit or credit per line")
            debit+=d;credit+=c
            row=accounts.setdefault(account,{"account":account,"debit_cents":0,"credit_cents":0})
            row["debit_cents"]+=d;row["credit_cents"]+=c
        if debit!=credit:
            raise ValueError("Unbalanced journal entry "+entry["id"])
    trial=[]
    for account in sorted(accounts):
        a=accounts[account]
        net=a["debit_cents"]-a["credit_cents"]
        trial.append({"account":account,"debit_cents":max(net,0),"credit_cents":max(-net,0)})
    def aging(rows):
        seen=set()
        buckets={"not_due":0,"1_30":0,"31_60":0,"61_90":0,"over_90":0}
        due=[]
        for row in records(rows):
            strict_keys(row,("id","party","due","open_cents"))
            key=text(row["id"]);unique(seen,key)
            party=text(row["party"])
            due_date=day(row["due"])
            amount=cents(row["open_cents"])
            if amount<=0:
                raise ValueError("Only positive open balances supported")
            age=(today-due_date).days
            bucket="not_due" if age<=0 else "1_30" if age<=30 else "31_60" if age<=60 else "61_90" if age<=90 else "over_90"
            buckets[bucket]+=amount
            due.append({"id":key,"party":party,"due":due_date.isoformat(),"open_cents":amount,"days_overdue":max(age,0)})
        return {"buckets":buckets,"total_cents":sum(buckets.values()),"items":due}
    ar,ap=aging(data["receivables"]),aging(data["payables"])
    horizon=today+timedelta(days=30)
    # Overdue amounts are included as immediately due; no assumption of actual collection.
    incoming=sum(r["open_cents"] for r in ar["items"] if day(r["due"])<=horizon)
    outgoing=sum(r["open_cents"] for r in ap["items"] if day(r["due"])<=horizon)
    deadlines=[]
    seen=set()
    for row in records(data["deadlines"]):
        strict_keys(row,("id","label","due","completed"))
        key=text(row["id"]);unique(seen,key)
        label=text(row["label"]);due=day(row["due"])
        if type(row["completed"]) is not bool:
            raise ValueError("completed must be boolean")
        if not row["completed"]:
            delta=(due-today).days
            deadlines.append({"id":key,"label":label,"due":due.isoformat(),"days_remaining":delta,"status":"overdue" if delta<0 else "due_soon" if delta<=30 else "upcoming"})
    return {"company":company,"snapshot_date":asof.isoformat(),"report_date":today.isoformat(),"stale_days":(today-asof).days,
            "accountant":{"trial_balance":trial,"total_debit_cents":sum(r["debit_cents"] for r in trial),"total_credit_cents":sum(r["credit_cents"] for r in trial)},
            "receivables":ar,"payables":ap,"tax_and_other_deadlines":sorted(deadlines,key=lambda x:x["due"]),
            "treasury":{"snapshot_cash_cents":cash,"scheduled_incoming_cents":incoming,"scheduled_outgoing_cents":outgoing,"illustrative_ending_cash_cents":cash+incoming-outgoing,
                        "note":"Scenario only: assumes all listed due balances settle and no other movements; cash may be stale."},
            "audit":{"balanced_entries":len(data["journal"]),"note":"Arithmetic check only; does not verify completeness, existence or assurance."}}

def schema(db):
    db.execute("""CREATE TABLE IF NOT EXISTS office_reports(
        id TEXT PRIMARY KEY, as_at TEXT NOT NULL, input BLOB NOT NULL,
        state TEXT NOT NULL, report TEXT, error TEXT, created TEXT NOT NULL)""")

def reject_duplicate_keys(pairs):
    obj={}
    for k,v in pairs:
        if k in obj:
            raise ValueError("Duplicate JSON field: "+k)
        obj[k]=v
    return obj

def tick(root,today=None):
    today=today or date.today()
    source=root/"office.json"
    if not source.exists():
        return None
    raw=read_limited(source)
    key=hashlib.sha256(today.isoformat().encode()+b"\0"+raw).hexdigest()
    with closing(connect(root)) as db, db:
        schema(db)
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT 1 FROM office_reports WHERE id=?",(key,)).fetchone():
            return key
        try:
            report=calculate(json.loads(raw.decode("utf-8-sig"),object_pairs_hook=reject_duplicate_keys),today)
        except (ValueError,TypeError,RecursionError) as exc:
            db.execute("INSERT INTO office_reports VALUES(?,?,?,'failed',NULL,?,?)",(key,today.isoformat(),raw,str(exc),now()))
            event(db,"office_failed",None,str(exc))
        else:
            db.execute("INSERT INTO office_reports VALUES(?,?,?,'complete',?,NULL,?)",(key,today.isoformat(),raw,json.dumps(report),now()))
            event(db,"office_completed",None,"Trial balance, receivables, payables, deadline checks and cash scenario refreshed; no ledger writes")
    return key

def latest(root):
    with closing(connect(root)) as db, db:
        schema(db)
        row=db.execute("SELECT id,as_at,state,report,error,created FROM office_reports ORDER BY rowid DESC LIMIT 1").fetchone()
    if row is None:
        return None
    result=dict(row)
    if result["report"]:
        result["report"]=json.loads(result["report"])
    return result

def demo(root,today=None):
    today=today or date.today()
    root.mkdir(parents=True,exist_ok=True)
    p=root/"office.json"
    data={"company":"Fictional Neuravale Demo Ltd.","currency":"CAD","as_of":today.isoformat(),"cash_cents":500000,
          "journal":[{"id":"J1","date":today.isoformat(),"lines":[{"account":"Cash","debit_cents":500000,"credit_cents":0},{"account":"Owner equity","debit_cents":0,"credit_cents":500000}]}],
          "receivables":[{"id":"AR1","party":"Example customer","due":(today-timedelta(days=12)).isoformat(),"open_cents":120000}],
          "payables":[{"id":"AP1","party":"Example supplier","due":(today+timedelta(days=7)).isoformat(),"open_cents":45000}],
          "deadlines":[{"id":"T1","label":"Illustrative GST/HST review (not a calculated statutory deadline)","due":(today+timedelta(days=15)).isoformat(),"completed":False}]}
    with p.open("x",encoding="utf-8") as f:
        json.dump(data,f,indent=2)
    return p

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--workspace",type=Path,default=Path.home()/"Neuravale-finance-desktop-demo")
    p.add_argument("action",choices=["demo","once","status"])
    a=p.parse_args()
    if a.action=="demo": print(demo(a.workspace))
    elif a.action=="once": print(tick(a.workspace))
    else: print(json.dumps(latest(a.workspace),indent=2))
