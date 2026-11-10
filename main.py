import os, traceback, inspect, hashlib, json
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
try:
    import pyotp
    TOTP_SECRET=clean("ALICE_TOTP_SECRET")
except:
    TOTP_SECRET=""
@app.route('/')
def home():
    return f"<h1>V28 MINI - SDK EXACT</h1><p>User:{USER_ID} DOB:{DOB_YEAR}</p><p><a href='/urls'>1. SHOW SDK URLS</a></p><p><a href='/login'>2. LOGIN SDK EXACT</a></p>"
@app.route('/urls')
def urls():
    out=[]
    try:
        import alice_blue as mod
        out.append(f"SDK File: {mod.__file__}")
        # AliceBlue_urls dict-a kaatu
        for name in ["AliceBlue_urls","urls","URLS","BASE_URL","base_url"]:
            v=getattr(mod, name, None)
            if v is not None:
                out.append(f"<h3>{name} = {v}</h3>")
        # AliceBlue class la irukka urls
        AB=getattr(mod,"AliceBlue",None)
        if AB:
            for name in ["AliceBlue_urls","urls","URLS"]:
                v=getattr(AB, name, None)
                if v is not None:
                    out.append(f"<h3>AliceBlue.{name} = {v}</h3>")
        # Full file la urls irukka line-a thedu
        txt=open(mod.__file__, errors="ignore").read()
        for i,line in enumerate(txt.splitlines()):
            low=line.lower()
            if "aliceblue_urls" in low or "twofa" in low or "weblogin" in low or "getencryption" in low or "sessionid" in low or "authorizevendor" in low or "http" in low and "alice" in low:
                out.append(f"{i+1}: {line.strip()[:400]}")
    except Exception as e:
        out.append(f"Fail {e} {traceback.format_exc()[:2000]}")
    return "<br>".join(out) + "<br><a href='/'>Home</a> | <a href='/login'>Login</a>"
@app.route('/login')
def login():
    out=[]
    try:
        import alice_blue as mod
        import pyotp
        urls_dict = getattr(mod, "AliceBlue_urls", None)
        if urls_dict is None:
            AB=getattr(mod,"AliceBlue",None)
            urls_dict=getattr(AB,"AliceBlue_urls",{})
        out.append(f"URLS: {urls_dict}")
        # TOTP
        try: totp_now=pyotp.TOTP(TOTP_SECRET).now() if TOTP_SECRET else None
        except: totp_now=None
        out.append(f"USER:{USER_ID} APP:{APP_ID} DOB:{DOB_YEAR} TOTP:{totp_now}")
        header={"Content-Type":"application/json"}
        for label, tfa in [("DOB",DOB_YEAR),("TOTP",totp_now)]:
            if not tfa: continue
            out.append(f"<b>=== TRY {label}={tfa} ===</b>")
            # STEP1
            r=requests.post(urls_dict['getEncKey'], headers=header, json={"userId":USER_ID}, timeout=20)
            out.append(f"STEP1 getEncKey Status:{r.status_code} Body:{r.text[:600]}")
            if r.status_code!=200: continue
            encKey=r.json()['encKey']
            out.append(f"encKey OK:{encKey[:10]}***")
            # STEP2 - SDK exact: CryptoJS.AES.encrypt(password.encode(), encKey.encode()).decode()
            try:
                CryptoJS=getattr(mod,"CryptoJS",None)
                checksum=CryptoJS.AES.encrypt(PASSWORD.encode(), encKey.encode()).decode("utf-8")
            except Exception as e:
                out.append(f"AES Fail {e}")
                continue
            out.append(f"STEP2 AES OK Start:{checksum[:30]}")
            r=requests.post(urls_dict['webLogin'], headers=header, json={"userId":USER_ID,"userData":checksum}, timeout=20)
            out.append(f"STEP2 webLogin Status:{r.status_code} Body:{r.text[:800]}")
            # STEP3 - SDK exact: sIndex included!
            data={"answer":str(tfa),"count":"1","sIndex":"1","userId":USER_ID,"vendor":APP_ID}
            r=requests.post(urls_dict['twoFA'], headers=header, json=data, timeout=20)
            out.append(f"STEP3 twoFA URL:{urls_dict['twoFA']} Status:{r.status_code} Body:{r.text[:1000]}")
            if r.status_code!=200: continue
            j=r.json()
            isAuth=j.get("isAuthorized")
            out.append(f"isAuthorized:{isAuth}")
            if not isAuth: continue
            authCode=parse_qs(urlparse(j['redirectUrl']).query)['authCode'][0]
            out.append(f"authCode OK:{authCode[:12]}***")
            # STEP4
            r=requests.post(urls_dict['apiEncKey'], headers=header, data=json.dumps({"userId":USER_ID}), timeout=20)
            out.append(f"STEP4 apiEncKey Status:{r.status_code} Body:{r.text[:400]}")
            # STEP5 - SDK exact: userSession!
            chk=hashlib.sha256(f"{USER_ID}{authCode}{APP_SECRET}".encode()).hexdigest()
            r=requests.post(urls_dict['sessionID'], headers=header, data=json.dumps({"checksum":chk}), timeout=20)
            out.append(f"STEP5 sessionID Status:{r.status_code} Body:{r.text[:800]}")
            if r.status_code!=200: continue
            sess=r.json().get("userSession")
            out.append(f"userSession:{str(sess)[:20] if sess else 'NONE'}")
            if not sess: continue
            # STEP6 - authorizeVendor
            r=requests.post(urls_dict['authorizeVendor'], headers=header, data=json.dumps({"userId":USER_ID,"vendor":APP_ID}), timeout=20)
            out.append(f"STEP6 authorizeVendor Status:{r.status_code} Body:{r.text[:600]}")
            out.append(f"<h2 style='color:green'>SUCCESS! Session:{str(sess)[:15]}*** via {label}</h2>")
            out.append(f"<p>Session-a copy pannunga: {sess}</p>")
            return "<br>".join(out) + "<br><a href='/'>Home</a>"
        out.append("LOGIN FAIL - Ella try-um fail")
    except Exception as e:
        out.append(f"Err {e} {traceback.format_exc()[:2000]}")
    return "<br>".join(out) + "<br><a href='/'>Home</a>"
if __name__=='__main__':
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0', port=port)
