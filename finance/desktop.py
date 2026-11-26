"""Windows-first local desktop control panel for the Finance pilot."""
import subprocess
import sys
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk
from .runtime import command

class Desktop:
    def __init__(self, window):
        self.window=window
        self.workspace=Path.home()/"Neuravale-finance-desktop-demo-v010"
        self.workspace.mkdir(parents=True,exist_ok=True)
        self.port=8766
        self.worker=None
        self.pilot=None
        window.title("Neuravale Finance Desktop 0.12.0 | local pilot")
        window.geometry("780x690")
        window.minsize(600,560)
        frame=ttk.Frame(window,padding=24)
        frame.pack(fill="both",expand=True)
        ttk.Label(frame,text="neuravale. finance",font=("Segoe UI",24,"bold")).pack(anchor="w")
        ttk.Label(frame,text="Desktop control · fictional data only",font=("Segoe UI",12)).pack(anchor="w",pady=(0,14))
        ttk.Label(frame,text="Run an actual local accounting worker and watch it operate a separate browser.",wraplength=610).pack(anchor="w")
        self.state=tk.StringVar(value="Worker stopped")
        self.detail=tk.StringVar(value="Browser pilot has not run.")
        ttk.Label(frame,textvariable=self.state).pack(anchor="w",pady=(16,4))
        tabs=ttk.Notebook(frame)
        tabs.pack(fill="both",expand=True,pady=(0,10))
        home=ttk.Frame(tabs,padding=12);work=ttk.Frame(tabs,padding=12);settings=ttk.Frame(tabs,padding=12)
        tabs.add(home,text="Office");tabs.add(work,text="Computer use");tabs.add(settings,text="Connections")
        self.auto=tk.BooleanVar(value=False)
        ttk.Label(home,text="Start your fictional accounting department.",font=("Segoe UI",13,"bold")).pack(anchor="w")
        self.start_btn=ttk.Button(home,text="Start accounting team",command=self.start_office)
        self.start_btn.pack(fill="x",pady=4)
        self.autonomy_btn=ttk.Button(home,text="Start Intelligence Engine",command=self.start_autonomous)
        self.autonomy_btn.pack(fill="x",pady=4)
        self.stop_btn=ttk.Button(home,text="Stop background worker",command=self.stop)
        self.stop_btn.pack(fill="x",pady=4)
        ttk.Button(home,text="Open activity and financial reports",command=self.open_dashboard).pack(fill="x",pady=4)
        ttk.Button(home,text="Prepare full specialist month-end close",command=self.prepare_close).pack(fill="x",pady=4)
        ttk.Button(home,text="Review and seal month-end snapshot",command=self.seal_close).pack(fill="x",pady=4)
        ttk.Checkbutton(home,text="Schedule read-only fictional browser exports every 5 minutes",variable=self.auto).pack(anchor="w",pady=8)
        self.native_btn=ttk.Button(work,text="Watch physical mouse and keyboard accounting",command=self.native_use)
        self.native_btn.pack(fill="x",pady=4)
        self.watch_btn=ttk.Button(work,text="Watch browser accounting workflow",command=self.watch_team)
        self.watch_btn.pack(fill="x",pady=4)
        self.run_btn=ttk.Button(work,text="Run visible browser export pilot",command=self.run_pilot)
        self.run_btn.pack(fill="x",pady=4)
        ttk.Button(work,text="Generate report in installed Excel",command=self.excel_export).pack(fill="x",pady=4)
        ttk.Button(settings,text="Connect your software (test integrations)",command=self.integrations).pack(fill="x",pady=4)
        ttk.Button(settings,text="Open accounting reports folder",command=self.open_reports).pack(fill="x",pady=4)
        ttk.Button(settings,text="Open local workspace",command=self.open_workspace).pack(fill="x",pady=4)
        ttk.Label(settings,text="Data and evidence remain on this computer. Test credentials only. No live ledger posting.",wraplength=590).pack(anchor="w",pady=12)
        ttk.Label(frame,textvariable=self.detail,wraplength=610).pack(anchor="w",pady=12)
        ttk.Label(frame,text="Test-only connections. No payments or tax filing. Closing this window stops its worker. Keep the computer awake.",wraplength=610).pack(anchor="w")
        window.protocol("WM_DELETE_WINDOW",self.close)
        self.refresh()
    def open_dashboard(self):
        if not self.running(self.worker):
            messagebox.showinfo("Worker not running","Start the accounting team first.")
            return
        webbrowser.open(f"http://127.0.0.1:{self.port}/")
    def start_office(self):
        from .office import demo as office_demo
        from .month_end import demo as close_demo
        try:
            for seed in (office_demo,lambda root: close_demo(root,advanced=True)):
                try: seed(self.workspace)
                except FileExistsError: pass
        except (OSError,ValueError) as exc:
            messagebox.showerror("Cannot prepare practice office",str(exc));return
        self.start()
        self.detail.set("Accounting team started; daily reports and specialist month-end checks run automatically.")
    def integrations(self):
        from .integration_ui import open_integrations
        open_integrations(self.window)
    def spawn(self, module, args, log_name):
        flags=getattr(subprocess,"CREATE_NO_WINDOW",0)
        with (self.workspace/log_name).open("ab") as log:
            return subprocess.Popen(command(module,args),stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,creationflags=flags)
    @staticmethod
    def running(proc):
        return proc is not None and proc.poll() is None
    def start_autonomous(self):
        if self.running(self.worker):
            messagebox.showinfo("Worker running","Stop the current worker before changing mode.");return
        if not messagebox.askyesno("Authorize fictional autonomy","Authorize the Intelligence Engine to assign and execute fictional accounting tasks, verify results and seal the exact approved fictional monthly fixture? No real accounts, payments, tax filing or physical mouse control. The worker runs while this window and computer remain active."):
            return
        self.start(autonomous=True)
        self.detail.set("Intelligence Engine authorized. Open reports to see the live task centre, assigned roles and verification results.")
    def start(self,autonomous=False):
        if self.running(self.worker): return
        try:
            args=["--workspace",str(self.workspace),"serve","--port",str(self.port)]
            if autonomous: args.append("--autonomous-demo")
            elif self.auto.get(): args.append("--browser-demo")
            self.worker=self.spawn("finance.worker",args,"worker.log")
        except OSError as exc:
            messagebox.showerror("Cannot start worker",str(exc))
    def stop(self):
        if self.running(self.worker):
            self.worker.terminate()
    def watch_team(self):
        if self.running(self.pilot): return
        self.seed_office()
        self.start()
        if not self.running(self.worker): return
        try:
            self.pilot=self.spawn("finance.operation",["--workspace",str(self.workspace)],"operation.log")
            self.detail.set("Watch the team open a practice ledger, reconcile, enter an allowed adjustment and verify it.")
        except OSError as exc:
            messagebox.showerror("Cannot start practice operation",str(exc))
    def native_use(self):
        if self.running(self.pilot): return
        if sys.platform!="win32":
            messagebox.showinfo("Windows required","The physical-input engine currently requires Windows.")
            return
        from .month_end import current_plan
        try:
            current_plan(self.workspace)
        except (OSError,ValueError,RuntimeError) as exc:
            messagebox.showinfo("Prepare month-end first",str(exc));return
        try:
            self.pilot=self.spawn("finance.computer_use",["--workspace",str(self.workspace)],"computer_use.log")
            self.detail.set("Open the practice window and select Start. Escape or move the mouse to stop.")
        except OSError as exc:
            messagebox.showerror("Cannot start computer-use pilot",str(exc))
    def run_pilot(self):
        if self.running(self.pilot): return
        try:
            self.pilot=self.spawn("finance.browser_pilot",["--workspace",str(self.workspace)],"browser.log")
            self.detail.set("Browser task started; look for the separate Chromium window.")
        except OSError as exc:
            messagebox.showerror("Cannot start browser task",str(exc))
    def excel_export(self):
        if sys.platform!="win32":
            messagebox.showinfo("Windows required","This pilot uses Microsoft Excel desktop automation on Windows.")
            return
        if self.running(self.pilot):
            messagebox.showinfo("Task running","Wait for the current browser or Excel task to finish.")
            return
        try:
            args=["powershell.exe","-NoProfile","-File",str(Path(__file__).with_name("excel_export.ps1")),"-Workspace",str(self.workspace)]
            if getattr(sys,"frozen",False): args.extend(["-FinanceExecutable",sys.executable])
            with (self.workspace/"excel.log").open("ab") as log:
                self.pilot=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            self.detail.set("Excel report started. Requires installed Excel.")
        except OSError as exc:
            messagebox.showerror("Cannot start Excel",str(exc))
    def prepare_close(self):
        from .month_end import demo
        try:
            demo(self.workspace,advanced=True)
        except FileExistsError:
            pass
        except OSError as exc:
            messagebox.showerror("Cannot create close sample",str(exc)); return
        self.start()
        self.detail.set("Month-end sample ready. Background worker will prepare reports; open dashboard to review.")
    def seal_close(self):
        from .month_end import latest,seal
        try:
            rows=latest(self.workspace)
            if not rows or rows[0]["state"]!="ready":
                messagebox.showinfo("Close not ready","Review month-end checklist in the dashboard first.")
                return
            r=rows[0]
            if messagebox.askyesno("Seal fictional month",f"Seal local snapshot {r['period']}? Review the dashboard first. No external accounting software is changed."):
                seal(self.workspace,r["period"],r["id"])
                self.detail.set("Fictional month sealed locally. Original snapshot preserved.")
        except (OSError,ValueError) as exc:
            messagebox.showerror("Cannot seal month",str(exc))
    def seed_office(self):
        from .office import demo
        try:
            demo(self.workspace)
            self.detail.set('Fictional office data created; worker will process it automatically.')
        except FileExistsError:
            self.detail.set('Office snapshot already exists; not overwritten.')
        except OSError as exc:
            messagebox.showerror('Cannot create sample',str(exc))
    def open_reports(self):
        folder=self.workspace/"reports"
        folder.mkdir(parents=True,exist_ok=True)
        if sys.platform=="win32":
            import os
            os.startfile(str(folder))
        else:
            webbrowser.open(folder.as_uri())
    def open_workspace(self):
        if sys.platform=="win32":
            import os
            os.startfile(str(self.workspace))
        else:
            webbrowser.open(self.workspace.as_uri())
    def refresh(self):
        working=self.running(self.worker)
        busy=self.running(self.pilot)
        self.state.set("Worker process running · verify heartbeat in dashboard" if working else ("Worker stopped" if self.worker is None else f"Worker exited ({self.worker.returncode}); see worker.log"))
        self.start_btn.configure(state="disabled" if working else "normal")
        self.autonomy_btn.configure(state="disabled" if working else "normal")
        self.stop_btn.configure(state="normal" if working else "disabled")
        self.run_btn.configure(state="disabled" if busy else "normal")
        self.watch_btn.configure(state="disabled" if busy else "normal")
        self.native_btn.configure(state="disabled" if busy else "normal")
        if self.pilot is not None and not busy:
            code=self.pilot.returncode
            self.detail.set("Local task finished. Check dashboard or workspace/reports." if code==0 else f"Local task failed ({code}); see computer_use.log, operation.log, browser.log or excel.log.")
        self.window.after(1000,self.refresh)
    def close(self):
        if self.running(self.pilot):
            messagebox.showinfo("Local task running","Wait until the browser, Excel or native input task finishes before closing.")
            return
        self.stop()
        self.window.destroy()

def main():
    window=tk.Tk()
    Desktop(window)
    window.mainloop()

if __name__=="__main__":
    main()
