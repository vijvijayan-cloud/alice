import os, traceback, hashlib, json
from flask import Flask
import requests
from urllib.parse import urlparse, parse_qs
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
    return f"<h1>V29 MINI - FIND URLS</h1><p>User:{USER_ID} DOB:{DOB_YEAR}</p><p><a href='/urls'>1. FIND URLS FILE</a></p><p><a href='/login'>2. LOGIN</a></p>"
@app.route('/urls')
def urls():
    out=[]
    try:
        import alice_blue as mod
        base=os.path.dirname(mod.__file__)
        out.append(f"Package Dir: {base}")
        out.append(f"Files: {os.listdir(base)}")
        # Ella .py file-layum AliceBlue_urls thedu - 1 file thaan
        for root, dirs, files in os.walk(base):
            for f in files:
                if not f.endswith(".py"): continue
                fp=os.path.join(root,f)
                try:
                    txt=open(fp, errors="ignore").read()
                    if "AliceBlue_urls" in txt or "twoFA" in txt:
                        out.append(f"<h3>FOUND IN: {f} - {fp}</h3>")
                        for i,line in enumerate(txt.splitlines()):
                            if "AliceBlue_urls" in line or "twoFA" in line or "getEncKey" in line or "webLogin" in line or "apiEncKey" in line or "sessionID" in line or "authorizeVendor" in line or "http" in line:
                                out.append(f"{f}:{i+1}: {line.strip()[:500]}")
                except Exception as e:
                    out.append(f"Read {f} fail {e}")
        # Direct import try
        for modname in ["alice_blue.constants","alice_blue.urls","alice_blue.config","alice_blue.utils"]:
            try:
                m2=__import__(modname, fromlist=["*"])
                out.append(f"<h3>Module {modname} OK - dir: {[x for x in dir(m2) if 'url' in x.lower() or 'Alice' in x]}</h3>")
                for attr in dir(m2):
                    if "url" in attr.lower() or "Alice" in attr:
                        try: out.append(f"{modname}.{attr} = {getattr(m2,attr)}")
                        except: pass
            except Exception as e:
                out.append(f"Module {modname} fail: {e}")
    except Exception as e:
        out.append(f"Fail {e} {traceback.format_exc()[:3000]}")
    return "<br>".join(out) + "<br><a href='/'>Home</a> | <a href='/login'>Login</a>"
def get_urls():
    import alice_blue as mod
    base=os.path.dirname(mod.__file__)
    # File-la irundhu urls-a edhu
    for root, dirs, files in os.walk(base):
        for f in files:
            if f.endswith(".py"):
                try:
                    txt=open(os.path.join(root,f), errors="ignore").read()
                    if "AliceBlue_urls" in txt and "=" in txt:
                        # dict-a exec panni edhu
                        ns={}
                        try:
                            # AliceBlue_urls = { ... } block-a mattum exec pannu
                            start=txt.find("AliceBlue_urls")
                            # = ku apparam { la irundhu } varaikkum
                            eq=txt.find("=", start)
                            brace=txt.find("{", eq)
                            # matching } kandu pidikkuradhu kashtam - simple-a full file exec vendam, import try pannu
                            pass
                        except: pass
                except: pass
    # Import vazhiya try
    for modname in ["alice_blue.constants","alice_blue.urls","alice_blue.config"]:
        try:
            m2=__import__(modname, fromlist=["*"])
            for attr in dir(m2):
                if attr=="AliceBlue_urls":
                    return getattr(m2,attr)
        except: pass
    # mod la irundha?
    v=getattr(mod,"AliceBlue_urls",None)
    if v: return v
    AB=getattr(mod,"AliceBlue",None)
    if AB:
        v=getattr(AB,"AliceBlue_urls",None)
        if v: return v
    return {}
@app.route('/login')
def login():
    out=[]
    try:
        import alice_blue as mod
        import pyotp
        urls_dict=get_urls()
        out.append(f"URLS: {urls_dict}")
        if not urls_dict:
            out.append("<h3>URLS Empty - /urls paaru, enga file-la irukku nu theriyum</h3>")
            return "<br>".join(out) + "<br><a href='/urls'>URLs</a> | <a href='/'>Home</a>"
        try: totp_now=pyotp.TOTP(TOTP_SECRET).now() if TOTP_SECRET else None
        except: totp_now=None
        out.append(f"USER:{USER_ID} APP:{APP_ID} DOB:{DOB_YEAR} TOTP:{totp_now}")
        header={"Content-Type":"application/json"}
        for label, tfa in [("DOB",DOB_YEAR),("TOTP",totp_now)]:
            if not tfa: continue
            out.append(f"<b>=== TRY {label}={tfa} ===</b>")
            r=requests.post(urls_dict['getEncKey'], headers=header, json={"userId":USER_ID}, timeout=20)
            out.append(f"STEP1 Status:{r.status_code} Body:{r.text[:600]}")
            if r.status_code!=200: continue
            encKey=r.json()['encKey']
            out.append(f"encKey OK:{encKey[:10]}***")
            try:
                CryptoJS=getattr(mod,"CryptoJS",None)
                checksum=CryptoJS.AES.encrypt(PASSWORD.encode(), encKey.encode()).decode("utf-8")
            except Exception as e:
                out.append(f"AES Fail {e}"); continue
            out.append(f"AES OK:{checksum[:30]}")
            r=requests.post(urls_dict['webLogin'], headers=header, json={"userId":USER_ID,"userData":checksum}, timeout=20)
            out.append(f"STEP2 webLogin Status:{r.status_code} Body:{r.text[:800]}")
            data={"answer":str(tfa),"count":"1","sIndex":"1","userId":USER_ID,"vendor":APP_ID}
            r=requests.post(urls_dict['twoFA'], headers=header, json=data, timeout=20)
            out.append(f"STEP3 twoFA URL:{urls_dict['twoFA']} Status:{r.status_code} Body:{r.text[:1000]}")
            if r.status_code!=200: continue
            j=r.json(); isAuth=j.get("isAuthorized")
            out.append(f"isAuthorized:{isAuth}")
            if not isAuth: continue
            authCode=parse_qs(urlparse(j['redirectUrl']).query)['authCode'][0]
            out.append(f"authCode OK:{authCode[:12]}***")
            r=requests.post(urls_dict['apiEncKey'], headers=header, data=json.dumps({"userId":USER_ID}), timeout=20)
            out.append(f"STEP4 apiEncKey Status:{r.status_code} Body:{r.text[:400]}")
            chk=hashlib.sha256(f"{USER_ID}{authCode}{APP_SECRET}".encode()).hexdigest()
            r=requests.post(urls_dict['sessionID'], headers=header, data=json.dumps({"checksum":chk}), timeout=20)
            out.append(f"STEP5 sessionID Status:{r.status_code} Body:{r.text[:800]}")
            if r.status_code!=200: continue
            sess=r.json().get("userSession")
            out.append(f"userSession:{str(sess)[:20] if sess else 'NONE'}")
            if not sess: continue
            r=requests.post(urls_dict['authorizeVendor'], headers=header, data=json.dumps({"userId":USER_ID,"vendor":APP_ID}), timeout=20)
            out.append(f"STEP6 authorizeVendor Status:{r.status_code} Body:{r.text[:600]}")
            out.append(f"<h2 style='color:green'>SUCCESS! Session:{str(sess)[:15]}*** via {label}</h2><p>Full Session: {sess}</p>")
            return "<br>".join(out) + "<br><a href='/'>Home</a>"
        out.append("LOGIN FAIL")
    except Exception as e:
        out.append(f"Err {e} {traceback.format_exc()[:3000]}")
    return "<br>".join(out) + "<br><a href='/'>Home</a>"
if __name__=='__main__':
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0', port=port)
