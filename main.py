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
HOST="https://ant.aliceblueonline.com/rest/AliceBlueAPIService"
# SDK-la irundhu edutha UNMAIYAANA URLS - Guess illa!
URLS={
  "webLogin": f"{HOST}/customer/webLogin",
  "twoFA": f"{HOST}/sso/validAnswer",
  "sessionID": f"{HOST}/sso/getUserDetails",
  "getEncKey": f"{HOST}/customer/getEncryptionKey",
  "apiEncKey": f"{HOST}/customer/getEncpkey",
  "authorizeVendor": f"{HOST}/sso/authorizeVendor",
}
@app.route('/')
def home():
    return f"<h1>V30 - SDK CORRECT URLS</h1><p>User:{USER_ID} DOB:{DOB_YEAR}</p><p>webLogin: {URLS['webLogin']}</p><p>twoFA: {URLS['twoFA']}</p><p>sessionID: {URLS['sessionID']}</p><p><a href='/login'><b>LOGIN - SDK EXACT</b></a></p>"
@app.route('/login')
def login():
    out=[]
    try:
        import alice_blue as mod
        import pyotp
        try: totp_now=pyotp.TOTP(TOTP_SECRET).now() if TOTP_SECRET else None
        except: totp_now=None
        out.append(f"USER:{USER_ID} APP:{APP_ID} DOB:{DOB_YEAR} TOTP:{totp_now}")
        out.append(f"URLS: {URLS}")
        header={"Content-Type":"application/json"}
        for label, tfa in [("DOB",DOB_YEAR),("TOTP",totp_now)]:
            if not tfa: continue
            out.append(f"<b>=== TRY {label}={tfa} ===</b>")
            # STEP1 - SDK exact: customer/getEncryptionKey
            r=requests.post(URLS['getEncKey'], headers=header, json={"userId":USER_ID}, timeout=20)
            out.append(f"STEP1 getEncKey Status:{r.status_code} Body:{r.text[:600]}")
            if r.status_code!=200: continue
            try: encKey=r.json()['encKey']
            except: continue
            out.append(f"encKey OK:{encKey[:10]}***")
            # STEP2 - SDK exact: CryptoJS AES + customer/webLogin
            try:
                CryptoJS=getattr(mod,"CryptoJS",None)
                checksum=CryptoJS.AES.encrypt(PASSWORD.encode(), encKey.encode()).decode("utf-8")
            except Exception as e:
                out.append(f"AES Fail {e}"); continue
            out.append(f"AES OK:{checksum[:30]}")
            r=requests.post(URLS['webLogin'], headers=header, json={"userId":USER_ID,"userData":checksum}, timeout=20)
            out.append(f"STEP2 webLogin Status:{r.status_code} Body:{r.text[:800]}")
            # STEP3 - SDK exact: sso/validAnswer + sIndex
            data={"answer":str(tfa),"count":"1","sIndex":"1","userId":USER_ID,"vendor":APP_ID}
            r=requests.post(URLS['twoFA'], headers=header, json=data, timeout=20)
            out.append(f"STEP3 twoFA Status:{r.status_code} Body:{r.text[:1000]}")
            if r.status_code!=200: continue
            j=r.json(); isAuth=j.get("isAuthorized")
            out.append(f"isAuthorized:{isAuth}")
            if not isAuth:
                out.append(f"twoFA Fail Full:{j}"); continue
            authCode=parse_qs(urlparse(j['redirectUrl']).query)['authCode'][0]
            out.append(f"authCode OK:{authCode[:12]}***")
            # STEP4 - apiEncKey
            r=requests.post(URLS['apiEncKey'], headers=header, data=json.dumps({"userId":USER_ID}), timeout=20)
            out.append(f"STEP4 apiEncKey Status:{r.status_code} Body:{r.text[:400]}")
            # STEP5 - SDK exact: sso/getUserDetails + userSession
            chk=hashlib.sha256(f"{USER_ID}{authCode}{APP_SECRET}".encode()).hexdigest()
            r=requests.post(URLS['sessionID'], headers=header, data=json.dumps({"checksum":chk}), timeout=20)
            out.append(f"STEP5 sessionID Status:{r.status_code} Body:{r.text[:1000]}")
            if r.status_code!=200: continue
            sess=r.json().get("userSession")
            out.append(f"userSession:{str(sess)[:30] if sess else 'NONE'}")
            if not sess: continue
            # STEP6
            r=requests.post(URLS['authorizeVendor'], headers=header, data=json.dumps({"userId":USER_ID,"vendor":APP_ID}), timeout=20)
            out.append(f"STEP6 authorizeVendor Status:{r.status_code} Body:{r.text[:600]}")
            out.append(f"<h2 style='color:green'>SUCCESS! Session via {label}</h2><p>Full Session: {sess}</p><p>Idha copy pannunga - Test Order ku use pannalam</p>")
            return "<br>".join(out) + "<br><a href='/'>Home</a>"
        out.append("<b>LOGIN FAIL - Ella try-um fail</b>")
    except Exception as e:
        out.append(f"Err {e} {traceback.format_exc()[:3000]}")
    return "<br>".join(out) + "<br><a href='/'>Home</a>"
if __name__=='__main__':
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0', port=port)
