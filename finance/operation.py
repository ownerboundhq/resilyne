"""Allowlisted end-to-end computer-use practice workflow, never live accounting."""
import argparse
import json
import shutil
import tempfile
import time
from contextlib import closing
from pathlib import Path
from .worker import connect,event,parse,read_limited,reconcile,submit,cycle

def operation(root,headless=False):
    from playwright.sync_api import sync_playwright
    root=root.resolve()
    out=root/"operations"
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="practice-",dir=out))
    trace=[]
    def record(step,detail):
        item={"step":step,"detail":detail}
        trace.append(item)
        with closing(connect(root)) as db, db:
            event(db,"practice_operation",None,step+": "+detail)
        (run/"trace.json").write_text(json.dumps(trace,indent=2),encoding="utf-8")
    fixture=Path(__file__).with_name("operation.html").resolve().as_uri()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=headless,slow_mo=0 if headless else 450)
            try:
                context=browser.new_context(accept_downloads=True,service_workers="block",viewport={"width":1200,"height":850})
                context.route("http://**/*",lambda route:route.abort())
                context.route("https://**/*",lambda route:route.abort())
                page=context.new_page()
                page.goto(fixture,wait_until="load",timeout=15000)
                if page.url!=fixture or page.title()!="Neuravale Practice Ledger":
                    raise RuntimeError("Unexpected application; stopped")
                record("open","Opened isolated fictional ledger")
                def ensure_page():
                    if page.url!=fixture:
                        raise RuntimeError("Unexpected navigation; stopped")
                def click(name):
                    ensure_page()
                    page.get_by_role("button",name=name,exact=True).click(timeout=10000)
                def export(side,dest):
                    click("Bank statement" if side=="bank" else "General ledger")
                    with page.expect_download(timeout=15000) as pending:
                        click(f"Export {side} CSV")
                    download=pending.value
                    if download.suggested_filename!=side+".csv":
                        raise RuntimeError("Unexpected export")
                    download.save_as(dest)
                    return parse(read_limited(dest))
                bank=export("bank",run/"bank.csv")
                before=export("ledger",run/"ledger-before.csv")
                report_before, findings=reconcile(bank,before)
                record("reconcile",f"{report_before['exceptions']} exceptions before correction")
                page.screenshot(path=str(run/"01-before.png"))
                # This explicit fixture policy is not a general permission to post transactions.
                permitted=[e for kind,ref,e in findings if kind=="missing_from_ledger" and ref=="FEE-001"]
                if len(permitted)!=1:
                    raise RuntimeError("Practice fee missing or ambiguous")
                e=permitted[0]
                if len(e["bank"])!=1 or e["ledger"] or (e["bank"][0]["date"],e["bank"][0]["cents"])!=("2026-11-24",-300):
                    raise RuntimeError("Practice fee differs from allowlisted policy")
                click("Adjustment desk")
                ensure_page()
                for label,value in (("Reference","FEE-001"),("Date","2026-11-24"),("Amount (CAD)","-3.00"),("Expense account","Bank fees")):
                    page.get_by_label(label,exact=True).fill(value,timeout=10000)
                page.screenshot(path=str(run/"02-adjustment.png"))
                click("Post practice adjustment")
                page.get_by_text("Posted permitted practice adjustment FEE-001.",exact=True).wait_for(timeout=10000)
                page.get_by_text("Journal: debit Bank fees CAD 3.00; credit Cash CAD 3.00.",exact=True).wait_for(timeout=10000)
                record("post","Posted pre-authorized fictional bank fee only; balanced CAD 3.00 journal")
                after=export("ledger",run/"ledger-after.csv")
                report_after,remaining=reconcile(bank,after)
                expected=sorted((r["reference"],r["date"],r["cents"]) for r in before)+[("FEE-001","2026-11-24",-300)]
                observed=sorted((r["reference"],r["date"],r["cents"]) for r in after)
                if sorted(expected)!=observed or report_after["exceptions"]!=1 or remaining[0][0:2]!=("date_or_amount_mismatch","BILL-001"):
                    raise RuntimeError("Post-action verification failed; do not accept output")
                page.screenshot(path=str(run/"03-verified.png"))
                record("verify","Verified only the approved bank fee was added; BILL-001 held for review")
                if not headless:
                    page.wait_for_timeout(1800)
                context.close()
            finally:
                browser.close()
        summary={"mode":"fictional practice only","before":report_before,"after":report_after,"remaining":[{"kind":k,"reference":ref,"evidence":e} for k,ref,e in remaining],"journal":{"debit_account":"Bank fees","credit_account":"Cash","cents":300},"trace":trace}
        (run/"report.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
        inbox=root/"inbox"
        inbox.mkdir(parents=True,exist_ok=True)
        folder=Path(tempfile.mkdtemp(prefix="practice-verified-",dir=inbox))
        shutil.copyfile(run/"bank.csv",folder/"bank.csv")
        shutil.copyfile(run/"ledger-after.csv",folder/"ledger.csv")
        (folder/"READY").touch()
        key=submit(root,folder)
        cycle(root)
        record("complete",f"Verified practice results queued as {key}; evidence in {run.name}")
        summary["trace"]=trace
        summary["batch_id"]=key
        (run/"report.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
        return summary
    except Exception as exc:
        record("failed",str(exc))
        raise

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workspace",type=Path,required=True)
    p.add_argument("--headless",action="store_true")
    a=p.parse_args()
    r=operation(a.workspace,a.headless)
    print(json.dumps({"batch_id":r["batch_id"],"before":r["before"]["exceptions"],"after":r["after"]["exceptions"]}),flush=True)

if __name__=="__main__":
    main()
