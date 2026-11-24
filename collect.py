import os,json,urllib.request,urllib.error,datetime,time, pathlib, ssl
BASE="https://invest-public-api.tbank.ru/rest/tinkoff.public.invest.api.contract.v1.InstrumentsService/"
TOKEN=os.environ.get("TBANK_TOKEN","").strip()
if not TOKEN:
    raise SystemExit("::error::Missing TBANK_TOKEN. Add repository Actions secret TBANK_TOKEN in Settings.")
if TOKEN.lower().startswith("bearer "):
    TOKEN=TOKEN[7:].strip()
# Additional trust is scoped to this API client, not the system.
TLS=ssl.create_default_context()
ca=os.environ.get("TBANK_CA_FILE")
if ca:
    TLS.load_verify_locations(cafile=ca)
    print("T-Invest CA bundle loaded; TLS verification enabled",flush=True)
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
OPENER=urllib.request.build_opener(NoRedirect(),urllib.request.HTTPSHandler(context=TLS))
def call(method,body):
    req=urllib.request.Request(BASE+method,data=json.dumps(body).encode(),headers={"Authorization":"Bearer "+TOKEN,"Content-Type":"application/json"})
    for attempt in range(3):
        try:
            with OPENER.open(req,timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            print(f"{method}: HTTP {e.code}; tracking-id={e.headers.get('x-tracking-id','-')}",flush=True)
            if e.code in (429,500,502,503,504) and attempt<2:
                time.sleep(3*(attempt+1))
                continue
            if e.code in (401,403):
                raise SystemExit(f"::error::{method}: HTTP {e.code}. Check production read-only token and API access.")
            raise
        except urllib.error.URLError as e:
            print(f"{method}: network error ({type(e.reason).__name__})",flush=True)
            if isinstance(e.reason,ssl.SSLCertVerificationError):
                raise SystemExit("::error::TLS certificate verification failed: "+e.reason.verify_message)
            if attempt<2:
                time.sleep(3*(attempt+1))
                continue
            raise
def money(x):
    return int(x.get("units",0))+int(x.get("nano",0))/1e9
blue=set("SBER SBERP GAZP LKOH GMKN NVTK ROSN PLZL YDEX T MTSS".split())
now=datetime.datetime.now(datetime.timezone.utc)
start=datetime.datetime(now.year-1,1,1,tzinfo=datetime.timezone.utc)
end=datetime.datetime(now.year+2,1,1,tzinfo=datetime.timezone.utc)
print("Checking T-Invest API connection (Shares)...",flush=True)
shares=call("Shares",{"instrumentStatus":"INSTRUMENT_STATUS_BASE"})["instruments"]
print(f"API connected: {len(shares)} instruments received",flush=True)
events=[]; errors=0; total=0
for s in shares:
    if s.get("currency")!="rub" or s.get("classCode")!="TQBR": continue
    total+=1
    try:
        div=call("GetDividends",{"instrumentId":s["uid"],"from":start.isoformat(),"to":end.isoformat()})
        for d in div.get("dividends",[]):
            cash=d.get("dividendNet",{})
            if cash.get("currency")!="rub": continue
            events.append({"ticker":s["ticker"],"name":s["name"],"sector":s.get("sector","unknown"),"blue":s["ticker"] in blue,"amount":money(cash),"lastBuy":d.get("lastBuyDate","")[:10],"payment":d.get("paymentDate","")[:10],"yield":money(d["yieldValue"]) if d.get("yieldValue") else None})
    except Exception as e:
        errors+=1
        print(s["ticker"],type(e).__name__)
    time.sleep(0.8)
print(f"Processed {total} shares; errors={errors}; dividends={len(events)}",flush=True)
if not total or errors==total: raise RuntimeError("No successful dividend requests")
p=pathlib.Path("data.json")
p.write_text(json.dumps({"updated":now.isoformat(),"events":events,"errors":errors},ensure_ascii=False),encoding="utf-8")
