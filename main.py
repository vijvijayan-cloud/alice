import os, time, traceback, hashlib, json
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify, request, redirect
import threading
import yfinance as yf
import requests

app = Flask(__name__)

def clean_env(name):
    v = os.getenv(name, "")
    return v.strip().replace(" ", "").replace("\n", "").replace("\r", "").replace('"', "").replace("'", "")

USER_ID = clean_env("ALICE_USER_ID")
PASSWORD = clean_env("ALICE_PASSWORD")
TOTP_SECRET = clean_env("ALICE_TOTP_SECRET")
APP_ID = clean_env("ALICE_APP_ID")
APP_SECRET = clean_env("ALICE_APP_SECRET")
DOB_YEAR = clean_env("ALICE_YEAR") or clean_env("ALICE_DOB_YEAR") or clean_env("ALICE_2FA") or clean_env("ALICE_TWOFA")
AUTH_CODE = clean_env("ALICE_AUTH_CODE")
MODE = os.getenv("MODE", "PAPER")
try: LOTS = int(os.getenv("LOTS", "1"))
except: LOTS = 1
LOT_SIZE = 65

state = {"strategy":"NIFTY_2ND_CANDLE_FLIP","mode":MODE,"login":"STARTING...","nifty_price":0,"signal":"WAITING FOR 9:20","in_trade":False,"side":"","entry":0,"pnl":0,"reason":"","last_update":"","candle1":"","candle2":"","live_order":"","debug":"Waiting...","session_id":"","real_session":"","api_version":"V7_OFFICIAL_SDK","login_url":"","auth_code":"","test_order_result":"","lot_size":LOT_SIZE}

def get_ist():
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)

session_id_global = ""
real_session_global = ""
enc_key_global = ""
base_url_global = "https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/"
auth_code_global = AUTH_CODE
last_login_try = 0

def is_valid_key(k):
    if not k: return False
    k=str(k).strip()
    if k.lower() in ["null","none","","no","available"]: return False
    return True

def alice_login_v2():
    global session_id_global, real_session_global, last_login_try
    last_login_try=time.time()
    # V7: Official SDK - login_and_get_access_token(username, password, twoFA, api_secret, app_id)
    # Idhu Ulla Encpkey + SHA + getSessionID Ella Correct-a Pannidum
    try:
        print(f"V7 SDK LOGIN TRY USER:{USER_ID} APP_ID:{APP_ID} SECRET_LEN:{len(APP_SECRET)} 2FA_LEN:{len(DOB_YEAR)}", flush=True)
        state["debug"] = f"SDK Login Try USER:{USER_ID} APP_ID:{APP_ID} SECRET_LEN:{len(APP_SECRET)} 2FA:{DOB_YEAR[:2]}***"
        if not USER_ID or not PASSWORD or not APP_SECRET or not APP_ID:
            state["login"] = "NEED CREDENTIALS - Render la ALICE_USER_ID / PASSWORD / APP_ID / APP_SECRET Check pannunga"
            return False
        if not DOB_YEAR:
            state["login"] = "NEED 2FA - Render la ALICE_YEAR = Birth Year (eg 1990) Podunga - 2FA = Year of Birth"
            return False
        try:
            from alice_blue import AliceBlue
        except Exception as e:
            state["login"] = f"SDK NOT INSTALLED - requirements.txt la alice-blue Podunga - Error:{e}"
            state["debug"] += f" | SDK Import Fail:{e}"
            return False
        # SDK Call - Idhu thaan Correct Method
        token = AliceBlue.login_and_get_access_token(username=USER_ID, password=PASSWORD, twoFA=DOB_YEAR, api_secret=APP_SECRET, app_id=APP_ID)
        print(f"SDK Token Got:{str(token)[:30]}*** Len:{len(str(token))}", flush=True)
        state["debug"] += f" | SDK Token Len:{len(str(token))} Token:{str(token)[:20]}***"
        if not token or not is_valid_key(str(token)):
            state["login"] = f"SDK TOKEN EMPTY - Password / 2FA / App Secret Thappu - Token:{token}"
            return False
        session_id_global = str(token)
        real_session_global = str(token)
        state["session_id"] = str(token)[:12]+"***"
        state["real_session"] = str(token)[:12]+"***"
        state["login"] = f"LIVE READY V7 - User {USER_ID[:3]}*** - LOT 65 - OFFICIAL SDK TOKEN OK"
        print("V7 LOGIN SUCCESS", flush=True)
        return True
    except Exception as e:
        err = str(e)
        print(f"V7 SDK LOGIN FAIL: {err}", flush=True)
        print(traceback.format_exc(), flush=True)
        state["debug"] += f" | SDK Fail:{err[:500]}"
        # Common Errors - User ku Puriyura Maadhiri
        if "Invalid" in err or "invalid" in err:
            state["login"] = f"SDK LOGIN FAIL - Password / 2FA / App Secret Thappu - Error:{err[:200]}"
        elif "2FA" in err or "twoFA" in err or "Year" in err:
            state["login"] = f"SDK LOGIN FAIL - 2FA Thappu - ALICE_YEAR = Birth Year Correct-a? Error:{err[:200]}"
        else:
            state["login"] = f"SDK LOGIN FAIL - {err[:300]}"
        return False

def alice_login():
    if MODE=="PAPER":
        state["login"]=f"PAPER READY - User {USER_ID[:3]}***"; return True
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
    ist=get_ist(); d=ist.date()
    days_ahead=(3-d.weekday())%7
    if days_ahead==0 and ist.hour>=15: days_ahead=7
    return d+timedelta(days=days_ahead)

def get_nifty_price():
    try:
        df=yf.download("^NSEI", interval="1m", period="1d", progress=False, auto_adjust=False)
        if df is not None and len(df)>0: return safe_float(df.iloc[-1]['Close'])
    except: pass
    return 0

def place_order_direct_v2(strike, side, qty):
    exp=get_expiry_date(); exp_str=exp.strftime("%d-%b-%Y").upper()
    sess=real_session_global if real_session_global else session_id_global
    headers={"Content-Type":"application/json","Authorization":f"Bearer {USER_ID} {sess}","userId":USER_ID,"sessionId":sess}
    payload={"userId":USER_ID,"sessionId":sess,"tradingSymbol":f"NIFTY {strike} {side}","exchange":"NFO","transactionType":"BUY","orderType":"MARKET","productType":"MIS","quantity":qty,"price":"0","triggerPrice":"0","expiry":exp_str,"strike":str(strike),"optionType":side}
    urls=[base_url_global+"placeOrder/executePlaceOrder",base_url_global+"placeOrder/placeOrder"]
    last_body=""; last_code=0
    for url in urls:
        try:
            print(f"TRY ORDER URL:{url} Payload:{payload}",flush=True)
            r=requests.post(url, json=payload, headers=headers, timeout=20)
            print(f"Order URL:{url} Status:{r.status_code} Body:{r.text[:800]}",flush=True)
            last_code=r.status_code; last_body=r.text[:800]
            if r.status_code==200: return r.status_code,r.text[:800],url
            if r.status_code!=404: return r.status_code,r.text[:800],url
        except Exception as e: last_body=str(e)
    return last_code,last_body,urls[-1]

def place_trade(side, price, nifty_price):
    state["in_trade"]=True; state["side"]=side; state["entry"]=round(float(price),2); state["nifty_price"]=round(float(nifty_price),2)
    if MODE=="PAPER":
        state["reason"]=f"PAPER TRADE - {side} @ {price}"; state["live_order"]="PAPER - No Order Sent"; return
    if MODE=="LIVE":
        try:
            if not real_session_global and not session_id_global:
                alice_login()
                if not real_session_global and not session_id_global:
                    state["reason"]="LIVE FAILED - No Session"; state["live_order"]="FAILED - No Session"; state["in_trade"]=False; return
            strike=round(float(nifty_price)/50)*50; qty=LOT_SIZE*LOTS
            code,body,url=place_order_direct_v2(strike,side,qty)
            state["reason"]=f"LIVE ORDER V7 - NIFTY {strike} {side} x {LOTS} Lot (Qty {qty}) - Status:{code}"
            state["live_order"]=f"V7 - URL:{url} Status:{code} Body:{body}"
        except Exception as e:
            state["reason"]=f"LIVE ORDER FAILED:{e}"; state["live_order"]=f"FAILED:{e}"; print(traceback.format_exc(),flush=True)

trade_done_today=""
def bot_loop():
    global trade_done_today, last_login_try
    while True:
        try:
            ist=get_ist(); state["last_update"]=ist.strftime("%d-%m-%Y %H:%M:%S IST"); today=ist.strftime("%d-%m-%Y")
            if MODE=="LIVE" and not real_session_global and (time.time()-last_login_try>60):
                try: alice_login()
                except: pass
            if trade_done_today!=today and ist.hour<9:
                trade_done_today=""; state["in_trade"]=False; state["signal"]="WAITING FOR 9:20"; state["reason"]=""; state["candle1"]=""; state["candle2"]=""; state["live_order"]=""
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
    return f"""
    <h1>ALICE BOT - NIFTY 2ND CANDLE FLIP - {state['mode']} - V7 OFFICIAL SDK</h1>
    <p>Time: {state['last_update']}</p><p>Login: {state['login']} | Mode: <b>{state['mode']}</b> | Lot: <b>{LOT_SIZE}</b></p>
    <p>Signal: {state['signal']}</p><p>Candle1: {state['candle1']}</p><p>Candle2: {state['candle2']}</p>
    <p>In Trade: {state['in_trade']} Side: {state['side']} Entry: {state['entry']}</p><p>Reason: {state['reason']}</p><p>Live Order: {state['live_order']}</p><p>Test: {state['test_order_result']}</p><p>Session: {state['session_id']}</p>
    <hr><h3 style='color:red'>REAL TEST ORDER - NO MONEY TEST - 65 QTY</h3>
    <p><a href='/test-order-confirm' style='background:orange; padding:10px; color:black;'><b>TEST ORDER - NIFTY ATM CE - 65 QTY</b></a></p>
    <hr><p><a href='/force-login'><b>/force-login - SDK Login</b></a> | <a href='/test'>/test</a> | <a href='/status'>STATUS</a></p>
    <hr><h3>DEBUG:</h3><p>{state['debug']}</p><p>USER:{USER_ID} APP_ID:{APP_ID} SECRET_LEN:{len(APP_SECRET)} 2FA_LEN:{len(DOB_YEAR)} PASS_LEN:{len(PASSWORD)}</p>
    <script>setTimeout(()=>location.reload(),10000)</script>
    """

@app.route('/login')
def login_redirect(): return redirect(f"https://ant.aliceblueonline.com/?appcode={APP_ID}")

@app.route('/callback')
def callback():
    global auth_code_global
    code=request.args.get("authCode") or ""
    if code and is_valid_key(code): auth_code_global=code; ok=alice_login_v2(); return f"<h2>Login: {state['login']}</h2><p>{state['debug']}</p><p><a href='/'>Home</a></p>"
    return f"<h2>No authCode - SDK Method la authCode Thevai Illa - /force-login Click pannunga</h2><p><a href='/force-login'>Force Login</a></p>"

@app.route('/setcode', methods=['GET','POST'])
def setcode():
    return f"""<h2>V7 la authCode Thevai Illa - SDK Method</h2><p>Login: {state['login']}</p><p>Render la Iva Irukka nu Paaru: ALICE_USER_ID, ALICE_PASSWORD, ALICE_YEAR (Birth Year), ALICE_APP_ID, ALICE_APP_SECRET</p><p><a href='/force-login'>Force Login</a> | <a href='/'>Home</a></p>"""

@app.route('/force-login')
def force_login():
    ok=alice_login_v2()
    return f"<h2>Force Login V7 SDK</h2><p>Result: {state['login']}</p><p>Debug: {state['debug']}</p><p>USER:{USER_ID} APP_ID:{APP_ID} SECRET_LEN:{len(APP_SECRET)} 2FA_LEN:{len(DOB_YEAR)} PASS_LEN:{len(PASSWORD)}</p><p><a href='/'>Home</a> | <a href='/test-order-confirm'>Test Order</a></p>"

@app.route('/test-order-confirm')
def test_order_confirm():
    nifty=get_nifty_price(); strike=round(float(nifty)/50)*50 if nifty else 0
    return f"""<h2 style='color:red'>CONFIRM REAL TEST ORDER - NO MONEY TEST</h2><p>Login: {state['login']}</p><p>Nifty: {nifty}</p><p>Strike: {strike} CE - 65 Qty - MIS - MARKET</p><p>Expected: Insufficient Funds - SUCCESS</p><hr><p><a href='/test-order-do' style='background:red; color:white; padding:15px 30px;'><b>YES - REAL TEST ORDER PODU - 65 QTY</b></a></p><br><br><p><a href='/'>NO</a></p>"""

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
    return f"""<h2>REAL TEST ORDER RESULT - V7 - LOT 65</h2><p>Nifty:{nifty} Strike:{strike} CE Qty:{qty}</p><p>URL:{url}</p><p>Status:{code}</p><p>Body:{body}</p><hr>{interp}<hr><p><a href='/'>Home</a></p>"""

@app.route('/test')
def test_encpkey():
    out=[f"<p>USER:{USER_ID} APP_ID:{APP_ID} SECRET_LEN:{len(APP_SECRET)} 2FA_LEN:{len(DOB_YEAR)} PASS_LEN:{len(PASSWORD)}</p>"]
    try:
        from alice_blue import AliceBlue
        out.append("<p>SDK Installed: YES</p>")
        # SDK Login Try - Real Error Kaatum
        try:
            t=AliceBlue.login_and_get_access_token(username=USER_ID, password=PASSWORD, twoFA=DOB_YEAR, api_secret=APP_SECRET, app_id=APP_ID)
            out.append(f"<p style='color:green'>SDK LOGIN SUCCESS Token:{str(t)[:30]}*** Len:{len(str(t))}</p>")
        except Exception as e:
            out.append(f"<p style='color:red'>SDK LOGIN FAIL: {e}</p>")
    except Exception as e: out.append(f"<p style='color:red'>SDK NOT INSTALLED: {e} - requirements.txt la alice-blue Podunga</p>")
    return "<h2>Test V7 SDK</h2>"+"".join(out)+"<br><a href='/'>Home</a> | <a href='/force-login'>Force Login</a>"

@app.route('/status')
def status(): return jsonify(state)

if __name__=='__main__':
    port=int(os.environ.get("PORT",10000)); print(f"Starting PORT {port} MODE {MODE}",flush=True); app.run(host='0.0.0.0', port=port)
