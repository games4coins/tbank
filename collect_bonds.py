import os,json,ssl,urllib.request,urllib.error,datetime as dt,time,pathlib
now=dt.datetime.now(dt.timezone.utc)
token=os.environ["TBANK_TOKEN"].strip().removeprefix("Bearer ").removeprefix("bearer ")
tls=ssl.create_default_context()
if os.environ.get("TBANK_CA_FILE"): tls.load_verify_locations(cafile=os.environ["TBANK_CA_FILE"])
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args): return None
opener=urllib.request.build_opener(NoRedirect(),urllib.request.HTTPSHandler(context=tls))
def call(service,method,body):
    url="https://invest-public-api.tbank.ru/rest/tinkoff.public.invest.api.contract.v1."+service+"/"+method
    req=urllib.request.Request(url,data=json.dumps(body).encode(),headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"})
    with opener.open(req,timeout=25) as r: return json.load(r)
def q(v):
    v=v or {}
    return int(v.get("units",0))+int(v.get("nano",0))/1e9
bonds=call("InstrumentsService","Bonds",{"instrumentStatus":"INSTRUMENT_STATUS_BASE"}).get("instruments",[])
eligible=[b for b in bonds if b.get("currency")=="rub" and b.get("classCode")=="TQOB" and b.get("buyAvailableFlag") and b.get("maturityDate","")[:10]>now.date().isoformat()]
eligible.sort(key=lambda b:b.get("maturityDate",""))
eligible=eligible[:160]
if not eligible: raise SystemExit("No eligible bonds")
prices={}
for i in range(0,len(eligible),80):
    rows=call("MarketDataService","GetLastPrices",{"instrumentId":[b["uid"] for b in eligible[i:i+80]]}).get("lastPrices",[])
    for p in rows:
        if p.get("instrumentUid"): prices[p["instrumentUid"]]=p
        if p.get("figi"): prices[p["figi"]]=p
result=[];errors=0
for b in eligible:
    try:
        coupons=call("InstrumentsService","GetBondCoupons",{"instrumentId":b["uid"],"from":now.isoformat(),"to":(min(now+dt.timedelta(days=365*15),dt.datetime.fromisoformat(b["maturityDate"].replace("Z","+00:00")))).isoformat()}).get("events",[])
        p=prices.get(b["uid"]) or prices.get(b.get("figi")) or {}
        result.append({"ticker":b["ticker"],"name":b["name"],"uid":b["uid"],"isin":b.get("isin"),"maturity":b.get("maturityDate","")[:10],"perpetual":b.get("perpetualFlag",False),"nominal":q(b.get("nominal")),"aci":q(b.get("aciValue")),"quote":q(p["price"]) if p.get("price") else None,"quoteTime":p.get("time"),"lot":b.get("lot",1),"floating":b.get("floatingCouponFlag",False),"amortization":b.get("amortizationFlag",False),"subordinated":b.get("subordinatedFlag",False),"ofz":b.get("ticker","").startswith("SU"),"couponHorizon":"maturity_or_15_years","coupons":[{"date":c.get("couponDate","")[:10],"amount":q(c.get("payOneBond"))} for c in coupons if c.get("payOneBond",{}).get("currency")=="rub"]})
    except Exception as e:
        errors+=1
        print("Coupon error",b["ticker"],type(e).__name__,flush=True)
    time.sleep(.35)
if not result: raise SystemExit("No bond schedules received")
pathlib.Path("bonds.json").write_text(json.dumps({"updated":now.isoformat(),"errors":errors,"bonds":result},ensure_ascii=False,separators=(",",":")),encoding="utf-8")
print("Bond snapshot complete:",len(result))
