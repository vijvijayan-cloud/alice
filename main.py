import os, time, pyotp, traceback, hashlib, json
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

state = {
    "strategy": "NIFTY_2ND_CANDLE_FLIP",
    "mode": MODE,
    "login": "STARTING...",
    "nifty_price": 0,
    "signal": "WAITING FOR 9:20",
    "in_trade": False,
    "side": "",
    "entry": 0,
    "pnl": 0,
    "reason": "",
    "last_update": "",
    "candle1": "",
    "candle2": "",
    "live_order": "",
    "debug": "Waiting...",
    "session_id": "",
    "real_session": "",
    "api_version": "V2_FIX_NULL_KEY",
    "login_url": "",
    "auth_code": ""
}

def get_ist():
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)

session_id_global = ""
real_session_global = ""
enc_key_global = ""
base_url_global = "https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/"
auth_code_global = AUTH_CODE

def is_valid_key(k):
    if not k:
        return False
    k = str(k).strip()
    if k.lower() in ["null", "none", ""]:
        return False
    return True

def try_encpkey():
    global base_url_global, enc_key_global
    # ant mattum thaan correct - a3 405 tharum - adhanala ant mattum
    base = "https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/"
    try:
        print(f"TRY Encpkey {base} USER:{USER_ID}", flush=True)
        r = requests.post(base + "customer/getAPIEncpkey", json={"userId": USER_ID}, timeout=10, headers={"Content-Type": "application/json"})
        print(f"Encpkey RESULT St:{r.status_code} Body:{r.text[:600]}", flush=True)
        state["debug"] += f" | Encpkey St:{r.status_code} Body:{r.text[:300]}"
        if r.status_code == 200 and r.text.strip():
            try:
                j = r.json()
            except:
                return "", "", "JSON Fail"
            enc = j.get("encKey") or j.get("encpkey") or ""
            emsg = j.get("emsg") or ""
            # Alice "null" string tharudha nu check - Idhu thaan Mukkiyam
            if not is_valid_key(enc):
                state["debug"] += f" | Encpkey NULL - Alice Solludhu: {emsg} - Web la Login Pannanum"
                return "", base, emsg
            enc_key_global = enc
            base_url_global = base
            return enc, base, r.text[:300]
    except Exception as e:
        print(f"Encpkey ERROR : {e}", flush=True)
        state["debug"] += f" | Encpkey Err : {e}"
    return "", base, "Fail"

def alice_login_v2():
    global session_id_global, real_session_global, enc_key_global, base_url_global
    try:
        try:
            totp = pyotp.TOTP(TOTP_SECRET).now() if TOTP_SECRET else ""
        except:
            totp = ""
        login_url = f"https://ant.aliceblueonline.com/?appcode={APP_ID}"
        state["login_url"] = login_url
        state["debug"] = f"V2 - USER:{USER_ID} APP_ID:{APP_ID} AUTHCODE_LEN:{len(auth_code_global)}"
        print(state["debug"], flush=True)

        # STEP 1 - Encpkey - Login pannala na NULL varum
        enc_key, base, msg = try_encpkey()
        if not enc_key:
            state["login"] = "NEED WEB LOGIN FIRST - /login la Login pannunga - Apparam Encpkey Varum"
            state["debug"] += f" | Encpkey NULL kaaranam: {msg}"
            print("Encpkey NULL - Need Web Login", flush=True)
            return False

        # STEP 2 - authCode Check
        if not auth_code_global:
            state["login"] = "NEED LOGIN - /login Open pannunga - authCode Edukkavum"
            state["debug"] += f" | authCode Illa. Login: {login_url}"
            return False

        # STEP 3 - getSessionID
        payload = {"userId": USER_ID, "sessionId": auth_code_global}
        print(f"TRY getSessionID Payload:{payload}", flush=True)
        r2 = requests.post(base + "customer/getSessionID", json=payload, timeout=10, headers={"Content-Type": "application/json"})
        print(f"getSessionID St:{r2.status_code} Body:{r2.text[:600]}", flush=True)
        state["debug"] += f" | getSessionID St:{r2.status_code} Body:{r2.text[:200]}"
        if r2.status_code == 200 and r2.text.strip():
            try:
                j2 = r2.json()
            except:
                j2 = {}
            real = j2.get("sessionId") or j2.get("sessionID") or j2.get("token") or j2.get("accessToken") or j2.get("userSession") or ""
            stat = str(j2.get("stat") or j2.get("status") or "").upper()
            if is_valid_key(real) and len(str(real)) > 10:
                session_id_global = auth_code_global
                real_session_global = str(real)
                state["session_id"] = auth_code_global[:12] + "***"
                state["real_session"] = str(real)[:12] + "***"
                state["login"] = f"LIVE READY V2 - User {USER_ID[:3]}*** - REAL SESSION OK"
                return True
            if stat == "OK":
                session_id_global = auth_code_global
                real_session_global = r2.text[:200]
                state["login"] = f"LIVE READY V2 - Stat OK"
                return True
        state["login"] = "LIVE ERROR - authCode Expire / Thappu - Thirumba /login la Login pannunga"
        return False
    except Exception as e:
        state["debug"] += f" | V2 Exception: {e}"
        print(traceback.format_exc(), flush=True)
        return False

def alice_login():
    if MODE == "PAPER":
        state["login"] = f"PAPER READY - User {USER_ID[:3]}***"
        return True
    return alice_login_v2()

def get_candles():
    try:
        df = yf.download("^NSEI", interval="5m", period="1d", progress=False, auto_adjust=False)
        if df is None or df.empty:
            return None
        return df
    except Exception as e:
        print("Candle Error:", e, flush=True)
        return None

def safe_float(x):
    try:
        if hasattr(x, 'iloc'):
            return float(x.iloc[0])
        return float(x)
    except:
        return float(x)

def get_expiry_date():
    ist = get_ist()
    d = ist.date()
    days_ahead = (3 - d.weekday()) % 7
    if days_ahead == 0 and ist.hour >= 15:
        days_ahead = 7
    return d + timedelta(days=days_ahead)

def place_order_direct_v2(strike, side, qty):
    try:
        exp = get_expiry_date()
        exp_str = exp.strftime("%d-%b-%Y").upper()
        url = base_url_global + "placeOrder/placeOrder"
        sess = real_session_global if real_session_global else session_id_global
        headers = {"Content-Type": "application/json","Authorization": f"Bearer {USER_ID} {sess}","userId": USER_ID,"sessionId": sess}
        payload = {"userId": USER_ID,"sessionId": sess,"tradingSymbol": f"NIFTY {strike} {side}","exchange": "NFO","transactionType": "BUY","orderType": "MARKET","productType": "MIS","quantity": qty,"price": "0","triggerPrice": "0","expiry": exp_str,"strike": str(strike),"optionType": side}
        print(f"V2 Order URL:{url} Payload:{payload}", flush=True)
        r = requests.post(url, json=payload, headers=headers, timeout=20)
        print(f"V2 Order Status:{r.status_code} Body:{r.text[:600]}", flush=True)
        return r.status_code, r.text[:600]
    except Exception as e:
        return 0, str(e)

def place_trade(side, price, nifty_price):
    state["in_trade"] = True
    state["side"] = side
    state["entry"] = round(float(price), 2)
    state["nifty_price"] = round(float(nifty_price), 2)
    if MODE == "PAPER":
        state["reason"] = f"PAPER TRADE - {side} @ {price} - NO REAL MONEY"
        state["live_order"] = "PAPER - No Order Sent"
        return
    if MODE == "LIVE":
        try:
            if not real_session_global and not session_id_global:
                alice_login()
                if not real_session_global and not session_id_global:
                    state["reason"] = "LIVE FAILED - No Real Session - /login la Login pannunga"
                    state["live_order"] = "FAILED - No Session"
                    state["in_trade"] = False
                    return
            strike = round(float(nifty_price) / 50) * 50
            qty = 75 * LOTS
            code, body = place_order_direct_v2(strike, side, qty)
            state["reason"] = f"LIVE ORDER TRY V2 - NIFTY {strike} {side} x {LOTS} - Status:{code}"
            state["live_order"] = f"V2 DIRECT - Status:{code} Body:{body}"
        except Exception as e:
            state["reason"] = f"LIVE ORDER FAILED: {e}"
            state["live_order"] = f"FAILED: {e}"
            print(traceback.format_exc(), flush=True)

trade_done_today = ""
def bot_loop():
    global trade_done_today
    try:
        alice_login()
    except Exception as e:
        print(f"Initial Login Error: {e}", flush=True)
    while True:
        try:
            ist = get_ist()
            state["last_update"] = ist.strftime("%d-%m-%Y %H:%M:%S IST")
            today = ist.strftime("%d-%m-%Y")
            if trade_done_today != today and ist.hour < 9:
                trade_done_today = ""
                state["in_trade"] = False
                state["signal"] = "WAITING FOR 9:20"
                state["reason"] = ""
                state["candle1"] = ""
                state["candle2"] = ""
                state["live_order"] = ""
            if ist.hour == 9 and ist.minute == 25 and trade_done_today != today:
                state["signal"] = "CHECKING 2ND CANDLE..."
                df = get_candles()
                if df is not None and len(df) >= 2:
                    c1 = df.iloc[-2]; c2 = df.iloc[-1]
                    try:
                        c1_o = safe_float(c1['Open']); c1_c = safe_float(c1['Close'])
                        c2_o = safe_float(c2['Open']); c2_c = safe_float(c2['Close'])
                    except Exception as e:
                        state["reason"] = "Candle Parse Error"
                        trade_done_today = today
                        time.sleep(10); continue
                    c1_color = "GREEN" if c1_c > c1_o else "RED"
                    c2_color = "GREEN" if c2_c > c2_o else "RED"
                    state["candle1"] = f"1st {c1_color} O:{c1_o:.1f} C:{c1_c:.1f}"
                    state["candle2"] = f"2nd {c2_color} O:{c2_o:.1f} C:{c2_c:.1f}"
                    state["nifty_price"] = round(c2_c, 2)
                    if c1_color == "RED" and c2_color == "GREEN":
                        place_trade("CE", c2_c, c2_c)
                    elif c1_color == "GREEN" and c2_color == "RED":
                        place_trade("PE", c2_c, c2_c)
                    else:
                        state["reason"] = f"NO TRADE - NO FLIP - 1st {c1_color} 2nd {c2_color}"
                        state["signal"] = "NO TRADE - NO FLIP"
                    trade_done_today = today
                else:
                    state["reason"] = "NO TRADE - Candle Data Not Found"
            elif ist.hour == 9 and ist.minute < 25:
                state["signal"] = f"WAITING - Time {ist.strftime('%H:%M')} - Entry at 9:25"
            elif state["in_trade"]:
                state["signal"] = f"IN TRADE - {state['side']} @ {state['entry']} - {state['mode']}"
            else:
                if not state["reason"]:
                    state["signal"] = f"WAITING - {ist.strftime('%H:%M')}"
            time.sleep(10)
        except Exception as e:
            print(f"Bot Loop Error: {e}", flush=True)
            time.sleep(10)

try:
    threading.Thread(target=bot_loop, daemon=True).start()
except Exception as e:
    print(f"Thread Error: {e}", flush=True)

@app.route('/')
def home():
    login_url = f"https://ant.aliceblueonline.com/?appcode={APP_ID}"
    return f"""
    <h1>ALICE BOT - NIFTY 2ND CANDLE FLIP - {state['mode']} - V2 FIX</h1>
    <p>Time: {state['last_update']}</p>
    <p>Login: {state['login']} | Mode: <b>{state['mode']}</b></p>
    <p>Signal: {state['signal']}</p>
    <p>Candle1: {state['candle1']}</p>
    <p>Candle2: {state['candle2']}</p>
    <p>In Trade: {state['in_trade']} Side: {state['side']} Entry: {state['entry']}</p>
    <p>Reason: {state['reason']}</p>
    <p>Live Order: {state['live_order']}</p>
    <p>Session: {state['session_id']} | Real: {state['real_session']}</p>
    <hr>
    <h3>STEP 1 - WEB LOGIN MUDHALIL SEYAVUM:</h3>
    <p><a href='/login' target='_blank'><b>CLICK HERE - /login - Alice Web la Login pannunga</b></a></p>
    <p>User: TN15K7 + Password + TOTP (496287 maadhiri - App la Paaru) + DOB Year 1987</p>
    <p>Login Mudinja Apparam - Home Page la Encpkey Varum - Apparam authCode Edukkalam</p>
    <p>Direct: <a href='{login_url}' target='_blank'>{login_url}</a></p>
    <hr>
    <p><a href='/test'><b>/test - Encpkey Test</b></a> | <a href='/status'>STATUS JSON</a></p>
    <hr>
    <h3>DEBUG:</h3>
    <p>{state['debug']}</p>
    <script>setTimeout(()=>location.reload(),10000)</script>
    """

@app.route('/login')
def login_redirect():
    url = f"https://ant.aliceblueonline.com/?appcode={APP_ID}"
    return redirect(url)

@app.route('/callback')
def callback():
    global auth_code_global
    code = request.args.get("authCode") or request.args.get("authcode") or request.args.get("code") or ""
    if code:
        auth_code_global = code
        state["auth_code"] = code[:12] + "***"
        state["debug"] += f" | Callback authCode Got:{code[:12]}***"
        ok = alice_login_v2()
        return f"<h2>authCode Kidaichiduchu: {code[:15]}***</h2><p>Login: {state['login']}</p><p>Render la ALICE_AUTH_CODE = {code} nu Podunga</p><p><a href='/'>Home ku Ponga</a></p>"
    return f"<h2>No authCode</h2><p>URL la authCode Illa. <a href='/login'>Thirumba Login</a></p><p>Debug: {request.args}</p>"

@app.route('/test')
def test_encpkey():
    out = []
    out.append(f"<p>USER_ID: {USER_ID} | APP_ID: {APP_ID} | MODE: {MODE}</p>")
    base = "https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/"
    try:
        out.append(f"<p><b>Trying {base}</b></p>")
        r = requests.post(base + "customer/getAPIEncpkey", json={"userId": USER_ID}, timeout=10, headers={"Content-Type": "application/json"})
        out.append(f"<p>Status: {r.status_code}<br>Body: {r.text[:800]}</p><hr>")
        j = r.json()
        enc = j.get("encKey")
        if not is_valid_key(enc):
            out.append(f"<p style='color:red'><b>Encpkey NULL - Kaaranam: {j.get('emsg')} - Web la Login Pannanum!</b></p>")
        else:
            out.append(f"<p style='color:green'><b>Encpkey OK: {str(enc)[:20]}***</b></p>")
    except Exception as e:
        out.append(f"<p style='color:red'><b>ERROR: {e}</b></p>")
    return "<h2>Encpkey Test</h2>" + "".join(out) + "<br><a href='/'>Home</a> | <a href='/test'>Test Again</a> | <a href='/login'>Login</a>"

@app.route('/status')
def status():
    return jsonify(state)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    print(f"Starting on PORT {port} MODE {MODE}", flush=True)
    app.run(host='0.0.0.0', port=port)
