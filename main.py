import os, traceback, inspect
from flask import Flask
import requests, json
app = Flask(__name__)
def clean(n):
    return os.getenv(n,"").strip().replace('"',"").replace("'","")
USER_ID=clean("ALICE_USER_ID")
PASSWORD=clean("ALICE_PASSWORD")
APP_ID=clean("ALICE_APP_ID")
APP_SECRET=clean("ALICE_APP_SECRET")
@app.route('/')
def home():
    return f"<h1>V27 MINI OK</h1><p>User:{USER_ID}</p><p><a href='/inspect-sdk'>INSPECT SDK</a> | <a href='/test'>TEST</a></p>"
@app.route('/inspect-sdk')
def inspect_sdk():
    out=[]
    try:
        import alice_blue as mod
        out.append(f"SDK File: {mod.__file__}")
        for fname in ["login_and_get_sessionID","login","get_session_id"]:
            fn=getattr(mod, fname, None)
            if fn:
                try:
                    src=inspect.getsource(fn)
                    out.append(f"<h3>{fname}</h3><pre>{src[:6000]}</pre>")
                except Exception as e:
                    out.append(f"{fname} fail {e}")
        AB=getattr(mod,"AliceBlue",None)
        if AB:
            out.append(f"AliceBlue class: {AB}")
            for m in dir(AB):
                if "login" in m.lower() or "session" in m.lower() or "encrypt" in m.lower():
                    out.append(f"Method: {m}")
                    try:
                        out.append(f"<pre>{inspect.getsource(getattr(AB,m))[:4000]}</pre>")
                    except Exception as e:
                        out.append(f"fail {e}")
    except Exception as e:
        out.append(f"Fail: {e} {traceback.format_exc()[:2000]}")
    return "<br>".join(out) + "<br><a href='/'>Home</a>"
@app.route('/test')
def test():
    out=[]
    try:
        r=requests.post("https://ant.aliceblueonline.com/rest/AliceBlueAPIService/sso/getEncryptionKey", json={"userId":USER_ID}, timeout=20)
        out.append(f"STEP1 Status:{r.status_code} Body:{r.text[:600]}")
    except Exception as e:
        out.append(f"STEP1 Fail:{e}")
    return "<br>".join(out) + "<br><a href='/'>Home</a>"
if __name__=='__main__':
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0', port=port)
