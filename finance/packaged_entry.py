"""Windows frozen executable entry point."""
import os
import sys
from pathlib import Path

def main():
    if getattr(sys,"frozen",False):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"]=str(Path(sys.executable).resolve().parent/"browsers")
    if len(sys.argv)>1:
        mode=sys.argv.pop(1)
        if mode=="--worker":
            from finance.worker import main as worker_main
            worker_main()
        elif mode=="--browser":
            from finance.browser_pilot import main as browser_main
            browser_main()
        elif mode=="--operation":
            from finance.operation import main as operation_main
            operation_main()
        elif mode=="--computer-use":
            from finance.computer_use import main as computer_main
            computer_main()
        elif mode=="--intelligence":
            from finance.intelligence import main as intelligence_main
            intelligence_main()
        elif mode=="--autonomy":
            from finance.autonomy import main as autonomy_main
            autonomy_main()
        elif mode=="--month-end":
            from finance.month_end import main as month_main
            month_main()
        elif mode=="--office":
            import argparse
            import json
            from finance.office import demo,tick,latest
            p=argparse.ArgumentParser()
            p.add_argument("--workspace",type=Path,required=True)
            p.add_argument("action",choices=["demo","once","status"])
            a=p.parse_args()
            if a.action=="demo": print(demo(a.workspace))
            elif a.action=="once": print(tick(a.workspace))
            else: print(json.dumps(latest(a.workspace),indent=2))
        else:
            raise SystemExit("Unsupported mode: "+mode)
    else:
        from finance.desktop import main as desktop_main
        desktop_main()

if __name__=="__main__":
    main()
