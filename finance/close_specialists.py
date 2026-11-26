"""Deterministic specialist calculations for the fictional monthly close.

The source registers are explicit inputs, not guessed by a language model.
All money is integer CAD cents; no external posting or statutory payroll/tax engine.
"""
from collections import defaultdict, deque
from copy import deepcopy
from .office import strict_keys,text,cents,day,records,unique

SPECIAL_CHECKS=("inventory","payroll","sales_tax","accruals_and_prepaids","fixed_assets_and_depreciation")
TAX="hst"
PAY=("payroll_tax","payroll_cpp","payroll_ei")
ADJUST=("inventory","cogs","prepaid","prepaid_exp","equipment","accum_dep","dep_exp","accrual","accrual_exp")

def nonnegative(x):
    x=cents(x)
    if x<0: raise ValueError("Expected nonnegative cents")
    return x

def positive(x):
    x=nonnegative(x)
    if not x: raise ValueError("Expected positive cents")
    return x

def count(x,zero=False):
    if type(x) is not int or x<(0 if zero else 1) or x>10**7:
        raise ValueError("Invalid unit count")
    return x

def require(ok,message):
    if not ok: raise ValueError(message)

def round_ratio(n,d):
    require(n>=0 and d>0,"Invalid rounding inputs")
    return (2*n+d)//(2*d)

def prepare(data,start,end):
    """Return base snapshot plus locally generated journal entries and reports.

    Any invalid/missing register or failed tie-out blocks the advanced close.
    """
    data=deepcopy(data)
    spec=data.pop("specialists")
    strict_keys(spec,("inventory","payroll","sales_tax","accruals","prepaids","depreciation"))
    accounts={}
    for a in records(data["accounts"]):
        key=text(a["id"])
        require(key not in accounts,"Duplicate account "+key)
        accounts[key]=a
    required={"inventory":"asset","cogs":"expense","wages":"expense","employer_payroll":"expense",
              "payroll_tax":"liability","payroll_cpp":"liability","payroll_ei":"liability","hst":"liability",
              "prepaid":"asset","prepaid_exp":"expense","equipment":"asset","accum_dep":"asset",
              "dep_exp":"expense","accrual":"liability","accrual_exp":"expense"}
    for k,kind in required.items():
        require(k in accounts and accounts[k]["type"]==kind,"Missing specialist account "+k)
    opening={k:cents(v["opening_cents"]) for k,v in accounts.items()}
    journal={}
    dates={}
    for entry in records(data["journal"]):
        ref=text(entry["id"])
        require(ref not in journal and not ref.startswith("NV-CLOSE-"),"Duplicate or reserved journal reference "+ref)
        dates[ref]=day(entry["date"])
        lines=defaultdict(int)
        for line in records(entry["lines"]):
            key=text(line["account"])
            require(key in accounts,"Unknown journal account "+key)
            d,c=nonnegative(line["debit_cents"]),nonnegative(line["credit_cents"])
            require((d>0)!=(c>0),"Invalid debit/credit")
            lines[key]+=d-c
        journal[ref]=dict(lines)
    used=set()
    additions=[]
    def entry(id,dr,cr,amount,evidence):
        if not amount: return
        amount=positive(amount)
        unique(used,id)
        additions.append({"id":"NV-CLOSE-"+id,"date":end.isoformat(),"evidence":text(evidence),
                          "lines":[{"account":dr,"debit_cents":amount,"credit_cents":0},
                                   {"account":cr,"debit_cents":0,"credit_cents":amount}]})
    def tie(expected,keys,label):
        keys=set(keys)
        for ref,lines in journal.items():
            actual={k:v for k,v in lines.items() if k in keys and v}
            wanted={k:v for k,v in expected.get(ref,{}).items() if k in keys and v}
            require(actual==wanted,label+" journal mismatch: "+ref)
        require(set(expected)<=set(journal),label+" missing source journal")
    def movement(k):
        return sum(lines.get(k,0) for lines in journal.values())
    def source(ref):
        ref=text(ref)
        require(ref in journal,"Missing source journal "+ref)
        return ref

    # FIFO perpetual inventory: chronological register, purchases already posted,
    # COGS not yet posted. Physical counts must agree; shortages are not auto-written off.
    inv=spec["inventory"]
    strict_keys(inv,("items","evidence"))
    evidence=text(inv["evidence"])
    inv_expected={}
    inv_open=inv_bought=inv_cogs=inv_end=0
    sku_seen=set()
    details=[]
    for item in records(inv["items"]):
        strict_keys(item,("sku","opening_layers","movements","physical_units","count_evidence"))
        sku=text(item["sku"]);unique(sku_seen,sku);text(item["count_evidence"])
        layers=deque()
        initial=0
        for l in records(item["opening_layers"]):
            strict_keys(l,("units","unit_cost_cents"))
            qty=count(l["units"]);cost=positive(l["unit_cost_cents"])
            layers.append([qty,cost]);initial+=qty*cost
        inv_open+=initial
        bought=sold=cogs=0
        prior=start
        refs=set()
        for m in records(item["movements"]):
            strict_keys(m,("reference","date","kind","units","unit_cost_cents"))
            ref=source(m["reference"]);unique(refs,ref)
            dt=day(m["date"])
            require(start<=dt<=end and dt>=prior and dates[ref]==dt,"Inventory movement date or order mismatch "+ref)
            prior=dt
            qty=count(m["units"])
            if m["kind"]=="purchase":
                cost=positive(m["unit_cost_cents"])
                layers.append([qty,cost]);bought+=qty*cost
                inv_expected.setdefault(ref,{"inventory":0})["inventory"]+=qty*cost
            elif m["kind"]=="sale":
                require(m["unit_cost_cents"]==0 and any(accounts[k]["type"]=="revenue" and v<0 for k,v in journal[ref].items()),"Inventory sale needs revenue journal and FIFO-derived cost")
                sold+=qty
                while qty:
                    require(bool(layers),"Negative inventory: "+sku)
                    take=min(qty,layers[0][0]);cogs+=take*layers[0][1]
                    qty-=take;layers[0][0]-=take
                    if layers[0][0]==0: layers.popleft()
            else: raise ValueError("Unsupported inventory movement")
        units=sum(q for q,c in layers)
        value=sum(q*c for q,c in layers)
        require(units==count(item["physical_units"],True),"Physical inventory count mismatch: "+sku)
        require(initial+bought-cogs==value,"Inventory cost rollforward mismatch")
        inv_bought+=bought;inv_cogs+=cogs;inv_end+=value
        details.append({"sku":sku,"closing_units":units,"opening_cents":initial,"purchases_cents":bought,"cogs_cents":cogs,"closing_cents":value})
    require(opening["inventory"]==inv_open and opening["cogs"]==0,"Inventory opening control mismatch")
    tie(inv_expected,("inventory","cogs"),"Inventory")
    entry("COGS","cogs","inventory",inv_cogs,evidence)

    # Payroll registers are imported actual gross, deductions and employer amounts.
    # Tie each component to its own GL account, then reconcile actual remittances.
    pay=spec["payroll"]
    strict_keys(pay,("runs","remittances","closing","evidence"))
    text(pay["evidence"]);strict_keys(pay["closing"],PAY)
    pe={}
    gross=net=employer=remitted=0
    totals={k:-opening[k] for k in PAY}
    require(all(v>=0 for v in totals.values()),"Unsupported opening payroll credit balance")
    for row in records(pay["runs"]):
        strict_keys(row,("reference","gross_cents","income_tax_cents","employee_cpp_cents","employee_ei_cents","employer_cpp_cents","employer_ei_cents","evidence"))
        ref=source(row["reference"]);require(ref not in pe,"Duplicate payroll register reference");text(row["evidence"])
        g=positive(row["gross_cents"]);tax=nonnegative(row["income_tax_cents"])
        cpp,ei=nonnegative(row["employee_cpp_cents"]),nonnegative(row["employee_ei_cents"])
        ec,ee=nonnegative(row["employer_cpp_cents"]),nonnegative(row["employer_ei_cents"])
        n=g-tax-cpp-ei;require(n>=0,"Payroll deductions exceed gross")
        gross+=g;net+=n;employer+=ec+ee
        pe[ref]={"wages":g,"employer_payroll":ec+ee,"cash":-n,"payroll_tax":-tax,"payroll_cpp":-cpp-ec,"payroll_ei":-ei-ee}
        for k in PAY: totals[k]-=pe[ref][k]
        require(journal[ref].get("cash",0)==-n,"Payroll net cash mismatch "+ref)
    for row in records(pay["remittances"]):
        strict_keys(row,("reference","income_tax_cents","cpp_cents","ei_cents","evidence"))
        ref=source(row["reference"]);require(ref not in pe,"Duplicate payroll remittance reference");text(row["evidence"])
        amounts=dict(zip(PAY,[nonnegative(row["income_tax_cents"]),nonnegative(row["cpp_cents"]),nonnegative(row["ei_cents"])]))
        amount=sum(amounts.values());require(amount>0,"Empty payroll remittance")
        pe[ref]=amounts;remitted+=amount
        for k,v in amounts.items(): totals[k]-=v
        require(journal[ref].get("cash",0)==-amount,"Payroll remittance cash mismatch "+ref)
    tie(pe,(*PAY,"wages","employer_payroll"),"Payroll")
    require(all(v>=0 and nonnegative(pay["closing"][k])==v for k,v in totals.items()),"Payroll closing liability mismatch")

    # GST/HST supplied rate and eligibility, not statutory jurisdiction/ITC advice.
    # Round each tax line half-up; match its base account and tax posting.
    tax=spec["sales_tax"]
    strict_keys(tax,("lines","remittances","closing_cents","evidence"))
    text(tax["evidence"])
    te={};collected=itc=paid=0
    for row in records(tax["lines"]):
        strict_keys(row,("reference","kind","base_account","base_cents","rate_bps","claimable_bps","evidence"))
        ref=source(row["reference"]);require(ref not in te,"One tax register row per journal in pilot");text(row["evidence"])
        key=text(row["base_account"]);require(key in accounts and key!=TAX,"Invalid tax base account")
        base=positive(row["base_cents"])
        rate=row["rate_bps"];claim=row["claimable_bps"]
        require(type(rate) is int and 0<=rate<=1500 and type(claim) is int and 0<=claim<=10000,"Invalid supplied tax rate/eligibility")
        calculated=round_ratio(base*rate,10000)
        if row["kind"]=="sale":
            require(accounts[key]["type"]=="revenue" and claim==10000 and journal[ref].get(key,0)==-base,"Sales tax base mismatch "+ref)
            collected+=calculated;te[ref]={TAX:-calculated}
        elif row["kind"]=="purchase":
            eligible=round_ratio(calculated*claim,10000)
            require(accounts[key]["type"] in ("expense","asset") and journal[ref].get(key,0)==base+calculated-eligible,"Purchase tax base/ITC mismatch "+ref)
            itc+=eligible;te[ref]={TAX:eligible}
        else: raise ValueError("Unknown tax register type")
    for row in records(tax["remittances"]):
        strict_keys(row,("reference","cents","evidence"))
        ref=source(row["reference"]);require(ref not in te,"Duplicate tax remittance");text(row["evidence"])
        amount=positive(row["cents"])
        require(journal[ref].get("cash",0)==-amount,"Tax remittance cash mismatch")
        te[ref]={TAX:amount};paid+=amount
    tie(te,(TAX,),"GST/HST")
    # Every revenue journal must be represented, even if zero-rated.
    for ref,lines in journal.items():
        if any(accounts[k]["type"]=="revenue" and v<0 for k,v in lines.items()):
            require(ref in te,"Revenue missing tax register: "+ref)
    tax_close=-opening[TAX]+collected-itc-paid
    require(cents(tax["closing_cents"])==tax_close,"GST/HST closing control mismatch")

    # Simplified single-month schedules: no pre-existing adjustment movements,
    # additions are generated exactly once on a copied snapshot.
    for k in ("prepaid","prepaid_exp","equipment","accum_dep","dep_exp","accrual","accrual_exp"):
        require(movement(k)==0,"Existing movement in adjustment account; manual review: "+k)
    accrued=0;seen=set()
    for row in records(spec["accruals"]):
        strict_keys(row,("id","amount_cents","evidence"))
        id=text(row["id"]);unique(seen,id);amt=positive(row["amount_cents"])
        accrued+=amt;entry("ACCRUAL-"+id,"accrual_exp","accrual",amt,row["evidence"])
    require(opening["accrual"]==0 and opening["accrual_exp"]==0,"Opening accrual requires a supported rollforward")
    prepaid_open=prepaid_exp=0;seen=set()
    for row in records(spec["prepaids"]):
        strict_keys(row,("id","cost_cents","months","elapsed_months","evidence"))
        id=text(row["id"]);unique(seen,id);cost=positive(row["cost_cents"]);months=count(row["months"]);elapsed=count(row["elapsed_months"],True)
        require(elapsed<months,"Prepaid schedule exhausted")
        prior=round_ratio(cost*elapsed,months);current=round_ratio(cost*(elapsed+1),months)-prior
        prepaid_open+=cost-prior;prepaid_exp+=current
        entry("PREPAID-"+id,"prepaid_exp","prepaid",current,row["evidence"])
    require(opening["prepaid"]==prepaid_open and opening["prepaid_exp"]==0,"Prepaid opening balance mismatch")
    cost_total=accum=dep=0;seen=set()
    for row in records(spec["depreciation"]):
        strict_keys(row,("id","cost_cents","residual_cents","life_months","elapsed_months","evidence"))
        id=text(row["id"]);unique(seen,id);cost=positive(row["cost_cents"]);residual=nonnegative(row["residual_cents"])
        life=count(row["life_months"]);elapsed=count(row["elapsed_months"],True)
        require(residual<=cost and elapsed<=life,"Invalid depreciation schedule")
        basis=cost-residual;prior=round_ratio(basis*elapsed,life)
        current=round_ratio(basis*min(elapsed+1,life),life)-prior
        cost_total+=cost;accum+=prior;dep+=current
        entry("DEP-"+id,"dep_exp","accum_dep",current,row["evidence"])
    require(opening["equipment"]==cost_total and opening["accum_dep"]==-accum and opening["dep_exp"]==0,"Fixed asset opening balance mismatch")
    data["journal"]+=additions
    report={"inventory":{"method":"FIFO","items":details,"opening_cents":inv_open,"purchases_cents":inv_bought,"cogs_cents":inv_cogs,"closing_cents":inv_end},
            "payroll":{"gross_cents":gross,"net_pay_cents":net,"employer_cost_cents":employer,"remitted_cents":remitted,"closing_by_component":totals},
            "sales_tax":{"collected_cents":collected,"claimable_itc_cents":itc,"remitted_cents":paid,"closing_cents":tax_close},
            "adjustments":{"accrued_cents":accrued,"prepaid_expense_cents":prepaid_exp,"prepaid_closing_cents":prepaid_open-prepaid_exp,"depreciation_cents":dep,"accumulated_depreciation_cents":accum+dep,"generated_journals":additions},
            "limitations":"Supplied fictional registers and policy assumptions; no statutory payroll calculation, tax eligibility determination, independent source authentication, or external posting."}
    return data,report

def advanced_sample(base):
    """Upgrade legacy fictional close fixture to a nontrivial specialist scenario."""
    d=deepcopy(base);start=d["period"]+"-01"
    def account(id,name,kind,opening=0):
        return {"id":id,"name":name,"type":kind,"opening_cents":opening}
    def j(id,lines):
        return {"id":id,"date":start,"evidence":"fictional:"+id,"lines":[{"account":k,"debit_cents":max(v,0),"credit_cents":max(-v,0)} for k,v in lines if v]}
    d["accounts"] += [account("inventory","Inventory","asset",10000),account("cogs","Cost of goods sold","expense"),account("wages","Wages","expense"),account("employer_payroll","Employer payroll","expense"),account("payroll_tax","Payroll tax payable","liability"),account("payroll_cpp","CPP payable","liability"),account("payroll_ei","EI payable","liability"),account("hst","GST/HST control","liability"),account("prepaid","Prepaid expense","asset",120000),account("prepaid_exp","Prepaid expense amortization","expense"),account("equipment","Equipment","asset",60000),account("accum_dep","Accumulated depreciation","asset",-10000),account("dep_exp","Depreciation expense","expense"),account("accrual","Accrued liabilities","liability"),account("accrual_exp","Accrued expenses","expense")]
    next(a for a in d["accounts"] if a["id"]=="equity")["opening_cents"]=-680000
    d["journal"]=[j("SALE1",[("cash",339000),("sales",-300000),("hst",-39000)]),j("INV1",[("ar",120000),("sales",-120000)]),j("RENT1",[("rent",100000),("cash",-100000)]),j("BILL1",[("supplies",45000),("hst",5850),("ap",-50850)]),j("PUR1",[("inventory",12000),("hst",1560),("ap",-13560)]),j("PAY1",[("wages",100000),("employer_payroll",11600),("cash",-80000),("payroll_tax",-10000),("payroll_cpp",-12000),("payroll_ei",-9600)]),j("REM1",[("payroll_tax",10000),("cash",-10000)]),j("TAXREM1",[("hst",10000),("cash",-10000)])]
    d["bank"]["closing_cents"]=639000
    d["bank"]["transactions"]=[{"reference":r,"date":start,"cents":v} for r,v in [("SALE1",339000),("RENT1",-100000),("PAY1",-80000),("REM1",-10000),("TAXREM1",-10000)]]
    d["payables"]=[{"id":"BILL1","open_cents":50850,"evidence":"fictional supplier bill"},{"id":"PUR1","open_cents":13560,"evidence":"fictional stock purchase"}]
    def tax(ref,kind,account,base,rate):
        return {"reference":ref,"kind":kind,"base_account":account,"base_cents":base,"rate_bps":rate,"claimable_bps":10000,"evidence":"fictional tax register"}
    d["specialists"]={
      "inventory":{"evidence":"fictional FIFO register","items":[{"sku":"SKU-1","opening_layers":[{"units":10,"unit_cost_cents":1000}],"movements":[{"reference":"PUR1","date":start,"kind":"purchase","units":10,"unit_cost_cents":1200},{"reference":"SALE1","date":start,"kind":"sale","units":12,"unit_cost_cents":0}],"physical_units":8,"count_evidence":"fictional physical count"}]},
      "payroll":{"evidence":"fictional payroll register","runs":[{"reference":"PAY1","gross_cents":100000,"income_tax_cents":10000,"employee_cpp_cents":6000,"employee_ei_cents":4000,"employer_cpp_cents":6000,"employer_ei_cents":5600,"evidence":"fictional payroll statement, not statutory rates"}],"remittances":[{"reference":"REM1","income_tax_cents":10000,"cpp_cents":0,"ei_cents":0,"evidence":"fictional remittance"}],"closing":{"payroll_tax":0,"payroll_cpp":12000,"payroll_ei":9600}},
      "sales_tax":{"evidence":"fictional supplied tax rates","lines":[tax("SALE1","sale","sales",300000,1300),tax("INV1","sale","sales",120000,0),tax("RENT1","purchase","rent",100000,0),tax("BILL1","purchase","supplies",45000,1300),tax("PUR1","purchase","inventory",12000,1300)],"remittances":[{"reference":"TAXREM1","cents":10000,"evidence":"fictional remittance"}],"closing_cents":21590},
      "accruals":[{"id":"UTIL","amount_cents":15000,"evidence":"fictional utility accrual"}],
      "prepaids":[{"id":"INS","cost_cents":120000,"months":12,"elapsed_months":0,"evidence":"fictional prepaid contract"}],
      "depreciation":[{"id":"EQ","cost_cents":60000,"residual_cents":0,"life_months":60,"elapsed_months":10,"evidence":"fictional fixed asset register"}]}
    return d
