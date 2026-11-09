import os, time, traceback, hashlib, json, inspect, base64, glob, re
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

state={"strategy":"NIFTY_2ND_CANDLE_FLIP","mode":MODE,"login":"STARTING...","nifty_price":0,"signal":"WAITING FOR 9:20","in_trade":False,"side":"","entry":0,"pnl":0,"reason":"","last_update":"","candle1":"","candle2":"","live_order":"","debug":"Waiting...","session_id":"","real_session":"","api_version":"V17_READ_SDK_FILES","test_order_result":"","lot_size":LOT_SIZE,"raw_login":""}

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
    d=b""; prev=b""
    while len(d) < key_len+iv_len:
        prev=hashlib.md5(prev+password+salt).digest()
        d+=prev
    return d[:key_len], d[key_len+iv_len]

def cryptojs_aes_encrypt(plaintext, passphrase):
    if not HAS_CRYPTO: return None
    salt=get_random_bytes(8)
    key, iv=evp_bytes_to_key(passphrase.encode(), salt)
    cipher=AES.new(key, AES.MODE_CBC, iv)
    ct=cipher.encrypt(pad(plaintext.encode(), AES.block_size))
    return base64.b64encode(b"Salted__"+salt+ct).decode()

def read_sdk_files():
    out=[]
    urls={}
    try:
        import alice_blue as mod
        pkg_dir=os.path.dirname(mod.__file__)
        out.append(f"PkgDir:{pkg_dir}")
        out.append(f"Files:{os.listdir(pkg_dir)}")
        # Ella .py File-yum Full-a Padi - URL Lines Mattum Edu
        for fn in sorted(os.listdir(pkg_dir)):
            if not fn.endswith(".py"): continue
            fp=os.path.join(pkg_dir,fn)
            try: txt=open(fp,encoding="utf-8",errors="ignore").read()
            except: continue
            # http Irukkura Ella Line-yum Edu
            for i, line in enumerate(txt.splitlines(),1):
                if "http" in line or "AliceBlue_urls" in line or "BASE" in line or "URL" in line or "url" in line.lower() and "requests.post" in line:
                    out.append(f"{fn}:{i}: {line.strip()[:300]}")
                    for u in re.findall(r"https?://[^\s\"'\)]+", line):
                        urls[u]=fn
            # webLogin.py + getEncpkey.py Full Source Kaatu - Adhu thaan Mukkiyam
            if fn in ["webLogin.py","getEncpkey.py","getSession.py","getSessionId.py"]:
                out.append(f"<b>=== FULL {fn} ===</b><pre>{txt[:5000]}</pre>")
        # alice_blue.py la AliceBlue_urls / URL Def Irukka?
        try:
            fp2=os.path.join(pkg_dir,"alice_blue.py")
            txt2=open(fp2,encoding="utf-8",errors="ignore").read()
            # AliceBlue_urls = ... 20 Lines Kaatu
            idx=txt2.find("AliceBlue_urls")
            if idx!=-1:
                out.append(f"<b>AliceBlue_urls Context in alice_blue.py:</b><pre>{txt2[max(0,idx-500):idx+3000]}</pre>")
            else:
                out.append("AliceBlue_urls - alice_blue.py la Illa")
            # Import Lines Kaatu - Enga Irundhu Import pannudhu?
            for line in txt2.splitlines():
                if "import" in line.lower() and ("url" in line.lower() or "webLogin" in line or "Encpkey" in line or "Session" in line):
                    out.append(f"alice_blue.py Import: {line.strip()}")
        except Exception as e: out.append(f"alice_blue.py Read Err:{e}")
    except Exception as e:
        out.append(f"Read Err:{e} {traceback.format_exc()[:800]}")
    return urls, "<br>".join(out)

def sdk_flow_login():
    out=[]
    totp_now=get_totp()
    out.append(f"USER:{USER_ID} APP:{APP_ID} DOB:{DOB_YEAR} TOTP:{totp_now} CRYPTO:{HAS_CRYPTO}")
    urls, file_log = read_sdk_files()
    out.append(f"<b>FILE SCAN:</b><br>{file_log}")
    out.append(f"<b>ALL URLs FOUND:</b> {urls}")
    # URLs Dict-a File Log la Irundhu Kaiyala Edu - Hardcode Try pannu
    # Common Pattern: Base + Endpoint - Ella Base la Try pannu
    # File Scan la Kidaicha URL-a Vachu Login Try pannu - Idhu Next Version la Hardcode pannuvom
    return "<br>".join(out), None

def alice_login_v2():
    global session_id_global, real_session_global, last_login_try
    last_login_try=time.time()
    try:
        raw, token = sdk_flow_login()
        state["raw_login"]=raw
        state["debug"]=f"V17 Read Files USER:{USER_ID} DOB:{DOB_YEAR} TOTP:{get_totp()}"
        state["login"]=f"LOGIN FAIL - /test la webLogin.py + getEncpkey.py Full Source Paaru - URL Anga Irukku"
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
            except: pass
    return 404,"No Order URL",""
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
            state["reason"]=f"LIVE ORDER V17 - NIFTY {strike} {side} x {LOTS} Lot (Qty {qty}) - Status:{code}"; state["live_order"]=f"V17 - URL:{url} Status:{code} Body:{body}"
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
    return f"""<h1>ALICE BOT - {state['mode']} - V17 READ SDK FILES</h1><p>Time: {state['last_update']}</p><p>Login: {state['login']} | Mode: <b>{state['mode']}</b> | Lot: <b>{LOT_SIZE}</b></p><p>Signal: {state['signal']}</p><p>Candle1: {state['candle1']}</p><p>Candle2: {state['candle2']}</p><p>In Trade: {state['in_trade']} Side: {state['side']} Entry: {state['entry']}</p><p>Reason: {state['reason']}</p><p>Live Order: {state['live_order']}</p><p>Test: {state['test_order_result']}</p><p>Session: {state['session_id']}</p><hr><h3 style='color:red'>REAL TEST ORDER - 65 QTY</h3><p><a href='/test-order-confirm' style='background:orange; padding:10px; color:black;'><b>TEST ORDER - NIFTY ATM CE - 65 QTY</b></a></p><hr><p><a href='/force-login'><b>/force-login</b></a> | <a href='/test'>/test - SDK Files Full Source</a> | <a href='/status'>STATUS</a></p><hr><h3>DEBUG:</h3><p>{state['debug']}</p><h3>RAW:</h3><p>{state['raw_login']}</p><script>setTimeout(()=>location.reload(),10000)</script>"""
@app.route('/force-login')
def force_login():
    ok=alice_login_v2()
    return f"<h2>Force Login V17 - Read SDK Files</h2><p>Result: {state['login']}</p><p>Debug: {state['debug']}</p><hr><h3>RAW:</h3><p>{state['raw_login']}</p><p><a href='/'>Home</a> | <a href='/test-order-confirm'>Test Order</a></p>"
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
    return f"""<h2>REAL TEST ORDER RESULT - V17 - LOT 65</h2><p>Nifty:{nifty} Strike:{strike} CE Qty:{qty}</p><p>URL:{url}</p><p>Status:{code}</p><p>Body:{body}</p><hr>{interp}<hr><p><a href='/'>Home</a></p>"""
@app.route('/test')
def test_encpkey():
    raw, token = sdk_flow_login()
    return f"<h2>Test V17 - SDK Files Full Source - URL Enga?</h2><p>{raw}</p><br><a href='/'>Home</a> | <a href='/force-login'>Force Login</a>"
@app.route('/status')
def status(): return jsonify(state)
@app.route('/login')
def login_redirect(): return redirect(f"https://ant.aliceblueonline.com/?appcode={APP_ID}")
@app.route('/callback')
def callback(): return f"<h2>V17 - Read SDK</h2><p><a href='/force-login'>Force Login</a></p>"
@app.route('/setcode', methods=['GET','POST'])
def setcode(): return f"""<h2>V17</h2><p>Login: {state['login']}</p><p><a href='/force-login'>Force Login</a> | <a href='/'>Home</a></p>"""
if __name__=='__main__':
    port=int(os.environ.get("PORT",10000)); print(f"Starting PORT {port} MODE {MODE}",flush=True); app.run(host='0.0.0.0', port=port)
