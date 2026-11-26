"""Windows physical-input pilot. Only the bundled fictional journal window is allowed."""
import argparse
import csv
import ctypes
import json
import os
import sys
import tempfile
from pathlib import Path
from ctypes import wintypes

# Unique visual borders, deliberately unlike the neutral background.
COLORS=("#ea346a","#16aa72","#a84ee0","#e78224","#137ccb","#b43592",
        "#1e9b9f","#a47619","#745ad9","#d14b3e","#4c9e2c","#3c70e4","#bb5b16")

def locate(image,color):
    """Find a rectangular visual marker in an RGB screen crop, not a widget coordinate."""
    image=image.convert("RGB")
    rgb=bytes.fromhex(color.lstrip("#"))
    raw=image.tobytes()
    w,h=image.size
    left,top,right,bottom=w,h,-1,-1
    count=0
    pos=0
    while True:
        pos=raw.find(rgb,pos)
        if pos<0: break
        if pos%3==0:
            x=(pos//3)%w;y=(pos//3)//w
            left=min(left,x);right=max(right,x);top=min(top,y);bottom=max(bottom,y)
            count+=1
        pos+=1
    if right-left<12 or bottom-top<8 or count<60:
        raise RuntimeError("Visual target not found")
    width=right-left+1;height=bottom-top+1
    if width>500 or height>100:
        raise RuntimeError("Visual target ambiguous")
    # The pilot draws a continuous 4px border. Verify all four edges.
    pix=image.load()
    target=tuple(rgb)
    edges=([pix[x,top] for x in range(left,right+1)],
           [pix[x,bottom] for x in range(left,right+1)],
           [pix[left,y] for y in range(top,bottom+1)],
           [pix[right,y] for y in range(top,bottom+1)])
    if any(sum(p==target for p in edge)<len(edge)*0.95 for edge in edges):
        raise RuntimeError("Visual target obscured or ambiguous")
    return ((left+right)//2,(top+bottom)//2)

def expected_journals():
    """Recalculate the actual specialist fixture, rather than hard-code entry amounts."""
    from .month_end import demo,evaluate
    from datetime import date
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        period=demo(root,advanced=True)
        data=json.loads((root/"month_end"/(period+".json")).read_text(encoding="utf-8"))
        report=evaluate(data,date.today())
    if not report["ready"]: raise RuntimeError("Practice close did not pass")
    return journal_rows(report["specialists"]["adjustments"]["generated_journals"])

def journal_rows(journals):
    rows=[]
    for j in journals:
        dr,cr=j["lines"]
        amount=dr["debit_cents"]
        if amount!=cr["credit_cents"] or amount<=0:
            raise RuntimeError("Unbalanced adjustment")
        rows.append((dr["account"],cr["account"],f"{amount//100}.{amount%100:02d}"))
    if len(rows)!=4: raise RuntimeError("This visual pilot supports exactly four adjustment journals")
    allowed={("cogs","inventory"),("accrual_exp","accrual"),("prepaid_exp","prepaid"),("dep_exp","accum_dep")}
    if {r[:2] for r in rows}!=allowed: raise RuntimeError("Unexpected fictional journal accounts")
    return rows

def verify_saved(path,expected):
    with path.open("r",encoding="utf-8",newline="") as f:
        actual=list(csv.reader(f))
    if actual!=[["debit_account","credit_account","amount_cad"]]+[list(r) for r in expected]:
        raise RuntimeError("Saved journal differs from calculated plan")
    return True

class WinInput:
    def __init__(self,hwnd):
        if sys.platform!="win32": raise RuntimeError("Windows required")
        self.u=ctypes.WinDLL("user32",use_last_error=True)
        self.hwnd=hwnd
        self.last=None
        u=self.u
        u.GetForegroundWindow.restype=wintypes.HWND
        u.GetAncestor.argtypes=[wintypes.HWND,wintypes.UINT];u.GetAncestor.restype=wintypes.HWND
        u.WindowFromPoint.argtypes=[wintypes.POINT];u.WindowFromPoint.restype=wintypes.HWND
        u.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
        u.GetClientRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
        u.ClientToScreen.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.POINT)]
        u.GetCursorPos.argtypes=[ctypes.POINTER(wintypes.POINT)]
        u.SetCursorPos.argtypes=[ctypes.c_int,ctypes.c_int]
        u.GetAsyncKeyState.argtypes=[ctypes.c_int];u.GetAsyncKeyState.restype=ctypes.c_short
        u.GetSystemMetrics.argtypes=[ctypes.c_int]
        ulongptr=ctypes.c_size_t
        class Mouse(ctypes.Structure):
            _fields_=[("dx",wintypes.LONG),("dy",wintypes.LONG),("mouseData",wintypes.DWORD),("dwFlags",wintypes.DWORD),("time",wintypes.DWORD),("extra",ulongptr)]
        class Key(ctypes.Structure):
            _fields_=[("vk",wintypes.WORD),("scan",wintypes.WORD),("flags",wintypes.DWORD),("time",wintypes.DWORD),("extra",ulongptr)]
        class Hardware(ctypes.Structure):
            _fields_=[("msg",wintypes.DWORD),("lo",wintypes.WORD),("hi",wintypes.WORD)]
        class Union(ctypes.Union):
            _fields_=[("mouse",Mouse),("key",Key),("hardware",Hardware)]
        class Input(ctypes.Structure):
            _anonymous_=("data",)
            _fields_=[("type",wintypes.DWORD),("data",Union)]
        self.Input=Input;self.Mouse=Mouse;self.Key=Key
        u.SendInput.argtypes=[wintypes.UINT,ctypes.POINTER(Input),ctypes.c_int]
        u.SendInput.restype=wintypes.UINT
        self.guard()
        self.last=self.cursor()

    def cursor(self):
        p=wintypes.POINT()
        if not self.u.GetCursorPos(ctypes.byref(p)): raise RuntimeError("Cannot read cursor")
        return p.x,p.y

    def guard(self,check_motion=True):
        u=self.u
        if u.GetAsyncKeyState(0x1B)&0x8000: raise RuntimeError("Emergency stop: Escape")
        if any(u.GetAsyncKeyState(k)&0x8000 for k in (0x10,0x11,0x12,0x5B,0x5C)):
            raise RuntimeError("Modifier key pressed; stopped")
        if u.GetForegroundWindow()!=self.hwnd: raise RuntimeError("Practice window lost foreground; stopped")
        pid=wintypes.DWORD()
        u.GetWindowThreadProcessId(self.hwnd,ctypes.byref(pid))
        if pid.value!=os.getpid(): raise RuntimeError("Unexpected application owner")
        x,y=self.cursor()
        if x<=2 and y<=2: raise RuntimeError("Emergency stop: cursor in upper-left corner")
        if check_motion and self.last is not None and (abs(x-self.last[0])>3 or abs(y-self.last[1])>3):
            raise RuntimeError("Mouse moved by user; stopped")

    def owned(self,x,y):
        hit=self.u.WindowFromPoint(wintypes.POINT(x,y))
        return bool(hit) and self.u.GetAncestor(hit,2)==self.hwnd

    def capture(self):
        from PIL import ImageGrab
        self.guard()
        r=wintypes.RECT();p=wintypes.POINT(0,0)
        if not self.u.GetClientRect(self.hwnd,ctypes.byref(r)) or not self.u.ClientToScreen(self.hwnd,ctypes.byref(p)):
            raise RuntimeError("Cannot locate practice window")
        x,y,w,h=p.x,p.y,r.right-r.left,r.bottom-r.top
        # Restrict the preview to the primary monitor and a fully visible window.
        if x<0 or y<0 or w<300 or h<200 or x+w>self.u.GetSystemMetrics(0) or y+h>self.u.GetSystemMetrics(1):
            raise RuntimeError("Practice window must fit entirely on the primary display")
        if not all(self.owned(px,py) for px,py in ((x+6,y+6),(x+w-7,y+6),(x+6,y+h-7),(x+w-7,y+h-7),(x+w//2,y+h//2))):
            raise RuntimeError("Practice window is obscured")
        shot=ImageGrab.grab(bbox=(x,y,x+w,y+h))
        self.guard()
        if shot.size!=(w,h): raise RuntimeError("Screen capture scale mismatch")
        return shot,x,y

    def send(self,inputs):
        self.guard()
        arr=(self.Input*len(inputs))(*inputs)
        if self.u.SendInput(len(arr),arr,ctypes.sizeof(self.Input))!=len(arr):
            raise RuntimeError("Windows rejected input")

    def click(self,color):
        shot,x,y=self.capture()
        dx,dy=locate(shot,color)
        point=(x+dx,y+dy)
        if not self.owned(*point): raise RuntimeError("Target belongs to another window")
        self.guard()
        if not self.u.SetCursorPos(*point): raise RuntimeError("Cannot move mouse")
        self.last=point
        self.guard()
        if not self.owned(*point): raise RuntimeError("Target changed")
        down=self.Input(type=0,mouse=self.Mouse(0,0,0,0x0002,0,0))
        up=self.Input(type=0,mouse=self.Mouse(0,0,0,0x0004,0,0))
        self.send([down,up])

    def type_text(self,value):
        if not value or len(value)>80 or any(c not in "abcdefghijklmnopqrstuvwxyz_0123456789." for c in value):
            raise RuntimeError("Text outside fictional journal policy")
        inputs=[]
        for c in value:
            inputs.append(self.Input(type=1,key=self.Key(0,ord(c),0x0004,0,0)))
            inputs.append(self.Input(type=1,key=self.Key(0,ord(c),0x0006,0,0)))
        self.send(inputs)

def run_window(workspace):
    if sys.platform!="win32": raise RuntimeError("Physical computer-use preview requires Windows")
    # Set DPI awareness before creating a Tk window. No global desktop hooks.
    try: ctypes.windll.user32.SetProcessDPIAware()
    except Exception: pass
    import tkinter as tk
    from tkinter import messagebox
    root=tk.Tk()
    root.title("Neuravale | Native accounting practice")
    root.configure(bg="#f3f5f8")
    root.geometry("750x520+30+40")
    root.resizable(False,False)
    from .month_end import current_plan
    plan_id,period,journals=current_plan(workspace)
    expected=journal_rows(journals)
    out=workspace/"computer_use"
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="journal-",dir=out))
    (run/"plan.json").write_text(json.dumps({"period":period,"close_id":plan_id,"journals":journals},indent=2),encoding="utf-8")
    def check_plan():
        current_id,current_period,current_journals=current_plan(workspace,period)
        if current_id!=plan_id or current_period!=period or current_journals!=journals:
            raise RuntimeError("Month-end source changed; workflow stopped")
    fields=[]
    state={"active":False,"driver":None,"index":0,"stage":"click","posted":False,"done":False,"trace":[]}
    status=tk.StringVar(value="Ready. Select Start to permit this one fictional desktop workflow.")
    def note(message):
        state["trace"].append(message)
        status.set(message)
        (run/"trace.json").write_text(json.dumps(state["trace"],indent=2),encoding="utf-8")
    def stop(message):
        state["active"]=False
        note(message)
        start_btn.configure(state="disabled")
    def close():
        if state["active"]: stop("Stopped: window closed.")
        root.destroy()
    root.protocol("WM_DELETE_WINDOW",close)
    root.bind("<Escape>",lambda e:stop("Emergency stop: Escape") if state["active"] else None)
    tk.Label(root,text="neuravale.  |  Practice journal",font=("Segoe UI",20,"bold"),bg="#f3f5f8",fg="#14233a").pack(anchor="w",padx=20,pady=(16,2))
    tk.Label(root,text="Physical Windows mouse and keyboard input · fictional data only",bg="#f3f5f8",fg="#42536c").pack(anchor="w",padx=20)
    grid=tk.Frame(root,bg="#f3f5f8");grid.pack(fill="x",padx=20,pady=18)
    for i,label in enumerate(("Debit account","Credit account","Amount CAD")):
        tk.Label(grid,text=label,bg="#f3f5f8",fg="#14233a",font=("Segoe UI",10,"bold")).grid(row=0,column=i,padx=5,sticky="w")
        grid.columnconfigure(i,weight=1)
    for i,row in enumerate(expected):
        for j in range(3):
            n=i*3+j
            border=tk.Frame(grid,bg=COLORS[n],padx=4,pady=4)
            border.grid(row=i+1,column=j,padx=5,pady=5,sticky="ew")
            field=tk.Entry(border,font=("Segoe UI",12),width=16 if j<2 else 10,bd=0,highlightthickness=0,bg="white")
            field.pack(fill="both",expand=True,ipady=5)
            fields.append(field)
    buttons=tk.Frame(root,bg="#f3f5f8");buttons.pack(fill="x",padx=25)
    post_border=tk.Frame(buttons,bg=COLORS[12],padx=4,pady=4);post_border.pack(side="right")
    def post():
        if not state["active"] or state["posted"] or state["stage"]!="post_verify":
            return
        try: check_plan()
        except (ValueError,RuntimeError,OSError) as exc: stop(str(exc));return
        actual=[tuple(f.get() for f in fields[i:i+3]) for i in range(0,len(fields),3)]
        if actual!=expected:
            stop("Practice ledger refused unexpected entries.");return
        with (run/"posted_journals.csv").open("x",encoding="utf-8",newline="") as f:
            writer=csv.writer(f);writer.writerow(["debit_account","credit_account","amount_cad"]);writer.writerows(actual)
        state["posted"]=True
        note("Practice ledger saved four balanced journals. Verifying saved records.")
    post_btn=tk.Button(post_border,text="Post fictional journals",command=post,bd=0,highlightthickness=0,padx=12,pady=8)
    post_btn.pack(fill="both",expand=True)
    values=[v for row in expected for v in row]
    def step():
        if not state["active"]: return
        try:
            driver=state["driver"]
            driver.guard()
            idx=state["index"]
            stage=state["stage"]
            if idx<len(fields):
                field=fields[idx]
                if stage=="click":
                    driver.click(COLORS[idx])
                    state["stage"]="type"
                    note(f"Clicked field {idx+1} of {len(fields)}")
                elif stage=="type":
                    if root.focus_get()!=field or field.get():
                        raise RuntimeError("Input field focus or initial value differs")
                    driver.type_text(values[idx])
                    state["stage"]="verify"
                    note(f"Typed {values[idx]}")
                else:
                    if field.get()!=values[idx]: raise RuntimeError("Typed field verification failed")
                    state["index"]+=1;state["stage"]="click"
            elif stage=="click":
                shot,_,_=driver.capture();shot.save(run/"01-entered.png")
                state["stage"]="post_verify"
                driver.click(COLORS[12])
                note("Clicked Post fictional journals")
            else:
                if not state["posted"]: raise RuntimeError("Practice posting did not complete")
                check_plan()
                verify_saved(run/"posted_journals.csv",expected)
                note("Verified all four journals for "+period+". Desktop workflow complete.")
                shot,_,_=driver.capture();shot.save(run/"02-verified.png")
                from .worker import connect,event
                from contextlib import closing
                with closing(connect(workspace)) as db, db:
                    event(db,"native_computer_use_verified",None,"Four fictional month-end adjustments entered with physical Windows input; close "+plan_id+"; evidence "+run.name)
                state["done"]=True;state["active"]=False
                return
            root.after(600,step)
        except Exception as exc:
            stop("Stopped safely: "+str(exc))
    def poll_stop():
        if state["active"] and state["driver"] is not None:
            try: state["driver"].guard()
            except Exception as exc: stop("Stopped safely: "+str(exc))
        root.after(80,poll_stop)
    def start():
        if state["active"] or state["done"]: return
        if not messagebox.askyesno("Allow physical computer input","Neuravale will move your actual mouse and type ONLY in this fictional journal window. Do not use the mouse or keyboard during the demo. Press Escape or move the mouse to stop. Continue?",parent=root):
            return
        start_btn.configure(state="disabled")
        root.after(500,begin)
    def begin():
        try:
            check_plan()
            root.update_idletasks()
            user32=ctypes.windll.user32
            user32.GetAncestor.argtypes=[wintypes.HWND,wintypes.UINT]
            user32.GetAncestor.restype=wintypes.HWND
            hwnd=user32.GetAncestor(root.winfo_id(),2)
            state["driver"]=WinInput(hwnd)
            state["active"]=True
            shot,_,_=state["driver"].capture();shot.save(run/"00-start.png")
            note("Physical desktop operation started. Escape or move mouse to stop.")
            root.after(600,step)
        except Exception as exc: stop("Stopped safely: "+str(exc))
    start_btn=tk.Button(buttons,text="Start computer-use demo",command=start,padx=12,pady=8)
    start_btn.pack(side="left")
    tk.Label(root,textvariable=status,bg="#f3f5f8",fg="#14233a",wraplength=690,justify="left",font=("Segoe UI",11)).pack(anchor="w",padx=25,pady=(15,4))
    tk.Label(root,text="Stop: Escape / move mouse / switch windows. Evidence is local. No real accounts or applications are controlled.",bg="#f3f5f8",fg="#42536c",wraplength=690,justify="left").pack(anchor="w",padx=25)
    root.after(80,poll_stop)
    root.mainloop()
    return state["done"]

def self_test():
    from PIL import Image,ImageDraw
    image=Image.new("RGB",(320,160),"white")
    ImageDraw.Draw(image).rectangle((30,40,160,80),outline=COLORS[0],width=4)
    if locate(image,COLORS[0])!=(95,60): raise RuntimeError("Visual target self-test failed")
    if expected_journals()!=[("cogs","inventory","124.00"),("accrual_exp","accrual","150.00"),("prepaid_exp","prepaid","100.00"),("dep_exp","accum_dep","10.00")]:
        raise RuntimeError("Journal plan self-test failed")
    print("Visual locator and calculated journal plan verified; no physical input sent.")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workspace",type=Path,default=Path.home()/"Neuravale-finance-desktop-demo-v06")
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test: self_test()
    elif not run_window(a.workspace): raise SystemExit(1)

if __name__=="__main__": main()
