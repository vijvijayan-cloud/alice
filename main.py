import os, traceback
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
    return f"<h1>V32 - SDK DIRECT</h1><p>User:{USER_ID} DOB:{DOB_YEAR}</p><p><a href='/login'><b>LOGIN - SDK FUNCTION DIRECT</b></a></p>"
@app.route('/login')
def login():
    out=[]
    try:
        import pyotp
        try: totp_now=pyotp.TOTP(TOTP_SECRET).now() if TOTP_SECRET else None
        except: totp_now=None
        out.append(f"USER:{USER_ID} APP:{APP_ID} DOB:{DOB_YEAR} TOTP:{totp_now}")
        # SDK MODULE-a direct-a import pannu - PACKAGE illa!
        from alice_blue.alice_blue import login_and_get_sessionID
        out.append(f"SDK Function Found: {login_and_get_sessionID}")
        for label, tfa in [("DOB",DOB_YEAR),("TOTP",totp_now)]:
            if not tfa: continue
            out.append(f"<b>=== SDK DIRECT TRY {label}={tfa} ===</b>")
            try:
                # SDK signature: login_and_get_sessionID(username, password, twoFA, app_id, api_secret)
                sess = login_and_get_sessionID(USER_ID, PASSWORD, str(tfa), APP_ID, APP_SECRET)
                out.append(f"SDK Returned: {str(sess)[:50] if sess else 'NONE'} Type:{type(sess)}")
                if sess and len(str(sess))>10:
                    out.append(f"<h2 style='color:green'>SUCCESS! Session via {label}</h2><p>Full Session: {sess}</p>")
                    return "<br>".join(out) + "<br><a href='/'>Home</a>"
                else:
                    out.append(f"SDK Returned Empty/None - Full:{sess}")
            except Exception as e:
                out.append(f"SDK Function Err {label}: {e} {traceback.format_exc()[:3000]}")
        out.append("<b>LOGIN FAIL - SDK Direct-um fail</b>")
    except Exception as e:
        out.append(f"Import Err {e} {traceback.format_exc()[:3000]}")
    return "<br>".join(out) + "<br><a href='/'>Home</a>"
if __name__=='__main__':
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0', port=port)
