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
@app.route('/')
def home():
    return f"<h1>V35 - __new__ TRICK - FINAL</h1><p>User:{USER_ID} DOB:{DOB_YEAR}</p><p><a href='/login'><b>LOGIN - SDK METHOD via __new__</b></a></p>"
@app.route('/login')
def login():
    out=[]
    try:
        import pyotp
        try: totp_now=pyotp.TOTP(TOTP_SECRET).now() if TOTP_SECRET else None
        except: totp_now=None
        out.append(f"USER:{USER_ID} APP:{APP_ID} DOB:{DOB_YEAR} TOTP:{totp_now}")
        from alice_blue.alice_blue import AliceBlue
        out.append(f"Init Sig: {inspect.signature(AliceBlue.__init__)}")
        out.append(f"Login Sig: {inspect.signature(AliceBlue.login_and_get_sessionID)}")
        for label, tfa in [("DOB",DOB_YEAR),("TOTP",totp_now)]:
            if not tfa: continue
            out.append(f"<b>=== TRY {label}={tfa} ===</b>")
            try:
                # __init__-a skip pannu - Object-a direct-a create pannu
                obj = AliceBlue.__new__(AliceBlue)
                out.append(f"Dummy Obj Created via __new__: {obj}")
                # Ippo login method-a koopdu - SDK-e ella vela-yum seiyum
                sess = obj.login_and_get_sessionID(USER_ID, PASSWORD, str(tfa), APP_ID, APP_SECRET)
                out.append(f"SDK Returned: {str(sess)[:100] if sess else 'NONE'} Type:{type(sess)}")
                if sess and len(str(sess))>10:
                    out.append(f"<h2 style='color:green'>SUCCESS! Session via {label}</h2><p>Full Session: {sess}</p><p>Idha copy pannunga - Adutha step: Order test pannalam</p>")
                    # Session vachu AliceBlue Object create panni profile test pannu
                    try:
                        real = AliceBlue(username=USER_ID, session_id=sess)
                        prof = real.get_profile()
                        out.append(f"<h3>Profile Test: {str(prof)[:800]}</h3>")
                    except Exception as e:
                        out.append(f"Profile Test Err (parava illa, session kidaichiduchu): {e}")
                    return "<br>".join(out) + "<br><a href='/'>Home</a>"
                else:
                    out.append(f"SDK Returned Empty - Full:{sess}")
            except Exception as e:
                out.append(f"Call Err {label}: {e} {traceback.format_exc()[:3000]}")
        out.append("<b>LOGIN FAIL</b>")
    except Exception as e:
        out.append(f"Err {e} {traceback.format_exc()[:3000]}")
    return "<br>".join(out) + "<br><a href='/'>Home</a>"
if __name__=='__main__':
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0', port=port)
