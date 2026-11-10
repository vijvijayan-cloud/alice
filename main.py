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
    return f"<h1>V33 - LIST SDK FUNCTIONS</h1><p>User:{USER_ID} DOB:{DOB_YEAR}</p><p><a href='/list'><b>1. LIST FUNCTIONS</b></a></p><p><a href='/login'><b>2. LOGIN - Correct Name</b></a></p>"
@app.route('/list')
def list_funcs():
    out=[]
    try:
        import alice_blue.alice_blue as m
        out.append(f"Module File: {m.__file__}")
        out.append(f"<h3>ALL Names in Module:</h3>")
        for name in sorted(dir(m)):
            if name.startswith("_"): continue
            out.append(f"{name}")
        out.append(f"<h3>Login/Session Functions:</h3>")
        for name in sorted(dir(m)):
            low=name.lower()
            if "login" in low or "session" in low or "auth" in low or "encrypt" in low or "two" in low or "valid" in low:
                obj=getattr(m,name)
                out.append(f"<b>{name}</b> Type:{type(obj)}")
                try:
                    out.append(f"<pre>{inspect.getsource(obj)[:3000]}</pre>")
                except Exception as e:
                    out.append(f"Source fail {e} - Doc:{getattr(obj,'__doc__','')}")
        # AliceBlue class-um paaru
        AB=getattr(m,"AliceBlue",None)
        if AB:
            out.append(f"<h3>AliceBlue Class Methods:</h3>")
            for name in sorted(dir(AB)):
                if name.startswith("_"): continue
                out.append(f"Method: {name}")
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
        import alice_blue.alice_blue as m
        # Correct function-a kandupidi - peru enna va irundhalum
        fn=None; fn_name=""
        for cand in ["login_and_get_sessionID","login_and_get_sessionId","login_and_get_session_id","get_sessionID","get_session_id","login_and_get_session","login","getSessionID"]:
            if hasattr(m,cand):
                fn=getattr(m,cand); fn_name=cand; break
        # Illana - login nu irukkura edha function-um edhu
        if not fn:
            for name in dir(m):
                if "login" in name.lower() and "session" in name.lower():
                    fn=getattr(m,name); fn_name=name; break
        out.append(f"Found Function: {fn_name} = {fn}")
        if not fn:
            out.append("Function Illa - /list paaru"); return "<br>".join(out)
        try:
            out.append(f"Signature: {inspect.signature(fn)}")
        except: pass
        for label, tfa in [("DOB",DOB_YEAR),("TOTP",totp_now)]:
            if not tfa: continue
            out.append(f"<b>=== TRY {label}={tfa} via {fn_name} ===</b>")
            try:
                # Ella signature-kum try - 5 arg, 4 arg, 3 arg
                sess=None
                try:
                    sess=fn(USER_ID, PASSWORD, str(tfa), APP_ID, APP_SECRET)
                except TypeError as te:
                    out.append(f"5-arg fail {te} - 4-arg try")
                    try: sess=fn(USER_ID, PASSWORD, str(tfa), APP_ID)
                    except TypeError as te2:
                        out.append(f"4-arg fail {te2} - 3-arg try")
                        sess=fn(USER_ID, PASSWORD, str(tfa))
                out.append(f"Returned: {str(sess)[:60] if sess else 'NONE'}")
                if sess and len(str(sess))>10:
                    out.append(f"<h2 style='color:green'>SUCCESS via {label}</h2><p>Full: {sess}</p>")
                    return "<br>".join(out) + "<br><a href='/'>Home</a>"
            except Exception as e:
                out.append(f"Call Err {label}: {e} {traceback.format_exc()[:2500]}")
        out.append("<b>LOGIN FAIL</b>")
    except Exception as e:
        out.append(f"Err {e} {traceback.format_exc()[:3000]}")
    return "<br>".join(out) + "<br><a href='/'>Home</a>"
if __name__=='__main__':
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0', port=port)
