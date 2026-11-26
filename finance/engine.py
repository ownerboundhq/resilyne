"""Neuravale Intelligence Engine: durable, allowlisted fictional-office controller.

The planner is deterministic, not an LLM. Executors and verifiers are separate jobs.
Only built-in practice tools are authorized; no credentials, live ledger writes or mouse
injection in unattended mode. Separate fictional companies are not a unified ledger.
"""
import argparse
import hashlib
import json
import time
import uuid
from contextlib import closing
from datetime import date,timedelta
from pathlib import Path
from .worker import connect,event,read_limited,parse,reconcile,now
from .office import reject_duplicate_keys
from . import office,month_end,extended_finance,intelligence
from .autonomy import run_browser,atomic_report

VERSION="engine-v1"
MAX_ATTEMPTS=3
LEASE_SECONDS=300
TOOLS={
    "daily_prepare":("Accountant","Refresh daily accounting reports"),
    "daily_verify":("Controller","Check daily accounting outputs"),
    "browser_execute":("Bookkeeper","Operate isolated browser ledger and correct authorized fee"),
    "browser_verify":("Audit specialist","Reconcile saved browser exports and validate fee correction"),
    "close_prepare":("Accountant","Calculate specialist month-end schedules"),
    "close_verify":("Audit specialist","Independently check close balances and adjusting entries"),
    "close_seal":("Controller","Seal verified exact fictional month-end snapshot"),
    "extended_prepare":("Treasury / Tax specialists","Prepare extended schedules and filing readiness"),
    "extended_verify":("Audit specialist","Validate extended schedules, source and report backup"),
}

def encode(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def digest(value):
    return hashlib.sha256(value).hexdigest()
def check(ok,reason):
    if not ok: raise ValueError(reason)
def schema(db):
    db.executescript("""
    CREATE TABLE IF NOT EXISTS engine_jobs(
        id TEXT PRIMARY KEY, tool TEXT NOT NULL, role TEXT NOT NULL, scope TEXT NOT NULL,
        reason TEXT NOT NULL, inputs TEXT NOT NULL, dependencies TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1, state TEXT NOT NULL DEFAULT 'queued',
        attempts INTEGER NOT NULL DEFAULT 0, next_due REAL NOT NULL DEFAULT 0,
        lease_until REAL NOT NULL DEFAULT 0, token TEXT, result TEXT, error TEXT,
        created TEXT NOT NULL, updated TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS engine_active ON engine_jobs(active,state,next_due);
    """)

def source_hash(path):
    try: return digest(read_limited(path))
    except (OSError,ValueError): return "unavailable"

def plan(root,today):
    """Discover due daily, monthly and changed-source work. Stable IDs deduplicate work."""
    previous=today.replace(day=1)-timedelta(days=1)
    period=previous.strftime("%Y-%m")
    try: office.demo(root,today)
    except FileExistsError: pass
    try: month_end.demo(root,today,advanced=True)
    except FileExistsError: pass
    p=root/"intelligence"/(period+".json")
    p.parent.mkdir(parents=True,exist_ok=True)
    try:
        with p.open("x",encoding="utf-8") as f: json.dump(extended_finance.sample(period),f,indent=2)
    except FileExistsError: pass
    daily={"day":today.isoformat(),"source":source_hash(root/"office.json")}
    monthly={"period":period,"source":source_hash(root/"month_end"/(period+".json"))}
    # Past source fingerprints are part of the dependency for quarterly/yearly rollups.
    past=[(f.stem,source_hash(f)) for f in sorted((root/"month_end").glob("*.json")) if f.stem!=period]
    extended={"period":period,"source":source_hash(p),"month_source":monthly["source"],"past":past}
    jobs=[]
    def add(tool,scope,inputs,dependencies=()):
        role,reason=TOOLS[tool]
        spec={"version":VERSION,"tool":tool,"scope":scope,"inputs":inputs,"dependencies":list(dependencies)}
        key=digest(encode(spec).encode())
        jobs.append(dict(spec,id=key,role=role,reason=reason))
        return key
    d=add("daily_prepare",daily["day"],daily)
    add("daily_verify",daily["day"],daily,[d])
    b=add("browser_execute",daily["day"],{"day":daily["day"],"fixture":"fee-001-v1"})
    add("browser_verify",daily["day"],{"day":daily["day"],"fixture":"fee-001-v1"},[b])
    c=add("close_prepare",period,monthly)
    v=add("close_verify",period,monthly,[c])
    s=add("close_seal",period,monthly,[v])
    e=add("extended_prepare",period,extended,[s])
    add("extended_verify",period,extended,[e])
    with closing(connect(root)) as db,db:
        schema(db);db.execute("BEGIN IMMEDIATE")
        db.execute("UPDATE engine_jobs SET active=0 WHERE active=1")
        for j in jobs:
            cur=db.execute("""INSERT OR IGNORE INTO engine_jobs
              (id,tool,role,scope,reason,inputs,dependencies,created,updated)
              VALUES(?,?,?,?,?,?,?,?,?)""",(j["id"],j["tool"],j["role"],j["scope"],j["reason"],encode(j["inputs"]),encode(j["dependencies"]),now(),now()))
            db.execute("UPDATE engine_jobs SET active=1 WHERE id=?",(j["id"],))
            if cur.rowcount: event(db,"engine_assigned",None,j["role"]+": "+j["reason"])
    return [j["id"] for j in jobs]

def claim(root,at):
    with closing(connect(root)) as db,db:
        schema(db);db.execute("BEGIN IMMEDIATE")
        # Crash recovery. Failed attempts count against the bounded retry budget.
        db.execute("""UPDATE engine_jobs SET state=CASE WHEN attempts>=? THEN 'failed' ELSE 'retry' END,
          token=NULL,lease_until=0,error='Interrupted execution; lease expired',next_due=?,updated=?
          WHERE state='running' AND lease_until<=?""",(MAX_ATTEMPTS,at,now(),at))
        rows=db.execute("SELECT * FROM engine_jobs WHERE active=1 ORDER BY rowid").fetchall()
        # Single active execution across the workspace.
        if any(r["state"]=="running" for r in rows): return None
        states={r["id"]:r["state"] for r in rows}
        for r in rows:
            if r["state"] not in ("queued","retry") or r["next_due"]>at: continue
            deps=json.loads(r["dependencies"])
            if any(states.get(d) in ("blocked","failed","needs_review") for d in deps):
                db.execute("UPDATE engine_jobs SET state='blocked',error='Dependency requires review',updated=? WHERE id=?",(now(),r["id"]))
                states[r["id"]]="blocked"
                continue
            if not all(states.get(d)=="completed" for d in deps): continue
            token=uuid.uuid4().hex
            db.execute("UPDATE engine_jobs SET state='running',attempts=attempts+1,token=?,lease_until=?,updated=? WHERE id=?",
                       (token,at+LEASE_SECONDS,now(),r["id"]))
            job=dict(r);job.update(token=token,attempts=r["attempts"]+1,inputs=json.loads(r["inputs"]),dependencies=deps)
            event(db,"engine_started",None,r["role"]+": "+r["reason"])
            return job
    return None

def finish(root,job,state,result=None,error=None,at=None):
    at=time.time() if at is None else at
    if state=="retry" and job["attempts"]>=MAX_ATTEMPTS: state="failed"
    with closing(connect(root)) as db,db:
        schema(db);db.execute("BEGIN IMMEDIATE")
        changed=db.execute("""UPDATE engine_jobs SET state=?,result=?,error=?,token=NULL,lease_until=0,
          next_due=?,updated=? WHERE id=? AND state='running' AND token=?""",
          (state,encode(result) if result is not None else None,error,at+min(300,30*2**(job["attempts"]-1)) if state=="retry" else 0,now(),job["id"],job["token"])).rowcount
        if changed: event(db,"engine_"+state,None,job["role"]+": "+job["reason"]+(" — "+error if error else ""))
    return bool(changed)

def dependency(root,job):
    check(len(job["dependencies"])==1,"Missing execution dependency")
    with closing(connect(root)) as db,db:
        r=db.execute("SELECT state,result FROM engine_jobs WHERE id=?",(job["dependencies"][0],)).fetchone()
    check(r and r["state"]=="completed" and r["result"],"Dependency output unavailable")
    return json.loads(r["result"])

def verify_daily(report):
    a=report["accountant"];t=report["treasury"]
    check(sum(x["debit_cents"] for x in a["trial_balance"])==a["total_debit_cents"]==a["total_credit_cents"]==sum(x["credit_cents"] for x in a["trial_balance"]),"Trial balance check failed")
    for k in ("receivables","payables"):
        ar=report[k]
        check(sum(ar["buckets"].values())==ar["total_cents"]==sum(x["open_cents"] for x in ar["items"]),"Aging totals do not tie")
    check(t["snapshot_cash_cents"]+t["scheduled_incoming_cents"]-t["scheduled_outgoing_cents"]==t["illustrative_ending_cash_cents"],"Cash scenario check failed")

def verify_close(report):
    check(report["ready"] and all(g["passed"] for g in report["gates"]) and report["specialists"],"Close gates not passed")
    trial=report["trial_balance"];inc=report["income_statement"];bal=report["balance_sheet"]
    check(sum(a["net_cents"] for a in trial)==0,"Closing trial balance does not balance")
    check(sum(a["debit_cents"] for a in trial)==sum(a["credit_cents"] for a in trial)==report["debits_cents"]==report["credits_cents"],"Closing totals mismatch")
    check(inc["revenue_cents"]==-sum(a["net_cents"] for a in trial if a["type"]=="revenue"),"Revenue mismatch")
    check(inc["expenses_cents"]==sum(a["net_cents"] for a in trial if a["type"]=="expense"),"Expense mismatch")
    check(inc["revenue_cents"]-inc["expenses_cents"]==inc["net_income_cents"]==bal["month_income_cents"],"Income mismatch")
    check(bal["assets_cents"]==bal["liabilities_cents"]+bal["total_equity_cents"],"Balance sheet equation failed")
    check(not report["bank"]["findings"],"Unresolved bank reconciliation")
    for journal in report["specialists"]["adjustments"]["generated_journals"]:
        check(sum(l["debit_cents"] for l in journal["lines"])==sum(l["credit_cents"] for l in journal["lines"]),"Unbalanced adjustment")

def exact_close_source(root,today,inputs):
    import tempfile
    period=inputs["period"];path=root/"month_end"/(period+".json")
    raw=read_limited(path)
    check(digest(raw)==inputs["source"],"Close source changed; replan required")
    with tempfile.TemporaryDirectory() as tmp:
        ref=Path(tmp)
        check(month_end.demo(ref,today,advanced=True)==period,"Unexpected close period")
        check(raw==read_limited(ref/"month_end"/(period+".json")),"Only exact approved fictional source may be sealed automatically")
    return raw

def current_close(root,period):
    row=next((r for r in month_end.latest(root) if r["period"]==period),None)
    check(row and row["report"] and row["state"] in ("ready","sealed"),"Current close is unavailable or blocked")
    return row

def run_tool(root,job,today,browser):
    tool=job["tool"];i=job["inputs"]
    check(tool in TOOLS,"Tool not authorized")
    if tool in ("daily_prepare","daily_verify"):
        raw=read_limited(root/"office.json")
        check(digest(raw)==i["source"],"Daily source changed; replan required")
        data=json.loads(raw.decode("utf-8-sig"),object_pairs_hook=reject_duplicate_keys)
        check(data.get("company")=="Fictional Neuravale Demo Ltd.","Only fictional office data authorized")
        if tool=="daily_prepare": office.tick(root,today)
        row=office.latest(root)
        check(row and row["state"]=="complete" and row["report"]["report_date"]==i["day"],"Daily report unavailable")
        if tool=="daily_verify":
            check(row["id"]==dependency(root,job)["report_id"],"Daily output changed")
            check(row["report"]==office.calculate(data,today),"Daily source recalculation mismatch")
            verify_daily(row["report"])
        return "completed",{"report_id":row["id"],"source":i["source"],"verified":tool=="daily_verify"}
    if tool=="browser_execute":
        r=browser(root)
        check(isinstance(r.get("batch_id"),str) and r["before"]==2 and r["after"]==1,"Unexpected browser outcome")
        return "completed",{"batch_id":r["batch_id"],"verified":False}
    if tool=="browser_verify":
        key=dependency(root,job)["batch_id"]
        with closing(connect(root)) as db,db:
            row=db.execute("SELECT * FROM batches WHERE id=?",(key,)).fetchone()
        check(row and row["state"]=="complete","Saved browser batch unavailable")
        bank,ledger=parse(row["bank"]),parse(row["ledger"])
        result,findings=reconcile(bank,ledger)
        check(result==json.loads(row["report"]),"Saved reconciliation mismatch")
        check(len(findings)==1 and findings[0][:2]==("date_or_amount_mismatch","BILL-001"),"Unexpected remaining browser discrepancies")
        fee=[x for x in ledger if x["reference"]=="FEE-001"]
        check(len(fee)==1 and fee[0]["cents"]==-300 and fee[0]["date"]=="2026-11-24","Fee correction not verified")
        return "needs_review",{"batch_id":key,"verified":True,"open_discrepancies":1,"detail":"Authorized fee verified; separate BILL-001 discrepancy remains open."}
    if tool in ("close_prepare","close_verify","close_seal"):
        raw=exact_close_source(root,today,i)
        if tool=="close_prepare": month_end.tick(root,today)
        row=current_close(root,i["period"]);r=row["report"]
        check(row["id"]==digest(i["period"].encode()+b"\0"+raw),"Close fingerprint mismatch")
        if tool!="close_prepare":
            check(dependency(root,job)["close_id"]==row["id"],"Close output changed")
            check(r==month_end.evaluate(json.loads(raw.decode("utf-8-sig"),object_pairs_hook=reject_duplicate_keys),today),"Close recalculation mismatch")
            verify_close(r)
        if tool=="close_seal":
            exact_close_source(root,today,i)
            if row["state"]=="ready": month_end.seal(root,i["period"],row["id"])
            row=current_close(root,i["period"])
            check(row["state"]=="sealed" and row["sealed_id"]==row["id"],"Seal readback failed")
            # Stable format used by the legacy autonomous office, to support safe migration.
            payload={"mode":"fictional automatic close only","period":i["period"],"close_id":row["id"],"source_sha256":i["source"],"sealed_at":row["sealed_at"],"report":row["report"],"note":"Independent fictional monthly company. Daily browser practice ledger is a separate exercise; its unresolved discrepancy is not waived or closed here."}
            path=root/"reports"/("autonomous-close-"+i["period"]+"-"+row["id"][:12]+".json")
            atomic_report(path,payload)
            check(json.loads(path.read_text(encoding="utf-8"))==payload,"Close package readback failed")
            return "completed",{"close_id":row["id"],"verified":True,"sealed":True,"report_file":path.name}
        return "completed",{"close_id":row["id"],"verified":tool=="close_verify"}
    if tool in ("extended_prepare","extended_verify"):
        raw=read_limited(root/"intelligence"/(i["period"]+".json"))
        check(digest(raw)==i["source"],"Extended source changed; replan required")
        check(source_hash(root/"month_end"/(i["period"]+".json"))==i["month_source"],"Month dependency changed")
        for p,expected in i["past"]:
            check(source_hash(root/"month_end"/(p+".json"))==expected,"Historical month source changed")
        result=intelligence.tick(root,today)
        check(result["state"]=="prepared" and result["report"],result.get("error") or "Extended schedules require review")
        r=result["report"];key=result["id"]
        if tool=="extended_verify":
            check(key==dependency(root,job)["report_id"],"Extended output changed")
            calculated=extended_finance.calculate(json.loads(raw.decode("utf-8-sig"),object_pairs_hook=reject_duplicate_keys))
            check(r["financial"]==calculated and intelligence.verify(calculated)["passed"] and not calculated["review_required"],"Extended verification failed")
            check(r["compliance"]["status"]=="not_ready_to_file","Unexpected filing status")
            path=root/"reports"/("intelligence-"+i["period"]+"-"+key[:12]+".json")
            check(json.loads(path.read_text(encoding="utf-8"))==r,"Extended report readback failed")
            intelligence.backup(root,key)
        return "completed",{"report_id":key,"verified":tool=="extended_verify","filing":"not_ready_to_file"}
    raise ValueError("Unsupported tool")

def snapshot(root):
    with closing(connect(root)) as db,db:
        schema(db)
        rows=[dict(r) for r in db.execute("SELECT id,tool,role,scope,reason,dependencies,active,state,attempts,result,error,updated FROM engine_jobs ORDER BY active DESC,rowid DESC LIMIT 100")]
    for r in rows:
        r["dependencies"]=json.loads(r["dependencies"])
        r["result"]=json.loads(r["result"]) if r["result"] else None
    active=[r for r in rows if r["active"]]
    return {"mode":"fictional-only deterministic orchestration","counts":{state:sum(r["state"]==state for r in active) for state in ("queued","running","retry","completed","needs_review","blocked","failed")},"jobs":rows}

def tick(root,today=None,browser=run_browser,clock=time.time,max_jobs=12):
    today=today or date.today()
    plan(root,today)
    for _ in range(max_jobs):
        job=claim(root,clock())
        if not job: break
        try:
            state,result=run_tool(root,job,today,browser)
            finish(root,job,state,result,at=clock())
        except (ValueError,KeyError,TypeError,AttributeError) as exc:
            finish(root,job,"blocked",error=str(exc)[:500],at=clock())
        except Exception as exc:
            finish(root,job,"retry",error=type(exc).__name__+": "+str(exc)[:300],at=clock())
    return snapshot(root)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workspace",type=Path,required=True)
    p.add_argument("action",choices=["once","status"])
    a=p.parse_args()
    print(json.dumps(tick(a.workspace) if a.action=="once" else snapshot(a.workspace),indent=2))
if __name__=="__main__": main()
