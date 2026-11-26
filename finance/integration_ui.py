"""Local connection manager: explicitly initiated, session-only test API reads."""
import json
import queue
import threading
import tkinter as tk
from tkinter import ttk,messagebox
from .integrations import ADAPTERS,CATALOG,read_sample

def open_integrations(parent):
    win=tk.Toplevel(parent)
    win.title("Neuravale Finance | Integrations")
    win.geometry("880x700")
    win.minsize(650,540)
    f=ttk.Frame(win,padding=16);f.pack(fill="both",expand=True)
    ttk.Label(f,text="Connect your software",font=("Segoe UI",22,"bold")).pack(anchor="w")
    ttk.Label(f,text="Developer preview. Test accounts and fictional data only. Credentials and returned samples stay in this window's session; no scheduled API sync or posting.",wraplength=810).pack(anchor="w",pady=(4,12))
    tabs=ttk.Notebook(f);tabs.pack(fill="both",expand=True)
    read=ttk.Frame(tabs,padding=12);catalog=ttk.Frame(tabs,padding=12)
    tabs.add(read,text="Test a connector");tabs.add(catalog,text="All integrations")
    tree=ttk.Treeview(catalog,columns=("status",),show="tree headings")
    tree.heading("#0",text="Application");tree.heading("status",text="Implementation")
    tree.column("#0",width=320);tree.column("status",width=320)
    scroll=ttk.Scrollbar(catalog,orient="vertical",command=tree.yview);tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left",fill="both",expand=True);scroll.pack(side="right",fill="y")
    for group,apps in CATALOG.items():
        key=tree.insert("","end",text=group,open=True)
        for app in apps:
            state="Test read adapter" if app in ADAPTERS else "Local Excel export pilot" if app=="Microsoft Excel" else "Planned"
            tree.insert(key,"end",text=app,values=(state,))
    provider=tk.StringVar(value="Google Sheets")
    picker=ttk.Combobox(read,textvariable=provider,values=list(ADAPTERS),state="readonly")
    picker.pack(fill="x")
    fields=ttk.Frame(read);fields.pack(fill="x",pady=8)
    variables={}
    secret=tk.StringVar()
    consent=tk.BooleanVar(value=False)
    status=tk.StringVar(value="Not connected")
    result=tk.Text(read,height=14,wrap="word",state="disabled")
    q=queue.Queue()
    def render_fields(*_):
        for w in fields.winfo_children(): w.destroy()
        variables.clear();secret.set("");consent.set(False);status.set("Not connected")
        set_result("")
        for key,label in ADAPTERS[provider.get()]["fields"]:
            ttk.Label(fields,text=label).pack(anchor="w")
            v=tk.StringVar();variables[key]=v
            ttk.Entry(fields,textvariable=v).pack(fill="x",pady=(0,6))
        ttk.Label(fields,text=ADAPTERS[provider.get()]["secret"]).pack(anchor="w")
        ttk.Entry(fields,textvariable=secret,show="*").pack(fill="x")
    def set_result(value):
        result.configure(state="normal");result.delete("1.0","end");result.insert("end",value);result.configure(state="disabled")
    def run():
        if not consent.get():
            messagebox.showinfo("Test access","Confirm that you own or are authorized to access the test account and that it contains only fictional data.",parent=win);return
        p=provider.get();c={k:v.get().strip() for k,v in variables.items()};t=secret.get().strip()
        secret.set("");set_result("");status.set("Reading sample from "+p+"…")
        btn.configure(state="disabled");picker.configure(state="disabled")
        def work():
            try:
                q.put((True,read_sample(p,c,t)))
            except ValueError as exc:
                q.put((False,str(exc)))
            except Exception:
                q.put((False,"Unexpected response format; no data imported."))
        threading.Thread(target=work,daemon=True).start()
        win.after(100,poll)
    def poll():
        try: ok,value=q.get_nowait()
        except queue.Empty:
            win.after(100,poll);return
        btn.configure(state="normal");picker.configure(state="readonly")
        if ok:
            status.set("Sample read succeeded · "+str(value["count"])+" records · "+("more records exist" if value["truncated"] else "bounded sample"))
            set_result(json.dumps(value,indent=2,ensure_ascii=False))
        else: status.set("Read failed: "+value)
    ttk.Checkbutton(read,text="I authorize this test read and confirm the account contains fictional data.",variable=consent).pack(anchor="w")
    btn=ttk.Button(read,text="Read test sample",command=run);btn.pack(fill="x",pady=6)
    ttk.Label(read,textvariable=status,wraplength=810).pack(anchor="w")
    result.pack(fill="both",expand=True,pady=6)
    picker.bind("<<ComboboxSelected>>",render_fields)
    render_fields()
