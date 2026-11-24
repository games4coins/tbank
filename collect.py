import os,json,urllib.request,datetime,time, pathlib
BASE="https://invest-public-api.tbank.ru/rest/tinkoff.public.invest.api.contract.v1.InstrumentsService/"
TOKEN=os.environ["TBANK_TOKEN"]
def call(method,body):
    req=urllib.request.Request(BASE+method,data=json.dumps(body).encode(),headers={"Authorization":"Bearer "+TOKEN,"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=30) as r: return json.load(r)
def money(x):
    return int(x.get("units",0))+int(x.get("nano",0))/1e9
blue=set("SBER SBERP GAZP LKOH GMKN NVTK ROSN PLZL YDEX T MTSS".split())
now=datetime.datetime.now(datetime.timezone.utc)
start=datetime.datetime(now.year-1,1,1,tzinfo=datetime.timezone.utc)
end=datetime.datetime(now.year+2,1,1,tzinfo=datetime.timezone.utc)
shares=call("Shares",{"instrumentStatus":"INSTRUMENT_STATUS_BASE"})["instruments"]
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
if not total or errors==total: raise RuntimeError("No successful dividend requests")
p=pathlib.Path("data.json")
p.write_text(json.dumps({"updated":now.isoformat(),"events":events,"errors":errors},ensure_ascii=False),encoding="utf-8")
