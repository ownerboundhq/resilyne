"""Single-user, local, read-only accounting reconciliation pilot."""
import argparse
from contextlib import closing
import csv
import hashlib
import html
import io
import json
import re
import sqlite3
import threading
import time
from datetime import date, datetime, timezone
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROLES = {
    "Bookkeeper": "Implemented: exact-reference reconciliation (CAD CSV)",
    "Controller": "Implemented: exception queue and evidence review",
    "Accountant": "Implemented pilot: trial balance, monthly statements and close checklist",
    "Tax specialist": "Implemented pilot: GST/HST reconciliation and deadline monitoring; returns planned",
    "AR specialist": "Implemented pilot: open receivable aging",
    "AP specialist": "Implemented pilot: open payable aging",
    "Payroll specialist": "Implemented pilot: payroll register and remittance reconciliation; statutory calculation planned",
    "Audit specialist": "Implemented pilot: journal balance and input fingerprint; not assurance",
    "Treasury specialist": "Implemented pilot: 30-day scheduled cash projection",
}
FIELDS = ["reference", "date", "amount"]
MAX_BYTES = 5_000_000
MAX_ROWS = 20_000

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def connect(root):
    root.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(root / "finance.sqlite3", timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS batches (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, created TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('queued','complete','failed')),
        bank BLOB NOT NULL, ledger BLOB NOT NULL, report TEXT, error TEXT
    );
    CREATE TABLE IF NOT EXISTS findings (
        id INTEGER PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES batches(id),
        kind TEXT NOT NULL, reference TEXT NOT NULL, evidence TEXT NOT NULL,
        reviewed TEXT, reason TEXT, UNIQUE(batch_id,reference)
    );
    CREATE TABLE IF NOT EXISTS activity (
        id INTEGER PRIMARY KEY, at TEXT NOT NULL, event TEXT NOT NULL,
        batch_id TEXT, detail TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS runtime (key TEXT PRIMARY KEY,value TEXT NOT NULL);
    """)
    return db

def event(db, kind, batch_id, detail):
    db.execute("INSERT INTO activity(at,event,batch_id,detail) VALUES(?,?,?,?)",
               (now(),kind,batch_id,detail))

def parse(raw):
    if len(raw) > MAX_BYTES:
        raise ValueError("CSV exceeds 5 MB")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    if reader.fieldnames != FIELDS:
        raise ValueError("Required CSV header: reference,date,amount")
    rows = []
    for line, row in enumerate(reader, 2):
        if len(rows) >= MAX_ROWS:
            raise ValueError("CSV exceeds 20,000 rows")
        if None in row or any(row.get(k) is None for k in FIELDS):
            raise ValueError(f"Malformed CSV row {line}")
        ref = row["reference"].strip()
        if not ref or len(ref) > 128 or any(ord(c)<32 for c in ref):
            raise ValueError(f"Invalid reference on row {line}")
        day = row["date"].strip()
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError(f"Use YYYY-MM-DD on row {line}")
        amt = row["amount"].strip()
        if not re.fullmatch(r"[+-]?\d{1,12}(?:\.\d{1,2})?", amt):
            raise ValueError(f"Invalid CAD amount on row {line}")
        rows.append({"reference":ref,"date":day,"cents":int(Decimal(amt)*100),"row":line})
    if not rows:
        raise ValueError("Empty CSV")
    return rows

def reconcile(bank, ledger):
    by_ref = {}
    for side, rows in (("bank",bank),("ledger",ledger)):
        for row in rows:
            by_ref.setdefault(row["reference"],{"bank":[],"ledger":[]})[side].append(row)
    findings = []
    matched = 0
    for ref, evidence in sorted(by_ref.items()):
        b, l = evidence["bank"], evidence["ledger"]
        if len(b)>1 or len(l)>1:
            kind = "duplicate_or_ambiguous_reference"
        elif not b:
            kind = "missing_from_bank"
        elif not l:
            kind = "missing_from_ledger"
        elif (b[0]["date"],b[0]["cents"]) != (l[0]["date"],l[0]["cents"]):
            kind = "date_or_amount_mismatch"
        else:
            matched += 1
            continue
        findings.append((kind,ref,evidence))
    bt, lt = sum(r["cents"] for r in bank), sum(r["cents"] for r in ledger)
    return {"bank_rows":len(bank),"ledger_rows":len(ledger),"matched":matched,
            "exceptions":len(findings),"bank_total_cents":bt,"ledger_total_cents":lt,
            "difference_cents":bt-lt}, findings

def read_limited(path):
    with path.open("rb") as f:
        raw = f.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:
        raise ValueError("CSV exceeds 5 MB")
    return raw

def submit(root, folder):
    b, l = (read_limited(folder / x) for x in ("bank.csv","ledger.csv"))
    # Include boundaries, so different input pairs cannot hash to the same concatenation.
    key = hashlib.sha256(hashlib.sha256(b).digest()+hashlib.sha256(l).digest()).hexdigest()
    with closing(connect(root)) as db, db:
        cur = db.execute("INSERT OR IGNORE INTO batches(id,name,created,state,bank,ledger) VALUES(?,?,?,'queued',?,?)",
                         (key,folder.name,now(),b,l))
        if cur.rowcount:
            event(db,"queued",key,"Immutable input pair captured; CAD single-account snapshot")
    return key

def process_one(root):
    db = connect(root)
    try:
        # Single transaction: interrupted processing rolls back, leaving the queued job recoverable.
        db.execute("BEGIN IMMEDIATE")
        job = db.execute("SELECT * FROM batches WHERE state='queued' ORDER BY created,id LIMIT 1").fetchone()
        if not job:
            db.commit()
            return False
        key = job["id"]
        try:
            report, findings = reconcile(parse(job["bank"]),parse(job["ledger"]))
        except (ValueError, csv.Error) as exc:
            db.execute("UPDATE batches SET state='failed',error=? WHERE id=?",(str(exc),key))
            event(db,"failed",key,str(exc))
        else:
            for kind,ref,evidence in findings:
                db.execute("INSERT INTO findings(batch_id,kind,reference,evidence) VALUES(?,?,?,?)",
                           (key,kind,ref,json.dumps(evidence)))
            db.execute("UPDATE batches SET state='complete',report=? WHERE id=?",(json.dumps(report),key))
            event(db,"completed",key,f"{report['matched']} exact matches; {len(findings)} exceptions")
        db.commit()
        return True
    finally:
        db.close()

def cycle(root):
    inbox = root / "inbox"
    inbox.mkdir(parents=True,exist_ok=True)
    for folder in sorted(inbox.iterdir()):
        if folder.is_dir() and (folder/"READY").is_file():
            try:
                submit(root,folder)
            except (OSError,ValueError) as exc:
                # Avoid a new activity row on each poll for the same broken input.
                with closing(connect(root)) as db, db:
                    detail = f"{folder.name}: {exc}"
                    if not db.execute("SELECT 1 FROM activity WHERE event='input_error' AND detail=?",(detail,)).fetchone():
                        event(db,"input_error",None,detail)
    while process_one(root):
        pass
    from .office import tick as office_tick
    from .month_end import tick as close_tick
    for name,task in (("office",office_tick),("month_end",close_tick)):
        try:
            task(root)
        except (OSError,ValueError,TypeError,KeyError,AttributeError,OverflowError,RecursionError) as exc:
            with closing(connect(root)) as db, db:
                detail=name+": "+str(exc)
                if not db.execute("SELECT 1 FROM activity WHERE event='module_error' AND detail=?",(detail,)).fetchone():
                    event(db,"module_error",None,detail)
    with closing(connect(root)) as db, db:
        db.execute("INSERT OR REPLACE INTO runtime VALUES('last_cycle',?)",(now(),))

def acknowledge(root, finding_id, reason):
    reason = reason.strip()
    if not reason or len(reason)>1000:
        raise ValueError("Provide a review reason of 1–1000 characters")
    with closing(connect(root)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT batch_id,reviewed FROM findings WHERE id=?",(finding_id,)).fetchone()
        if not row or row["reviewed"]:
            raise ValueError("Finding does not exist or was already acknowledged")
        db.execute("UPDATE findings SET reviewed=?,reason=? WHERE id=?",(now(),reason,finding_id))
        event(db,"acknowledged",row["batch_id"],f"Finding {finding_id}: {reason}; no ledger change")

def snapshot(root):
    with closing(connect(root)) as db, db:
        batches = [dict(r) for r in db.execute("SELECT id,name,created,state,report,error FROM batches ORDER BY created DESC,id LIMIT 100")]
        findings = [dict(r) for r in db.execute("SELECT * FROM findings ORDER BY id DESC LIMIT 500")]
        activity = [dict(r) for r in db.execute("SELECT * FROM activity ORDER BY id DESC LIMIT 100")]
        counts = dict(db.execute("SELECT count(*) AS batches, (SELECT count(*) FROM batches WHERE state='queued') AS queued, (SELECT count(*) FROM findings WHERE reviewed IS NULL) AS open_exceptions FROM batches").fetchone())
        heartbeat = db.execute("SELECT value FROM runtime WHERE key='last_cycle'").fetchone()
    for b in batches:
        b["report"] = json.loads(b["report"]) if b["report"] else None
    for f in findings:
        f["evidence"] = json.loads(f["evidence"])
    from .office import latest
    from .month_end import latest as close_latest
    from .autonomy import status as autonomy_status
    return {"autonomy":autonomy_status(root),"month_end":close_latest(root),"office":latest(root),"roles":ROLES,"counts":counts,"last_cycle":heartbeat[0] if heartbeat else None,
            "batches":batches,"findings":findings,"activity":activity}

def demo(root):
    folder = root/"inbox"/"sample-cad"
    folder.mkdir(parents=True,exist_ok=True)
    inputs = {
        "bank.csv":"reference,date,amount\nSALE-01,2026-11-20,120.00\nBILL-01,2026-11-20,-25.00\nSALE-02,2026-11-21,90.00\nFEE-01,2026-11-22,-3.25\nDUP-01,2026-11-22,-10.00\nDUP-01,2026-11-22,-10.00\n",
        "ledger.csv":"reference,date,amount\nSALE-01,2026-11-20,120.00\nBILL-01,2026-11-20,-25.00\nSALE-02,2026-11-21,95.00\nDUP-01,2026-11-22,-10.00\nBILL-02,2026-11-23,-20.00\n"
    }
    if any((folder/f).exists() for f in (*inputs,"READY")):
        raise ValueError("Demo already exists; not overwriting input")
    for name, data in inputs.items():
        (folder/name).write_bytes(data.encode("utf-8"))
    (folder/"READY").touch()
    return folder

def serve(root, port, interval, browser_demo=False, autonomous_demo=False):
    if interval<5:
        raise ValueError("Minimum interval is five seconds")
    stop = threading.Event()
    def run():
        while not stop.is_set():
            try:
                cycle(root)
                if autonomous_demo and not stop.is_set():
                    from .autonomy import tick as autonomy_tick
                    autonomy_tick(root)
                elif browser_demo and not stop.is_set():
                    from .schedule import browser_tick
                    browser_tick(root)
            except Exception as exc:
                print("Worker error:",repr(exc),flush=True)
                try:
                    with closing(connect(root)) as db, db:
                        event(db,"worker_error",None,str(exc))
                except sqlite3.Error:
                    pass
            stop.wait(interval)
    dashboard = Path(__file__).with_name("dashboard.html").read_bytes()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.headers.get("Host") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
                self.send_error(403)
                return
            if self.path=="/":
                body,typ=dashboard,"text/html; charset=utf-8"
            elif self.path=="/api/status":
                body,typ=json.dumps(snapshot(root)).encode(),"application/json"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type",typ)
            self.send_header("Cache-Control","no-store")
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("X-Frame-Options","DENY")
            self.send_header("Content-Security-Policy","default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
            self.send_header("Content-Length",str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    with ThreadingHTTPServer(("127.0.0.1",port),Handler) as server:
        thread=threading.Thread(target=run,daemon=True)
        thread.start()
        print(f"Neuravale Finance: http://127.0.0.1:{port} | workspace {root}",flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            stop.set()
            thread.join()
            
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workspace",type=Path,default=Path.home()/"Neuravale-finance")
    sub=p.add_subparsers(dest="action",required=True)
    sub.add_parser("demo")
    sub.add_parser("once")
    sub.add_parser("status")
    s=sub.add_parser("serve")
    s.add_argument("--port",type=int,default=8765)
    s.add_argument("--interval",type=int,default=30)
    s.add_argument("--browser-demo",action="store_true",help="Opt in to scheduled fictional browser exports")
    s.add_argument("--autonomous-demo",action="store_true",help="Run authorized autonomous fictional office")
    ack=sub.add_parser("ack")
    ack.add_argument("id",type=int)
    ack.add_argument("--reason",required=True)
    a=p.parse_args()
    root=a.workspace.expanduser().resolve()
    if a.action=="demo":
        print("Created synthetic demo:",demo(root))
    elif a.action=="once":
        cycle(root)
        print(json.dumps(snapshot(root),indent=2))
    elif a.action=="status":
        print(json.dumps(snapshot(root),indent=2))
    elif a.action=="ack":
        acknowledge(root,a.id,a.reason)
        print("Acknowledged; no financial records changed.")
    else:
        serve(root,a.port,a.interval,a.browser_demo,a.autonomous_demo)

if __name__=="__main__":
    main()
