"""Deterministic orchestration, persistent policy memory, verified reports and backup.

No LLM is used. No arbitrary commands or applications may be chosen by the planner.
"""
import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import date,timedelta
from pathlib import Path
from .worker import connect,event,read_limited,now
from .office import reject_duplicate_keys
from .extended_finance import calculate,sample
from .month_end import latest
from .autonomy import atomic_report,set_status

def schema(db):
    db.execute("""CREATE TABLE IF NOT EXISTS intelligence_runs(
      id TEXT PRIMARY KEY, period TEXT NOT NULL, state TEXT NOT NULL,
      input BLOB NOT NULL, report TEXT, error TEXT, created TEXT NOT NULL)""")

def verify(report):
    """Separate read-only arithmetic checks, not professional assurance."""
    errors=[]
    for r in report["documents"]:
        if r["subtotal_cents"]+r["tax_cents"]!=r["total_cents"]: errors.append("Invoice arithmetic")
    totals={}
    for r in report["documents"]:
        if r["account"]: totals[r["account"]]=totals.get(r["account"],0)+r["subtotal_cents"]
    if totals!=report["expense_categories_cents"]: errors.append("Category total")
    if report["card"]["reconciled"] and report["card"]["exceptions"]: errors.append("Card control")
    if not all(r["reconciled"] for r in report["loans"]+report["related_parties"]):
        errors.append("Unresolved loan or related-party control")
    return {"passed":not errors,"errors":errors,"scope":"Independent arithmetic and control checks on derived outputs; not external source assurance."}

def period_rollup(rows,periods):
    """Only contiguous, current, sealed periods with compatible carry-forward."""
    by={r["period"]:r for r in rows}
    selected=[by.get(p) for p in periods]
    if not all(r and r["state"]=="sealed" and r["id"]==r["sealed_id"] and r["report"] for r in selected):
        return {"state":"blocked","reason":"Every constituent period must have a current verified local seal.","periods":periods}
    reports=[r["report"] for r in selected]
    company=reports[0]["company"]
    if any(r["company"]!=company for r in reports):
        return {"state":"blocked","reason":"Company mismatch.","periods":periods}
    for prev,nxt in zip(reports,reports[1:]):
        prior={a["id"]:a for a in prev["trial_balance"] if a["type"] not in ("revenue","expense")}
        current={a["id"]:a for a in nxt["trial_balance"] if a["type"] not in ("revenue","expense")}
        if set(prior)!=set(current):
            return {"state":"blocked","reason":"Chart of accounts changed.","periods":periods}
        for key,a in prior.items():
            expected=a["net_cents"]
            if key=="equity": expected-=prev["income_statement"]["net_income_cents"]
            if current[key]["type"]!=a["type"] or current[key]["opening_cents"]!=expected:
                return {"state":"blocked","reason":"Opening balance carry-forward mismatch: "+key,"periods":periods}
    revenue=sum(r["income_statement"]["revenue_cents"] for r in reports)
    expenses=sum(r["income_statement"]["expenses_cents"] for r in reports)
    return {"state":"prepared","periods":periods,"company":company,"source_ids":[r["id"] for r in selected],
            "revenue_cents":revenue,"expenses_cents":expenses,"net_income_cents":revenue-expenses,"ending_balance_sheet":reports[-1]["balance_sheet"]}

def compliance(report,rollups):
    # No invented tax rates, due dates, legal eligibility or filing approvals.
    return {"jurisdiction":"Canada / Ontario practice profile","status":"not_ready_to_file",
            "t2":{"state":"blocked","reason":"Verified fiscal-year ledger, tax adjustments, GIFI mapping and approved filing software required."},
            "gst_hst":{"state":"blocked","reason":"Complete reporting-period registers, eligibility verification and authorized return submission required."},
            "t4_t5":{"state":"source_worksheets_only","count":len(report["tax_source_worksheets"]),"reason":"Annual source register, statutory box calculations, validation and authorized filing required."},
            "assurance":{"state":"not_provided","reason":"Formal assurance requires the appropriate professional engagement."},
            "payments":{"state":"disabled","reason":"No authority to move funds."},
            "privacy":{"state":"practice_only","reason":"No production data, external recipients or credentials permitted; local files not encrypted by this pilot."},
            "annual_rollup":rollups["year"]["state"]}

def backup(root,key):
    path=root/"backups"/("finance-"+key[:20]+".sqlite3")
    path.parent.mkdir(parents=True,exist_ok=True)
    # SQLite online backup includes committed WAL data. Never overwrite an existing backup.
    if not path.exists():
        import tempfile,os
        fd,temp=tempfile.mkstemp(prefix=".backup-",dir=path.parent);os.close(fd)
        try:
            with closing(connect(root)) as source,closing(sqlite3.connect(temp)) as dest:
                source.backup(dest)
                if dest.execute("PRAGMA integrity_check").fetchone()[0]!="ok": raise ValueError("Backup integrity check failed")
            os.replace(temp,path)
        finally:
            if os.path.exists(temp): os.unlink(temp)
    with closing(sqlite3.connect(str(path))) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok": raise ValueError("Backup is corrupt")
    return path.name

def tick(root,today=None):
    today=today or date.today()
    end=today.replace(day=1)-timedelta(days=1)
    period=end.strftime("%Y-%m")
    folder=root/"intelligence";folder.mkdir(parents=True,exist_ok=True)
    source=folder/(period+".json")
    if not source.exists():
        try:
            with source.open("x",encoding="utf-8") as f: json.dump(sample(period),f,indent=2)
        except FileExistsError: pass
    raw=read_limited(source)
    rows=latest(root)
    # Dependency fingerprint includes current seal states and report content.
    deps=json.dumps(rows,sort_keys=True,ensure_ascii=False).encode()
    key=hashlib.sha256(b"extended-v1\0"+raw+b"\0"+deps).hexdigest()
    with closing(connect(root)) as db,db:
        schema(db)
        old=db.execute("SELECT * FROM intelligence_runs WHERE id=?",(key,)).fetchone()
    if old:
        state=old["state"]
        if state=="prepared":
            payload=json.loads(old["report"])
            atomic_report(root/"reports"/("intelligence-"+period+"-"+key[:12]+".json"),payload)
            backup(root,key)
        set_status(root,"intelligence",state,period+": "+("Verified practice package and database backup available." if state=="prepared" else (old["error"] or "Exceptions require review.")))
        return {"id":key,"state":state,"report":json.loads(old["report"]) if old["report"] else None,"error":old["error"]}
    report=None;error=None;state="blocked"
    try:
        data=json.loads(raw.decode("utf-8-sig"),object_pairs_hook=reject_duplicate_keys)
        if data.get("period")!=period: raise ValueError("Source period mismatch")
        financial=calculate(data)
        audit=verify(financial)
        quarter_end=((end.month-1)//3)*3+3
        quarter_year=end.year
        if end.month!=quarter_end:
            quarter_end-=3
            if quarter_end==0: quarter_end=12;quarter_year-=1
        quarter=[f"{quarter_year:04d}-{m:02d}" for m in range(quarter_end-2,quarter_end+1)]
        year=end.year if end.month==12 else end.year-1
        annual=[f"{year:04d}-{m:02d}" for m in range(1,13)]
        rollups={"quarter":period_rollup(rows,quarter),"year":period_rollup(rows,annual)}
        report={"period":period,"source_sha256":hashlib.sha256(raw).hexdigest(),"financial":financial,"verification":audit,"period_reports":rollups,
                "compliance":compliance(financial,rollups),"tasks":[{"role":"Bookkeeper","state":"prepared","work":"Extract labelled invoices and categorize from saved vendor policy"},
                  {"role":"Controller","state":"needs_review" if financial["review_required"] else "prepared","work":"Card, debt, related-party and anomaly checks"},
                  {"role":"Treasury","state":"prepared","work":"FX and budget variance schedules"},
                  {"role":"Tax specialist","state":"blocked","work":"Source worksheets only; no authorized filing"},
                  {"role":"Verifier","state":"prepared" if audit["passed"] else "blocked","work":"Independent arithmetic checks"}]}
        state="prepared" if audit["passed"] and not financial["review_required"] else "needs_review"
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError,RecursionError) as exc: error=str(exc)
    with closing(connect(root)) as db,db:
        schema(db)
        db.execute("INSERT OR IGNORE INTO intelligence_runs VALUES(?,?,?,?,?,?,?)",(key,period,state,raw,json.dumps(report) if report else None,error,now()))
        event(db,"intelligence_"+state,None,period+": "+(error or "Practice accounting tasks evaluated; no external action."))
    if state=="prepared":
        atomic_report(root/"reports"/("intelligence-"+period+"-"+key[:12]+".json"),report)
        backup(root,key)
    set_status(root,"intelligence",state,period+": "+(error or ("Verified practice package and database backup available." if state=="prepared" else "Exceptions require review.")))
    return {"id":key,"state":state,"report":report,"error":error}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--workspace",type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(tick(a.workspace),indent=2))

if __name__=="__main__": main()
