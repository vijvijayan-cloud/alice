import os, traceback
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
    return f"<h1>V47 - 405 BREAK - Method Kandupidi</h1><p>User:{USER_ID} DOB:{DOB_YEAR} APP:{APP_ID}</p><p><a href='/methods'><b>1. METHODS - sso/validAnswer - GET / POST-FORM / POST-JSON - Edhu 405 Illa?</b></a></p><p><a href='/full'><b>2. FULL - WebLogin + validAnswer - Same Session (Cookie) vachu Try</b></a></p>"
@app.route('/methods')
def methods():
    import requests
    out=["<h1>METHODS - Root Host - sso/validAnswer</h1>"]
    # Root host thaan LIVE - rest/ prefix ILLA!
    base="https://ant.aliceblueonline.com"
    payload={"answer1":str(DOB_YEAR),"sCount":"1","sIndex":"1","userId":USER_ID,"vendor":APP_ID}
    tests=[
        ("GET-query", "GET", f"{base}/sso/validAnswer", {"params":payload}),
        ("GET-no-payload", "GET", f"{base}/sso/validAnswer", {}),
        ("POST-JSON", "POST", f"{base}/sso/validAnswer", {"json":payload}),
        ("POST-FORM", "POST", f"{base}/sso/validAnswer", {"data":payload}),
        ("POST-FORM-json-header", "POST", f"{base}/sso/validAnswer", {"data":payload, "headers":{"Content-Type":"application/x-www-form-urlencoded"}}),
        ("PUT-JSON", "PUT", f"{base}/sso/validAnswer", {"json":payload}),
        ("POST-JSON-no-vendor", "POST", f"{base}/sso/validAnswer", {"json":{"answer1":str(DOB_YEAR),"userId":USER_ID}}),
        ("OPTIONS", "OPTIONS", f"{base}/sso/validAnswer", {}),
    ]
    for name,method,url,kw in tests:
        try:
            r=requests.request(method, url, timeout=7, **kw)
            txt=(r.text or "")
            is_html="<html" in txt.lower()
            allow=r.headers.get("Allow","")
            mark="✅" if (r.status_code not in (404,405) and not is_html) else ("⚠️" if r.status_code==405 else "❌")
            out.append(f"<p>{mark} <b>{name}</b> Status:{r.status_code} Len:{len(txt)} Allow:{allow} Body:{txt[:500].replace('<','&lt;')}</p>")
            if r.status_code==200 and not is_html:
                out.append(f"<h2 style='color:green'>FOUND! Method: {name} Body: {txt[:600]}</h2>")
        except Exception as e: out.append(f"<p>❌ {name} Err:{e}</p>")
    return "<br>".join(out)+"<br><a href='/'>Home</a> | <a href='/full'>Full</a>"
@app.route('/full')
def full():
    import requests, json
    out=["<h1>FULL - WebLogin Cookie vachu - validAnswer</h1>"]
    try:
        s=requests.Session()
        host_root="https://ant.aliceblueonline.com"
        # Step 1 - getEncKey - Root host la? Rest host la? Rendum try - WebLogin enga work aagudhu nu paappom
        # Munnadi rest host la webLogin work aachu - Adha Session la pannuvom
        out.append("<h3>Step 1 - getEncKey (rest host)</h3>")
        r1=s.post("https://ant.aliceblueonline.com/rest/AliceBlueAPIService/customer/getEncryptionKey", headers={"Content-Type":"application/json"}, data=json.dumps({"userId":USER_ID}), timeout=10)
        out.append(f"Status:{r1.status_code} Body:{r1.text[:400]} Cookies:{dict(s.cookies)}")
        try: encKey=r1.json().get("encKey")
        except: encKey=None
        # Step 2 - webLogin - Rest host
        if encKey:
            from alice_blue.alice_blue import CryptoJsAES
            enc_pass=CryptoJsAES.encrypt(PASSWORD.encode(), encKey.encode()).decode()
            checksum=__import__("hashlib").sha256(USER_ID.encode()).hexdigest()
            data={"userId":USER_ID,"password":enc_pass,"checksum":checksum}
            out.append("<h3>Step 2 - webLogin (rest host) - Session Cookie save</h3>")
            r2=s.post("https://ant.aliceblueonline.com/rest/AliceBlueAPIService/customer/webLogin", json=data, timeout=10)
            out.append(f"Status:{r2.status_code} Body:{r2.text[:600]} Cookies:{dict(s.cookies)} Headers:{dict(r2.headers)}")
            # Step 3 - validAnswer - ROOT host - Same Session + Cookies + GET + POST-FORM + POST-JSON
            payload={"answer1":str(DOB_YEAR),"sCount":"1","sIndex":"1","userId":USER_ID,"vendor":APP_ID}
            for name,kw in [("GET-query",{"params":payload}),("POST-JSON",{"json":payload}),("POST-FORM",{"data":payload})]:
                try:
                    r3=s.request("GET" if "GET" in name else "POST", f"{host_root}/sso/validAnswer", timeout=10, **kw)
                    out.append(f"<p><b>{name} + Cookies</b> Status:{r3.status_code} Body:{r3.text[:500].replace('<','&lt;')}</p>")
                    if r3.status_code==200 and "<html" not in r3.text.lower():
                        out.append(f"<h2 style='color:green'>FOUND! {name} Body: {r3.text[:600]}</h2>")
                except Exception as e: out.append(f"<p>{name} Err:{e}</p>")
        else:
            out.append("<b>encKey Illa</b>")
    except Exception as e: out.append(f"Err {e} {traceback.format_exc()[:2000]}")
    return "<br>".join(out)+"<br><a href='/'>Home</a>"
if __name__=='__main__':
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0', port=port)
