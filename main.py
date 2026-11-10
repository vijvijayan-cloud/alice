import os, traceback, inspect, json
from flask import Flask
app = Flask(__name__)
def clean(n):
    return os.getenv(n,"").strip().replace('"',"").replace("'","")
USER_ID=clean("ALICE_USER_ID")
PASSWORD=clean("ALICE_PASSWORD")
APP_ID=clean("ALICE_APP_ID")
APP_SECRET=clean("ALICE_APP_SECRET")
DOB_YEAR=clean("ALICE_YEAR") or clean("ALICE_DOB_YEAR") or clean("ALICE_2FA")
TOTP_SECRET=clean("ALICE_TOTP_SECRET")
# Pudhu HOST candidates - Ella host-um try pannuvom
HOSTS=[
  "https://ant.aliceblueonline.com/rest/AliceBlueAPIService",
  "https://ant.aliceblueonline.com",
  "https://ant.aliceblueonline.com/rest",
  "https://api.aliceblueonline.com",
  "https://ant.aliceblueonline.com/api",
  "https://a3.aliceblueonline.com/rest/AliceBlueAPIService",
  "https://ant.aliceblueonline.com/rest/AliceBlueAPI",
]
PATHS=[
  "sso/validAnswer","sso/validateAnswer","sso/validUserDetails",
  "customer/validAnswer","customer/validateAnswer",
  "sso/verifyAnswer","sso/validate2FA","sso/verify2FA",
  "sso/validanswer","sso/ValidAnswer",
  "sso/validAnswer/",
  "AliceBlueAPIService/sso/validAnswer",
]
@app.route('/')
def home():
    return f"<h1>V39 - FIND NEW HOST</h1><p>User:{USER_ID} DOB:{DOB_YEAR}</p><p><a href='/probe2'><b>1. PROBE HOST x PATH - 84 Try (FAST)</b></a></p><p><a href='/weblogin'><b>2. WEBLOGIN FULL RESPONSE - Pudhu URL Irukka Paaru</b></a></p><p><a href='/sdkurls'><b>3. SDK FULL URLs</b></a></p>"
@app.route('/sdkurls')
def sdkurls():
    out=["<h1>SDK FULL URLs + SOURCE</h1>"]
    try:
        import alice_blue.alice_blue as mod
        for name in ["AliceBlue_urls","urls","URLS","base_url","BASE_URL"]:
            if hasattr(mod,name): out.append(f"<b>{name} = {getattr(mod,name)}</b>")
        # Module file la URL maadhiri irukkura ella line-um thedu
        import pathlib
        txt=pathlib.Path(mod.__file__).read_text(errors="ignore")
        for i,line in enumerate(txt.splitlines(),1):
            low=line.lower()
            if "http" in low or "aliceblue" in low or "valid" in low or "twofa" in low or "sso" in low or "ant." in low:
                out.append(f"Line {i}: {line.strip()[:300]}")
    except Exception as e: out.append(f"Err {e} {traceback.format_exc()[:2000]}")
    return "<br>".join(out)+"<br><a href='/'>Home</a>"
@app.route('/weblogin')
def weblogin():
    out=["<h1>WEBLOGIN FULL RESPONSE</h1>"]
    try:
        import alice_blue.alice_blue as mod
        # Spy - WebLogin enna return pannudhu nu paaru
        orig_post=mod.requests.post
        def spy(url,*a,**kw):
            r=orig_post(url,*a,**kw)
            try: body=r.text[:3000]
            except: body="?"
            out.append(f"<p><b>POST {url}</b> Status:{r.status_code}<br>Body:{body}<br>Data:{str(kw.get('data') or kw.get('json'))[:600]}</p>")
            return r
        mod.requests.post=spy
        try:
            obj=mod.AliceBlue.__new__(mod.AliceBlue)
            # WebLogin varaikkum mattum try - twoFA la fail aana parava illa, log already irukkum
            try: sess=obj.login_and_get_sessionID(USER_ID,PASSWORD,str(DOB_YEAR),APP_ID,APP_SECRET)
            except Exception as e: out.append(f"<p>Login End Err (expected): {e}</p>")
        finally: mod.requests.post=orig_post
        out.append("<p><b>WebLogin Body la - Pudhu URL / Token / Next Step irukka paaru! 'questions' ku appuram enna irukku?</b></p>")
    except Exception as e: out.append(f"Err {e} {traceback.format_exc()[:2000]}")
    return "<br>".join(out)+"<br><a href='/'>Home</a>"
@app.route('/probe2')
def probe2():
    import requests
    out=["<h1>PROBE HOST x PATH - 404 Illa Edhu?</h1>"]
    found=[]
    for h in HOSTS:
        for p in PATHS:
            full=f"{h}/{p}"
            try:
                r=requests.post(full, json={"userId":USER_ID,"answer":DOB_YEAR}, timeout=6)
                if r.status_code!=404:
                    found.append(full)
                    out.append(f"<p style='color:green'><b>✅ {full} Status:{r.status_code} Body:{(r.text or '')[:300]}</b></p>")
            except Exception as e:
                pass
    if not found:
        out.append("<p><b>Ella 84-um 404 / fail - Host vera edathula irukku! /weblogin + /sdkurls paaru!</b></p>")
    else:
        out.append(f"<p><b>FOUND: {found}</b></p>")
    return "<br>".join(out)+"<br><a href='/'>Home</a>"
if __name__=='__main__':
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0', port=port)
