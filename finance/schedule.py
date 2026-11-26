"""Durable lease and retry for the explicitly enabled fictional browser job."""
import subprocess
import sys
import time
import uuid
from contextlib import closing
from .worker import connect,event
from .runtime import command

def schema(db):
    db.execute("""CREATE TABLE IF NOT EXISTS schedules(
      name TEXT PRIMARY KEY, next_due REAL NOT NULL, lease_until REAL NOT NULL,
      token TEXT, last_result TEXT, attempts INTEGER NOT NULL DEFAULT 0)""")

def claim(root,name,at,lease=180):
    with closing(connect(root)) as db, db:
        schema(db)
        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT OR IGNORE INTO schedules(name,next_due,lease_until) VALUES(?,0,0)",(name,))
        row=db.execute("SELECT * FROM schedules WHERE name=?",(name,)).fetchone()
        if row["next_due"]>at or row["lease_until"]>at:
            return None
        token=uuid.uuid4().hex
        db.execute("UPDATE schedules SET token=?,lease_until=?,attempts=attempts+1 WHERE name=?",(token,at+lease,name))
        event(db,"scheduled_started",None,name)
        return token

def finish(root,name,token,at,ok,detail,interval=300):
    with closing(connect(root)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        changed=db.execute("UPDATE schedules SET token=NULL,lease_until=0,next_due=?,last_result=? WHERE name=? AND token=?",
                           (at+(interval if ok else 120),detail[:500],name,token)).rowcount
        if changed:
            event(db,"scheduled_completed" if ok else "scheduled_failed",None,name+": "+detail[:500])
        return bool(changed)

def browser_tick(root):
    name="fictional_browser_export"
    token=claim(root,name,time.time())
    if not token:
        return False
    try:
        result=subprocess.run(command("finance.browser_pilot",["--workspace",str(root),"--headless"]),capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=90)
        ok=result.returncode==0
        detail=(result.stdout if ok else result.stderr).strip()[-500:]
    except (OSError,subprocess.TimeoutExpired) as exc:
        ok=False;detail=str(exc)
    finish(root,name,token,time.time(),ok,detail)
    return ok
