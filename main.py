import os, traceback, inspect
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
HOST="https://ant.aliceblueonline.com/rest/AliceBlueAPIService"
# twoFA ku possible ella URL-um - Oru URL work aana podhum!
CANDIDATES=[
  "sso/validAnswer",
  "sso/validateAnswer",
  "sso/validUserDetails",
  "sso/verifyAnswer",
  "sso/checkAnswer",
  "customer/validAnswer",
  "customer/validateAnswer",
  "customer/validUserDetails",
  "sso/validanswer",
  "sso/validate2FA",
  "sso/verify2FA",
  "customer/verifyAnswer",
]
@app.route('/')
def home():
    return f"<h1>V37 - FIND CORRECT twoFA URL</h1><p>User:{USER_ID} DOB:{DOB_YEAR}</p><p><a href='/login'><b>TRY ALL twoFA URLs</b></a></p>"
@app.route('/login')
def login():
    out=[]
    try:
        import pyotp
        try: totp_now=pyotp.TOTP(TOTP_SECRET).now() if TOTP_SECRET else None
        except: totp_now=None
        out.append(f"USER:{USER_ID} APP:{APP_ID} DOB:{DOB_YEAR} TOTP:{totp_now}")
        import alice_blue.alice_blue as mod
        orig_urls=dict(mod.AliceBlue_urls) if hasattr(mod,"AliceBlue_urls") else {}
        out.append(f"Original SDK URLs: {orig_urls}")
        # TOTP-a kooda try pannuvom - DOB + TOTP
        tfas=[("DOB",DOB_YEAR)]
        if totp_now: tfas.append(("TOTP",totp_now))
        for cand in CANDIDATES:
            full=f"{HOST}/{cand}"
            out.append(f"<b>=== CANDIDATE: {cand} ===</b>")
            # SDK URLs-a patch pannu
            try:
                mod.AliceBlue_urls['twoFA']=full
                # AliceBlue class la vera dict irundha adhayum patch pannu
                if hasattr(mod.AliceBlue,"AliceBlue_urls"):
                    try: mod.AliceBlue.AliceBlue_urls['twoFA']=full
                    except: pass
            except Exception as e:
                out.append(f"Patch fail {e}")
            for label, tfa in tfas:
                if not tfa: continue
                try:
                    obj = mod.AliceBlue.__new__(mod.AliceBlue)
                    sess = obj.login_and_get_sessionID(USER_ID, PASSWORD, str(tfa), APP_ID, APP_SECRET)
                    out.append(f"  {label}={tfa} -> Returned: {str(sess)[:80] if sess else 'NONE'}")
                    if sess and len(str(sess))>10:
                        out.append(f"<h2 style='color:green'>SUCCESS! Correct twoFA URL = {full} via {label}</h2><p>Full Session: {sess}</p>")
                        try:
                            real = mod.AliceBlue(username=USER_ID, session_id=sess)
                            prof = real.get_profile()
                            out.append(f"<h3>Profile: {str(prof)[:800]}</h3>")
                        except Exception as e:
                            out.append(f"Profile Err (parava illa): {e}")
                        return "<br>".join(out) + "<br><a href='/'>Home</a>"
                except Exception as e:
                    msg=str(e)[:300]
                    out.append(f"  {label} -> Fail: {msg}")
                    # 404-a illa vera error-a nu paaru - 404 illa na, URL correct-a irukkalam, 2FA thappu-nu artham
                    if "404" not in msg and "Expecting value" not in msg and "Not Found" not in msg:
                        out.append(f"  *** {cand} - 404 ILLA! Vera error - Idhu correct URL-a irukkalam! Full: {traceback.format_exc()[:1500]}")
        # Original-a restore pannu
        try: mod.AliceBlue_urls.update(orig_urls)
        except: pass
        out.append("<b>LOGIN FAIL - Ella candidate-um 404 / fail</b><p>Idhu vandha, twoFA URL vera host-la irukku nu artham - Adutha step: Host-a theduvom</p>")
    except Exception as e:
        out.append(f"Err {e} {traceback.format_exc()[:3000]}")
    return "<br>".join(out) + "<br><a href='/'>Home</a>"
if __name__=='__main__':
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0', port=port)
