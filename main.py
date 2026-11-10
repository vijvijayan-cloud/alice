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
    return f"<h1>V53 - DIRECT API - No SDK</h1><p>User:{USER_ID}</p><p>Session: {'YES - '+s[:30]+'...' if s else 'ILLA'}</p><p><a href='{auth_url}'><b>1. LOGIN</b></a></p><p><a href='/manual'><b>2. MANUAL - AuthCode</b></a></p><p><a href='/test'><b>3. TEST - Direct API - Profile + Holdings</b></a></p>"
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
    out=[f"<h1>V53 EXCHANGE</h1><p>AuthCode: {code[:25]}...</p>"]
    if not code: return "<h1>AuthCode Illa</h1><a href='/'>Home</a>"
    try:
        REST="https://ant.aliceblueonline.com/rest/AliceBlueAPIService"
        checksum=hashlib.sha256(f"{USER_ID}{code}{APP_SECRET}".encode()).hexdigest()
        r=requests.post(f"{REST}/sso/getUserDetails", json={"checkSum":checksum,"userId":USER_ID}, timeout=10)
        out.append(f"<p>Status:{r.status_code}</p><pre>{r.text[:1500].replace('<','&lt;')}</pre>")
        j=r.json()
        sess=j.get("userSession")
        if sess:
            STORE["session"]=str(sess)
            out.append(f"<h2 style='color:green'>SUCCESS! Session Saved! Len:{len(str(sess))}</h2><p><a href='/test'><b>CLICK - TEST Direct API</b></a></p>")
        else:
            out.append("<b>Session Illa - Pudhu Login pannunga - AuthCode oru thadava thaan!</b>")
    except Exception as e: out.append(f"Err {e} {traceback.format_exc()[:1200]}")
    return "<br>".join(out)+"<br><a href='/'>Home</a>"
@app.route('/test')
def test():
    import requests
    sess=STORE.get("session")
    if not sess: return "<h1>Session Illa - Login pannunga!</h1><a href='/'>Home</a>"
    out=[f"<h1>V53 TEST - DIRECT API</h1><p>Session: {sess[:50]}...</p>"]
    BASE="https://ant.aliceblueonline.com/rest/AliceBlueAPIService"
    # Vera vera Header combination try pannuvom - Edhu work aagudhu nu paappom
    header_sets=[
        ("Bearer", {"Authorization":f"Bearer {sess}", "Content-Type":"application/json", "Accept":"application/json"}),
        ("Session-Header", {"sessionId":sess, "userId":USER_ID, "Content-Type":"application/json"}),
        ("Auth-Token", {"Authorization":sess, "Content-Type":"application/json"}),
        ("X-Session", {"X-Session-Id":sess, "userId":USER_ID, "Content-Type":"application/json"}),
    ]
    # Profile-ku candidate endpoints
    endpoints=[
        ("profile", f"{BASE}/api/profile", {"userId":USER_ID}),
        ("accountDetails", f"{BASE}/api/customer/accountDetails", {"userId":USER_ID}),
        ("getProfile", f"{BASE}/customer/getProfile", {"userId":USER_ID}),
        ("holdings", f"{BASE}/api/positionAndHoldings/holdings", {"userId":USER_ID}),
        ("getHoldings", f"{BASE}/api/holdings", {"userId":USER_ID}),
        ("positions", f"{BASE}/api/positionAndHoldings/positions", {"userId":USER_ID}),
        ("funds", f"{BASE}/api/funds", {"userId":USER_ID}),
        ("limits", f"{BASE}/api/limits", {"userId":USER_ID}),
    ]
    for hname, headers in header_sets:
        out.append(f"<h3>Headers: {hname}</h3>")
        for ename, url, payload in endpoints:
            try:
                # GET try
                r=requests.get(url, headers=headers, params={"userId":USER_ID}, timeout=7)
                txt=(r.text or "")
                is_html="<html" in txt.lower()
                mark="✅" if (r.status_code==200 and not is_html and "Not_Ok" not in txt and "Invalid" not in txt) else "❌"
                out.append(f"<p>{mark} GET {ename} Status:{r.status_code} HTML:{is_html} Body:{txt[:450].replace('<','&lt;')}</p>")
                if mark=="✅":
                    out.append(f"<h2 style='color:green'>FOUND! {ename} with {hname}</h2>")
                # POST try - GET fail aana mattum
                if r.status_code!=200 or is_html:
                    r2=requests.post(url, headers=headers, json=payload, timeout=7)
                    txt2=(r2.text or "")
                    is_html2="<html" in txt2.lower()
                    mark2="✅" if (r2.status_code==200 and not is_html2 and "Not_Ok" not in txt2) else "❌"
                    out.append(f"<p>{mark2} POST {ename} Status:{r2.status_code} Body:{txt2[:450].replace('<','&lt;')}</p>")
                    if mark2=="✅":
                        out.append(f"<h2 style='color:green'>FOUND POST! {ename} with {hname}</h2>")
            except Exception as e:
                out.append(f"<p>❌ {ename} Err:{e}</p>")
        # Oru Header set la FOUND vandha - Adutha set-a skip pannalaam - Aana full-a paappom
        out.append("<hr>")
    return "<br>".join(out)+"<br><a href='/'>Home</a>"
if __name__=='__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT",10000)))
