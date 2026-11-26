"""Read-only test connector adapters. No credentials or response bodies persisted."""
import json
import re
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import quote, urlencode
from urllib.error import HTTPError, URLError

CATALOG={
 "Accounting":["QuickBooks Online","QuickBooks Desktop","Xero","Wave","Sage 50","FreshBooks","Zoho Books"],
 "Spreadsheets and documents":["Microsoft Excel","Google Sheets","Google Drive","OneDrive","Dropbox"],
 "Commerce and POS":["Shopify","Amazon Seller Central","WooCommerce","Square","Lightspeed","Clover"],
 "Payments":["Stripe","PayPal","Moneris","Helcim","Wise"],
 "Payroll":["ADP","Wagepoint","Dayforce","Payworks","Employment Hero","Gusto"],
 "Banking":["RBC","TD","Scotiabank","BMO","CIBC","National Bank","Plaid","Flinks"],
 "Expenses":["Dext","Hubdoc","Expensify","Ramp"],
 "Tax":["CRA My Business Account","TaxCycle","Taxprep","ProFile","TurboTax Business"],
 "Communication":["Gmail","Microsoft Outlook","Slack","Microsoft Teams"],
 "Business management":["ServiceTitan","Jobber","Housecall Pro","Odoo","Microsoft Dynamics 365","NetSuite"],
}
ADAPTERS={
 "Google Sheets":{"fields":[("spreadsheet","Spreadsheet ID"),("range","A1 range (e.g. Sheet1!A1:D20)")],"secret":"Short-lived OAuth access token (read-only Sheets scope)"},
 "Shopify":{"fields":[("shop","Development store (name.myshopify.com)")],"secret":"Admin API access token (read_orders)"},
 "Stripe":{"fields":[],"secret":"Restricted test-mode API key (rk_test_...)"},
 "QuickBooks Online":{"fields":[("realm","Sandbox company realm ID")],"secret":"Sandbox OAuth access token"},
}
MAX_RESPONSE=2_000_000

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

def request_json(url,headers,body=None):
    # URLs originate only from validated adapter configuration below. No proxy from environment,
    # redirect following, caller-provided headers or arbitrary request methods.
    from urllib.request import ProxyHandler
    req=Request(url,headers={"Accept":"application/json",**headers},data=body,
                method="POST" if body is not None else "GET")
    try:
        with build_opener(ProxyHandler({}),NoRedirect()).open(req,timeout=20) as response:
            raw=response.read(MAX_RESPONSE+1)
    except HTTPError as exc:
        raise ValueError("Provider returned HTTP "+str(exc.code)+". Check test credentials, access scope and rate limits.") from None
    except (URLError,TimeoutError,OSError):
        raise ValueError("Provider connection failed or timed out.") from None
    if len(raw)>MAX_RESPONSE:
        raise ValueError("Response too large; select a smaller test range.")
    try:
        data=json.loads(raw)
    except (ValueError,UnicodeError):
        raise ValueError("Provider did not return valid JSON.") from None
    if not isinstance(data,dict):
        raise ValueError("Unexpected provider response.")
    return data

def checked(value,pattern,label):
    if not isinstance(value,str) or not re.fullmatch(pattern,value):
        raise ValueError("Invalid "+label)
    return value

def read_sample(provider,config,token,transport=request_json):
    if provider not in ADAPTERS:
        raise ValueError("No implemented adapter for this application.")
    if not isinstance(token,str) or not 8<=len(token)<=8192 or any(ord(c)<=32 or ord(c)>126 for c in token):
        raise ValueError("Invalid token format.")
    if set(config)!={k for k,_ in ADAPTERS[provider]["fields"]}:
        raise ValueError("Unexpected connector configuration.")
    auth={"Authorization":"Bearer "+token}
    if provider=="Google Sheets":
        sheet=checked(config["spreadsheet"],r"[A-Za-z0-9_-]{10,150}","spreadsheet ID")
        range_=config["range"]
        if not isinstance(range_,str) or not 1<=len(range_)<=180 or any(ord(c)<32 for c in range_):
            raise ValueError("Invalid range")
        # Restrict to bounded rectangular A1 ranges (maximum 100 rows and 20 columns).
        match=re.fullmatch(r"(?:[^!]+!)?([A-Z]{1,3})([1-9]\d{0,6}):([A-Z]{1,3})([1-9]\d{0,6})",range_)
        if not match: raise ValueError("Use a bounded A1 range, e.g. Sheet1!A1:D20.")
        def col(s):
            n=0
            for c in s: n=n*26+ord(c)-64
            return n
        width=col(match[3])-col(match[1])+1
        height=int(match[4])-int(match[2])+1
        if not 1<=width<=20 or not 1<=height<=100: raise ValueError("Range maximum is 100 rows by 20 columns.")
        data=transport("https://sheets.googleapis.com/v4/spreadsheets/"+sheet+"/values/"+quote(range_,safe="")+"?valueRenderOption=UNFORMATTED_VALUE",auth)
        if "error" in data: raise ValueError("Sheets returned an error.")
        rows=data.get("values",[])
        if not isinstance(rows,list) or len(rows)>height or any(not isinstance(r,list) or len(r)>width for r in rows):
            raise ValueError("Unexpected Sheets data.")
        return {"provider":provider,"scope":"Selected test cells; not a complete ledger","count":len(rows),"truncated":False,"records":rows}
    if provider=="Shopify":
        shop=checked(config["shop"],r"[a-z0-9][a-z0-9-]{0,62}\.myshopify\.com","development shop hostname")
        query={"query":"query FinanceRead { orders(first: 20) { nodes { id createdAt currentTotalPriceSet { shopMoney { amount currencyCode } } } pageInfo { hasNextPage } } }"}
        data=transport("https://"+shop+"/admin/api/2026-10/graphql.json",{"X-Shopify-Access-Token":token,"Content-Type":"application/json"},json.dumps(query).encode())
        if data.get("errors"): raise ValueError("Shopify query failed. Check development shop and read_orders scope.")
        block=data["data"]["orders"];rows=block["nodes"]
        if not isinstance(rows,list) or len(rows)>20: raise ValueError("Unexpected Shopify data.")
        output=[{"id":r["id"],"created":r["createdAt"],"total":r["currentTotalPriceSet"]["shopMoney"]["amount"],"currency":r["currentTotalPriceSet"]["shopMoney"]["currencyCode"]} for r in rows]
        return {"provider":provider,"scope":"Up to 20 order totals; not net sales or payouts","count":len(output),"truncated":bool(block["pageInfo"]["hasNextPage"]),"records":output}
    if provider=="Stripe":
        checked(token,r"rk_test_[A-Za-z0-9_]{8,200}","restricted Stripe test key")
        data=transport("https://api.stripe.com/v1/balance_transactions?limit=20",auth)
        rows=data["data"]
        if not isinstance(rows,list) or len(rows)>20: raise ValueError("Unexpected Stripe data.")
        output=[{k:r[k] for k in ("id","created","currency","amount","fee","net","type")} for r in rows]
        return {"provider":provider,"scope":"Up to 20 test balance transactions; amounts in currency minor units","count":len(output),"truncated":bool(data["has_more"]),"records":output}
    realm=checked(config["realm"],r"\d{1,30}","QuickBooks sandbox realm ID")
    query=urlencode({"query":"SELECT * FROM Invoice MAXRESULTS 20"})
    data=transport("https://sandbox-quickbooks.api.intuit.com/v3/company/"+realm+"/query?"+query,auth)
    if "Fault" in data: raise ValueError("QuickBooks returned a query fault.")
    block=data["QueryResponse"];rows=block.get("Invoice",[])
    if not isinstance(rows,list) or len(rows)>20: raise ValueError("Unexpected QuickBooks data.")
    output=[{"id":r["Id"],"date":r["TxnDate"],"total":r["TotalAmt"],"balance":r["Balance"],"currency":r.get("CurrencyRef",{}).get("value","unspecified")} for r in rows]
    return {"provider":provider,"scope":"Up to 20 sandbox invoices; not a complete receivable ledger","count":len(output),"truncated":len(rows)==20,"records":output}
