import os, time, traceback, hashlib, json, base64, glob, tempfile
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify, request, redirect
import threading
import yfinance as yf
import requests
from urllib.parse import urlparse, parse_qs
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

HOST="https://ant.aliceblueonline.com/rest/AliceBlueAPIService"
HOST2="https://v2api.aliceblueonline.com/restpy"
URLS={
  "getEncpkey": f"{HOST}/sso/getEncryptionKey",
  "webLogin": f"{HOST}/sso/webLogin",
  "twoFA": f"{HOST}/sso/validUserDetails",
  "apiGetEncpkey": f"{HOST}/sso/getEncpkey",
  "sessionID": f"{HOST}/sso/authorize/getSession",
  "placeOrder": f"{HOST}/api/placeOrder/executePlaceOrder",
}

state={"strategy":"NIFTY_2ND_CANDLE_FLIP","mode":MODE,"login":"STARTING...","nifty_price":0,"signal":"WAITING FOR 9:20","in_trade":False,"side":"","entry":0,"pnl":0,"reason":"","last_update":"","candle1":"","candle2":"","live_order":"","debug":"Waiting...","session_id":"","real_session":"","api_version":"V23_RAW_DEBUG","test_order_result":"","lot_size":LOT_SIZE,"raw_login":""}

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

def my_aes(plain_str, key_str):
    try:
        salt=get_random_bytes(8)
        key=hashlib.sha256(key_str.encode()+salt).digest()
        iv=hashlib.md5(key_str.encode()+salt).digest()
        cipher=AES.new(key, AES.MODE_CBC, iv)
        ct=cipher.encrypt(pad(plain_str.encode(), AES.block_size))
        return base64.b64encode(b"Salted__"+salt+ct).decode()
    except Exception as e:
        print(f"AES Fail {e}",flush=True)
        return None

def sdk_aes(plain_str, key_str):
    try:
        import alice_blue as mod
        CryptoJS=getattr(mod,"CryptoJS",None)
        if CryptoJS is not None:
            aes_obj=getattr(CryptoJS,"AES",None)
            if aes_obj is not None and hasattr(aes_obj,"encrypt"):
                try:
                    r=aes_obj.encrypt(plain_str, key_str)
                    if isinstance(r,bytes): return r.decode()
                    if isinstance(r,str) and len(r)>20: return r
                except: pass
                try:
                    r=aes_obj.encrypt(plain_str.encode(), key_str.encode())
                    if isinstance(r,bytes): return r.decode()
                    if isinstance(r,str) and len(r)>20: return r
                except: pass
    except Exception as e:
        print(f"SDK AES Fail {e}",flush=True)
    return my_aes(plain_str, key_str)

def safe_post(url, payload, use_json=True):
    # Raw response-a thiruppi tharum - JSON crash aagadhu
    try:
        headers={"Content-Type":"application/json","User-Agent":"Mozilla/5.0","Accept":"application/json"}
        if use_json:
            r=requests.post(url, json=payload, headers=headers, timeout=20)
        else:
            r=requests.post(url, data=json.dumps(payload), headers=headers, timeout=20)
        txt=r.text or ""
        return r.status_code, txt[:1000], r.headers.get("Content-Type","")
    except Exception as e:
        return 0, f"REQUEST ERR: {e}", ""

def sdk_flow_login():
    out=[]
    totp_now=get_totp()
    out.append(f"USER:{USER_ID} APP:{APP_ID} DOB:{DOB_YEAR} TOTP:{totp_now} MODE:{MODE}")
    # 0. Server Uyirla Irukka-nu Check - Idhu thaan Mukkiyam
    for name, url in [("HOST",HOST),("HOST2",HOST2)]:
        try:
            r=requests.get(url, timeout=10)
            out.append(f"CHECK {name} GET {url} Status:{r.status_code} Len:{len(r.text)} Body:{r.text[:300]}")
        except Exception as e:
            out.append(f"CHECK {name} Fail:{e}")
    header={"Content-Type":"application/json"}
    for tfa_label, tfa_val in [("DOB",DOB_YEAR),("TOTP",totp_now)]:
        if not tfa_val: continue
        try:
            out.append(f"<b>=== TRY {tfa_label}={tfa_val} ===</b>")
            # STEP1 - getEncpkey - RAW paaru
            code, txt, ctype = safe_post(URLS["getEncpkey"], {"userId":USER_ID}, True)
            out.append(f"STEP1 getEncpkey Status:{code} ContentType:{ctype} Len:{len(txt)} Body:{txt[:600]}")
            print(f"STEP1 {code} {txt[:600]}",flush=True)
            if code!=200 or not txt.strip().startswith("{"):
                out.append(f"STEP1 FAIL - Server JSON tharala. Body empty-a? Cloudflare block-a? Next Try")
                # HOST2 try
                code2, txt2, _ = safe_post(f"{HOST2}/getEncryptionKey", {"userId":USER_ID}, True)
                out.append(f"STEP1 HOST2 Status:{code2} Body:{txt2[:400]}")
                continue
            try: j1=json.loads(txt)
            except: continue
            encKey=j1.get("encKey") or j1.get("encpkey") or ""
            if not encKey:
                out.append(f"STEP1 encKey Illa Keys:{list(j1.keys())}")
                continue
            out.append(f"STEP1 encKey OK:{str(encKey)[:10]}***")
            # STEP2
            checksum=sdk_aes(PASSWORD, str(encKey))
            if not checksum:
                out.append("STEP2 AES Fail")
                continue
            out.append(f"STEP2 AES OK Len:{len(checksum)} Start:{str(checksum)[:20]}")
            data2={"userId":USER_ID,"userData":checksum,"twoFA":str(tfa_val),"app_id":APP_ID,"api_secret":APP_SECRET}
            code, txt, _ = safe_post(URLS["webLogin"], data2, True)
            out.append(f"STEP2 webLogin Status:{code} Len:{len(txt)} Body:{txt[:800]}")
            print(f"STEP2 {code} {txt[:800]}",flush=True)
            if code!=200 or not txt.strip().startswith("{"):
                out.append("STEP2 FAIL - Server JSON tharala")
                continue
            # STEP3
            data3={"answer":str(tfa_val),"count":"1","vendor":APP_ID,"userId":USER_ID}
            code, txt, _ = safe_post(URLS["twoFA"], data3, True)
            out.append(f"STEP3 twoFA Status:{code} Len:{len(txt)} Body:{txt[:800]}")
            print(f"STEP3 {code} {txt[:800]}",flush=True)
            if code!=200 or not txt.strip().startswith("{"): continue
            try: j3=json.loads(txt)
            except: continue
            out.append(f"STEP3 Keys:{list(j3.keys())} isAuthorized:{j3.get('isAuthorized')}")
            if not j3.get("isAuthorized"):
                out.append(f"STEP3 isAuthorized False - Password/DOB Thappu. Full:{j3}")
                continue
            ru=j3.get("redirectUrl") or ""
            auth_code=""
            if ru:
                try:
                    q=parse_qs(urlparse(ru).query)
                    if "authCode" in q: auth_code=q["authCode"][0]
                except: pass
            if not auth_code: auth_code=j3.get("authCode") or ""
            if not auth_code:
                out.append(f"STEP3 authCode Illa Full:{j3}")
                continue
            out.append(f"STEP3 authCode OK:{auth_code[:12]}***")
            # STEP4
            code, txt, _ = safe_post(URLS["apiGetEncpkey"], {"userId":USER_ID}, False)
            out.append(f"STEP4 apiGetEncpkey Status:{code} Body:{txt[:300]}")
            # STEP5
            checksum2=hashlib.sha256(f"{USER_ID}{auth_code}{APP_SECRET}".encode()).hexdigest()
            code, txt, _ = safe_post(URLS["sessionID"], {"checksum":checksum2}, False)
            out.append(f"STEP5 sessionID Status:{code} Body:{txt[:800]}")
            print(f"STEP5 {code} {txt[:800]}",flush=True)
            if code!=200 or not txt.strip().startswith("{"): continue
            try: j5=json.loads(txt)
            except: continue
            sess=j5.get("session_id") or j5.get("sessionId") or j5.get("sessionID")
            if sess and len(str(sess))>10:
                out.append(f"<b style='color:green'>SUCCESS! Session:{str(sess)[:12]}*** via {tfa_label}</b>")
                return "<br>".join(out), str(sess)
            else:
                out.append(f"STEP5 Session Illa JSON:{j5}")
                continue
        except Exception as e:
            out.append(f"TRY {tfa_label} Err:{e} {traceback.format_exc()[:600]}")
            continue
    return "<br>".join(out), None

def alice_login_v2():
    global session_id_global, real_session_global, last_login_try
    last_login_try=time.time()
    try:
        # Manual session irundha adha use pannu - Login thevai illa
        if real_session_global and is_valid_key(real_session_global):
            state["login"]=f"LIVE READY - Manual Session - User {USER_ID[:3]}***"
            return True
        raw, token = sdk_flow_login()
        state["raw_login"]=raw
        state["debug"]=f"V23 RAW USER:{USER_ID} DOB:{DOB_YEAR} TOTP:{get_totp()}"
        if token and is_valid_key(token):
            session_id_global=token; real_session_global=token
            state["session_id"]=token[:12]+"***"; state["real_session"]=token[:12]+"***"
            state["login"]=f"LIVE READY V23 - User {USER_ID[:3]}*** - LOT 65"
            return True
        state["login"]=f"LOGIN FAIL - /test la STEP1 Body Paaru - Server Enna Tharudhu?"
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
    try:
        r=requests.post(URLS["placeOrder"], json=payload, headers=headers, timeout=20)
        return r.status_code, r.text[:800], URLS["placeOrder"]
    except Exception as e:
        return 0, str(e), URLS["placeOrder"]
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
            state["reason"]=f"LIVE ORDER V23 - NIFTY {strike} {side} x {LOTS} Lot (Qty {qty}) - Status:{code}"; state["live_order"]=f"V23 - URL:{url} Status:{code} Body:{body}"
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
    return f"""<h1>ALICE BOT - {state['mode']} - V23 RAW DEBUG</h1><p>Time: {state['last_update']}</p><p>Login: {state['login']} | Mode: <b>{state['mode']}</b> | Lot: <b>{LOT_SIZE}</b></p><p>Signal: {state['signal']}</p><p>Candle1: {state['candle1']}</p><p>Candle2: {state['candle2']}</p><p>In Trade: {state['in_trade']} Side: {state['side']} Entry: {state['entry']}</p><p>Reason: {state['reason']}</p><p>Live Order: {state['live_order']}</p><p>Test: {state['test_order_result']}</p><p>Session: {state['session_id']}</p><hr><h3 style='color:red'>REAL TEST ORDER - 65 QTY</h3><p><a href='/test-order-confirm' style='background:orange; padding:10px; color:black;'><b>TEST ORDER - NIFTY ATM CE - 65 QTY</b></a></p><hr><p><a href='/force-login'><b>/force-login</b></a> | <a href='/test'>/test</a> | <a href='/status'>STATUS</a> | <a href='/set-session'>Manual Session Paste</a></p><hr><h3>DEBUG:</h3><p>{state['debug']}</p><h3>RAW:</h3><p>{state['raw_login']}</p><script>setTimeout(()=>location.reload(),10000)</script>"""
@app.route('/force-login')
def force_login():
    ok=alice_login_v2()
    return f"<h2>Force Login V23</h2><p>Result: {state['login']}</p><p>Debug: {state['debug']}</p><hr><h3>RAW:</h3><p>{state['raw_login']}</p><p><a href='/'>Home</a> | <a href='/test-order-confirm'>Test Order</a></p>"
@app.route('/set-session')
def set_session_page():
    sess=request.args.get("s","").strip()
    if sess and len(sess)>10:
        global session_id_global, real_session_global
        session_id_global=sess; real_session_global=sess
        state["session_id"]=sess[:12]+"***"; state["real_session"]=sess[:12]+"***"
        state["login"]=f"LIVE READY - Manual Session - User {USER_ID[:3]}***"
        return f"<h2>Manual Session Saved ✅</h2><p>Session: {sess[:12]}***</p><p><a href='/'>Home</a> | <a href='/test-order-confirm'>Test Order</a></p>"
    return f"""<h2>Manual Session Paste - Login Bypass</h2><p>Login work aagalana idha use pannunga. Browser la AliceBlue login pannitu session_id-a inga paste pannunga.</p><form><input name='s' placeholder='session_id paste pannunga' style='width:400px;padding:10px'><br><br><button style='padding:10px 20px;background:green;color:white'>SAVE SESSION</button></form><p><a href='/'>Home</a></p>"""
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
    return f"""<h2>REAL TEST ORDER RESULT - V23 - LOT 65</h2><p>Nifty:{nifty} Strike:{strike} CE Qty:{qty}</p><p>URL:{url}</p><p>Status:{code}</p><p>Body:{body}</p><hr>{interp}<hr><p><a href='/'>Home</a></p>"""
@app.route('/test')
def test_encpkey():
    raw, token = sdk_flow_login()
    return f"<h2>Test V23 - Raw Debug</h2><p>{raw}</p><p>Token: {str(token)[:12] if token else 'NONE'}</p><br><a href='/'>Home</a> | <a href='/force-login'>Force Login</a> | <a href='/set-session'>Manual Session</a>"
@app.route('/status')
def status(): return jsonify(state)
@app.route('/login')
def login_redirect(): return redirect(f"https://ant.aliceblueonline.com/?appcode={APP_ID}")
@app.route('/callback')
def callback(): return f"<h2>V23</h2><p><a href='/force-login'>Force Login</a></p>"
@app.route('/setcode', methods=['GET','POST'])
def setcode(): return f"""<h2>V23</h2><p>Login: {state['login']}</p><p><a href='/force-login'>Force Login</a> | <a href='/'>Home</a></p>"""
if __name__=='__main__':
    port=int(os.environ.get("PORT",10000)); print(f"Starting PORT {port} MODE {MODE}",flush=True); app.run(host='0.0.0.0', port=port)
