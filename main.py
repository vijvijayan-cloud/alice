import os, time, pyotp, traceback, hashlib, json
from datetime import datetime, timedelta
from flask import Flask, jsonify
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
    "api_version": "V2_MANUAL"
}

def get_ist():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

alice = None
session_id_global = ""
enc_key_global = ""
base_url_global = "https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/"

def alice_login_v2():
    global session_id_global, enc_key_global, base_url_global, alice
    try:
        try:
            totp = pyotp.TOTP(TOTP_SECRET).now() if TOTP_SECRET else ""
        except:
            totp = ""
        state["debug"] = f"V2 TRY - USER:{USER_ID} APP_ID:{APP_ID} LEN:{len(APP_ID)} SECRET:{APP_SECRET[:3]}*** LEN:{len(APP_SECRET)} TOTP:{totp} DOB:{DOB_YEAR}"
        print(state["debug"])
        base_urls = [
            "https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/",
            "https://a3.aliceblueonline.com/rest/AliceBlueAPIService/api/",
        ]
        for base in base_urls:
            try:
                url = base + "customer/getAPIEncpkey"
                r = requests.post(url, json={"userId": USER_ID}, timeout=15, headers={"Content-Type": "application/json"})
                print(f"Encpkey {base} Status:{r.status_code} Body:{r.text[:300]}")
                state["debug"] += f" | {base[:25]} Status:{r.status_code}"
                if r.status_code != 200 or not r.text.strip():
                    continue
                try:
                    j = r.json()
                except:
                    continue
                enc_key = j.get("encKey") or j.get("encpkey") or ""
                if not enc_key:
                    continue
                enc_key_global = enc_key
                base_url_global = base
                # SHA256 - Combo 0 thaan Work Aachu Ungalukku - USER + APP_ID + ENC
                combo = USER_ID + APP_ID + enc_key
                sid = hashlib.sha256(combo.encode()).hexdigest()
                session_id_global = sid
                state["session_id"] = sid[:15] + "***"
                # V2 Session-a AliceBlue Library ku Kuduthu Order Podavum Mudiyum
                try:
                    from alice_blue import AliceBlue
                    alice = AliceBlue(username=USER_ID, session_id=sid)
                    print(f"AliceBlue Object Created with V2 Session")
                    state["debug"] += f" | AliceBlue Obj OK"
                except Exception as e:
                    print(f"AliceBlue Obj Failed: {e}")
                    state["debug"] += f" | AliceBlue Obj Failed: {e}"
                state["login"] = f"LIVE READY V2 - User {USER_ID[:3]}*** - REAL MONEY - EncKey OK"
                state["debug"] += f" | SUCCESS V2 SID:{sid[:10]}"
                return True
            except Exception as e:
                print(f"V2 Base Failed: {e}")
                state["debug"] += f" | Base Failed: {e}"
                continue
        state["login"] = "LIVE ERROR V2 - Encpkey Kedaikala"
        return False
    except Exception as e:
        state["debug"] += f" | V2 Exception: {e}"
        print(traceback.format_exc())
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
        print("Candle Error:", e)
        return None

def safe_float(x):
    try:
        if hasattr(x, 'iloc'):
            return float(x.iloc[0])
        return float(x)
    except:
        return float(x)

def get_expiry_date():
    # Nearest Thursday - NIFTY Weekly Expiry
    ist = get_ist()
    d = ist.date()
    # Thursday = 3 (Monday=0)
    days_ahead = (3 - d.weekday()) % 7
    if days_ahead == 0 and ist.hour >= 15:
        days_ahead = 7
    exp = d + timedelta(days=days_ahead)
    return exp

def place_order_v2_direct(strike, side, qty):
    # Direct V2 Place Order - Library Fail Aana Idhu Work Aagum
    try:
        # Expiry Format: DD-MMM-YYYY Eg: 13-NOV-2026
        exp = get_expiry_date()
        exp_str = exp.strftime("%d-%b-%Y").upper()
        # Symbol Format V2: NIFTY + Expiry + Strike + CE/PE
        # Eg: NIFTY13NOV2626000CE - Alice ku Vera Format Thevai na Library-a Use pannuvom
        url = base_url_global + "placeOrder/placeOrder"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {USER_ID} {session_id_global}",
            "auth": f"Bearer {USER_ID} {session_id_global}",
            "userId": USER_ID,
            "sessionId": session_id_global,
        }
        # Alice V2 PlaceOrder Payload - Standard
        payload = {
            "userId": USER_ID,
            "sessionId": session_id_global,
            "tradingSymbol": f"NIFTY {strike} {side}",
            "exchange": "NFO",
            "transactionType": "BUY",
            "orderType": "MARKET",
            "productType": "MIS",
            "quantity": qty,
            "price": "0",
            "triggerPrice": "0",
            "expiry": exp_str,
            "strike": str(strike),
            "optionType": side,
        }
        print(f"V2 Direct Order URL:{url} Payload:{payload}")
        r = requests.post(url, json=payload, headers=headers, timeout=20)
        print(f"V2 Direct Order Status:{r.status_code} Body:{r.text[:500]}")
        return r.status_code, r.text[:500]
    except Exception as e:
        print(f"V2 Direct Order Failed: {e}")
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
            if not session_id_global and alice is None:
                state["reason"] = "LIVE FAILED - Alice Not Logged In - Re-Login Try pannuren"
                alice_login()
                if not session_id_global and alice is None:
                    state["live_order"] = "FAILED - Not Logged In"
                    state["in_trade"] = False
                    return
            strike = round(float(nifty_price) / 50) * 50
            qty = 75 * LOTS
            # TRY 1 - Library Vaichu Order - V2 Session Kuduthirukkom
            if alice is not None:
                try:
                    instrument = None
                    try:
                        instrument = alice.get_instrument_by_symbol('NFO', f"NIFTY {strike} {side}")
                    except Exception as e:
                        print(f"Inst1 Failed: {e}")
                        try:
                            instrument = alice.get_instrument_for_fno(symbol='NIFTY', expiry_date=get_expiry_date(), is_fut=False, strike=strike, is_CE=(side == "CE"))
                        except Exception as e2:
                            print(f"Inst2 Failed: {e2}")
                    if instrument is not None:
                        order = alice.place_order(transaction_type='BUY', instrument=instrument, quantity=qty, order_type='MARKET', product_type='MIS', price=0.0, trigger_price=None, stop_loss=None, square_off=None, trailing_sl=None, is_amo=False)
                        state["reason"] = f"LIVE ORDER PLACED - NIFTY {strike} {side} x {LOTS} Lot"
                        state["live_order"] = f"PLACED VIA LIBRARY - {order}"
                        print(f"Library Order Success: {order}")
                        return
                    else:
                        state["debug"] += f" | Instrument Not Found {strike} {side}"
                except Exception as e:
                    print(f"Library Order Failed: {e} {traceback.format_exc()}")
                    state["debug"] += f" | Library Order Failed: {e}"
            # TRY 2 - Direct V2 API Order
            code, body = place_order_v2_direct(strike, side, qty)
            state["reason"] = f"LIVE ORDER TRY V2 DIRECT - NIFTY {strike} {side} x {LOTS} - Status:{code}"
            state["live_order"] = f"V2 DIRECT - Status:{code} Body:{body}"
            # TRY 3 - Session Refresh panni Thirumba Library Try
            if code != 200:
                alice_login()
                if alice is not None:
                    try:
                        instrument = alice.get_instrument_by_symbol('NFO', f"NIFTY {strike} {side}")
                        order = alice.place_order(transaction_type='BUY', instrument=instrument, quantity=qty, order_type='MARKET', product_type='MIS', price=0.0, trigger_price=None, stop_loss=None, square_off=None, trailing_sl=None, is_amo=False)
                        state["reason"] = f"LIVE ORDER PLACED RETRY - NIFTY {strike} {side}"
                        state["live_order"] = f"PLACED RETRY - {order}"
                    except Exception as e:
                        state["reason"] = f"LIVE ORDER FAILED RETRY: {e}"
        except Exception as e:
            state["reason"] = f"LIVE ORDER FAILED: {e}"
            state["live_order"] = f"FAILED: {e}"
            print(traceback.format_exc())

trade_done_today = ""
def bot_loop():
    global trade_done_today
    try:
        alice_login()
    except Exception as e:
        print(f"Initial Login Error: {e}")
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
            print(f"Bot Loop Error: {e}")
            time.sleep(10)

try:
    threading.Thread(target=bot_loop, daemon=True).start()
except Exception as e:
    print(f"Thread Error: {e}")

@app.route('/')
def home():
    return f"""
    <h1>ALICE BOT - NIFTY 2ND CANDLE FLIP - {state['mode']} - V2</h1>
    <p>Time: {state['last_update']}</p>
    <p>Login: {state['login']} | Mode: <b>{state['mode']}</b></p>
    <p>Signal: {state['signal']}</p>
    <p>Candle1: {state['candle1']}</p>
    <p>Candle2: {state['candle2']}</p>
    <p>In Trade: {state['in_trade']} Side: {state['side']} Entry: {state['entry']}</p>
    <p>Reason: {state['reason']}</p>
    <p>Live Order: {state['live_order']}</p>
    <p>Session: {state['session_id']}</p>
    <hr>
    <h3>DEBUG:</h3>
    <p>{state['debug']}</p>
    <p><a href='/status'>STATUS JSON</a> | <a href='/test-order'>TEST ORDER (PAPER CHECK)</a></p>
    <script>setTimeout(()=>location.reload(),10000)</script>
    """
@app.route('/status')
def status():
    return jsonify(state)
@app.route('/test-order')
def test_order():
    # Order Logic Test panna - Real Order Podadhu - Logic mattum Check pannum
    try:
        if alice is not None:
            inst = alice.get_instrument_by_symbol('NFO', 'NIFTY 26000 CE')
            return jsonify({"alice_obj": "OK", "instrument_test": str(inst)[:200], "session": state['session_id'], "login": state['login']})
        else:
            return jsonify({"alice_obj": "NONE", "session": state['session_id'], "login": state['login'], "debug": state['debug']})
    except Exception as e:
        return jsonify({"error": str(e), "session": state['session_id'], "debug": state['debug']})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    print(f"Starting on PORT {port} MODE {MODE}")
    app.run(host='0.0.0.0', port=port)
