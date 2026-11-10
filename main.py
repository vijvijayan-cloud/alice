import os, traceback, inspect, json
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
@app.route('/')
def home():
    return f"<h1>V43 - SKIP AUTHORIZE - GET SESSION ONLY</h1><p>User:{USER_ID} APP:{APP_ID} DOB:{DOB_YEAR}</p><p><a href='/login'><b>1. LOGIN - Spy - AuthorizeVendor Raw Response Paaru</b></a></p><p><a href='/session'><b>2. SESSION ONLY - Authorize-a Skip Panni Session Mattum Edu</b></a></p>"
@app.route('/login')
def login():
    out=["<h1>LOGIN SPY - AuthorizeVendor Raw</h1>"]
    try:
        import alice_blue.alice_blue as mod
        orig_post=mod.requests.post; orig_get=mod.requests.get
        def spy_post(url,*a,**kw):
            r=orig_post(url,*a,**kw)
            txt=(r.text or "")
            body=txt[:700].replace("<","&lt;")
            out.append(f"<p><b>POST {url}</b><br>Status:{r.status_code} Len:{len(txt)} Content-Type:{r.headers.get('Content-Type')}<br>Body:{body}</p>")
            return r
        def spy_get(url,*a,**kw):
            r=orig_get(url,*a,**kw)
            txt=(r.text or "")
            out.append(f"<p><b>GET {url}</b><br>Status:{r.status_code} Len:{len(txt)}<br>Body:{txt[:700].replace('<','&lt;')}</p>")
            return r
        mod.requests.post=spy_post; mod.requests.get=spy_get
        try:
            obj=mod.AliceBlue.__new__(mod.AliceBlue)
            sess=obj.login_and_get_sessionID(USER_ID,PASSWORD,str(DOB_YEAR),APP_ID,APP_SECRET)
            out.append(f"<h2>Session: {sess}</h2>")
        except Exception as e:
            out.append(f"<h3>STOPPED at: {e}</h3><p>{traceback.format_exc()[:1500]}</p><p><b>Mela irukkura LAST POST thaan fail - Adhoda Status + Body paaru! Empty-a? HTML-a? 404-a?</b></p>")
        finally:
            mod.requests.post=orig_post; mod.requests.get=orig_get
    except Exception as e: out.append(f"Err {e} {traceback.format_exc()[:2000]}")
    return "<br>".join(out)+"<br><a href='/'>Home</a> | <a href='/session'>Session Only</a>"
@app.route('/session')
def session_only():
    out=["<h1>SESSION ONLY - Authorize Skip</h1>"]
    try:
        import alice_blue.alice_blue as mod
        # SDK-oda r.json() crash-a thadukka - authorizeVendor response-a patch pannuvom
        # SDK line 216: isAuthorized = r.json()["isAuthorized"]
        # Namma patch: r.json() - Empty na {"isAuthorized": True} nu return pannu
        orig_post=mod.requests.post
        captured={}
        def patched_post(url,*a,**kw):
            r=orig_post(url,*a,**kw)
            if "authorizeVendor" in url or "Authorize" in url:
                captured['url']=url; captured['status']=r.status_code; captured['text']=(r.text or "")[:500]
                # Empty response-a fake JSON-a maathu
                orig_json=r.json
                def fake_json(*ja,**jk):
                    try: return orig_json(*ja,**jk)
                    except: return {"isAuthorized": True, "status":"patched"}
                r.json=fake_json
            if "sessionID" in url or "getSession" in url.lower() or "session" in url.lower():
                try: captured['session_raw']=(r.text or "")[:500]
                except: pass
            return r
        mod.requests.post=patched_post
        try:
            obj=mod.AliceBlue.__new__(mod.AliceBlue)
            sess=obj.login_and_get_sessionID(USER_ID,PASSWORD,str(DOB_YEAR),APP_ID,APP_SECRET)
            out.append(f"<p>Authorize Captured: {captured}</p>")
            out.append(f"<h2>Session Returned: {str(sess)[:200] if sess else 'NONE'}</h2>")
            if sess and len(str(sess))>10:
                out.append(f"<h2 style='color:green'>SUCCESS! Session: {sess}</h2>")
                # Profile try - Session vachu
                try:
                    real=mod.AliceBlue(username=USER_ID, session_id=str(sess))
                    prof=real.get_profile()
                    out.append(f"<h3>Profile: {str(prof)[:1000]}</h3>")
                except Exception as e: out.append(f"Profile Err: {e} - Session kidaichiduchu, adhu podhum!")
                # Holdings try
                try:
                    real2=mod.AliceBlue(username=USER_ID, session_id=str(sess))
                    hold=real2.get_holdings()
                    out.append(f"<h3>Holdings: {str(hold)[:1000]}</h3>")
                except Exception as e: out.append(f"Holdings Err: {e}")
            else:
                out.append("<b>Session Empty - /login screenshot anuppu</b>")
        except Exception as e:
            out.append(f"Still Err: {e} {traceback.format_exc()[:2000]} Captured:{captured}")
        finally:
            mod.requests.post=orig_post
    except Exception as e: out.append(f"Err {e} {traceback.format_exc()[:2000]}")
    return "<br>".join(out)+"<br><a href='/'>Home</a>"
if __name__=='__main__':
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0', port=port)
