import os, time, traceback, hashlib, json, inspect, base64
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify, request, redirect
import threading
import yfinance as yf
import requests
try:
    import pyotp
    HAS_PYOTP=True
except:
    pyotp=None; HAS_PYOTP=False
try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
    from Crypto.Random import get_random_bytes
    HAS_CRYPTO=True
except:
    HAS_CRYPTO=False

app = Flask(__name__)

def clean_env(name):
    v=os.getenv(name,"")
    return v.strip().replace("\n","").replace("\r","").replace('"',"").replace("'","")

USER_ID=clean_env("ALICE_USER_ID")
PASSWORD=clean_env("ALICE_PASSWORD")
APP_ID=clean_env("ALICE_APP_ID")
APP_SECRET=clean_env("ALICE_APP_SECRET")
DOB_YEAR=clean_env("ALICE_YEAR") or clean_env("ALICE_DOB_YEAR") or clean_env("ALICE_2FA")
TOTP_SECRET=clean_env("ALICE_TOTP_SECRET")
MODE=os.getenv("MODE","PAPER")
try: LOTS=int(os.getenv("LOTS","1"))
except: LOTS=1
LOT_SIZE=65

state={"strategy":"NIFTY_2ND_CANDLE_FLIP","mode":MODE,"login":"STARTING...","nifty_price":0,"signal":"WAITING FOR 9:20","in_trade":False,"side":"","entry":0,"pnl":0,"reason":"","last_update":"","candle1":"","candle2":"","live_order":"","debug":"Waiting...","session_id":"","real_session":"","api_version":"V14_SDK_FLOW_AES","test_order_result":"","lot_size":LOT_SIZE,"raw_login":""}

def get_ist(): return datetime.now(timezone.utc)+timedelta(hours=5,minutes=30)
session_id_global=""; real_session_global=""; last_login_try=0

def is_valid_key(k):
    if not k: return False
    k=str(k).strip()
    if k.lower() in ["null","none","","no","available"]: return False
    return True

def get_totp():
    try:
        if HAS_PYOTP and TOTP_SECRET and len(TOTP_SECRET)>10:
            return pyotp.TOTP(TOTP_SECRET).now()
    except: pass
    return None

def evp_bytes_to_key(password, salt, key_len=32, iv_len=16):
    # CryptoJS EVP_BytesToKey - MD5 Loop - Idhu thaan CryptoJS AES Secret
    d=b""; prev=b""
    while len(d) < key_len+iv_len:
        prev=hashlib.md5(prev+password+salt).digest()
        d+=prev
    return d[:key_len], d[key_len:key_len+iv_len]

def cryptojs_aes_encrypt(plaintext, passphrase):
    # CryptoJS.AES.encrypt(password, encpkey) - Same Output Format
    if not HAS_CRYPTO:
        return None
    salt=get_random_bytes(8)
    key, iv=evp_bytes_to_key(passphrase.encode(), salt)
    cipher=AES.new(key, AES.MODE_CBC, iv)
    ct=cipher.encrypt(pad(plaintext.encode(), AES.block_size))
    # CryptoJS Format: Base64("Salted__" + salt + ciphertext)
    return base64.b64encode(b"Salted__"+salt+ct).decode()

def sdk_flow_login():
    out=[]
    totp_now=get_totp()
    out.append(f"USER:{USER_ID} APP:{APP_ID} SEC_LEN:{len(APP_SECRET)} DOB:{DOB_YEAR} TOTP:{totp_now} PASS_LEN:{len(PASSWORD)} CRYPTO:{HAS_CRYPTO}")
    if not HAS_CRYPTO:
        out.append("pycryptodome Illa - requirements.txt la Add pannunga - Deploy Fail Aana Kooda SDK Backup Try pannuvom")
    # SDK URLs-a Edu - Correct URL Anga thaan Irukku
    try:
        from alice_blue import AliceBlue
        # AliceBlue_urls Enga Irukku nu Paaru
        urls={}
        try:
            from alice_blue import AliceBlue_urls
            urls=AliceBlue_urls
        except:
            try:
                import alice_blue as mod
                urls=getattr(mod,"AliceBlue_urls",{}) or getattr(AliceBlue,"urls",{}) or {}
            except: urls={}
        out.append(f"SDK URLs: {urls}")
        print(f"SDK URLs: {urls}",flush=True)
        if not urls:
            # Fallback - Ant Base la SDK Endpoint Names
            urls={
                "getEncpkey":"https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/customer/getAPIEncpkey",
                "twoFA":"https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/customer/getUserSID",
                "apiGetEncpkey":"https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/customer/getAPIEncpkey",
                "getSession":"https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/customer/getSessionId",
            }
            # SDK Source la URL Names Vera Irukkalaam - /test la Full URLs Paaru
            out.append("URLs SDK la Kidaikala - Fallback Use pannuren - /test la SDK URLs Paaru")
    except Exception as e:
        out.append(f"SDK Import Err:{e}"); return "<br>".join(out), None
    # STEP 1 - Encpkey
    try:
        url1=urls.get("getEncpkey") or urls.get("getAPIEncpkey") or "https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/customer/getAPIEncpkey"
        r1=requests.post(url1, json={"userId":USER_ID}, headers={"Content-Type":"application/json"}, timeout=20)
        out.append(f"STEP1 getEncpkey Status:{r1.status_code} Body:{r1.text[:500]}")
        print(f"STEP1 {r1.status_code} {r1.text[:500]}",flush=True)
        if r1.status_code!=200:
            return "<br>".join(out), None
        encpkey=r1.json().get("encpkey","")
        if not encpkey:
            out.append("Encpkey Illa"); return "<br>".join(out), None
        out.append(f"Encpkey OK: {encpkey[:10]}*** Len:{len(encpkey)}")
        # STEP 2 - twoFA - DOB + TOTP Try pannu
        for tfa_label, tfa_val in [("DOB",DOB_YEAR),("TOTP",totp_now)]:
            if not tfa_val: continue
            try:
                # Password Encrypt - CryptoJS AES
                enc_pass=cryptojs_aes_encrypt(PASSWORD, encpkey)
                if not enc_pass:
                    out.append("AES Encrypt Fail - pycryptodome Illa"); continue
                # SDK: checksum = SHA256(enc_pass)
                checksum=hashlib.sha256(enc_pass.encode()).hexdigest()
                out.append(f"STEP2 {tfa_label}={tfa_val} EncPass:{enc_pass[:20]}*** Checksum:{checksum[:10]}***")
                # twoFA URL - SDK la Enna Per?
                url2=urls.get("twoFA") or urls.get("twofa") or urls.get("getUserSID") or urls.get("login") or ""
                # Ella Possible URL Key-yum Try pannu
                if not url2:
                    # URLs Dict la Ella Key-yum Kaatu
                    out.append(f"twoFA URL Key Kidaikala - URLs Keys:{list(urls.keys())}")
                    # Common twoFA Endpoint
                    url2="https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/customer/getUserSID"
                payload={"userId":USER_ID,"userData":checksum,"twoFA":str(tfa_val),"app_id":APP_ID,"password":PASSWORD,"api_secret":APP_SECRET}
                print(f"STEP2 {tfa_label} URL:{url2} Payload:{payload}",flush=True)
                r2=requests.post(url2, data=json.dumps(payload), headers={"Content-Type":"application/json"}, timeout=20)
                out.append(f"STEP2 {tfa_label} Status:{r2.status_code} Body:{r2.text[:800]}")
                print(f"STEP2 {tfa_label} {r2.status_code} {r2.text[:800]}",flush=True)
                if r2.status_code!=200: continue
                try: j2=r2.json()
                except: continue
                out.append(f"STEP2 JSON Keys:{list(j2.keys()) if isinstance(j2,dict) else j2}")
                # isAuthorized Check pannu
                if isinstance(j2,dict) and j2.get("isAuthorized")==False:
                    out.append(f"STEP2 {tfa_label} NOT Authorized - {j2} - Next twoFA Try pannuren")
                    continue
                # authCode Edu - Response la URL / authCode Irukkum
                auth_code=""
                # Response la authCode Direct-a Irukka?
                auth_code=j2.get("authCode") or j2.get("auth_code") or ""
                # Response la URL Irundha - Adhula authCode Edu
                for k,v in j2.items():
                    if isinstance(v,str) and "authCode" in v:
                        try:
                            from urllib.parse import urlparse, parse_qs
                            q=parse_qs(urlparse(v).query)
                            if "authCode" in q: auth_code=q["authCode"][0]
                        except: pass
                    if isinstance(v,str) and len(v)>20 and "http" in v:
                        out.append(f"STEP2 URL Field {k}:{v[:200]}")
                if not auth_code and isinstance(j2,dict):
                    # Full Response-a Kaatu - authCode Enga?
                    out.append(f"STEP2 Full Response:{str(j2)[:1000]}")
                    continue
                out.append(f"STEP2 {tfa_label} authCode Found: {str(auth_code)[:10]}*** Len:{len(str(auth_code))}")
                # STEP 3 - API Encpkey
                try:
                    url3=urls.get("apiGetEncpkey") or urls.get("getAPIEncpkey") or url1
                    r3=requests.post(url3, json={"userId":USER_ID}, headers={"Content-Type":"application/json"}, timeout=20)
                    out.append(f"STEP3 apiGetEncpkey Status:{r3.status_code} Body:{r3.text[:300]}")
                    api_encpkey=r3.json().get("encpkey","") if r3.status_code==200 else encpkey
                except: api_encpkey=encpkey
                # STEP 4 - getSession - checksum = SHA256(authCode + api_secret) - SDK Source la Ippadi thaan
                for sess_formula, sess_checksum in [
                    ("authCode+secret", hashlib.sha256(f"{auth_code}{APP_SECRET}".encode()).hexdigest()),
                    ("authCode+secret+encp", hashlib.sha256(f"{auth_code}{APP_SECRET}{api_encpkey}".encode()).hexdigest()),
                ]:
                    try:
                        url4=urls.get("getSession") or urls.get("getSessionId") or urls.get("getSessionID") or "https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/customer/getSessionId"
                        payload4={"checksum":sess_checksum,"userId":USER_ID,"authCode":str(auth_code),"api_secret":APP_SECRET,"app_id":APP_ID}
                        print(f"STEP4 {sess_formula} URL:{url4}",flush=True)
                        r4=requests.post(url4, data=json.dumps(payload4), headers={"Content-Type":"application/json"}, timeout=20)
                        out.append(f"STEP4 {sess_formula} Status:{r4.status_code} Body:{r4.text[:800]}")
                        print(f"STEP4 {sess_formula} {r4.status_code} {r4.text[:800]}",flush=True)
                        if r4.status_code==200 and r4.text.strip().startswith("{"):
                            j4=r4.json()
                            sess=j4.get("session_id") or j4.get("sessionId") or j4.get("sessionID") or j4.get("token")
                            if sess and len(str(sess))>10:
                                out.append(f"<b style='color:green'>SUCCESS! Session:{str(sess)[:12]}*** via {tfa_label} {sess_formula}</b>")
                                return "<br>".join(out), str(sess)
                            else:
                                out.append(f"STEP4 JSON:{j4}")
                    except Exception as e: out.append(f"STEP4 {sess_formula} Err:{e}")
            except Exception as e:
                out.append(f"STEP2 {tfa_label} Exception:{e} {traceback.format_exc()[:500]}")
                continue
    except Exception as e:
        out.append(f"Flow Exception:{e} {traceback.format_exc()[:800]}")
    return "<br>".join(out), None

def alice_login_v2():
    global session_id_global, real_session_global, last_login_try
    last_login_try=time.time()
    try:
        raw, token = sdk_flow_login()
        state["raw_login"]=raw
        state["debug"]=f"V14 SDK Flow USER:{USER_ID} DOB:{DOB_YEAR} TOTP:{get_totp()} CRYPTO:{HAS_CRYPTO}"
        if token and is_valid_key(token):
            session_id_global=token; real_session_global=token
            state["session_id"]=token[:12]+"***"; state["real_session"]=token[:12]+"***"
            state["login"]=f"LIVE READY V14 - User {USER_ID[:3]}*** - LOT 65 - AES+authCode OK"
            return True
        # Backup - SDK Direct - Temp File Delete panni Try pannu - Stale Session File Problem Irukkalaam
        try:
            import tempfile, glob
            for f in glob.glob(os.path.join(tempfile.gettempdir(),"*session*")):
                try: os.remove(f)
                except: pass
            from alice_blue import AliceBlue
            fn=getattr(AliceBlue,"login_and_get_sessionID",None)
            if fn:
                for tfa in [DOB_YEAR, get_totp()]:
                    if not tfa: continue
                    try:
                        res=fn(USER_ID, PASSWORD, str(tfa), APP_ID, APP_SECRET)
                        if res:
                            if isinstance(res,dict): token=res.get("sessionId") or res.get("sessionID")
                            elif isinstance(res,str) and len(res)>10: token=res
                            if token and len(str(token))>10: break
                    except Exception as e: state["debug"]+=f" | SDK Backup {tfa} Fail:{str(e)[:200]}"
            if token and is_valid_key(str(token)):
                session_id_global=str(token); real_session_global=str(token)
                state["session_id"]=str(token)[:12]+"***"; state["real_session"]=str(token)[:12]+"***"
                state["login"]=f"LIVE READY V14 - SDK Backup OK"
                return True
        except Exception as e: state["debug"]+=f" | SDK Backup Err:{e}"
        state["login"]=f"LOGIN FAIL - /test la Raw + SDK URLs Paaru - authCode / twoFA Enna Sonna nu Theriyum"
        return False
    except Exception as e:
        print(traceback.format_exc(),flush=True)
        state["login"]=f"LOGIN FAIL - {e}"; return False

def alice_login():
    if MODE=="PAPER": state["login"]=f"PAPER READY - User {USER_ID[:3]}***"; return True
    return alice_login_v2()
def get_candles():
    try:
        df=yf.download("^NSEI", interval="5m", period="1d", progress=False, auto_adjust=False)
        if df is None or df.empty: return None
        return df
    except Exception as e: print("Candle Error:",e,flush=True); return None
def safe_float(x):
    try:
        if hasattr(x,'iloc'): return float(x.iloc[0])
        return float(x)
    except: return float(x)
def get_expiry_date():
    ist=get_ist(); d=ist.date(); days_ahead=(3-d.weekday())%7
    if days_ahead==0 and ist.hour>=15: days_ahead=7
    return d+timedelta(days=days_ahead)
def get_nifty_price():
    try:
        df=yf.download("^NSEI", interval="1m", period="1d", progress=False, auto_adjust=False)
        if df is not None and len(df)>0: return safe_float(df.iloc[-1]['Close'])
    except: pass
    return 0
def place_order_direct_v2(strike, side, qty):
    exp=get_expiry_date(); exp_str=exp.strftime("%d-%b-%Y").upper(); sess=real_session_global if real_session_global else session_id_global
    headers={"Content-Type":"application/json","Authorization":f"Bearer {USER_ID} {sess}","userId":USER_ID,"sessionId":sess}
    payload={"userId":USER_ID,"sessionId":sess,"tradingSymbol":f"NIFTY {strike} {side}","exchange":"NFO","transactionType":"BUY","orderType":"MARKET","productType":"MIS","quantity":qty,"price":"0","triggerPrice":"0","expiry":exp_str,"strike":str(strike),"optionType":side}
    for base in ["https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/"]:
        for ep in ["placeOrder/executePlaceOrder","placeOrder/placeOrder"]:
            try:
                url=base+ep
                r=requests.post(url, json=payload, headers=headers, timeout=20)
                if r.status_code==200: return r.status_code,r.text[:800],url
                if r.status_code!=404: return r.status_code,r.text[:800],url
            except Exception as e: pass
    return 404,"No Order URL", ""
def place_trade(side, price, nifty_price):
    state["in_trade"]=True; state["side"]=side; state["entry"]=round(float(price),2); state["nifty_price"]=round(float(nifty_price),2)
    if MODE=="PAPER": state["reason"]=f"PAPER TRADE - {side} @ {price}"; state["live_order"]="PAPER - No Order Sent"; return
    if MODE=="LIVE":
        try:
            if not real_session_global and not session_id_global:
                alice_login()
                if not real_session_global and not session_id_global: state["reason"]="LIVE FAILED - No Session"; state["live_order"]="FAILED - No Session"; state["in_trade"]=False; return
            strike=round(float(nifty_price)/50)*50; qty=LOT_SIZE*LOTS
            code,body,url=place_order_direct_v2(strike,side,qty)
            state["reason"]=f"LIVE ORDER V14 - NIFTY {strike} {side} x {LOTS} Lot (Qty {qty}) - Status:{code}"; state["live_order"]=f"V14 - URL:{url} Status:{code} Body:{body}"
        except Exception as e: state["reason"]=f"LIVE ORDER FAILED:{e}"; state["live_order"]=f"FAILED:{e}"
trade_done_today=""
def bot_loop():
    global trade_done_today, last_login_try
    while True:
        try:
            ist=get_ist(); state["last_update"]=ist.strftime("%d-%m-%Y %H:%M:%S IST"); today=ist.strftime("%d-%m-%Y")
            if MODE=="LIVE" and not real_session_global and (time.time()-last_login_try>60):
                try: alice_login()
                except: pass
            if trade_done_today!=today and ist.hour<9: trade_done_today=""; state["in_trade"]=False; state["signal"]="WAITING FOR 9:20"; state["reason"]=""; state["candle1"]=""; state["candle2"]=""; state["live_order"]=""
            if ist.hour==9 and ist.minute==25 and trade_done_today!=today:
                state["signal"]="CHECKING 2ND CANDLE..."; df=get_candles()
                if df is not None and len(df)>=2:
                    c1=df.iloc[-2]; c2=df.iloc[-1]
                    try: c1_o=safe_float(c1['Open']); c1_c=safe_float(c1['Close']); c2_o=safe_float(c2['Open']); c2_c=safe_float(c2['Close'])
                    except: state["reason"]="Candle Parse Error"; trade_done_today=today; time.sleep(10); continue
                    c1_color="GREEN" if c1_c>c1_o else "RED"; c2_color="GREEN" if c2_c>c2_o else "RED"
                    state["candle1"]=f"1st {c1_color} O:{c1_o:.1f} C:{c1_c:.1f}"; state["candle2"]=f"2nd {c2_color} O:{c2_o:.1f} C:{c2_c:.1f}"; state["nifty_price"]=round(c2_c,2)
                    if c1_color=="RED" and c2_color=="GREEN": place_trade("CE",c2_c,c2_c)
                    elif c1_color=="GREEN" and c2_color=="RED": place_trade("PE",c2_c,c2_c)
                    else: state["reason"]=f"NO TRADE - NO FLIP - 1st {c1_color} 2nd {c2_color}"; state["signal"]="NO TRADE - NO FLIP"
                    trade_done_today=today
                else: state["reason"]="NO TRADE - Candle Data Not Found"
            elif ist.hour==9 and ist.minute<25: state["signal"]=f"WAITING - Time {ist.strftime('%H:%M')} - Entry at 9:25"
            elif state["in_trade"]: state["signal"]=f"IN TRADE - {state['side']} @ {state['entry']} - {state['mode']}"
            else:
                if not state["reason"]: state["signal"]=f"WAITING - {ist.strftime('%H:%M')}"
            time.sleep(10)
        except Exception as e: print(f"Bot Loop Error:{e}",flush=True); time.sleep(10)
try: threading.Thread(target=bot_loop, daemon=True).start()
except Exception as e: print(f"Thread Error:{e}",flush=True)
@app.route('/')
def home():
    return f"""<h1>ALICE BOT - {state['mode']} - V14 SDK FLOW AES</h1><p>Time: {state['last_update']}</p><p>Login: {state['login']} | Mode: <b>{state['mode']}</b> | Lot: <b>{LOT_SIZE}</b></p><p>Signal: {state['signal']}</p><p>Candle1: {state['candle1']}</p><p>Candle2: {state['candle2']}</p><p>In Trade: {state['in_trade']} Side: {state['side']} Entry: {state['entry']}</p><p>Reason: {state['reason']}</p><p>Live Order: {state['live_order']}</p><p>Test: {state['test_order_result']}</p><p>Session: {state['session_id']}</p><hr><h3 style='color:red'>REAL TEST ORDER - 65 QTY</h3><p><a href='/test-order-confirm' style='background:orange; padding:10px; color:black;'><b>TEST ORDER - NIFTY ATM CE - 65 QTY</b></a></p><hr><p><a href='/force-login'><b>/force-login</b></a> | <a href='/test'>/test - SDK URLs + Raw Paaru</a> | <a href='/status'>STATUS</a></p><hr><h3>DEBUG:</h3><p>{state['debug']}</p><h3>RAW:</h3><p>{state['raw_login']}</p><script>setTimeout(()=>location.reload(),10000)</script>"""
@app.route('/force-login')
def force_login():
    ok=alice_login_v2()
    return f"<h2>Force Login V14 - AES + authCode Flow</h2><p>Result: {state['login']}</p><p>Debug: {state['debug']}</p><hr><h3>RAW:</h3><p>{state['raw_login']}</p><p><a href='/'>Home</a> | <a href='/test-order-confirm'>Test Order</a></p>"
@app.route('/test-order-confirm')
def test_order_confirm():
    nifty=get_nifty_price(); strike=round(float(nifty)/50)*50 if nifty else 0
    return f"""<h2>CONFIRM REAL TEST ORDER</h2><p>Login: {state['login']}</p><p>Nifty: {nifty}</p><p>Strike: {strike} CE - 65 Qty</p><p>Expected: Insufficient Funds - SUCCESS</p><hr><p><a href='/test-order-do' style='background:red; color:white; padding:15px 30px;'><b>YES - REAL TEST ORDER PODU - 65 QTY</b></a></p><br><br><p><a href='/'>NO</a></p>"""
@app.route('/test-order-do')
def test_order_do():
    nifty=get_nifty_price()
    if not nifty: nifty=24950
    strike=round(float(nifty)/50)*50; qty=LOT_SIZE*LOTS
    if MODE=="PAPER": return f"<h2>PAPER</h2><p><a href='/'>Home</a></p>"
    if not real_session_global: alice_login_v2()
    code,body,url=place_order_direct_v2(strike,"CE",qty)
    state["test_order_result"]=f"REAL TEST - NIFTY {strike} CE x {qty} - Status:{code} Body:{body}"; state["live_order"]=state["test_order_result"]
    bl=body.lower()
    if "insufficient" in bl or "margin" in bl or "fund" in bl or "balance" in bl: interp="<h3 style='color:green'>✅ SUCCESS! Order API Correct! Money Mattum Illa!</h3>"
    elif "401" in str(code) or "invalid" in bl: interp="<h3 style='color:red'>❌ FAIL - Session Problem</h3>"
    elif code==200: interp="<h3 style='color:green'>✅ ORDER PLACED!</h3>"
    else: interp=f"<h3>Status {code} - Screenshot Anuppunga</h3>"
    return f"""<h2>REAL TEST ORDER RESULT - V14 - LOT 65</h2><p>Nifty:{nifty} Strike:{strike} CE Qty:{qty}</p><p>URL:{url}</p><p>Status:{code}</p><p>Body:{body}</p><hr>{interp}<hr><p><a href='/'>Home</a></p>"""
@app.route('/test')
def test_encpkey():
    raw, token = sdk_flow_login()
    # SDK URLs Full-a Kaatu
    sdk_urls=""
    try:
        import alice_blue as mod
        sdk_urls=f"Module Attrs: {[x for x in dir(mod) if not x.startswith('_')]}<br>"
        for name in ["AliceBlue_urls","urls","BASE_URL","base_url"]:
            if hasattr(mod,name): sdk_urls+=f"{name}: {getattr(mod,name)}<br>"
        from alice_blue import AliceBlue
        for attr in ["urls","AliceBlue_urls"]:
            if hasattr(AliceBlue,attr): sdk_urls+=f"AliceBlue.{attr}: {getattr(AliceBlue,attr)}<br>"
        import inspect as ins
        fn=getattr(AliceBlue,"login_and_get_sessionID",None)
        if fn:
            try: sdk_urls+=f"<pre>{ins.getsource(fn)[:8000]}</pre>"
            except: pass
    except Exception as e: sdk_urls=f"Err:{e}"
    return f"<h2>Test V14 - SDK Flow Raw + SDK URLs</h2><p>{raw}</p><p>Token: {str(token)[:12] if token else 'NONE'}</p><hr><h3>SDK URLs + Full Source:</h3><p>{sdk_urls}</p><br><a href='/'>Home</a> | <a href='/force-login'>Force Login</a>"
@app.route('/status')
def status(): return jsonify(state)
@app.route('/login')
def login_redirect(): return redirect(f"https://ant.aliceblueonline.com/?appcode={APP_ID}")
@app.route('/callback')
def callback(): return f"<h2>V14 la authCode Thevai Illa - SDK Flow la Auto Edukkum</h2><p><a href='/force-login'>Force Login</a></p>"
@app.route('/setcode', methods=['GET','POST'])
def setcode(): return f"""<h2>V14 - SDK Flow</h2><p>Login: {state['login']}</p><p><a href='/force-login'>Force Login</a> | <a href='/'>Home</a></p>"""
if __name__=='__main__':
    port=int(os.environ.get("PORT",10000)); print(f"Starting PORT {port} MODE {MODE}",flush=True); app.run(host='0.0.0.0', port=port)
