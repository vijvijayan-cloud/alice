import os, traceback, json, hashlib
from flask import Flask
app = Flask(__name__)
def clean(n):
    return os.getenv(n,"").strip().replace('"',"").replace("'","")
USER_ID=clean("ALICE_USER_ID")
PASSWORD=clean("ALICE_PASSWORD")
APP_ID=clean("ALICE_APP_ID")
APP_SECRET=clean("ALICE_APP_SECRET")
DOB_YEAR=clean("ALICE_YEAR") or clean("ALICE_DOB_YEAR") or clean("ALICE_2FA")
@app.route('/')
def home():
    return f"<h1>V49 - REST + COOKIE - Correct Combination</h1><p>User:{USER_ID} DOB:{DOB_YEAR} APP:{APP_ID}</p><p><a href='/combo'><b>1. COMBO - REST Host + Cookie vachu - Ella 2FA Path-um Try</b></a></p>"
@app.route('/combo')
def combo():
    import requests
    from alice_blue.alice_blue import CryptoJsAES
    out=["<h1>COMBO - REST + Cookie</h1>"]
    try:
        s=requests.Session()
        s.headers.update({"User-Agent":"Mozilla/5.0","Accept":"application/json"})
        REST="https://ant.aliceblueonline.com/rest/AliceBlueAPIService"
        # Step 1 - getEncKey
        r1=s.post(f"{REST}/customer/getEncryptionKey", json={"userId":USER_ID}, timeout=10)
        out.append(f"<p><b>Step1 getEncKey</b> Status:{r1.status_code} Body:{r1.text[:400]} Cookies:{dict(s.cookies)}</p>")
        try: encKey=r1.json().get("encKey")
        except: encKey=None
        if not encKey:
            return "<br>".join(out)+"<br><b>encKey Illa</b>"
        # Step 2 - webLogin - FULL JSON
        enc_pass=CryptoJsAES.encrypt(PASSWORD.encode(), encKey.encode()).decode()
        checksum=hashlib.sha256(USER_ID.encode()).hexdigest()
        data={"userId":USER_ID,"password":enc_pass,"checksum":checksum}
        r2=s.post(f"{REST}/customer/webLogin", json=data, timeout=10)
        out.append(f"<h3>Step2 webLogin FULL</h3><p>Status:{r2.status_code}</p><p>Cookies:{dict(s.cookies)}</p><p>Headers:{dict(r2.headers)}</p><pre>{r2.text[:3000].replace('<','&lt;')}</pre>")
        try:
            j2=r2.json()
            out.append(f"<p><b>webLogin Keys: {list(j2.keys()) if isinstance(j2,dict) else type(j2)}</b></p>")
            # Adhula URL / Token / Next Step irukka?
            for k,v in j2.items() if isinstance(j2,dict) else []:
                out.append(f"<p>Key: {k} = {str(v)[:500]}</p>")
        except Exception as e: out.append(f"<p>webLogin JSON parse Err: {e}</p>")
        # Step 3 - 2FA - REST + Cookie - Ella Path-um
        out.append("<h3>Step3 - 2FA - REST + Cookie</h3>")
        payload={"answer1":str(DOB_YEAR),"sCount":"1","sIndex":"1","userId":USER_ID,"vendor":APP_ID}
        cands=[
            "sso/validAnswer","sso/validateAnswer","sso/verifyAnswer","sso/validUserDetails",
            "customer/validAnswer","customer/validateAnswer","customer/verifyAnswer",
            "customer/validUserDetails","sso/validate2FA","sso/verify2FA",
            "customer/validate2FA","sso/checkAnswer","customer/checkAnswer",
            "sso/validanswer","sso/answer","customer/answer",
        ]
        for c in cands:
            full=f"{REST}/{c}"
            try:
                r3=s.post(full, json=payload, timeout=7)
                txt=(r3.text or "")
                is_html="<html" in txt.lower() or "status report" in txt.lower()
                mark="✅" if (r3.status_code==200 and not is_html) else ("⚠️" if r3.status_code in (400,401,405) else "❌")
                out.append(f"<p>{mark} {c} Status:{r3.status_code} Len:{len(txt)} HTML:{is_html} Body:{txt[:450].replace('<','&lt;')}</p>")
                if r3.status_code==200 and not is_html:
                    out.append(f"<h2 style='color:green'>FOUND! {full} Body: {txt[:800]}</h2>")
                    # Adutha step - SessionID try - Adhayum inga ye panniduvom
                    try:
                        j3=r3.json()
                        out.append(f"<p>2FA JSON Keys: {list(j3.keys()) if isinstance(j3,dict) else j3}</p>")
                    except: pass
            except Exception as e: out.append(f"<p>❌ {c} Err:{e}</p>")
        # Step 3b - Same paths - FORM data-oda - Cookie vachu
        out.append("<h3>Step3b - FORM + Cookie</h3>")
        for c in ["sso/validAnswer","customer/validAnswer"]:
            try:
                r4=s.post(f"{REST}/{c}", data=payload, timeout=7)
                out.append(f"<p>FORM {c} Status:{r4.status_code} Body:{r4.text[:400].replace('<','&lt;')}</p>")
            except Exception as e: out.append(f"<p>FORM {c} Err:{e}</p>")
    except Exception as e: out.append(f"Err {e} {traceback.format_exc()[:2000]}")
    return "<br>".join(out)+"<br><a href='/'>Home</a>"
if __name__=='__main__':
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0', port=port)
