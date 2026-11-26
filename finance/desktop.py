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
        self.workspace=Path.home()/"Neuravale-finance-desktop-demo"
        self.workspace.mkdir(parents=True,exist_ok=True)
        self.port=8766
        self.worker=None
        self.pilot=None
        window.title("Neuravale Finance Desktop 0.4.0 | local pilot")
        window.geometry("780x720")
        window.minsize(600,620)
        frame=ttk.Frame(window,padding=24)
        frame.pack(fill="both",expand=True)
        ttk.Label(frame,text="neuravale. finance",font=("Segoe UI",24,"bold")).pack(anchor="w")
        ttk.Label(frame,text="Desktop control · fictional data only",font=("Segoe UI",12)).pack(anchor="w",pady=(0,14))
        ttk.Label(frame,text="Run an actual local accounting worker and watch it operate a separate browser.",wraplength=610).pack(anchor="w")
        self.state=tk.StringVar(value="Worker stopped")
        self.detail=tk.StringVar(value="Browser pilot has not run.")
        ttk.Label(frame,textvariable=self.state).pack(anchor="w",pady=(16,4))
        self.auto=tk.BooleanVar(value=False)
        ttk.Checkbutton(frame,text="Schedule fictional browser export every 5 minutes (headless)",variable=self.auto).pack(anchor="w")
        ttk.Button(frame,text="Create fictional financial office data",command=self.seed_office).pack(fill="x",pady=3)
        self.watch_btn=ttk.Button(frame,text="Start team and watch accounting workflow",command=self.watch_team)
        self.watch_btn.pack(fill="x",pady=5)
        self.start_btn=ttk.Button(frame,text="Start local accounting worker",command=self.start)
        self.start_btn.pack(fill="x",pady=3)
        self.stop_btn=ttk.Button(frame,text="Stop worker",command=self.stop)
        self.stop_btn.pack(fill="x",pady=3)
        self.run_btn=ttk.Button(frame,text="Run visible browser export pilot",command=self.run_pilot)
        self.run_btn.pack(fill="x",pady=3)
        ttk.Button(frame,text="Generate report in installed Excel",command=self.excel_export).pack(fill="x",pady=3)
        ttk.Button(frame,text="Open activity dashboard",command=lambda:webbrowser.open(f"http://127.0.0.1:{self.port}/")).pack(fill="x",pady=3)
        ttk.Button(frame,text="Open local workspace",command=self.open_workspace).pack(fill="x",pady=3)
        ttk.Label(frame,textvariable=self.detail,wraplength=610).pack(anchor="w",pady=12)
        ttk.Label(frame,text="No live accounts, credentials, payments, or tax filing. Closing this window stops its worker. Keep the computer awake.",wraplength=610).pack(anchor="w")
        window.protocol("WM_DELETE_WINDOW",self.close)
        self.refresh()
    def spawn(self, module, args, log_name):
        flags=getattr(subprocess,"CREATE_NO_WINDOW",0)
        with (self.workspace/log_name).open("ab") as log:
            return subprocess.Popen(command(module,args),stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,creationflags=flags)
    @staticmethod
    def running(proc):
        return proc is not None and proc.poll() is None
    def start(self):
        if self.running(self.worker): return
        try:
            args=["--workspace",str(self.workspace),"serve","--port",str(self.port)]
            if self.auto.get(): args.append("--browser-demo")
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
    def seed_office(self):
        from .office import demo
        try:
            demo(self.workspace)
            self.detail.set('Fictional office data created; worker will process it automatically.')
        except FileExistsError:
            self.detail.set('Office snapshot already exists; not overwritten.')
        except OSError as exc:
            messagebox.showerror('Cannot create sample',str(exc))
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
        self.stop_btn.configure(state="normal" if working else "disabled")
        self.run_btn.configure(state="disabled" if busy else "normal")
        self.watch_btn.configure(state="disabled" if busy else "normal")
        if self.pilot is not None and not busy:
            code=self.pilot.returncode
            self.detail.set("Local task finished. Check dashboard or workspace/reports." if code==0 else f"Local task failed ({code}); see operation.log, browser.log or excel.log.")
        self.window.after(1000,self.refresh)
    def close(self):
        if self.running(self.pilot):
            messagebox.showinfo("Local task running","Wait until the browser or Excel task finishes before closing.")
            return
        self.stop()
        self.window.destroy()

def main():
    window=tk.Tk()
    Desktop(window)
    window.mainloop()

if __name__=="__main__":
    main()
