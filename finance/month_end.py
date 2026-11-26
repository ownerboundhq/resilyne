"""Fictional single-company monthly close. No external ledger changes."""
import argparse
import calendar
import hashlib
import json
import re
from contextlib import closing
from datetime import date,timedelta
from pathlib import Path
from .office import strict_keys,text,cents,day,records,unique,reject_duplicate_keys
from .worker import connect,event,now,read_limited,reconcile

CHECKS=("cutoff","inventory","payroll","sales_tax","accruals_and_prepaids","fixed_assets_and_depreciation","debt_and_interest","owner_and_intercompany","other_accounts")
TYPES=("asset","liability","equity","revenue","expense")
COMPANY="Fictional Neuravale Close Ltd."

def period_dates(period):
    if not isinstance(period,str) or not re.fullmatch(r"\d{4}-\d{2}",period):
        raise ValueError("Period must be YYYY-MM")
    start=day(period+"-01")
    end=start.replace(day=calendar.monthrange(start.year,start.month)[1])
    return start,end

def evaluate(data,today):
    strict_keys(data,("company","currency","period","accounts","journal","bank","receivables","payables","checks"))
    if data["company"]!=COMPANY or data["currency"]!="CAD":
        raise ValueError("Pilot only accepts the fictional CAD close company")
    start,end=period_dates(data["period"])
    if end>=today:
        raise ValueError("Period must have ended before closing")
    gates=[]
    def gate(name,ok,detail):
        gates.append({"name":name,"passed":bool(ok),"detail":detail})
    accounts={}
    for a in records(data["accounts"]):
        strict_keys(a,("id","name","type","opening_cents"))
        key=text(a["id"])
        if key in accounts or a["type"] not in TYPES:
            raise ValueError("Invalid or duplicate account: "+key)
        opening=cents(a["opening_cents"])
        if a["type"] in ("revenue","expense") and opening:
            raise ValueError("Monthly income accounts must start at zero; opening equity includes prior results")
        accounts[key]={"id":key,"name":text(a["name"]),"type":a["type"],"opening_cents":opening,"net_cents":opening}
    for key,kind in (("cash","asset"),("ar","asset"),("ap","liability")):
        if key not in accounts or accounts[key]["type"]!=kind:
            raise ValueError("Missing or invalid control account: "+key)
    gate("Opening trial balance",sum(a["opening_cents"] for a in accounts.values())==0,"Opening balances must balance.")
    seen=set()
    cash_rows=[]
    for entry in records(data["journal"]):
        strict_keys(entry,("id","date","evidence","lines"))
        ref=text(entry["id"]);unique(seen,ref)
        posted=day(entry["date"])
        text(entry["evidence"])
        if not start<=posted<=end:
            raise ValueError("Out-of-period journal: "+ref)
        lines=records(entry["lines"])
        if len(lines)<2:
            raise ValueError("Journal needs at least two lines")
        net=0
        cash_net=0
        for line in lines:
            strict_keys(line,("account","debit_cents","credit_cents"))
            key=text(line["account"])
            if key not in accounts:
                raise ValueError("Unknown account "+key)
            d,c=cents(line["debit_cents"]),cents(line["credit_cents"])
            if d<0 or c<0 or (d>0)==(c>0):
                raise ValueError("Exactly one positive amount per journal line")
            delta=d-c
            net+=delta
            accounts[key]["net_cents"]+=delta
            if key=="cash": cash_net+=delta
        if net:
            raise ValueError("Unbalanced journal: "+ref)
        if cash_net:
            cash_rows.append({"reference":ref,"date":posted.isoformat(),"cents":cash_net})
    gate("Journal arithmetic and cutoff",True,"All entries balance, are within the month and include supplied evidence identifiers.")
    bank=data["bank"]
    strict_keys(bank,("opening_cents","closing_cents","statement_id","transactions"))
    text(bank["statement_id"])
    bo,bc=cents(bank["opening_cents"]),cents(bank["closing_cents"])
    bank_rows=[]
    for row in records(bank["transactions"]):
        strict_keys(row,("reference","date","cents"))
        ref=text(row["reference"]);dt=day(row["date"]);amt=cents(row["cents"])
        if not start<=dt<=end or not amt:
            raise ValueError("Bank movement outside period or zero")
        bank_rows.append({"reference":ref,"date":dt.isoformat(),"cents":amt})
    rec,findings=reconcile(bank_rows,cash_rows)
    gate("Bank reconciliation",bo==accounts["cash"]["opening_cents"] and bo+sum(r["cents"] for r in bank_rows)==bc and bc==accounts["cash"]["net_cents"] and not findings,
         "Statement opening, movements, closing, cash control and unique transaction references must match exactly.")
    def control(rows,key,sign):
        seen=set()
        total=0
        for row in records(rows):
            strict_keys(row,("id","open_cents","evidence"))
            unique(seen,text(row["id"]));text(row["evidence"])
            value=cents(row["open_cents"])
            if value<=0:
                raise ValueError("Open item must be positive")
            total+=value
        expected=accounts[key]["net_cents"]*sign
        gate(key.upper()+" control account",total==expected,f"Open items {total} cents; GL control {expected} cents.")
        return total
    ar=control(data["receivables"],"ar",1)
    ap=control(data["payables"],"ap",-1)
    checks=data["checks"]
    if not isinstance(checks,dict) or set(checks)-set(CHECKS):
        raise ValueError("Unexpected close checklist")
    for name in CHECKS:
        item=checks.get(name)
        ok=False
        detail="Required review evidence missing."
        if item is not None:
            strict_keys(item,("status","evidence"))
            evidence=text(item["evidence"])
            if item["status"] not in ("reviewed","not_applicable","pending"):
                raise ValueError("Invalid checklist status")
            ok=item["status"] in ("reviewed","not_applicable")
            detail=item["status"]+": "+evidence+" (supplied fictional assertion; not independently verified)"
        gate(name,ok,detail)
    def total(kind):
        return sum(a["net_cents"] for a in accounts.values() if a["type"]==kind)
    rev=-total("revenue")
    exp=total("expense")
    profit=rev-exp
    assets=total("asset")
    liabilities=-total("liability")
    equity=-total("equity")
    trial=[dict(a,debit_cents=max(a["net_cents"],0),credit_cents=max(-a["net_cents"],0)) for a in accounts.values()]
    debits=sum(a["debit_cents"] for a in trial)
    credits=sum(a["credit_cents"] for a in trial)
    gate("Closing trial balance",debits==credits,"Closing debits equal credits.")
    gate("Balance sheet equation",assets==liabilities+equity+profit,"Assets = liabilities + opening/other equity + current month earnings.")
    return {"company":COMPANY,"period":data["period"],"gates":gates,"ready":all(g["passed"] for g in gates),
            "trial_balance":trial,"debits_cents":debits,"credits_cents":credits,
            "income_statement":{"revenue_cents":rev,"expenses_cents":exp,"net_income_cents":profit},
            "balance_sheet":{"assets_cents":assets,"liabilities_cents":liabilities,"equity_excluding_month_income_cents":equity,"month_income_cents":profit,"total_equity_cents":equity+profit},
            "bank":{"reconciliation":rec,"findings":[{"kind":k,"reference":r,"evidence":e} for k,r,e in findings]},
            "receivables_cents":ar,"payables_cents":ap,
            "note":"Fictional single-month management reports. Supplied evidence references and manual review assertions are not independent verification. No external books or income accounts are closed; local snapshot seal only."}

def schema(db):
    db.executescript("""
    CREATE TABLE IF NOT EXISTS month_close_runs(
        id TEXT PRIMARY KEY, period TEXT NOT NULL, input BLOB NOT NULL,
        state TEXT NOT NULL, report TEXT, error TEXT, created TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS month_close_seals(
        period TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES month_close_runs(id),
        sealed_at TEXT NOT NULL);
    """)

def tick(root,today=None):
    today=today or date.today()
    folder=root/"month_end"
    if not folder.exists(): return
    for path in sorted(folder.glob("*.json")):
        if not re.fullmatch(r"\d{4}-\d{2}\.json",path.name):
            continue
        try:
            raw=read_limited(path)
        except (OSError,ValueError) as exc:
            # An unreadable snapshot must never disappear behind an old successful report.
            raw=("UNREADABLE: "+str(exc)).encode("utf-8")
        period=path.stem
        key=hashlib.sha256(period.encode()+b"\0"+raw).hexdigest()
        with closing(connect(root)) as db, db:
            schema(db)
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM month_close_runs WHERE id=?",(key,)).fetchone():
                continue
            seal=db.execute("SELECT run_id FROM month_close_seals WHERE period=?",(period,)).fetchone()
            state="blocked"; report=None; error=None
            if seal:
                state="sealed_conflict"
                error="Period already sealed. Changed source requires explicit review; original sealed snapshot preserved."
            else:
                try:
                    data=json.loads(raw.decode("utf-8-sig"),object_pairs_hook=reject_duplicate_keys)
                    if not isinstance(data,dict) or data.get("period")!=period:
                        raise ValueError("Snapshot period must match filename")
                    report=evaluate(data,today)
                    state="ready" if report["ready"] else "blocked"
                except (ValueError,TypeError,RecursionError) as exc:
                    error=str(exc)
                    # Future periods are retried when eligible instead of being permanently blocked.
                    try:
                        if period_dates(period)[1]>=today:
                            continue
                    except ValueError:
                        pass
            db.execute("INSERT INTO month_close_runs VALUES(?,?,?,?,?,?,?)",
                       (key,period,raw,state,json.dumps(report) if report else None,error,now()))
            event(db,"month_end_"+state,None,period+": "+(error or ("All fictional close gates passed; awaiting explicit seal" if state=="ready" else "Review required")))

def seal(root,period,expected):
    period_dates(period)
    # Re-read before sealing to reject stale approvals.
    raw=read_limited(root/"month_end"/(period+".json"))
    key=hashlib.sha256(period.encode()+b"\0"+raw).hexdigest()
    if key!=expected:
        raise ValueError("Snapshot changed; refresh and review new report")
    with closing(connect(root)) as db, db:
        schema(db)
        db.execute("BEGIN IMMEDIATE")
        row=db.execute("SELECT * FROM month_close_runs WHERE id=? AND period=?",(key,period)).fetchone()
        if not row or row["state"]!="ready":
            raise ValueError("Only a ready reviewed snapshot can be sealed")
        old=db.execute("SELECT run_id FROM month_close_seals WHERE period=?",(period,)).fetchone()
        if old:
            if old["run_id"]==key: return key
            raise ValueError("Period already sealed")
        db.execute("INSERT INTO month_close_seals VALUES(?,?,?)",(period,key,now()))
        event(db,"month_end_sealed",None,period+": local fictional snapshot sealed; no external ledger change")
    return key

def latest(root):
    with closing(connect(root)) as db, db:
        schema(db)
        rows=db.execute("""SELECT r.id,r.period,r.state,r.report,r.error,r.created,s.run_id AS sealed_id,s.sealed_at
             FROM month_close_runs r LEFT JOIN month_close_seals s ON s.period=r.period
             WHERE r.rowid IN (SELECT max(rowid) FROM month_close_runs GROUP BY period)
             ORDER BY r.period DESC LIMIT 24""").fetchall()
    result=[]
    for row in rows:
        d=dict(row)
        d["report"]=json.loads(d["report"]) if d["report"] else None
        if d["id"]==d["sealed_id"]: d["state"]="sealed"
        result.append(d)
    return result

def demo(root,today=None,blocked=False):
    today=today or date.today()
    end=today.replace(day=1)-timedelta(days=1)
    start=end.replace(day=1)
    period=end.strftime("%Y-%m")
    def account(id,name,kind,opening=0):
        return {"id":id,"name":name,"type":kind,"opening_cents":opening}
    def journal(id,dr,cr,amt):
        return {"id":id,"date":start.isoformat(),"evidence":"fictional:"+id,
                "lines":[{"account":dr,"debit_cents":amt,"credit_cents":0},{"account":cr,"debit_cents":0,"credit_cents":amt}]}
    def movement(id,amt):
        return {"reference":id,"date":start.isoformat(),"cents":amt}
    data={"company":COMPANY,"currency":"CAD","period":period,
          "accounts":[account("cash","Bank","asset",500000),account("ar","Receivables","asset"),account("ap","Payables","liability"),account("equity","Opening equity","equity",-500000),account("sales","Revenue","revenue"),account("rent","Rent expense","expense"),account("supplies","Supplies expense","expense")],
          "journal":[journal("SALE1","cash","sales",300000),journal("INV1","ar","sales",120000),journal("RENT1","rent","cash",100000),journal("BILL1","supplies","ap",45000)],
          "bank":{"opening_cents":500000,"closing_cents":700000 if not blocked else 699999,"statement_id":"fictional-bank-statement","transactions":[movement("SALE1",300000),movement("RENT1",-100000)]},
          "receivables":[{"id":"INV1","open_cents":120000,"evidence":"fictional invoice"}],
          "payables":[{"id":"BILL1","open_cents":45000,"evidence":"fictional bill"}],
          "checks":{k:{"status":"reviewed" if k=="cutoff" else "not_applicable","evidence":"Fictional scenario: "+k+" reviewed or no applicable transactions"} for k in CHECKS}}
    folder=root/"month_end";folder.mkdir(parents=True,exist_ok=True)
    path=folder/(period+".json")
    with path.open("x",encoding="utf-8") as f: json.dump(data,f,indent=2)
    return period

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workspace",type=Path,required=True)
    sub=p.add_subparsers(dest="action",required=True)
    d=sub.add_parser("demo");d.add_argument("--blocked",action="store_true")
    sub.add_parser("once")
    sub.add_parser("status")
    s=sub.add_parser("seal");s.add_argument("period");s.add_argument("fingerprint")
    a=p.parse_args()
    if a.action=="demo": print(demo(a.workspace,blocked=a.blocked))
    elif a.action=="once": tick(a.workspace);print(json.dumps(latest(a.workspace),indent=2))
    elif a.action=="status": print(json.dumps(latest(a.workspace),indent=2))
    else: print(seal(a.workspace,a.period,a.fingerprint))

if __name__=="__main__": main()
