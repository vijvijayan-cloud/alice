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
    return f"<h1>V52 - FINAL</h1><p>User:{USER_ID}</p><p>Session Saved: {'YES - '+s[:30]+'...' if s else 'ILLA'}</p><p><a href='{auth_url}'><b>1. LOGIN - AliceBlue Website</b></a></p><p><a href='/manual'><b>2. MANUAL - AuthCode Paste</b></a></p><p><a href='/test'><b>3. TEST - Profile + Holdings</b></a></p>"
@app.route('/manual')
def manual():
    return """<h1>AuthCode Paste</h1><form action='/exchange'><input name='authCode' placeholder='AuthCode' style='width:320px'><button>EXCHANGE</button></form><br><a href='/'>Home</a>"""
@app.route('/callback')
def callback():
    code=request.args.get("authCode") or request.args.get("code")
    if not code: return f"No AuthCode {request.url} <a href='/'>Home</a>"
    return redirect(f"/exchange?authCode={code}")
@app.route('/exchange')
def exchange():
    import requests
    code=request.args.get("authCode","").strip()
    out=[f"<h1>V52 EXCHANGE</h1><p>AuthCode: {code[:25]}...</p>"]
    if not code: return "<h1>AuthCode Illa</h1><a href='/'>Home</a>"
    try:
        REST="https://ant.aliceblueonline.com/rest/AliceBlueAPIService"
        checksum=hashlib.sha256(f"{USER_ID}{code}{APP_SECRET}".encode()).hexdigest()
        r=requests.post(f"{REST}/sso/getUserDetails", json={"checkSum":checksum,"userId":USER_ID}, timeout=10)
        out.append(f"<p>Status:{r.status_code}</p><pre>{r.text[:2000].replace('<','&lt;')}</pre>")
        j=r.json()
        sess=j.get("userSession")  # CORRECT KEY - Idhu thaan Session!
        out.append(f"<p><b>Keys: {list(j.keys())}</b></p>")
        out.append(f"<p><b>userSession Found: {'YES' if sess else 'NO'} Len:{len(str(sess)) if sess else 0}</b></p>")
        if sess:
            STORE["session"]=str(sess)
            out.append(f"<h2 style='color:green'>SUCCESS! Session Saved!</h2><p>Session: {str(sess)[:80]}...</p><p><a href='/test'><b>CLICK - TEST</b></a></p>")
        else:
            out.append("<b>Session Illa - AuthCode already used-a? Pudhu Login pannunga!</b>")
    except Exception as e: out.append(f"Err {e} {traceback.format_exc()[:1500]}")
    return "<br>".join(out)+"<br><a href='/'>Home</a>"
@app.route('/test')
def test():
    sess=STORE.get("session")
    if not sess: return "<h1>Session Illa - Login pannunga!</h1><a href='/'>Home</a>"
    out=[f"<h1>TEST</h1><p>Session: {sess[:50]}...</p>"]
    try:
        from alice_blue.alice_blue import AliceBlue
        try:
            real=AliceBlue(username=USER_ID, session_id=sess)
            prof=real.get_profile()
            out.append(f"<h2 style='color:green'>✅ PROFILE SUCCESS</h2><pre>{str(prof)[:1500]}</pre>")
        except Exception as e: out.append(f"<p>Profile Err: {e}</p>")
        try:
            real2=AliceBlue(username=USER_ID, session_id=sess)
            hold=real2.get_holdings()
            out.append(f"<h2>✅ HOLDINGS</h2><pre>{str(hold)[:2000]}</pre>")
        except Exception as e: out.append(f"<p>Holdings Err: {e}</p>")
    except Exception as e: out.append(f"Err {e} {traceback.format_exc()[:1000]}")
    return "<br>".join(out)+"<br><a href='/'>Home</a>"
if __name__=='__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT",10000)))
