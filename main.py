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
    return f"<h1>V55 - FINAL Dashboard</h1><p>User:{USER_ID}</p><p>Session: {'YES - '+s[:30]+'...' if s else 'ILLA'}</p><p><a href='{auth_url}'><b>1. LOGIN</b></a></p><p><a href='/manual'><b>2. MANUAL - AuthCode</b></a></p><p><a href='/dashboard'><b>3. DASHBOARD - Full Details</b></a></p><p><a href='/test'><b>4. TEST - Holdings + Positions + Funds</b></a></p>"
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
            return "<h2 style='color:green'>SUCCESS! Session Saved!</h2><p><a href='/dashboard'><b>CLICK - DASHBOARD</b></a></p><p><a href='/test'><b>CLICK - TEST Holdings</b></a></p>"
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
        out=[f"<h1>Dashboard - {j.get('accountName') or j.get('accountname') or j.get('clientName') or 'VIJAYAN M'}</h1>"]
        out.append("<h3>ALL KEYS - Full JSON:</h3>")
        for k,v in j.items():
            out.append(f"<p><b>{k}</b> = {v}</p>")
        out.append(f"<h3>Raw JSON:</h3><pre>{r.text[:2000].replace('<','&lt;')}</pre>")
        out.append("<p><a href='/test'><b>TEST - Holdings / Positions / Funds</b></a></p>")
        return "<br>".join(out)+"<br><a href='/'>Home</a>"
    except Exception as e: return f"Err {e} {traceback.format_exc()[:1000]}"
@app.route('/test')
def test():
    import requests
    sess=STORE.get("session")
    if not sess: return "<h1>Session Illa - Login pannunga!</h1><a href='/'>Home</a>"
    h={"Authorization":f"Bearer {sess}","Content-Type":"application/json","Accept":"application/json"}
    BASE="https://ant.aliceblueonline.com/rest/AliceBlueAPIService"
    out=["<h1>V55 TEST - Bearer - Customer API</h1>"]
    cands=[
        ("holdings","api/customer/holdings"),("holdings2","api/customer/getHoldings"),
        ("positions","api/customer/positions"),("positions2","api/customer/getPositions"),
        ("daywise","api/customer/daywisePositions"),("funds","api/customer/funds"),
        ("limits","api/customer/limits"),("orderBook","api/customer/orderBook"),
        ("tradeBook","api/customer/tradeBook"),("margin","api/customer/margin"),
    ]
    for name, path in cands:
        url=f"{BASE}/{path}"
        try:
            r=requests.get(url, headers=h, params={"userId":USER_ID}, timeout=7)
            txt=(r.text or "")
            is_html="<html" in txt.lower()
            ok=(r.status_code==200 and not is_html and '"stat":"Ok"' in txt)
            mark="✅" if ok else "❌"
            out.append(f"<p>{mark} GET {name} Status:{r.status_code} Body:{txt[:700].replace('<','&lt;')}</p>")
            if ok: out.append(f"<h2 style='color:green'>FOUND! {name}</h2>")
            if not ok:
                r2=requests.post(url, headers=h, json={"userId":USER_ID}, timeout=7)
                txt2=(r2.text or "")
                ok2=(r2.status_code==200 and "<html" not in txt2.lower() and '"stat":"Ok"' in txt2)
                out.append(f"<p>{'✅' if ok2 else '❌'} POST {name} Status:{r2.status_code} Body:{txt2[:700].replace('<','&lt;')}</p>")
                if ok2: out.append(f"<h2 style='color:green'>FOUND POST! {name}</h2>")
        except Exception as e: out.append(f"<p>❌ {name} Err:{e}</p>")
    return "<br>".join(out)+"<br><a href='/'>Home</a> | <a href='/dashboard'>Dashboard</a>"
if __name__=='__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT",10000)))
