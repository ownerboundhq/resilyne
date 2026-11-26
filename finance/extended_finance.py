"""Bounded Canadian practice accounting calculations, with explicit source evidence.

No OCR, tax advice, statutory returns, payment initiation or external ledger writes.
Money is integer cents; rates are supplied policy inputs, not live exchange rates.
"""
import re
from collections import defaultdict
from .office import strict_keys,text,cents,day,records,unique

def require(ok,message):
    if not ok: raise ValueError(message)

def nonnegative(v):
    v=cents(v);require(v>=0,"Negative amount not supported");return v

def ratio(n,d):
    require(type(n) is int and type(d) is int and d>0,"Invalid rate")
    return (1 if n>=0 else -1)*((2*abs(n)+d)//(2*d))

def receipt(raw):
    """Extract a deliberately narrow, labelled UTF-8 invoice format; never guess."""
    require(isinstance(raw,str) and len(raw)<=20000,"Unsupported invoice text")
    fields={}
    for line in raw.splitlines():
        if not line.strip(): continue
        require(":" in line,"Unrecognized invoice line")
        k,v=line.split(":",1);k=k.strip().lower()
        require(k not in fields,"Duplicate invoice field")
        fields[k]=v.strip()
    strict_keys(fields,("invoice","vendor","date","currency","subtotal","tax","total"))
    def amount(v):
        require(bool(re.fullmatch(r"\d{1,9}\.\d{2}",v)),"Use explicit decimal invoice amounts")
        a,b=v.split(".");return int(a)*100+int(b)
    require(fields["currency"]=="CAD","Receipt format currently CAD only")
    sub,tax,total=map(amount,(fields["subtotal"],fields["tax"],fields["total"]))
    require(sub+tax==total and total>0,"Invoice totals do not reconcile")
    return {"id":text(fields["invoice"]),"vendor":text(fields["vendor"]),"date":day(fields["date"]).isoformat(),"subtotal_cents":sub,"tax_cents":tax,"total_cents":total}

def calculate(data):
    strict_keys(data,("company","period","policy","documents","card","loans","related_parties","fx","budget","tax_inputs"))
    require(data["company"]=="Fictional Neuravale Extended Ltd.","Only fictional practice data permitted")
    from .month_end import period_dates
    start,end=period_dates(data["period"])
    policy=data["policy"]
    strict_keys(policy,("version","vendor_accounts","large_transaction_cents"))
    text(policy["version"])
    require(isinstance(policy["vendor_accounts"],dict),"Invalid vendor account policy")
    mapping={text(k).casefold():text(v) for k,v in policy["vendor_accounts"].items()}
    require(len(mapping)==len(policy["vendor_accounts"]),"Ambiguous vendor policy")
    threshold=nonnegative(policy["large_transaction_cents"])
    docs=[];flags=[];seen=set();totals=defaultdict(int)
    for item in records(data["documents"]):
        strict_keys(item,("source","text"))
        source=text(item["source"])
        r=receipt(item["text"])
        require(start<=day(r["date"])<=end,"Invoice outside reporting period")
        key=r["vendor"].casefold()+"|"+r["id"]
        if key in seen:
            flags.append({"type":"duplicate_invoice","source":source,"id":r["id"]});continue
        seen.add(key)
        account=mapping.get(r["vendor"].casefold())
        if not account: flags.append({"type":"uncategorized","source":source,"id":r["id"]})
        if r["total_cents"]>threshold: flags.append({"type":"large_transaction","source":source,"id":r["id"]})
        if account: totals[account]+=r["subtotal_cents"]
        docs.append(dict(r,source=source,account=account))
    card=data["card"]
    strict_keys(card,("opening_cents","closing_cents","gl_closing_cents","statement","ledger","evidence"))
    text(card["evidence"])
    from .worker import reconcile
    def movements(rows):
        out=[]
        for r in records(rows):
            strict_keys(r,("reference","date","cents"))
            dt=day(r["date"]);require(start<=dt<=end,"Card movement outside period")
            out.append({"reference":text(r["reference"]),"date":dt.isoformat(),"cents":cents(r["cents"])})
        return out
    statement=movements(card["statement"]);ledger=movements(card["ledger"])
    rec,findings=reconcile(statement,ledger)
    card_ok=(not findings and cents(card["opening_cents"])+rec["bank_total_cents"]==cents(card["closing_cents"])==cents(card["gl_closing_cents"]))
    if not card_ok: flags.append({"type":"card_mismatch","source":card["evidence"]})
    loans=[];seen=set()
    for r in records(data["loans"]):
        strict_keys(r,("id","opening_cents","draws_cents","payment_cents","interest_cents","fees_cents","statement_closing_cents","gl_closing_cents","evidence"))
        key=text(r["id"]);unique(seen,key);text(r["evidence"])
        opening,draw,pay,interest,fees=map(nonnegative,(r["opening_cents"],r["draws_cents"],r["payment_cents"],r["interest_cents"],r["fees_cents"]))
        principal=pay-interest-fees
        require(principal>=0 and principal<=opening+draw,"Unsupported loan repayment")
        close=opening+draw-principal
        ok=close==nonnegative(r["statement_closing_cents"])==nonnegative(r["gl_closing_cents"])
        if not ok: flags.append({"type":"loan_mismatch","source":r["evidence"],"id":key})
        loans.append({"id":key,"principal_paid_cents":principal,"interest_cents":interest,"fees_cents":fees,"closing_cents":close,"reconciled":ok})
    related=[];seen=set()
    for r in records(data["related_parties"]):
        strict_keys(r,("id","kind","opening_cents","movements_cents","counterparty_signed_cents","gl_closing_cents","evidence"))
        key=text(r["id"]);unique(seen,key);text(r["evidence"])
        require(r["kind"] in ("shareholder","intercompany"),"Unknown related-party type")
        close=cents(r["opening_cents"])+sum(cents(v) for v in records(r["movements_cents"]))
        ok=close==cents(r["gl_closing_cents"])==-cents(r["counterparty_signed_cents"])
        if not ok: flags.append({"type":"related_party_mismatch","source":r["evidence"],"id":key})
        related.append({"id":key,"kind":r["kind"],"closing_cents":close,"reconciled":ok})
    fx=[];seen=set()
    for r in records(data["fx"]):
        strict_keys(r,("id","currency","foreign_minor_units","book_cad_cents","cad_rate_millionths","rate_evidence"))
        key=text(r["id"]);unique(seen,key);text(r["rate_evidence"])
        require(r["currency"] in ("USD","EUR","GBP"),"Unsupported currency")
        rate=nonnegative(r["cad_rate_millionths"]);require(rate>0,"Missing FX rate")
        # All supported currency minor units are hundredths.
        value=ratio(cents(r["foreign_minor_units"])*rate,1000000)
        fx.append({"id":key,"currency":r["currency"],"closing_cad_cents":value,"signed_remeasurement_cents":value-cents(r["book_cad_cents"])})
    budget=[];seen=set()
    for r in records(data["budget"]):
        strict_keys(r,("account","planned_cents","actual_cents","kind"))
        key=text(r["account"]);unique(seen,key)
        require(r["kind"] in ("revenue","expense"),"Invalid budget account type")
        planned,actual=nonnegative(r["planned_cents"]),nonnegative(r["actual_cents"])
        budget.append({"account":key,"planned_cents":planned,"actual_cents":actual,"favourable_variance_cents":(actual-planned)*(1 if r["kind"]=="revenue" else -1)})
    tax=data["tax_inputs"]
    strict_keys(tax,("employees","shareholders"))
    slips=[];seen=set()
    for r in records(tax["employees"]):
        strict_keys(r,("id","employment_income_cents","income_tax_cents","cpp_cents","ei_cents","evidence"))
        key=text(r["id"]);unique(seen,key);text(r["evidence"])
        amounts={k:nonnegative(r[k]) for k in ("employment_income_cents","income_tax_cents","cpp_cents","ei_cents")}
        require(sum(v for k,v in amounts.items() if k!="employment_income_cents")<=amounts["employment_income_cents"],"Employee register deductions exceed income")
        slips.append({"type":"T4 source worksheet","id":key,**amounts})
    seen=set()
    for r in records(tax["shareholders"]):
        strict_keys(r,("id","actual_dividends_cents","interest_cents","evidence"))
        key=text(r["id"]);unique(seen,key);text(r["evidence"])
        slips.append({"type":"T5 source worksheet","id":key,"actual_dividends_cents":nonnegative(r["actual_dividends_cents"]),"interest_cents":nonnegative(r["interest_cents"])})
    return {"period":data["period"],"policy_version":policy["version"],"documents":docs,"expense_categories_cents":dict(totals),
            "card":{"reconciled":card_ok,"summary":rec,"exceptions":len(findings)},"loans":loans,"related_parties":related,"foreign_currency":fx,"budget":budget,
            "tax_source_worksheets":slips,"exceptions":flags,"review_required":bool(flags),
            "note":"Labelled text extraction only; supplied FX rates, policy, budget and tax registers. No fraud conclusion, OCR, tax slips, filing, or external posting."}

def sample(period):
    start=period+"-01"
    def movement(id,amount): return {"reference":id,"date":start,"cents":amount}
    return {"company":"Fictional Neuravale Extended Ltd.","period":period,
        "policy":{"version":"practice-v1","vendor_accounts":{"Example Office":"Office supplies"},"large_transaction_cents":50000},
        "documents":[{"source":"fictional invoice 001","text":"Invoice: INV001\nVendor: Example Office\nDate: "+start+"\nCurrency: CAD\nSubtotal: 100.00\nTax: 13.00\nTotal: 113.00"}],
        "card":{"opening_cents":10000,"closing_cents":21300,"gl_closing_cents":21300,"statement":[movement("CARD1",11300)],"ledger":[movement("CARD1",11300)],"evidence":"fictional statement"},
        "loans":[{"id":"loan1","opening_cents":100000,"draws_cents":0,"payment_cents":10000,"interest_cents":1000,"fees_cents":0,"statement_closing_cents":91000,"gl_closing_cents":91000,"evidence":"fictional amortization statement"}],
        "related_parties":[{"id":"owner1","kind":"shareholder","opening_cents":-10000,"movements_cents":[-5000],"counterparty_signed_cents":15000,"gl_closing_cents":-15000,"evidence":"fictional confirmation"},{"id":"inter1","kind":"intercompany","opening_cents":0,"movements_cents":[20000],"counterparty_signed_cents":-20000,"gl_closing_cents":20000,"evidence":"fictional confirmation"}],
        "fx":[{"id":"usd1","currency":"USD","foreign_minor_units":10000,"book_cad_cents":13000,"cad_rate_millionths":1350000,"rate_evidence":"fictional supplied rate"}],
        "budget":[{"account":"Revenue","planned_cents":400000,"actual_cents":420000,"kind":"revenue"},{"account":"Expenses","planned_cents":300000,"actual_cents":295000,"kind":"expense"}],
        "tax_inputs":{"employees":[{"id":"EMP1","employment_income_cents":100000,"income_tax_cents":10000,"cpp_cents":6000,"ei_cents":4000,"evidence":"fictional payroll register"}],"shareholders":[{"id":"SH1","actual_dividends_cents":20000,"interest_cents":0,"evidence":"fictional dividend register"}]}}
