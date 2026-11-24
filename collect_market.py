import os,json,ssl,urllib.request,urllib.error,datetime as dt,time,pathlib,statistics,math
UTC=dt.timezone.utc
now=dt.datetime.now(UTC)
token=os.environ["TBANK_TOKEN"].strip().removeprefix("Bearer ").removeprefix("bearer ")
tls=ssl.create_default_context()
if os.environ.get("TBANK_CA_FILE"): tls.load_verify_locations(cafile=os.environ["TBANK_CA_FILE"])
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args): return None
opener=urllib.request.build_opener(NoRedirect(),urllib.request.HTTPSHandler(context=tls))
def call(service,method,body):
    url="https://invest-public-api.tbank.ru/rest/tinkoff.public.invest.api.contract.v1."+service+"/"+method
    req=urllib.request.Request(url,data=json.dumps(body).encode(),headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"})
    for attempt in range(3):
        try:
            with opener.open(req,timeout=25) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code not in (429,500,502,503,504) or attempt==2: raise
            time.sleep(2**attempt)
def q(v):
    v=v or {}
    return int(v.get("units",0))+int(v.get("nano",0))/1e9
def instrument(method):
    return call("InstrumentsService",method,{"instrumentStatus":"INSTRUMENT_STATUS_BASE"}).get("instruments",[])
def candles(uid,interval,days):
    rows=call("MarketDataService","GetCandles",{"instrumentId":uid,"from":(now-dt.timedelta(days=days)).isoformat(),"to":now.isoformat(),"interval":interval}).get("candles",[])
    return sorted([[x["time"],q(x["open"]),q(x["high"]),q(x["low"]),q(x["close"]),int(x.get("volume",0))] for x in rows if x.get("isComplete") and q(x["close"])>0],key=lambda x:x[0])
blue=set("SBER SBERP GAZP LKOH GMKN NVTK ROSN PLZL YDEX T MTSS".split())
selected=set("SBER SBERP GAZP LKOH GMKN NVTK ROSN PLZL YDEX T MTSS VTBR MOEX MGNT CHMF NLMK AFLT ALRS SNGS SNGSP TATN TATNP PHOR RUAL IRAO FLOT BSPB".split())
shares=[s for s in instrument("Shares") if s.get("currency")=="rub" and s.get("classCode")=="TQBR"]
result=[]; errors=0
for s in shares:
    if s["ticker"] not in selected: continue
    try:
        daily=candles(s["uid"],"CANDLE_INTERVAL_DAY",180)
        intraday=candles(s["uid"],"CANDLE_INTERVAL_5_MIN",2)
        if daily:
            result.append({"ticker":s["ticker"],"name":s["name"],"sector":s.get("sector",""),"blue":s["ticker"] in blue,"lot":s.get("lot",1),"daily":daily,"intraday":intraday})
    except Exception as e:
        errors+=1
        print("Market data error",s["ticker"],type(e).__name__,flush=True)
    time.sleep(.3)
if not result: raise SystemExit("No market series received")
pathlib.Path("market.json").write_text(json.dumps({"updated":now.isoformat(),"errors":errors,"shares":result},ensure_ascii=False,separators=(",",":")),encoding="utf-8")
print("Market snapshot complete:",len(result),"shares")
