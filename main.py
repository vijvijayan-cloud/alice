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
    return f"<h1>V57 - Discovery</h1><p>User:{USER_ID}</p><p>Session: {'YES' if s else 'ILLA'}</p><p><a href='{auth_url}'><b>1. LOGIN</b></a></p><p><a href='/manual'><b>2. MANUAL</b></a></p><p><a href='/dashboard'><b>3. DASHBOARD</b></a></p><p><a href='/test'><b>4. TEST - Full Discovery</b></a></p>"
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
    if not code: return "<h1>AuthCode Illa</h1><a href='/'>Home</a>"
    try:
        REST="https://ant.aliceblueonline.com/rest/AliceBlueAPIService"
        checksum=hashlib.sha256(f"{USER_ID}{code}{APP_SECRET}".encode()).hexdigest()
        r=requests.post(f"{REST}/sso/getUserDetails", json={"checkSum":checksum,"userId":USER_ID}, timeout=10)
        sess=r.json().get("userSession")
        if sess:
            STORE["session"]=str(sess)
            return "<h2 style='color:green'>SUCCESS! Session Saved!</h2><p><a href='/test'><b>CLICK - TEST Discovery</b></a></p>"
        else: return f"<b>Session Illa - {r.text[:500]}</b><br><a href='/'>Home</a>"
    except Exception as e: return f"Err {e} <br><a href='/'>Home</a>"
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
        return f"<h1>Vanakkam {j.get('accountName')}</h1><p>Account: {j.get('accountId')} | Status: {j.get('accountStatus')} | Broker: {j.get('sBrokerName')}</p><p>Mobile: {j.get('cellAddr')} | Email: {j.get('emailAddr')}</p><p>Products: {j.get('product')}</p><p><a href='/test'>TEST</a></p><br><a href='/'>Home</a>"
    except Exception as e: return f"Err {e}"
@app.route('/test')
def test():
    import requests
    sess=STORE.get("session")
    if not sess: return "<h1>Session Illa - Login pannunga!</h1><a href='/'>Home</a>"
    h={"Authorization":f"Bearer {sess}","Content-Type":"application/json","Accept":"application/json"}
    BASE="https://ant.aliceblueonline.com/rest/AliceBlueAPIService"
    out=["<h1>V57 DISCOVERY - Compact</h1><p>404 = Path Illa | 200 + JSON = FOUND | 401 = Auth thappu</p>"]
    # Vera vera BASE try pannuvom
    bases=[
        ("cust", f"{BASE}/api/customer/"),
        ("api", f"{BASE}/api/"),
        ("root", f"{BASE}/"),
        ("posHold", f"{BASE}/api/positionAndHoldings/"),
        ("sso", f"{BASE}/sso/"),
    ]
    names=["holdings","getHoldings","positions","getPositions","positionBook","getPositionBook",
           "daywisePositions","holdingsBook","orderBook","getOrderBook","tradeBook","getTradeBook",
           "funds","getFunds","limits","getLimits","margin","fundsAndMargins","profile",
           "accountDetails","netPositions","squareoff","orderHistory","holdingsAndPositions"]
    for bname, burl in bases:
        out.append(f"<h2>BASE: {bname} - {burl}</h2>")
        for n in names:
            url=burl+n
            try:
                # GET - Compact
                r=requests.get(url, headers=h, params={"userId":USER_ID}, timeout=6)
                txt=(r.text or "").strip()
                is_json=txt.startswith("{") or txt.startswith("[")
                snippet=txt[:220].replace("<","&lt;") if is_json else f"HTML Len:{len(txt)}"
                ok=(r.status_code==200 and is_json)
                out.append(f"<p>{'✅' if ok else '❌'} GET {n} Status:{r.status_code} JSON:{is_json} {snippet}</p>")
                if ok: out.append(f"<h3 style='color:green'>FOUND GET! {bname}/{n}</h3>")
                # POST - GET 404 / fail aana mattum
                if not ok:
                    r2=requests.post(url, headers=h, json={"userId":USER_ID}, timeout=6)
                    txt2=(r2.text or "").strip()
                    is_json2=txt2.startswith("{") or txt2.startswith("[")
                    snippet2=txt2[:220].replace("<","&lt;") if is_json2 else f"HTML Len:{len(txt2)}"
                    ok2=(r2.status_code==200 and is_json2)
                    out.append(f"<p>{'✅' if ok2 else '❌'} POST {n} Status:{r2.status_code} JSON:{is_json2} {snippet2}</p>")
                    if ok2: out.append(f"<h3 style='color:green'>FOUND POST! {bname}/{n}</h3>")
            except Exception as e:
                out.append(f"<p>❌ {n} Err:{str(e)[:100]}</p>")
    return "<br>".join(out)+"<br><a href='/'>Home</a> | <a href='/dashboard'>Dashboard</a>"
if __name__=='__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT",10000)))
