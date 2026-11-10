import os, traceback, inspect, subprocess, sys
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
    return f"<h1>V40 - NEW SDK - ACCESS TOKEN</h1><p>User:{USER_ID} DOB:{DOB_YEAR}</p><p><a href='/upgrade'><b>1. UPGRADE SDK + LIST NEW URLs</b></a></p><p><a href='/login'><b>2. LOGIN - login_and_get_access_token</b></a></p>"
@app.route('/upgrade')
def upgrade():
    out=["<h1>UPGRADE SDK</h1>"]
    try:
        r=subprocess.run([sys.executable,"-m","pip","install","--upgrade","alice-blue"], capture_output=True, text=True, timeout=120)
        out.append(f"<pre>{(r.stdout or '')[-1500:]}\n{(r.stderr or '')[-500:]}</pre>")
    except Exception as e: out.append(f"Pip Err {e}")
    try:
        import importlib, alice_blue.alice_blue as mod
        importlib.reload(mod)
        out.append(f"Module File: {mod.__file__}")
        try:
            import alice_blue; out.append(f"Version: {getattr(alice_blue,'__version__','?')}")
        except: pass
        for name in sorted(dir(mod.AliceBlue)):
            if "login" in name.lower() or "access" in name.lower() or "token" in name.lower():
                out.append(f"<b>Method: {name} Sig:{inspect.signature(getattr(mod.AliceBlue,name))}</b>")
        # Pudhu URLs
        import pathlib
        txt=pathlib.Path(mod.__file__).read_text(errors="ignore")
        for i,line in enumerate(txt.splitlines(),1):
            low=line.lower()
            if "http" in low or "aliceblue" in low or "valid" in low or "twofa" in low or "sso" in low or "token" in low:
                out.append(f"Line {i}: {line.strip()[:350]}")
    except Exception as e: out.append(f"Err {e} {traceback.format_exc()[:2500]}")
    return "<br>".join(out)+"<br><a href='/'>Home</a> | <a href='/login'>Login</a>"
@app.route('/login')
def login():
    out=[]
    try:
        import pyotp
        try: totp_now=pyotp.TOTP(TOTP_SECRET).now() if TOTP_SECRET else None
        except: totp_now=None
        out.append(f"USER:{USER_ID} APP:{APP_ID} DOB:{DOB_YEAR} TOTP:{totp_now}")
        import alice_blue.alice_blue as mod
        fn=None; fn_name=""
        for cand in ["login_and_get_access_token","login_and_get_sessionID","login_and_get_session_id"]:
            if hasattr(mod.AliceBlue,cand): fn=getattr(mod.AliceBlue,cand); fn_name=cand; break
        out.append(f"Function: {fn_name} = {fn}")
        if not fn: return "<br>".join(out)
        try: out.append(f"Sig: {inspect.signature(fn)}")
        except: pass
        for label,tfa in [("DOB",DOB_YEAR),("TOTP",totp_now)]:
            if not tfa: continue
            out.append(f"<b>=== TRY {label}={tfa} via {fn_name} ===</b>")
            try:
                # Pudhu SDK - Keyword args la koopdu - PyPI docs maadhiri
                token=None
                try:
                    token=fn(username=USER_ID, password=PASSWORD, twoFA=str(tfa), api_secret=APP_SECRET, app_id=APP_ID)
                except TypeError as te:
                    out.append(f"kw 5-arg fail {te} - kw 4-arg try")
                    try: token=fn(username=USER_ID, password=PASSWORD, twoFA=str(tfa), api_secret=APP_SECRET)
                    except TypeError as te2:
                        out.append(f"kw 4-arg fail {te2} - positional try")
                        token=fn(USER_ID, PASSWORD, str(tfa), APP_ID, APP_SECRET)
                out.append(f"Returned: {str(token)[:120] if token else 'NONE'}")
                if token and len(str(token))>10:
                    out.append(f"<h2 style='color:green'>SUCCESS! Access Token via {label}</h2><p>Full: {token}</p>")
                    try:
                        # Pudhu Object: AliceBlue(username, password, access_token=token)
                        real=mod.AliceBlue(username=USER_ID, password=PASSWORD, access_token=str(token))
                        prof=real.get_profile()
                        out.append(f"<h3>Profile: {str(prof)[:800]}</h3>")
                    except Exception as e: out.append(f"Profile try Err: {e} - Token kidaichiduchu, adhu podhum!")
                    return "<br>".join(out)+"<br><a href='/'>Home</a>"
            except Exception as e:
                out.append(f"Call Err {label}: {e} {traceback.format_exc()[:2500]}")
        out.append("<b>LOGIN FAIL</b>")
    except Exception as e: out.append(f"Err {e} {traceback.format_exc()[:2500]}")
    return "<br>".join(out)+"<br><a href='/'>Home</a>"
if __name__=='__main__':
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0', port=port)
