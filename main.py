import os, traceback, inspect
from flask import Flask, request
app = Flask(__name__)
def clean(n):
    return os.getenv(n,"").strip().replace('"',"").replace("'","")
USER_ID=clean("ALICE_USER_ID")
PASSWORD=clean("ALICE_PASSWORD")
APP_ID=clean("ALICE_APP_ID")
APP_SECRET=clean("ALICE_APP_SECRET")
DOB_YEAR=clean("ALICE_YEAR") or clean("ALICE_DOB_YEAR") or clean("ALICE_2FA")
TOTP_SECRET=clean("ALICE_TOTP_SECRET")
HOST="https://ant.aliceblueonline.com/rest/AliceBlueAPIService"
CANDIDATES=[
  "sso/validAnswer",
  "sso/validateAnswer",
  "sso/validUserDetails",
  "sso/verifyAnswer",
  "sso/checkAnswer",
  "customer/validAnswer",
  "customer/validateAnswer",
  "customer/validUserDetails",
  "sso/validate2FA",
  "sso/verify2FA",
  "customer/verifyAnswer",
  "sso/validanswer",
]
@app.route('/')
def home():
    h=f"<h1>V38 - FAST - Oru Click Oru URL</h1><p>User:{USER_ID} DOB:{DOB_YEAR}</p>"
    h+="<p><a href='/probe'><b>STEP 1: PROBE ALL - Edhu 404 Illa nu Paaru (FAST 10 sec)</b></a></p>"
    h+="<h3>STEP 2: Oru Oru URL-a Click Pannu - Login Try Pannu:</h3>"
    for i,c in enumerate(CANDIDATES):
        h+=f"<p><a href='/try/{i}'><b>{i+1}. LOGIN via {c}</b></a></p>"
    return h
@app.route('/probe')
def probe():
    import requests
    out=["<h1>PROBE - Edha URL 404 Illa?</h1>"]
    for c in CANDIDATES:
        full=f"{HOST}/{c}"
        try:
            # Dummy POST - Status mattum paakkanum - 404-a illa 200/400/500-a nu
            r=requests.post(full, json={"userId":USER_ID,"answer":DOB_YEAR}, timeout=8)
            body=(r.text or "")[:250].replace("<","&lt;")
            flag="✅ 404 ILLA - Idhu Correct-a Irukkalam!" if r.status_code!=404 else "❌ 404"
            out.append(f"<p><b>{c}</b> Status:{r.status_code} {flag}<br>Body:{body}</p>")
        except Exception as e:
            out.append(f"<p><b>{c}</b> Err:{e}</p>")
    out.append("<p><b>404 ILLA nu vandha URL thaan correct URL! Adha /try la click pannu!</b></p><a href='/'>Home</a>")
    return "<br>".join(out)
@app.route('/try/<int:idx>')
def try_one(idx):
    out=[]
    try:
        import pyotp
        try: totp_now=pyotp.TOTP(TOTP_SECRET).now() if TOTP_SECRET else None
        except: totp_now=None
        cand=CANDIDATES[idx]; full=f"{HOST}/{cand}"
        out.append(f"<h1>TRY {cand}</h1><p>Full: {full}</p><p>DOB:{DOB_YEAR} TOTP:{totp_now}</p>")
        import alice_blue.alice_blue as mod
        try: mod.AliceBlue_urls['twoFA']=full
        except: pass
        try:
            if hasattr(mod.AliceBlue,"AliceBlue_urls"): mod.AliceBlue.AliceBlue_urls['twoFA']=full
        except: pass
        for label, tfa in [("DOB",DOB_YEAR),("TOTP",totp_now)]:
            if not tfa: continue
            out.append(f"<b>--- {label}={tfa} ---</b>")
            try:
                obj = mod.AliceBlue.__new__(mod.AliceBlue)
                sess = obj.login_and_get_sessionID(USER_ID, PASSWORD, str(tfa), APP_ID, APP_SECRET)
                out.append(f"Returned: {str(sess)[:100] if sess else 'NONE'}")
                if sess and len(str(sess))>10:
                    out.append(f"<h2 style='color:green'>SUCCESS! Correct URL={full} via {label}</h2><p>Full Session: {sess}</p>")
                    try:
                        real = mod.AliceBlue(username=USER_ID, session_id=sess)
                        prof = real.get_profile()
                        out.append(f"<h3>Profile: {str(prof)[:800]}</h3>")
                    except Exception as e: out.append(f"Profile Err (parava illa): {e}")
                    return "<br>".join(out) + "<br><a href='/'>Home</a>"
            except Exception as e:
                out.append(f"Fail {label}: {str(e)[:400]}")
        out.append("<b>Idhu fail - Adutha URL-a Home la click pannu</b>")
    except Exception as e:
        out.append(f"Err {e} {traceback.format_exc()[:2000]}")
    return "<br>".join(out) + "<br><a href='/'>Home</a>"
if __name__=='__main__':
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0', port=port)
