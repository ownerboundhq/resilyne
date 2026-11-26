"""Windows-first local desktop control panel for the Finance pilot."""
import subprocess
import sys
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk

class Desktop:
    def __init__(self, window):
        self.window=window
        self.workspace=Path.home()/"Neuravale-finance-desktop-demo"
        self.workspace.mkdir(parents=True,exist_ok=True)
        self.port=8766
        self.worker=None
        self.pilot=None
        window.title("Neuravale Finance Desktop | local pilot")
        window.geometry("700x480")
        window.minsize(540,440)
        frame=ttk.Frame(window,padding=24)
        frame.pack(fill="both",expand=True)
        ttk.Label(frame,text="neuravale. finance",font=("Segoe UI",24,"bold")).pack(anchor="w")
        ttk.Label(frame,text="Desktop control · fictional data only",font=("Segoe UI",12)).pack(anchor="w",pady=(0,14))
        ttk.Label(frame,text="Run an actual local accounting worker and watch it operate a separate browser.",wraplength=610).pack(anchor="w")
        self.state=tk.StringVar(value="Worker stopped")
        self.detail=tk.StringVar(value="Browser pilot has not run.")
        ttk.Label(frame,textvariable=self.state).pack(anchor="w",pady=(16,4))
        self.start_btn=ttk.Button(frame,text="Start local accounting worker",command=self.start)
        self.start_btn.pack(fill="x",pady=3)
        self.stop_btn=ttk.Button(frame,text="Stop worker",command=self.stop)
        self.stop_btn.pack(fill="x",pady=3)
        self.run_btn=ttk.Button(frame,text="Run visible browser export pilot",command=self.run_pilot)
        self.run_btn.pack(fill="x",pady=3)
        ttk.Button(frame,text="Open activity dashboard",command=lambda:webbrowser.open(f"http://127.0.0.1:{self.port}/")).pack(fill="x",pady=3)
        ttk.Button(frame,text="Open local workspace",command=self.open_workspace).pack(fill="x",pady=3)
        ttk.Label(frame,textvariable=self.detail,wraplength=610).pack(anchor="w",pady=12)
        ttk.Label(frame,text="No live accounts, credentials, payments, or tax filing. Closing this window stops its worker. Keep the computer awake.",wraplength=610).pack(anchor="w")
        window.protocol("WM_DELETE_WINDOW",self.close)
        self.refresh()
    def spawn(self, module, args, log_name):
        flags=getattr(subprocess,"CREATE_NO_WINDOW",0)
        with (self.workspace/log_name).open("ab") as log:
            return subprocess.Popen([sys.executable,"-u","-m",module,*args],stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,creationflags=flags)
    @staticmethod
    def running(proc):
        return proc is not None and proc.poll() is None
    def start(self):
        if self.running(self.worker): return
        try:
            self.worker=self.spawn("finance.worker",["--workspace",str(self.workspace),"serve","--port",str(self.port)],"worker.log")
        except OSError as exc:
            messagebox.showerror("Cannot start worker",str(exc))
    def stop(self):
        if self.running(self.worker):
            self.worker.terminate()
    def run_pilot(self):
        if self.running(self.pilot): return
        try:
            self.pilot=self.spawn("finance.browser_pilot",["--workspace",str(self.workspace)],"browser.log")
            self.detail.set("Browser task started; look for the separate Chromium window.")
        except OSError as exc:
            messagebox.showerror("Cannot start browser task",str(exc))
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
        if self.pilot is not None and not busy:
            code=self.pilot.returncode
            self.detail.set("Browser pilot finished. Check the dashboard for captured evidence." if code==0 else f"Browser pilot failed ({code}); see browser.log.")
        self.window.after(1000,self.refresh)
    def close(self):
        if self.running(self.pilot):
            messagebox.showinfo("Browser task running","Wait until the browser pilot finishes before closing.")
            return
        self.stop()
        self.window.destroy()

def main():
    window=tk.Tk()
    Desktop(window)
    window.mainloop()

if __name__=="__main__":
    main()
