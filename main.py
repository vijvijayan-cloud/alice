import os, traceback, hashlib, json, base64
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
URLS={
  "webLogin": f"{HOST}/customer/webLogin",
  "twoFA": f"{HOST}/sso/validAnswer",
  "sessionID": f"{HOST}/sso/getUserDetails",
  "getEncKey": f"{HOST}/customer/getEncryptionKey",
  "apiEncKey": f"{HOST}/customer/getEncpkey",
  "authorizeVendor": f"{HOST}/sso/authorizeVendor",
}
# CryptoJS maadhiri AES - EVP_BytesToKey - Salted__ format
def my_aes(plain, key_str):
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
    from Crypto.Random import get_random_bytes
    salt=get_random_bytes(8)
    key=hashlib.sha256(key_str.encode()+salt).digest()
    iv=hashlib.md5(key_str.encode()+salt).digest()
    cipher=AES.new(key, AES.MODE_CBC, iv)
    ct=cipher.encrypt(pad(plain.encode(), AES.block_size))
    return base64.b64encode(b"Salted__"+salt+ct).decode()
@app.route('/')
def home():
    return f"<h1>V31 - MY AES</h1><p>User:{USER_ID} DOB:{DOB_YEAR}</p><p><a href='/login'><b>LOGIN</b></a></p>"
@app.route('/login')
def login():
    out=[]
    try:
        import pyotp
        try: totp_now=pyotp.TOTP(TOTP_SECRET).now() if TOTP_SECRET else None
        except: totp_now=None
        out.append(f"USER:{USER_ID} APP:{APP_ID} DOB:{DOB_YEAR} TOTP:{totp_now}")
        header={"Content-Type":"application/json"}
        for label, tfa in [("DOB",DOB_YEAR),("TOTP",totp_now)]:
            if not tfa: continue
            out.append(f"<b>=== TRY {label}={tfa} ===</b>")
            r=requests.post(URLS['getEncKey'], headers=header, json={"userId":USER_ID}, timeout=20)
            out.append(f"STEP1 Status:{r.status_code} Body:{r.text[:600]}")
            if r.status_code!=200: continue
            try: encKey=r.json()['encKey']
            except: continue
            out.append(f"encKey OK:{encKey[:10]}***")
            # Enoda AES - SDK CryptoJS vendaam
            try:
                checksum=my_aes(PASSWORD, encKey)
            except Exception as e:
                out.append(f"MY AES Fail {e} {traceback.format_exc()[:500]}"); continue
            out.append(f"MY AES OK Start:{checksum[:40]} Len:{len(checksum)}")
            r=requests.post(URLS['webLogin'], headers=header, json={"userId":USER_ID,"userData":checksum}, timeout=20)
            out.append(f"STEP2 webLogin Status:{r.status_code} Body:{r.text[:1000]}")
            # STEP2 fail-a irundha kooda STEP3 try pannu - sila samayam webLogin Not_Ok vandhalum twoFA work aagum
            data={"answer":str(tfa),"count":"1","sIndex":"1","userId":USER_ID,"vendor":APP_ID}
            r=requests.post(URLS['twoFA'], headers=header, json=data, timeout=20)
            out.append(f"STEP3 twoFA Status:{r.status_code} Body:{r.text[:1200]}")
            if r.status_code!=200: continue
            try: j=r.json()
            except: continue
            isAuth=j.get("isAuthorized")
            out.append(f"isAuthorized:{isAuth} Full Keys:{list(j.keys())}")
            if not isAuth: continue
            # redirectUrl irukka paaru - illa na direct authCode?
            ru=j.get("redirectUrl") or j.get("redirectURL") or ""
            if ru:
                authCode=parse_qs(urlparse(ru).query)['authCode'][0]
            else:
                authCode=j.get("authCode") or ""
            if not authCode:
                out.append(f"authCode Illa Full:{j}"); continue
            out.append(f"authCode OK:{authCode[:12]}***")
            r=requests.post(URLS['apiEncKey'], headers=header, data=json.dumps({"userId":USER_ID}), timeout=20)
            out.append(f"STEP4 apiEncKey Status:{r.status_code} Body:{r.text[:400]}")
            chk=hashlib.sha256(f"{USER_ID}{authCode}{APP_SECRET}".encode()).hexdigest()
            r=requests.post(URLS['sessionID'], headers=header, data=json.dumps({"checksum":chk}), timeout=20)
            out.append(f"STEP5 sessionID Status:{r.status_code} Body:{r.text[:1200]}")
            if r.status_code!=200: continue
            try: j5=r.json()
            except: continue
            sess=j5.get("userSession") or j5.get("session_id") or j5.get("sessionId")
            out.append(f"userSession:{str(sess)[:30] if sess else 'NONE'} Full Keys:{list(j5.keys())}")
            if not sess: continue
            r=requests.post(URLS['authorizeVendor'], headers=header, data=json.dumps({"userId":USER_ID,"vendor":APP_ID}), timeout=20)
            out.append(f"STEP6 authorizeVendor Status:{r.status_code} Body:{r.text[:600]}")
            out.append(f"<h2 style='color:green'>SUCCESS! Session via {label}</h2><p>Full Session: {sess}</p>")
            return "<br>".join(out) + "<br><a href='/'>Home</a>"
        out.append("<b>LOGIN FAIL</b>")
    except Exception as e:
        out.append(f"Err {e} {traceback.format_exc()[:3000]}")
    return "<br>".join(out) + "<br><a href='/'>Home</a>"
if __name__=='__main__':
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0', port=port)
