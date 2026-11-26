"""Visible local browser automation against the bundled fictional accounting app."""
import argparse
import shutil
import tempfile
from contextlib import closing
from pathlib import Path
from .worker import connect, event, parse, read_limited, submit, cycle

def browser_pilot(root, headless=False):
    from playwright.sync_api import sync_playwright
    root = root.resolve()
    inbox = root / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="browser-demo-", dir=inbox))
    sandbox = Path(__file__).with_name("sandbox.html").resolve().as_uri()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            try:
                context = browser.new_context(accept_downloads=True, service_workers="block")
                # This fixture has no remote dependencies. Deny all HTTP(S) requests.
                context.route("http://**/*", lambda route: route.abort())
                context.route("https://**/*", lambda route: route.abort())
                page = context.new_page()
                page.goto(sandbox, wait_until="load", timeout=15000)
                if page.url != sandbox or page.title() != "Neuravale Accounting Sandbox":
                    raise RuntimeError("Unexpected page; refusing to act")
                for side in ("bank","ledger"):
                    with page.expect_download(timeout=15000) as pending:
                        page.get_by_role("button", name=f"Export {side} CSV", exact=True).click(timeout=10000)
                    download = pending.value
                    if download.suggested_filename != side+".csv":
                        raise RuntimeError("Unexpected downloaded filename")
                    download.save_as(folder / (side+".csv"))
                    rows = parse(read_limited(folder / (side+".csv")))
                    if len(rows) != (3 if side=="bank" else 2):
                        raise RuntimeError("Unexpected fixture row count")
                context.close()
            finally:
                browser.close()
        (folder/"READY").touch()
        key = submit(root,folder)
        with closing(connect(root)) as db, db:
            event(db,"browser_export",key,"Local browser clicked both fictional accounting export buttons; verified CSV inputs")
        # Source bytes are already durably stored in SQLite; do not accumulate identical exports every five minutes.
        shutil.rmtree(folder)
        cycle(root)
        return key
    except BaseException:
        if not (folder/"READY").exists():
            shutil.rmtree(folder,ignore_errors=True)
        raise

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workspace",type=Path,default=Path.home()/"Neuravale-finance-desktop-demo")
    p.add_argument("--headless",action="store_true")
    args=p.parse_args()
    print("Reconciliation batch:",browser_pilot(args.workspace,args.headless),flush=True)

if __name__=="__main__":
    main()
