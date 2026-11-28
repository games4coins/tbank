import os, json, ssl, urllib.request, datetime, base64, pathlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

password=os.environ.get("PORTFOLIO_PASSWORD","")
if not password:
    print("Portfolio export disabled: no PORTFOLIO_PASSWORD")
    raise SystemExit(0)
if len(password)<20:
    raise SystemExit("::error::Use a unique random password of at least 20 characters")
token=os.environ["TBANK_TOKEN"].strip()
if token.lower().startswith("bearer "): token=token[7:].strip()
tls=ssl.create_default_context()
if os.environ.get("TBANK_CA_FILE"): tls.load_verify_locations(cafile=os.environ["TBANK_CA_FILE"])
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args): return None
opener=urllib.request.build_opener(NoRedirect(),urllib.request.HTTPSHandler(context=tls))
def call(service,method,body):
    url="https://invest-public-api.tbank.ru/rest/tinkoff.public.invest.api.contract.v1."+service+"/"+method
    req=urllib.request.Request(url,data=json.dumps(body).encode(),headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"})
    with opener.open(req,timeout=45) as response: return json.load(response)
def num(v):
    v=v or {}
    return int(v.get("units",0))+int(v.get("nano",0))/1e9
def money(v):
    return {"value":num(v),"currency":(v or {}).get("currency","")}
def collect():
    accounts=call("UsersService","GetAccounts",{}).get("accounts",[])
    shares=call("InstrumentsService","Shares",{"instrumentStatus":"INSTRUMENT_STATUS_BASE"}).get("instruments",[])
    bonds=call("InstrumentsService","Bonds",{"instrumentStatus":"INSTRUMENT_STATUS_BASE"}).get("instruments",[])
    index={k:s for s in shares+bonds for k in [s.get("uid"),s.get("figi")] if k}
    result=[]
    coupon_cache={}
    now=datetime.datetime.now(datetime.timezone.utc)
    for a in accounts:
        if a.get("status")!="ACCOUNT_STATUS_OPEN": continue
        p=call("OperationsService","GetPortfolio",{"accountId":a["id"],"currency":"RUB"})
        positions=[]
        for x in p.get("positions",[]):
            t=x.get("instrumentType","")
            if t not in ("share","bond"): continue
            m=index.get(x.get("instrumentUid")) or index.get(x.get("figi")) or {}
            uid=x.get("instrumentUid") or m.get("uid") or ""
            if t=="bond" and uid and uid not in coupon_cache:
                try:
                    events=call("InstrumentsService","GetBondCoupons",{"instrumentId":uid,"from":now.isoformat(),"to":(now+datetime.timedelta(days=366)).isoformat()}).get("events",[])
                    coupon_cache[uid]=[{"date":c.get("couponDate","")[:10],"amount":num(c.get("payOneBond"))} for c in events if c.get("payOneBond",{}).get("currency")=="rub"]
                except Exception:
                    coupon_cache[uid]=None
            positions.append({"ticker":m.get("ticker") or x.get("figi") or "—","name":m.get("name",""),"type":t,"quantity":num(x.get("quantity")),"average":money(x.get("averagePositionPrice")),"current":money(x.get("currentPrice")),"yield":num(x.get("expectedYield")),"uid":uid,"figi":x.get("figi",""),"coupons":coupon_cache.get(uid) if t=="bond" else None})
        result.append({"name":a.get("name") or "Брокерский счёт","total":money(p.get("totalAmountPortfolio")),"positions":positions})
    return {"updated":datetime.datetime.now(datetime.timezone.utc).isoformat(),"accounts":result}
try:
    payload=json.dumps(collect(),ensure_ascii=False).encode()
    salt=os.urandom(16); nonce=os.urandom(12); iterations=600000
    key=PBKDF2HMAC(algorithm=hashes.SHA256(),length=32,salt=salt,iterations=iterations).derive(password.encode("utf-8"))
    enc=AESGCM(key).encrypt(nonce,payload,b"tbank-portfolio-v1")
    b64=lambda b:base64.b64encode(b).decode("ascii")
    pathlib.Path("portfolio.enc.json").write_text(json.dumps({"version":1,"iterations":iterations,"salt":b64(salt),"nonce":b64(nonce),"ciphertext":b64(enc)}),encoding="utf-8")
    print("Encrypted portfolio export complete")
except Exception as e:
    print("::error::Portfolio export failed ("+type(e).__name__+")")
    raise SystemExit(1) from None
