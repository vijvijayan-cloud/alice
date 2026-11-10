import os, traceback, hashlib, json
from flask import Flask, request, redirect
app = Flask(__name__)
def clean(n):
    return os.getenv(n,"").strip().replace('"',"").replace("'","")
USER_ID=clean("ALICE_USER_ID")
APP_ID=clean("ALICE_APP_ID")
APP_SECRET=clean("ALICE_APP_SECRET")
STORE={"session":None}
@app.route('/')
def home():
    auth_url=f"https://ant.aliceblueonline.com/?appcode={APP_ID}"
    s=STORE.get("session")
    return f"<h1>V54 - FOUND Bearer + Customer API</h1><p>User:{USER_ID}</p><p>Session: {'YES - '+s[:30]+'...' if s else 'ILLA'}</p><p><a href='{auth_url}'><b>1. LOGIN</b></a></p><p><a href='/manual'><b>2. MANUAL - AuthCode</b></a></p><p><a href='/test'><b>3. TEST - Holdings + Positions + Funds + Orders</b></a></p><p><a href='/dashboard'><b>4. DASHBOARD - Account Details</b></a></p>"
@app.route('/manual')
def manual():
    return """<h1>AuthCode</h1><form action='/exchange'><input name='authCode' placeholder='AuthCode' style='width:320px'><button>EXCHANGE</button></form><br><a href='/'>Home</a>"""
@app.route('/callback')
def callback():
    code=request.args.get("authCode") or request.args.get("code")
    if not code: return f"No AuthCode {request.url} <a href='/'>Home</a>"
    return redirect(f"/exchange?authCode={code}")
@app.route('/exchange')
def exchange():
    import requests
    code=request.args.get("authCode","").strip()
    out=[f"<h1>V54 EXCHANGE</h1><p>AuthCode: {code[:25]}...</p>"]
    if not code: return "<h1>AuthCode Illa</h1><a href='/'>Home</a>"
    try:
        REST="https://ant.aliceblueonline.com/rest/AliceBlueAPIService"
        checksum=hashlib.sha256(f"{USER_ID}{code}{APP_SECRET}".encode()).hexdigest()
        r=requests.post(f"{REST}/sso/getUserDetails", json={"checkSum":checksum,"userId":USER_ID}, timeout=10)
        out.append(f"<p>Status:{r.status_code}</p><pre>{r.text[:1200].replace('<','&lt;')}</pre>")
        sess=r.json().get("userSession")
        if sess:
            STORE["session"]=str(sess)
            out.append(f"<h2 style='color:green'>SUCCESS! Session Saved!</h2><p><a href='/test'><b>CLICK - TEST</b></a></p>")
        else: out.append("<b>Session Illa - Pudhu Login pannunga!</b>")
    except Exception as e: out.append(f"Err {e} {traceback.format_exc()[:1200]}")
    return "<br>".join(out)+"<br><a href='/'>Home</a>"
@app.route('/dashboard')
def dashboard():
    import requests
    sess=STORE.get("session")
    if not sess: return "<h1>Session Illa - Login pannunga!</h1><a href='/'>Home</a>"
    h={"Authorization":f"Bearer {sess}","Content-Type":"application/json"}
    BASE="https://ant.aliceblueonline.com/rest/AliceBlueAPIService"
    try:
        r=requests.get(f"{BASE}/api/customer/accountDetails", headers=h, params={"userId":USER_ID}, timeout=8)
        j=r.json()
        out=[f"<h1>Dashboard - {j.get('accountName','')}</h1><p>Demat: {j.get('dematId')} | Broker: {j.get('brokerName')} | DP: {j.get('dpType')}</p><p>Mobile: {j.get('cellAddr')} | Email: {j.get('emailAddr')}</p><p>Product: {j.get('product')}</p><p>Exchanges: {j.get('exchEnabled')}</p><p><a href='/test'>TEST - Holdings/Positions/Funds</a></p>"]
        return "<br>".join(out)+"<br><a href='/'>Home</a>"
    except Exception as e: return f"Err {e} {traceback.format_exc()[:1000]}"
@app.route('/test')
def test():
    import requests
    sess=STORE.get("session")
    if not sess: return "<h1>Session Illa - Login pannunga!</h1><a href='/'>Home</a>"
    h={"Authorization":f"Bearer {sess}","Content-Type":"application/json","Accept":"application/json"}
    BASE="https://ant.aliceblueonline.com/rest/AliceBlueAPIService"
    out=[f"<h1>V54 TEST - Bearer ONLY - Customer API</h1>"]
    # Bearer + /api/customer/ la - Ella possibility-um
    cands=[
        ("holdings-1","api/customer/holdings"),("holdings-2","api/customer/getHoldings"),
        ("holdings-3","api/customer/Holdings"),("holdings-4","api/customer/holding"),
        ("holdings-5","api/customer/positionAndHoldings/holdings"),
        ("positions-1","api/customer/positions"),("positions-2","api/customer/getPositions"),
        ("positions-3","api/customer/daywisePositions"),("positions-4","api/customer/getDaywisePositions"),
        ("positions-5","api/customer/netPositions"),
        ("funds-1","api/customer/funds"),("funds-2","api/customer/getFunds"),
        ("funds-3","api/customer/limits"),("funds-4","api/customer/getLimits"),
        ("funds-5","api/customer/margin"),("funds-6","api/customer/accountBalance"),
        ("orders-1","api/customer/orderBook"),("orders-2","api/customer/getOrderBook"),
        ("orders-3","api/customer/orders"),("orders-4","api/customer/tradeBook"),
        ("orders-5","api/customer/getTradeBook"),("orders-6","api/customer/trades"),
        ("profile-2","api/customer/getAccountDetails"),("profile-3","api/customer/profile"),
    ]
    for name, path in cands:
        url=f"{BASE}/{path}"
        try:
            r=requests.get(url, headers=h, params={"userId":USER_ID}, timeout=7)
            txt=(r.text or "")
            is_html="<html" in txt.lower()
            ok=(r.status_code==200 and not is_html and '"stat":"Ok"' in txt)
            mark="✅" if ok else "❌"
            out.append(f"<p>{mark} GET {name} [{path}] Status:{r.status_code} HTML:{is_html} Body:{txt[:600].replace('<','&lt;')}</p>")
            if ok: out.append(f"<h2 style='color:green'>FOUND! {name} - {path}</h2>")
            if not ok:
                r2=requests.post(url, headers=h, json={"userId":USER_ID}, timeout=7)
                txt2=(r2.text or "")
                is_html2="<html" in txt2.lower()
                ok2=(r2.status_code==200 and not is_html2 and '"stat":"Ok"' in txt2)
                mark2="✅" if ok2 else "❌"
                out.append(f"<p>{mark2} POST {name} Status:{r2.status_code} Body:{txt2[:600].replace('<','&lt;')}</p>")
                if ok2: out.append(f"<h2 style='color:green'>FOUND POST! {name} - {path}</h2>")
        except Exception as e: out.append(f"<p>❌ {name} Err:{e}</p>")
    return "<br>".join(out)+"<br><a href='/'>Home</a> | <a href='/dashboard'>Dashboard</a>"
if __name__=='__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT",10000)))
