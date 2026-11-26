"""Opt-in autonomous fictional office. No external accounts or physical input."""
import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import time
from contextlib import closing
from datetime import date
from pathlib import Path
from .worker import connect,event,cycle,read_limited
from .schedule import claim,finish,schema as schedule_schema
from .runtime import command
from . import office,month_end

def set_status(root,key,state,detail):
    payload=json.dumps({"state":state,"detail":detail},ensure_ascii=False)
    with closing(connect(root)) as db, db:
        old=db.execute("SELECT value FROM runtime WHERE key=?",("autonomy_"+key,)).fetchone()
        if old and old[0]==payload: return
        db.execute("INSERT OR REPLACE INTO runtime VALUES(?,?)",("autonomy_"+key,payload))
        event(db,"autonomy_"+state,None,key+": "+detail)

def status(root):
    with closing(connect(root)) as db, db:
        schedule_schema(db)
        result={r["key"][len("autonomy_"):]:json.loads(r["value"]) for r in db.execute("SELECT * FROM runtime WHERE key LIKE 'autonomy_%'")}
        job=db.execute("SELECT next_due,lease_until,attempts,last_result FROM schedules WHERE name='autonomy_browser'").fetchone()
        if job: result["browser_schedule"]=dict(job)
    return result

def atomic_report(path,payload):
    content=json.dumps(payload,indent=2,ensure_ascii=False).encode("utf-8")
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if path.read_bytes()!=content:
            raise ValueError("Existing close package differs; manual review required")
        return
    fd,name=tempfile.mkstemp(prefix=".close-",dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(content);f.flush();os.fsync(f.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)

def prepare_month(root,today):
    # Exact fixture matching means no user-supplied or real ledger can be auto-sealed.
    with tempfile.TemporaryDirectory() as tmp:
        reference=Path(tmp)
        period=month_end.demo(reference,today,advanced=True)
        expected=read_limited(reference/"month_end"/(period+".json"))
    target=root/"month_end"/(period+".json")
    if not target.exists():
        try: month_end.demo(root,today,advanced=True)
        except FileExistsError: pass
    if read_limited(target)!=expected:
        set_status(root,"month_end","blocked","Source differs from approved fictional fixture; no autonomous seal.")
        return False
    month_end.tick(root,today)
    row=next((r for r in month_end.latest(root) if r["period"]==period),None)
    if not row or row["state"] not in ("ready","sealed") or not row["report"] or not row["report"].get("specialists"):
        set_status(root,"month_end","blocked","Current specialist close has unresolved checks.")
        return False
    # Verify current exact source again before local seal. No external transaction posting.
    if read_limited(target)!=expected:
        set_status(root,"month_end","blocked","Source changed during close.")
        return False
    if row["state"]=="ready":
        month_end.seal(root,period,row["id"])
    row=next(r for r in month_end.latest(root) if r["period"]==period)
    if row["state"]!="sealed" or row["id"]!=row["sealed_id"]:
        raise ValueError("Local close seal verification failed")
    report={"mode":"fictional automatic close only","period":period,"close_id":row["id"],
            "source_sha256":hashlib.sha256(expected).hexdigest(),"sealed_at":row["sealed_at"],"report":row["report"],
            "note":"Independent fictional monthly company. Daily browser practice ledger is a separate exercise; its unresolved discrepancy is not waived or closed here."}
    path=root/"reports"/("autonomous-close-"+period+"-"+row["id"][:12]+".json")
    atomic_report(path,report)
    set_status(root,"month_end","completed",period+": local snapshot sealed and verified report saved: "+path.name)
    return True

def run_browser(root):
    p=subprocess.run(command("finance.operation",["--workspace",str(root),"--headless"]),
                     capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=120)
    if p.returncode: raise RuntimeError("Browser practice task failed; see operations evidence.")
    result=json.loads(p.stdout.strip().splitlines()[-1])
    if result["before"]!=2 or result["after"]!=1:
        raise RuntimeError("Unexpected browser reconciliation result")
    return result

def tick(root,today=None,browser=run_browser,at=None):
    today=today or date.today()
    at=time.time() if at is None else at
    set_status(root,"mode","working","Authorized fictional-only autonomy. No real accounts or physical mouse control.")
    try:
        try: office.demo(root,today)
        except FileExistsError: pass
        office.tick(root,today)
        row=office.latest(root)
        if not row or row["state"]!="complete":
            set_status(root,"daily_office","blocked","Office report unavailable.")
        else:
            set_status(root,"daily_office","completed","Daily trial balance, AR/AP aging, deadline checks and cash scenario refreshed. Source date "+row["report"]["snapshot_date"]+".")
    except (OSError,ValueError,RuntimeError,KeyError,TypeError):
        set_status(root,"daily_office","blocked","Office inputs failed validation; review required.")
    token=claim(root,"autonomy_browser",at,lease=180)
    if token:
        set_status(root,"browser","working","Running isolated browser bookkeeping and verified fictional fee correction.")
        try:
            result=browser(root)
            if result["before"]!=2 or result["after"]!=1: raise ValueError("Unexpected result")
            set_status(root,"browser","needs_review","Verified permitted bank fee; one separate practice discrepancy remains unresolved.")
            finish(root,"autonomy_browser",token,at,True,"Verified correction; one unresolved discrepancy",interval=86400)
        except Exception:
            set_status(root,"browser","retry","Practice browser task failed; retry scheduled.")
            finish(root,"autonomy_browser",token,at,False,"Browser task failed; review local evidence.")
    try:
        prepare_month(root,today)
    except (OSError,ValueError,RuntimeError,KeyError,TypeError):
        set_status(root,"month_end","blocked","Month-end preparation or verification failed; no completion claim.")
    return status(root)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workspace",type=Path,required=True)
    p.add_argument("action",choices=["once","status"])
    a=p.parse_args()
    print(json.dumps(tick(a.workspace) if a.action=="once" else status(a.workspace),indent=2))

if __name__=="__main__": main()
