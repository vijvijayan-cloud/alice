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
    return f"<h1>V45 - URLs + Exact Payload Test</h1><p>User:{USER_ID} DOB:{DOB_YEAR} APP:{APP_ID}</p><p><a href='/urls'><b>1. URLS - AliceBlue_urls la twoFA URL enna?</b></a></p><p><a href='/try'><b>2. TRY - Exact SDK Payload-oda Ella Host-um Try</b></a></p>"
@app.route('/urls')
def urls():
    out=["<h1>AliceBlue_urls - FULL</h1>"]
    try:
        import alice_blue.alice_blue as mod, pathlib
        lines=pathlib.Path(mod.__file__).read_text(errors="ignore").splitlines()
        for i in range(0,130):
            if i < len(lines):
                out.append(f"Line {i+1}: {lines[i]}")
        # Direct dict print
        out.append(f"<h2>Direct Dict: {getattr(mod,'AliceBlue_urls', 'ILLAI')}</h2>")
        try:
            from alice_blue.alice_blue import AliceBlue_urls as U
            out.append(f"<h2>AliceBlue_urls Dict: {U}</h2>")
        except Exception as e: out.append(f"Dict Err: {e}")
    except Exception as e: out.append(f"Err {e} {traceback.format_exc()[:2000]}")
    return "<br>".join(out)+"<br><a href='/'>Home</a> | <a href='/try'>Try</a>"
@app.route('/try')
def try2fa():
    import requests
    out=["<h1>TRY - Exact SDK Payload</h1>"]
    # SDK exact payload - Screenshot Line 208-213
    payload={"answer1":str(DOB_YEAR),"sCount":"1","sIndex":"1","userId":USER_ID,"vendor":APP_ID}
    out.append(f"<p>Payload: {payload}</p>")
    # Ella possible twoFA URL-um - SDK URL + Prefix variations + Vera host
    bases=[
        "https://ant.aliceblueonline.com/rest/AliceBlueAPIService",
        "https://ant.aliceblueonline.com",
        "https://ant.aliceblueonline.com/rest/AliceBlueAPIService/",
        "https://api.aliceblueonline.com",
    ]
    paths=["sso/validAnswer","sso/validAnswer/","customer/validAnswer","sso/validateAnswer","sso/validUserDetails"]
    for b in bases:
        for p in paths:
            full=f"{b.rstrip('/')}/{p}"
            try:
                r=requests.post(full, json=payload, headers={"Content-Type":"application/json"}, timeout=7)
                txt=(r.text or "")
                is_html="<html" in txt.lower() or "status report" in txt.lower()
                mark="✅" if (r.status_code==200 and not is_html) else ("⚠️" if r.status_code in (400,401,405) else "❌")
                out.append(f"<p>{mark} {full} Status:{r.status_code} Len:{len(txt)} HTML:{is_html} Body:{txt[:350].replace('<','&lt;')}</p>")
                if r.status_code==200 and not is_html:
                    out.append(f"<h2 style='color:green'>FOUND! Correct URL: {full} Body: {txt[:500]}</h2>")
            except Exception as e:
                out.append(f"<p>❌ {full} Err:{e}</p>")
    return "<br>".join(out)+"<br><a href='/'>Home</a>"
if __name__=='__main__':
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0', port=port)
