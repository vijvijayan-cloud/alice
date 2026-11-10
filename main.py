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
TOTP_SECRET=clean("ALICE_TOTP_SECRET")
BASE="https://ant.aliceblueonline.com/rest/AliceBlueAPIService"
@app.route('/')
def home():
    return f"<h1>V44 - FIND CORRECT twoFA URL</h1><p>User:{USER_ID} DOB:{DOB_YEAR} APP:{APP_ID}</p><p><a href='/source'><b>1. SOURCE - SDK twoFA Step la Enna Payload Anuppuradhu?</b></a></p><p><a href='/find'><b>2. FIND - Ella twoFA URL-um - SDK Payload-oda Try Pannu</b></a></p>"
@app.route('/source')
def source():
    out=["<h1>SOURCE - twoFA Step</h1>"]
    try:
        import alice_blue.alice_blue as mod, pathlib
        lines=pathlib.Path(mod.__file__).read_text(errors="ignore").splitlines()
        for i in range(98,260):
            if i < len(lines):
                out.append(f"Line {i+1}: {lines[i]}")
    except Exception as e: out.append(f"Err {e} {traceback.format_exc()[:2000]}")
    return "<br>".join(out)+"<br><a href='/'>Home</a> | <a href='/find'>Find</a>"
@app.route('/find')
def find():
    import requests
    out=["<h1>FIND twoFA - Edhu 404/HTML Illa?</h1>"]
    # SDK payload variants - Screenshot la vandha exact format + vera formats
    payloads=[
        ("SDK-json", {"answer1":DOB_YEAR,"sCount":"1","sIndex":"1","userId":USER_ID,"vendor":APP_ID}),
        ("SDK-json-no-vendor", {"answer1":DOB_YEAR,"sCount":"1","sIndex":"1","userId":USER_ID}),
        ("answer-only", {"answer1":DOB_YEAR}),
        ("answer-user", {"answer":DOB_YEAR,"userId":USER_ID}),
        ("twoFA", {"twoFA":DOB_YEAR,"userId":USER_ID}),
    ]
    cands=[
        "sso/validAnswer","sso/validAnswer/","sso/validateAnswer","sso/validUserDetails",
        "sso/verifyAnswer","sso/checkAnswer","sso/validate2FA","sso/verify2FA",
        "customer/validAnswer","customer/validateAnswer","customer/validUserDetails",
        "customer/verifyAnswer","customer/validate2FA",
        "sso/validanswer","sso/ValidAnswer","sso/answer",
        "customer/validAnswer/","customer/answer",
    ]
    found=[]
    for c in cands:
        full=f"{BASE}/{c}"
        for pname,payload in payloads:
            try:
                # JSON + Form - Rendum try - Oru candidate ku oru try mattum podhum - JSON thaan SDK use pannudhu
                r=requests.post(full, json=payload, timeout=7)
                txt=(r.text or "")
                is_html="html" in txt.lower()[:200] or "<html" in txt.lower()
                if r.status_code!=404 and not is_html:
                    found.append((full,pname,r.status_code,txt[:400]))
                    out.append(f"<p style='color:green'><b>✅ FOUND! {full} Payload:{pname} Status:{r.status_code} Body:{txt[:400]}</b></p>")
                elif r.status_code==405:
                    out.append(f"<p><b>⚠️ {c} Payload:{pname} Status:405 - URL IRUKKU - Method thappu!</b></p>")
            except Exception as e:
                pass
    if not found:
        out.append("<p><b>Ella 404/HTML - Vera path la irukku! /source screenshot anuppu - SDK payload-a paappom!</b></p>")
    else:
        out.append(f"<p><b>FOUND LIST: {found}</b></p>")
    return "<br>".join(out)+"<br><a href='/'>Home</a>"
if __name__=='__main__':
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0', port=port)
