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
    return f"<h1>V34 - CLASS METHOD</h1><p>User:{USER_ID} DOB:{DOB_YEAR}</p><p><a href='/list'><b>1. METHOD SOURCE</b></a></p><p><a href='/login'><b>2. LOGIN - CLASS METHOD</b></a></p>"
@app.route('/list')
def list_funcs():
    out=[]
    try:
        from alice_blue.alice_blue import AliceBlue
        out.append(f"<h3>AliceBlue.__init__ Signature: {inspect.signature(AliceBlue.__init__)}</h3>")
        try: out.append(f"<pre>INIT SOURCE:\n{inspect.getsource(AliceBlue.__init__)[:4000]}</pre>")
        except Exception as e: out.append(f"Init source fail {e}")
        out.append(f"<h3>login_and_get_sessionID Signature: {inspect.signature(AliceBlue.login_and_get_sessionID)}</h3>")
        try: out.append(f"<pre>LOGIN SOURCE:\n{inspect.getsource(AliceBlue.login_and_get_sessionID)[:6000]}</pre>")
        except Exception as e: out.append(f"Login source fail {e}")
    except Exception as e:
        out.append(f"Err {e} {traceback.format_exc()[:3000]}")
    return "<br>".join(out) + "<br><a href='/'>Home</a> | <a href='/login'>Login</a>"
@app.route('/login')
def login():
    out=[]
    try:
        import pyotp
        try: totp_now=pyotp.TOTP(TOTP_SECRET).now() if TOTP_SECRET else None
        except: totp_now=None
        out.append(f"USER:{USER_ID} APP:{APP_ID} DOB:{DOB_YEAR} TOTP:{totp_now}")
        from alice_blue.alice_blue import AliceBlue
        out.append(f"AliceBlue Init Sig: {inspect.signature(AliceBlue.__init__)}")
        out.append(f"Login Method Sig: {inspect.signature(AliceBlue.login_and_get_sessionID)}")
        for label, tfa in [("DOB",DOB_YEAR),("TOTP",totp_now)]:
            if not tfa: continue
            out.append(f"<b>=== TRY {label}={tfa} ===</b>")
            # Pattern 1: Object create panni method-a koopdu - SDK docs maadhiri
            # AliceBlue(username, password, api_secret, ...) - ella pattern-um try
            attempts=[]
            try:
                obj=AliceBlue(username=USER_ID, password=PASSWORD, api_secret=APP_SECRET)
                attempts.append(("kw username/password/api_secret", obj))
            except Exception as e: out.append(f"Init kw1 fail {e}")
            try:
                obj=AliceBlue(USER_ID, PASSWORD, APP_SECRET)
                attempts.append(("pos USER/PASS/SECRET", obj))
            except Exception as e: out.append(f"Init pos fail {e}")
            try:
                obj=AliceBlue()
                attempts.append(("no-arg", obj))
            except Exception as e: out.append(f"Init no-arg fail {e}")
            for aname, obj in attempts:
                out.append(f"-- Attempt Object: {aname} Obj:{obj} --")
                try:
                    # Method signature-a paathu call pannu - 5 arg / self mattum?
                    sess=None
                    try:
                        sess=obj.login_and_get_sessionID(USER_ID, PASSWORD, str(tfa), APP_ID, APP_SECRET)
                    except TypeError as te:
                        out.append(f"5-arg fail {te} - try (tfa, app_id, secret)")
                        try: sess=obj.login_and_get_sessionID(str(tfa), APP_ID, APP_SECRET)
                        except TypeError as te2:
                            out.append(f"3-arg fail {te2} - try no-arg")
                            sess=obj.login_and_get_sessionID()
                    out.append(f"Returned: {str(sess)[:80] if sess else 'NONE'}")
                    # Object la session attribute irukka paaru
                    for attr in ["session_id","sessionID","userSession","session"]:
                        if hasattr(obj, attr):
                            out.append(f"Obj.{attr} = {str(getattr(obj,attr))[:60]}")
                    if sess and len(str(sess))>10:
                        out.append(f"<h2 style='color:green'>SUCCESS via {label} - {aname}</h2><p>Full: {sess}</p>")
                        return "<br>".join(out) + "<br><a href='/'>Home</a>"
                    # Session object la irundhalum success
                    for attr in ["session_id","sessionID"]:
                        v=getattr(obj,attr,None)
                        if v and len(str(v))>10:
                            out.append(f"<h2 style='color:green'>SUCCESS via Obj.{attr} {label}</h2><p>Full: {v}</p>")
                            return "<br>".join(out) + "<br><a href='/'>Home</a>"
                except Exception as e:
                    out.append(f"Call Err {aname}: {e} {traceback.format_exc()[:2500]}")
        out.append("<b>LOGIN FAIL</b>")
    except Exception as e:
        out.append(f"Err {e} {traceback.format_exc()[:3000]}")
    return "<br>".join(out) + "<br><a href='/'>Home</a>"
if __name__=='__main__':
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0', port=port)
