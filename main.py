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
    return f"<h1>V59 - VIJAYAN.M - FINAL Dashboard</h1><p>User:{USER_ID}</p><p>Session: {'YES' if s else 'ILLA'}</p><p><a href='{auth_url}'><b>1. LOGIN</b></a></p><p><a href='/manual'><b>2. MANUAL</b></a></p><p><a href='/dashboard'><b>3. DASHBOARD - Holdings + Funds</b></a></p>"
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
            return "<h2 style='color:green'>SUCCESS! Session Saved!</h2><p><a href='/dashboard'><b>CLICK - DASHBOARD</b></a></p>"
        else: return f"<b>Session Illa - {r.text[:500]}</b><br><a href='/'>Home</a>"
    except Exception as e: return f"Err {e} <br><a href='/'>Home</a>"
@app.route('/dashboard')
def dashboard():
    import requests
    sess=STORE.get("session")
    if not sess: return "<h1>Session Illa - Login pannunga!</h1><a href='/'>Home</a>"
    h={"Authorization":f"Bearer {sess}","Content-Type":"application/json","Accept":"application/json"}
    BASE="https://ant.aliceblueonline.com"
    def get(path):
        try:
            r=requests.get(f"{BASE}{path}", headers=h, params={"userId":USER_ID}, timeout=7)
            return r.json() if r.text.strip().startswith("{") else {"raw":r.text[:300]}
        except Exception as e: return {"error":str(e)}
    prof=get("/open-api/od/v1/profile")
    lim=get("/open-api/od/v1/limits")
    hold_cnc=get("/open-api/od/v1/holdings/CNC")
    hold_mtf=get("/open-api/od/v1/holdings/MTF")
    pos=get("/open-api/od/v1/positions")
    # Profile - result la irukkalam / direct la irukkalam
    p=prof.get("result") if isinstance(prof.get("result"), dict) else prof
    # Limits
    l=lim.get("result") if isinstance(lim.get("result"), dict) else lim
    out=[f"<h1>👋 Vanakkam {p.get('clientName') or p.get('accountName') or 'VIJAYAN.M'}</h1>"]
    out.append(f"<p><b>Account:</b> {p.get('clientId') or p.get('accountId')} | <b>Status:</b> {p.get('accountStatus')} | <b>POA:</b> {p.get('isPoaProvided')} | <b>TOTP:</b> {p.get('isTotpEnabled')}</p>")
    out.append(f"<p><b>Email:</b> {p.get('email')} | <b>Products:</b> {p.get('products')}</p>")
    out.append("<hr><h2>💰 FUNDS - Limits</h2>")
    if isinstance(l, dict) and l.get("tradingLimit"):
        out.append(f"<h1 style='color:green'>Rs. {l.get('tradingLimit')}</h1>")
        out.append(f"<p><b>Trading Limit:</b> {l.get('tradingLimit')} | <b>Opening Cash:</b> {l.get('openingCashLimit')}</p>")
        out.append(f"<p><b>Utilized Margin:</b> {l.get('utilizedMargin')} | <b>Collateral:</b> {l.get('collateralMargin')} | <b>Credit For Sell:</b> {l.get('creditForSell')}</p>")
        out.append(f"<p><b>Blocked For Payout:</b> {l.get('blockedForPayout')} | <b>AdHoc Margin:</b> {l.get('adHocMargin')}</p>")
    else:
        out.append(f"<p>Funds kidaikkala: {lim}</p>")
    out.append("<hr><h2>📈 HOLDINGS - CNC</h2>")
    hc=hold_cnc.get("result")
    if isinstance(hc, list) and len(hc)>0:
        for it in hc:
            out.append(f"<p><b>{it.get('symbol') or it.get('tradingSymbol') or it}</b> - Qty: {it.get('quantity') or it.get('qty')} - Avg: {it.get('avgPrice')} - LTP: {it.get('ltp')} - P&L: {it.get('pnl')}</p>")
    else:
        out.append(f"<p>Holdings Illa - {hold_cnc.get('message') or hold_cnc}</p><p>Share vaangina thaan inga varum!</p>")
    out.append("<hr><h2>📈 HOLDINGS - MTF</h2>")
    hm=hold_mtf.get("result")
    if isinstance(hm, list) and len(hm)>0:
        for it in hm: out.append(f"<p>{it}</p>")
    else:
        out.append(f"<p>MTF Holdings Illa - {hold_mtf.get('message') or hold_mtf}</p>")
    out.append("<hr><h2>📊 POSITIONS</h2>")
    pp=pos.get("result")
    if isinstance(pp, list) and len(pp)>0:
        for it in pp: out.append(f"<p>{it}</p>")
    else:
        out.append(f"<p>Positions Illa - {pos.get('message') or pos}</p><p>Trade pannina thaan inga varum!</p>")
    out.append("<hr><p><a href='/dashboard'>🔄 REFRESH</a> | <a href='/'>Home</a></p>")
    return "<br>".join(out)
if __name__=='__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT",10000)))
