import os, time, pyotp, traceback
from datetime import datetime, timedelta
from flask import Flask, jsonify
import threading
import yfinance as yf

app = Flask(__name__)

USER_ID = os.getenv("ALICE_USER_ID", "")
PASSWORD = os.getenv("ALICE_PASSWORD", "")
TOTP_SECRET = os.getenv("ALICE_TOTP_SECRET", "")
APP_ID = os.getenv("ALICE_APP_ID", "")
APP_SECRET = os.getenv("ALICE_APP_SECRET", "")
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
    "live_order": ""
}

def get_ist():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# ---------- ALICE BLUE LOGIN - ALL VERSION FIX ----------
alice = None
def alice_login():
    global alice
    try:
        if MODE == "PAPER":
            state["login"] = f"PAPER READY - User {USER_ID[:3]}*** - No Real Money"
            return True

        # LIVE ONLY
        try:
            from alice_blue import AliceBlue
        except Exception as e:
            state["login"] = f"LIVE ERROR - alice-blue not installed: {e}"
            return False

        print(f"AliceBlue Methods: {[m for m in dir(AliceBlue) if 'login' in m.lower() or 'token' in m.lower() or 'session' in m.lower()]}")

        if not TOTP_SECRET or not APP_ID or not APP_SECRET:
            state["login"] = "LIVE ERROR - APP_ID / APP_SECRET / TOTP_SECRET Missing in Render Env"
            return False

        if not USER_ID or not PASSWORD:
            state["login"] = "LIVE ERROR - USER_ID / PASSWORD Missing"
            return False

        totp = pyotp.TOTP(TOTP_SECRET).now()
        print(f"Trying LIVE Login User {USER_ID} App {APP_ID}")

        # Try 1 - Old Method - login_and_get_access_token
        if hasattr(AliceBlue, 'login_and_get_access_token'):
            try:
                access_token = AliceBlue.login_and_get_access_token(
                    username=USER_ID, password=PASSWORD, twoFA=totp,
                    api_secret=APP_SECRET, app_id=APP_ID
                )
                alice = AliceBlue(username=USER_ID, access_token=access_token)
                state["login"] = f"LIVE READY - User {USER_ID[:3]}*** - REAL MONEY"
                print("LIVE LOGIN SUCCESS - Method 1")
                return True
            except Exception as e:
                print(f"Method 1 Failed: {e}")

        # Try 2 - New Method - login_and_get_sessionID
        if hasattr(AliceBlue, 'login_and_get_sessionID'):
            try:
                session_id = AliceBlue.login_and_get_sessionID(
                    username=USER_ID, password=PASSWORD, twoFA=totp,
                    api_secret=APP_SECRET, app_id=APP_ID
                )
                alice = AliceBlue(username=USER_ID, session_id=session_id)
                state["login"] = f"LIVE READY - User {USER_ID[:3]}*** - REAL MONEY"
                print("LIVE LOGIN SUCCESS - Method 2")
                return True
            except Exception as e:
                print(f"Method 2 Failed: {e}")

        # Try 3 - login_and_get_access_token_v2
        if hasattr(AliceBlue, 'login_and_get_access_token_v2'):
            try:
                access_token = AliceBlue.login_and_get_access_token_v2(
                    username=USER_ID, password=PASSWORD, twoFA=totp,
                    api_secret=APP_SECRET, app_id=APP_ID
                )
                alice = AliceBlue(username=USER_ID, access_token=access_token)
                state["login"] = f"LIVE READY - User {USER_ID[:3]}*** - REAL MONEY"
                print("LIVE LOGIN SUCCESS - Method 3")
                return True
            except Exception as e:
                print(f"Method 3 Failed: {e}")

        state["login"] = "LIVE ERROR - No Login Method Worked - Check Logs"
        return False

    except Exception as e:
        state["login"] = f"LOGIN ERROR: {e}"
        print(traceback.format_exc())
        return False

# ---------- CANDLE FETCH ----------
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

# ---------- PLACE TRADE ----------
def place_trade(side, price, nifty_price):
    state["in_trade"] = True
    state["side"] = side
    state["entry"] = round(float(price), 2)
    state["nifty_price"] = round(float(nifty_price), 2)

    if MODE == "PAPER":
        state["reason"] = f"PAPER TRADE - {side} @ {price} - NO REAL MONEY"
        state["live_order"] = "PAPER - No Order Sent"
        print(f"PAPER TRADE: {side} @ {price}")
        return

    # LIVE REAL ORDER
    if MODE == "LIVE":
        try:
            if alice is None:
                state["reason"] = "LIVE FAILED - Alice Not Logged In - Retrying Login"
                state["live_order"] = "FAILED - Not Logged In"
                alice_login()
                state["in_trade"] = False
                return

            strike = round(float(nifty_price) / 50) * 50
            print(f"LIVE ORDER TRY: NIFTY {strike} {side} LOTS {LOTS}")

            instrument = None
            try:
                instrument = alice.get_instrument_by_symbol('NFO', f"NIFTY {strike} {side}")
            except Exception as e:
                print(f"Instrument Search 1 Failed: {e}")
                try:
                    instrument = alice.get_instrument_for_fno(symbol='NIFTY', expiry_date=None, is_fut=False, strike=strike, is_CE=(side == "CE"))
                except Exception as e2:
                    print(f"Instrument Search 2 Failed: {e2}")

            if instrument is None:
                state["reason"] = f"LIVE FAILED - Instrument Not Found {strike} {side}"
                state["live_order"] = "FAILED - Instrument Not Found"
                return

            qty = 75 * LOTS
            order = alice.place_order(
                transaction_type='BUY',
                instrument=instrument,
                quantity=qty,
                order_type='MARKET',
                product_type='MIS',
                price=0.0,
                trigger_price=None,
                stop_loss=None,
                square_off=None,
                trailing_sl=None,
                is_amo=False
            )
            print(f"LIVE ORDER PLACED: {order}")
            state["reason"] = f"LIVE ORDER PLACED - NIFTY {strike} {side} x {LOTS} Lot - REAL MONEY"
            state["live_order"] = f"PLACED - {order}"
        except Exception as e:
            state["reason"] = f"LIVE ORDER FAILED: {e}"
            state["live_order"] = f"FAILED: {e}"
            print(traceback.format_exc())

trade_done_today = ""
def bot_loop():
    global trade_done_today
    # First login - fail aana kooda loop odanum, app crash aagakoodadhu
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

            # ENTRY 9:25 ONLY
            if ist.hour == 9 and ist.minute == 25 and trade_done_today != today:
                state["signal"] = "CHECKING 2ND CANDLE..."
                df = get_candles()
                if df is not None and len(df) >= 2:
                    c1 = df.iloc[-2]
                    c2 = df.iloc[-1]
                    try:
                        c1_o = safe_float(c1['Open']); c1_c = safe_float(c1['Close'])
                        c2_o = safe_float(c2['Open']); c2_c = safe_float(c2['Close'])
                    except Exception as e:
                        print(f"Candle Parse Error: {e}")
                        state["reason"] = "Candle Parse Error"
                        trade_done_today = today
                        time.sleep(10)
                        continue

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
            print(traceback.format_exc())
            time.sleep(10)

# Thread start - app crash aagama
try:
    threading.Thread(target=bot_loop, daemon=True).start()
except Exception as e:
    print(f"Thread Start Error: {e}")

@app.route('/')
def home():
    return f"""
    <h1>ALICE BOT - NIFTY 2ND CANDLE FLIP - {state['mode']}</h1>
    <p>Time: {state['last_update']}</p>
    <p>Login: {state['login']} | Mode: <b>{state['mode']}</b></p>
    <p>Signal: {state['signal']}</p>
    <p>Candle1: {state['candle1']}</p>
    <p>Candle2: {state['candle2']}</p>
    <p>In Trade: {state['in_trade']} Side: {state['side']} Entry: {state['entry']}</p>
    <p>Reason: {state['reason']}</p>
    <p>Live Order: {state['live_order']}</p>
    <p><a href='/status'>STATUS JSON</a></p>
    <script>setTimeout(()=>location.reload(),10000)</script>
    """
@app.route('/status')
def status():
    return jsonify(state)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    print(f"Starting on PORT {port} MODE {MODE}")
    app.run(host='0.0.0.0', port=port)
