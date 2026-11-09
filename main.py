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
DOB_YEAR = clean_env("ALICE_YEAR") or clean_env("ALICE_DOB_YEAR") or clean_env("ALICE_2FA")
AUTH_CODE = clean_env("ALICE_AUTH_CODE")
MODE = os.getenv("MODE", "PAPER")
try:
    LOTS = int(os.getenv("LOTS", "1"))
except:
    LOTS = 1
LOT_SIZE = 65

state = {"strategy":"NIFTY_2ND_CANDLE_FLIP","mode":MODE,"login":"STARTING...","nifty_price":0,"signal":"WAITING FOR 9:20","in_trade":False,"side":"","entry":0,"pnl":0,"reason":"","last_update":"","candle1":"","candle2":"","live_order":"","debug":"Waiting...","session_id":"","real_session":"","api_version":"V6_SHA256_REAL_SESSION","login_url":"","auth_code":"","test_order_result":"","lot_size":LOT_SIZE}

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
    if k.lower() in ["null","none","","no","available","no available"]: return False
    return True

def try_encpkey():
    global base_url_global, enc_key_global
    base = "https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/"
    try:
        r = requests.post(base + "customer/getAPIEncpkey", json={"userId": USER_ID}, timeout=10, headers={"Content-Type":"application/json"})
        print(f"Encpkey St:{r.status_code} Body:{r.text[:600]}", flush=True)
        state["debug"] = f"Encpkey St:{r.status_code} Body:{r.text[:250]}"
        if r.status_code==200 and r.text.strip():
            try: j=r.json()
            except: return "",base,"JSON Fail"
            enc=j.get("encKey") or ""
            if not is_valid_key(enc): return "",base,j.get("emsg") or "Encpkey NULL"
            enc_key_global=enc; base_url_global=base
            return enc,base,"OK"
    except Exception as e:
        state["debug"]=f"Encpkey Err:{e}"
    return "",base,"Fail"

def alice_login_v2():
    global session_id_global, real_session_global, enc_key_global, base_url_global, last_login_try
    last_login_try=time.time()
    try:
        state["login_url"]=f"https://ant.aliceblueonline.com/?appcode={APP_ID}"
        enc_key,base,msg=try_encpkey()
        if not enc_key:
            state["login"]=f"NEED WEB LOGIN - {msg}"; return False
        if not APP_SECRET or not is_valid_key(APP_SECRET):
            state["login"]="NEED APP_SECRET - Render la ALICE_APP_SECRET Check pannunga - App Secret Illana Session Varadhu"; return False
        # V6 FIX: SHA-256 - USER_ID + APP_SECRET + ENCKEY = Session Hash
        # Alice Official SDK Method - authCode Thevai Illa
        combos=[
            f"{USER_ID}{APP_SECRET}{enc_key}",
            f"{USER_ID}{enc_key}{APP_SECRET}",
            f"{USER_ID}{APP_SECRET}",
        ]
        real=""
        last_resp=""
        for idx,combo in enumerate(combos):
            h=hashlib.sha256(combo.encode()).hexdigest()
            print(f"TRY SHA Combo {idx} Hash:{h[:20]}***", flush=True)
            try:
                payload={"userId":USER_ID,"userData":h}
                r2=requests.post(base+"customer/getSessionID", json=payload, timeout=10, headers={"Content-Type":"application/json"})
                print(f"getSessionID Combo{idx} St:{r2.status_code} Body:{r2.text[:600]}", flush=True)
                state["debug"]+=f" | Combo{idx} St:{r2.status_code} Body:{r2.text[:200]}"
                last_resp=r2.text[:500]
                if r2.status_code==200 and r2.text.strip():
                    try:
                        j2=r2.json()
                        cand=j2.get("sessionId") or j2.get("sessionID") or j2.get("token") or j2.get("accessToken") or j2.get("userSession") or ""
                        # Error case la sessionId Illadha Irukkum
                        if is_valid_key(cand) and len(str(cand))>10:
                            real=str(cand); break
                        # Stat / emsg check - Success nu Irundha
                        if j2.get("stat")=="Ok" or j2.get("status")=="success":
                            if cand: real=str(cand); break
                    except: pass
            except Exception as e:
                print(f"Combo {idx} Err:{e}", flush=True)
        if not real:
            state["login"]=f"SESSION FAIL - SHA Hash Work Aagala - Last:{last_resp[:200]} - APP_SECRET Check pannunga"
            state["session_id"]=""; state["real_session"]=""
            return False
        session_id_global=real; real_session_global=real
        state["session_id"]=real[:12]+"***"; state["real_session"]=real[:12]+"***"
        state["login"]=f"LIVE READY V6 - User {USER_ID[:3]}*** - LOT 65 - SHA256 SESSION OK"
        print(f"LOGIN SUCCESS V6 - Real Session:{real[:12]}***", flush=True)
        return True
    except Exception as e:
        state["debug"]+=f" | V6 Exception:{e}"; print(traceback.format_exc(), flush=True); return False

def alice_login():
    if MODE=="PAPER":
        state["login"]=f"PAPER READY - User {USER_ID[:3]}***"; return True
    return alice_login_v2()

def get_candles():
    try:
        df=yf.download("^NSEI", interval="5m", period="1d", progress=False, auto_adjust=False)
        if df is None or df.empty: return None
        return df
    except Exception as e:
        print("Candle Error:",e,flush=True); return None

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
            state["reason"]=f"LIVE ORDER V6 - NIFTY {strike} {side} x {LOTS} Lot (Qty {qty}) - Status:{code}"
            state["live_order"]=f"V6 - URL:{url} Status:{code} Body:{body}"
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
                    try:
                        c1_o=safe_float(c1['Open']); c1_c=safe_float(c1['Close']); c2_o=safe_float(c2['Open']); c2_c=safe_float(c2['Close'])
                    except:
                        state["reason"]="Candle Parse Error"; trade_done_today=today; time.sleep(10); continue
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
    <h1>ALICE BOT - NIFTY 2ND CANDLE FLIP - {state['mode']} - V6 SHA256</h1>
    <p>Time: {state['last_update']}</p><p>Login: {state['login']} | Mode: <b>{state['mode']}</b> | Lot: <b>{LOT_SIZE}</b></p>
    <p>Signal: {state['signal']}</p><p>Candle1: {state['candle1']}</p><p>Candle2: {state['candle2']}</p>
    <p>In Trade: {state['in_trade']} Side: {state['side']} Entry: {state['entry']}</p><p>Reason: {state['reason']}</p><p>Live Order: {state['live_order']}</p><p>Test: {state['test_order_result']}</p><p>Session: {state['session_id']} | Real: {state['real_session']}</p>
    <hr><h3 style='color:red'>REAL TEST ORDER - NO MONEY TEST - 65 QTY</h3>
    <p><a href='/test-order-confirm' style='background:orange; padding:10px; color:black;'><b>TEST ORDER - NIFTY ATM CE - 65 QTY</b></a></p>
    <hr><h3>LOGIN:</h3><p><a href='/force-login'><b>/force-login - SHA256 Login Try pannu</b></a> | <a href='/login'>/login</a> | <a href='/setcode'>/setcode</a></p>
    <hr><p><a href='/test'>/test</a> | <a href='/status'>STATUS</a></p><hr><h3>DEBUG:</h3><p>{state['debug']}</p>
    <script>setTimeout(()=>location.reload(),10000)</script>
    """

@app.route('/login')
def login_redirect():
    return redirect(f"https://ant.aliceblueonline.com/?appcode={APP_ID}")

@app.route('/callback')
def callback():
    global auth_code_global
    code=request.args.get("authCode") or request.args.get("authcode") or request.args.get("code") or ""
    if code and "authCode=" in code: code=code.split("authCode=")[-1].split("&")[0]
    if code and is_valid_key(code):
        auth_code_global=code.strip(); state["auth_code"]=code[:12]+"***"; ok=alice_login_v2()
        return f"<h2>authCode: {code[:15]}***</h2><p>Login: {state['login']}</p><p>Debug: {state['debug']}</p><p><a href='/'>Home</a></p>"
    return f"<h2>No authCode</h2><p>{dict(request.args)}</p><p><a href='/setcode'>/setcode</a></p>"

@app.route('/setcode', methods=['GET','POST'])
def setcode():
    global auth_code_global
    if request.method=='POST':
        code=request.form.get("authCode") or ""; code=code.strip()
        if "authCode=" in code: code=code.split("authCode=")[-1].split("&")[0].split()[0]
        if not code or not is_valid_key(code): return f"<h2>authCode Thappu</h2><p><a href='/setcode'>Try Again</a></p>"
        auth_code_global=code; state["auth_code"]=code[:12]+"***"; ok=alice_login_v2()
        return f"<h2>Set: {code[:15]}***</h2><p>Login: {state['login']}</p><p>Debug: {state['debug']}</p><p><a href='/'>Home</a></p>"
    code=request.args.get("authCode") or ""
    if code:
        if "authCode=" in code: code=code.split("authCode=")[-1].split("&")[0]
        if is_valid_key(code):
            auth_code_global=code; state["auth_code"]=code[:12]+"***"; ok=alice_login_v2()
            return f"<h2>Set: {code[:15]}***</h2><p>Login: {state['login']}</p><p>Debug: {state['debug']}</p><p><a href='/'>Home</a></p>"
    return f"""<h2>authCode Podunga</h2><p>Login: {state['login']}</p><form method="POST" action="/setcode"><input type="text" name="authCode" placeholder="authCode" style="width:90%; padding:12px;" required><br><br><button type="submit" style="padding:12px 30px; background:green; color:white;">LOGIN</button></form><p><a href='/'>Home</a></p>"""

@app.route('/force-login')
def force_login():
    ok=alice_login_v2()
    return f"<h2>Force Login V6 SHA256</h2><p>Result: {state['login']}</p><p>Debug: {state['debug']}</p><p><a href='/'>Home</a> | <a href='/test-order-confirm'>Test Order</a></p>"

@app.route('/test-order-confirm')
def test_order_confirm():
    nifty=get_nifty_price(); strike=round(float(nifty)/50)*50 if nifty else 0
    return f"""<h2 style='color:red'>CONFIRM REAL TEST ORDER - NO MONEY TEST</h2><p>Login: {state['login']}</p><p>Nifty: {nifty}</p><p>Strike: {strike} CE - 1 Lot = <b>65 Qty</b> - MIS - MARKET</p><p>Expected: Insufficient Funds / Margin - Adhu Vandha SUCCESS</p><p>Bad: 401 / 404 - FAIL</p><hr><p><a href='/test-order-do' style='background:red; color:white; padding:15px 30px;'><b>YES - REAL TEST ORDER PODU - 65 QTY</b></a></p><br><br><p><a href='/'>NO - Cancel</a></p>"""

@app.route('/test-order-do')
def test_order_do():
    nifty=get_nifty_price()
    if not nifty: nifty=24950
    strike=round(float(nifty)/50)*50; qty=LOT_SIZE*LOTS
    print(f"TEST ORDER START - Nifty {nifty} Strike {strike} CE Qty {qty}",flush=True)
    if MODE=="PAPER":
        state["test_order_result"]=f"PAPER TEST - NIFTY {strike} CE x {qty}"; return f"<h2>PAPER TEST</h2><p>{state['test_order_result']}</p><p><a href='/'>Home</a></p>"
    if not real_session_global and not session_id_global: alice_login_v2()
    code,body,url=place_order_direct_v2(strike,"CE",qty)
    state["test_order_result"]=f"REAL TEST - NIFTY {strike} CE x {qty} - URL:{url} Status:{code} Body:{body}"; state["live_order"]=state["test_order_result"]
    bl=body.lower()
    if "insufficient" in bl or "margin" in bl or "fund" in bl or "balance" in bl or "ledger" in bl: interp="<h3 style='color:green'>✅ SUCCESS! - Order API Correct! Money Mattum Illa! Login + Order Working!</h3>"
    elif "invalid" in bl or "session" in bl or "unauthor" in bl or "401" in str(code): interp="<h3 style='color:red'>❌ FAIL - Session Problem - APP_SECRET Check pannunga - /force-login Try pannunga</h3>"
    elif code==200: interp="<h3 style='color:green'>✅ ORDER PLACED! Alice App la Check pannunga!</h3>"
    elif code==404: interp="<h3 style='color:red'>❌ FAIL - Endpoint 404</h3>"
    else: interp=f"<h3>Result Status {code} - Screenshot Anuppunga</h3>"
    return f"""<h2>REAL TEST ORDER RESULT - LOT 65 - V6</h2><p>Nifty: {nifty} Strike: {strike} CE Qty: {qty}</p><p>URL: {url}</p><p>Status: {code}</p><p>Body: {body}</p><hr>{interp}<hr><p><a href='/'>Home</a></p>"""

@app.route('/test')
def test_encpkey():
    out=[f"<p>USER: {USER_ID} | APP_ID: {APP_ID} | APP_SECRET_LEN: {len(APP_SECRET)} | MODE: {MODE} | LOT: {LOT_SIZE}</p>"]
    base="https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/"
    try:
        r=requests.post(base+"customer/getAPIEncpkey", json={"userId":USER_ID}, timeout=10, headers={"Content-Type":"application/json"})
        out.append(f"<p>Encpkey Status:{r.status_code}<br>Body:{r.text[:800]}</p>")
        j=r.json(); enc=j.get("encKey")
        if is_valid_key(enc):
            h=hashlib.sha256(f"{USER_ID}{APP_SECRET}{enc}".encode()).hexdigest()
            out.append(f"<p>SHA256 Hash (USER+SECRET+ENC): {h[:30]}***</p>")
            r2=requests.post(base+"customer/getSessionID", json={"userId":USER_ID,"userData":h}, timeout=10, headers={"Content-Type":"application/json"})
            out.append(f"<p>getSessionID Status:{r2.status_code}<br>Body:{r2.text[:800]}</p>")
    except Exception as e: out.append(f"<p>ERROR:{e}</p>")
    return "<h2>Test V6</h2>"+"".join(out)+"<br><a href='/'>Home</a> | <a href='/force-login'>Force Login</a>"

@app.route('/status')
def status(): return jsonify(state)

if __name__=='__main__':
    port=int(os.environ.get("PORT",10000)); print(f"Starting PORT {port} MODE {MODE}",flush=True); app.run(host='0.0.0.0', port=port)
