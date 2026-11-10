import os, traceback, json, hashlib
from flask import Flask, request, redirect
app = Flask(__name__)
def clean(n):
    return os.getenv(n,"").strip().replace('"',"").replace("'","")
USER_ID=clean("ALICE_USER_ID")
APP_ID=clean("ALICE_APP_ID")
APP_SECRET=clean("ALICE_APP_SECRET")
@app.route('/')
def home():
    auth_url=f"https://ant.aliceblueonline.com/?appcode={APP_ID}"
    return f"<h1>V50 - FINAL - Browser OAuth Flow ONLY</h1><p>User:{USER_ID} APP:{APP_ID}</p><p><b>SDK Password Flow - DEAD - 500 + 404 - Mooditanga!</b></p><p><a href='{auth_url}'><b>1. CLICK - AliceBlue Website la Login Pannunga</b></a></p><p><a href='/manual'><b>2. MANUAL - AuthCode Paste Pannunga</b></a></p><p><a href='/check'><b>3. CHECK - getAPIEncpkey + getUserDetails - Endpoint Irukka?</b></a></p>"
@app.route('/manual')
def manual():
    return """<h1>MANUAL - AuthCode Paste</h1><p>AliceBlue la login pannina - URL la ?authCode=xxxx nu varum - Adha copy pannunga!</p><form action='/exchange'><input name='authCode' placeholder='AuthCode Inga Paste' style='width:320px'><button>EXCHANGE</button></form><br><a href='/'>Home</a>"""
@app.route('/callback')
def callback():
    code=request.args.get("authCode") or request.args.get("code") or request.args.get("auth_code")
    if not code: return f"<h1>No AuthCode - URL: {request.url}</h1><a href='/'>Home</a>"
    return redirect(f"/exchange?authCode={code}")
@app.route('/check')
def check():
    import requests
    out=["<h1>CHECK - Exchange Endpoints Irukka?</h1>"]
    REST="https://ant.aliceblueonline.com/rest/AliceBlueAPIService"
    for name,url,payload in [
        ("getAPIEncpkey",f"{REST}/customer/getAPIEncpkey",{"userId":USER_ID}),
        ("getEncryptionKey",f"{REST}/customer/getEncryptionKey",{"userId":USER_ID}),
        ("getUserDetails-DUMMY",f"{REST}/sso/getUserDetails",{"checkSum":"dummy","userId":USER_ID}),
        ("authorizeVendor-DUMMY",f"{REST}/sso/authorizeVendor",{"checkSum":"dummy","userId":USER_ID}),
    ]:
        try:
            r=requests.post(url, json=payload, timeout=8)
            txt=(r.text or "")
            out.append(f"<p><b>{name}</b> Status:{r.status_code} Len:{len(txt)} HTML:{'<html' in txt.lower()} Body:{txt[:400].replace('<','&lt;')}</p>")
        except Exception as e: out.append(f"<p>{name} Err:{e}</p>")
    out.append("<p><b>404 illa na - Exchange Flow WORK aagum! 404 na - Pudhu API Docs paakanum!</b></p>")
    return "<br>".join(out)+"<br><a href='/'>Home</a>"
@app.route('/exchange')
def exchange():
    import requests
    code=request.args.get("authCode","").strip()
    out=[f"<h1>EXCHANGE - AuthCode: {code[:25]}...</h1>"]
    if not code or code=="TEST": return "<h1>AuthCode Illa - /manual la paste pannunga!</h1><a href='/'>Home</a>"
    try:
        REST="https://ant.aliceblueonline.com/rest/AliceBlueAPIService"
        # Step 1 - getAPIEncpkey
        r1=requests.post(f"{REST}/customer/getAPIEncpkey", json={"userId":USER_ID}, timeout=10)
        out.append(f"<p>Step1 getAPIEncpkey Status:{r1.status_code} Body:{r1.text[:600]}</p>")
        try: encKey=r1.json().get("encKey")
        except: encKey=None
        # Step 2 - getUserDetails - checksum = SHA256(userId + authCode + api_secret)
        checksum=hashlib.sha256(f"{USER_ID}{code}{APP_SECRET}".encode()).hexdigest()
        out.append(f"<p>Checksum: {checksum[:20]}...</p>")
        r2=requests.post(f"{REST}/sso/getUserDetails", json={"checkSum":checksum,"userId":USER_ID}, timeout=10)
        out.append(f"<p>Step2 getUserDetails Status:{r2.status_code} Body:{r2.text[:1000]}</p>")
        sess=None
        try: sess=r2.json().get("sessionID") or r2.json().get("sessionId")
        except: pass
        out.append(f"<h2>SessionID: {sess}</h2>")
        if sess:
            out.append(f"<h2 style='color:green'>SUCCESS! Session: {sess}</h2>")
            try:
                from alice_blue.alice_blue import AliceBlue
                real=AliceBlue(username=USER_ID, session_id=str(sess))
                prof=real.get_profile()
                out.append(f"<h3>Profile: {str(prof)[:1000]}</h3>")
            except Exception as e: out.append(f"Profile Err: {e} {traceback.format_exc()[:1000]}")
            try:
                real2=AliceBlue(username=USER_ID, session_id=str(sess))
                hold=real2.get_holdings()
                out.append(f"<h3>Holdings: {str(hold)[:1000]}</h3>")
            except Exception as e: out.append(f"Holdings Err: {e}")
        else:
            out.append("<b>Session Illa - AuthCode thappa? Illa AliceBlue Dashboard la Redirect URL set pannala?</b>")
    except Exception as e: out.append(f"Err {e} {traceback.format_exc()[:2000]}")
    return "<br>".join(out)+"<br><a href='/'>Home</a> | <a href='/manual'>Manual</a>"
if __name__=='__main__':
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0', port=port)
