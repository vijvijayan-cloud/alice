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
LOGS=[]
@app.route('/')
def home():
    return f"<h1>V36 - SPY SDK CALLS</h1><p>User:{USER_ID} DOB:{DOB_YEAR}</p><p><a href='/login'><b>LOGIN - SPY</b></a></p>"
@app.route('/login')
def login():
    out=[]; LOGS.clear()
    try:
        import pyotp
        try: totp_now=pyotp.TOTP(TOTP_SECRET).now() if TOTP_SECRET else None
        except: totp_now=None
        out.append(f"USER:{USER_ID} APP:{APP_ID} DOB:{DOB_YEAR} TOTP:{totp_now}")
        import alice_blue.alice_blue as mod
        # 1. SDK Login Method Source-a full-a kaatu - Line 180-250
        try:
            src=inspect.getsource(mod.AliceBlue.login_and_get_sessionID)
            out.append(f"<h3>LOGIN METHOD FULL SOURCE:</h3><pre>{src[:7000]}</pre>")
        except Exception as e: out.append(f"Source fail {e}")
        # 2. SPY - SDK enna URL-a koopduvudhu nu paakkanum - requests.post-a intercept pannu
        orig_post = mod.requests.post
        orig_get = mod.requests.get
        def spy_post(url, *a, **kw):
            r = orig_post(url, *a, **kw)
            txt = ""
            try: txt = r.text[:800]
            except: txt = "<no text>"
            LOGS.append(f"<b>POST {url}</b> Status:{r.status_code} Body:{txt} Kw-Keys:{list(kw.keys())} Data:{str(kw.get('data') or kw.get('json'))[:300]}")
            return r
        def spy_get(url, *a, **kw):
            r = orig_get(url, *a, **kw)
            txt=""
            try: txt=r.text[:500]
            except: pass
            LOGS.append(f"<b>GET {url}</b> Status:{r.status_code} Body:{txt}")
            return r
        mod.requests.post = spy_post
        mod.requests.get = spy_get
        # 3. SDK Method-a koopdu - Spy log pannum
        for label, tfa in [("DOB",DOB_YEAR)]:
            if not tfa: continue
            out.append(f"<b>=== TRY {label}={tfa} - SPY ON ===</b>")
            try:
                obj = mod.AliceBlue.__new__(mod.AliceBlue)
                sess = obj.login_and_get_sessionID(USER_ID, PASSWORD, str(tfa), APP_ID, APP_SECRET)
                out.append(f"Returned: {str(sess)[:100] if sess else 'NONE'}")
                if sess and len(str(sess))>10:
                    out.append(f"<h2 style='color:green'>SUCCESS via {label}</h2><p>Full: {sess}</p>")
            except Exception as e:
                out.append(f"Call Err {label}: {e}")
                out.append(f"<pre>{traceback.format_exc()[:3000]}</pre>")
        mod.requests.post = orig_post
        mod.requests.get = orig_get
        out.append(f"<h2>SPY LOG - SDK Enna URL-a Koopduchunu Paaru:</h2>")
        for l in LOGS:
            out.append(l)
        out.append("<b>Idhula paaru - Edha URL la Status 404 / Empty Body vandhuchu nu - Adhu thaan thappu URL!</b>")
    except Exception as e:
        out.append(f"Err {e} {traceback.format_exc()[:3000]}")
    return "<br>".join(out) + "<br><a href='/'>Home</a>"
if __name__=='__main__':
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0', port=port)
