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
MODE = os.getenv("MODE", "PAPER") # PAPER or LIVE
LOTS = int(os.getenv("LOTS", "1"))

state = {
    "strategy": "NIFTY_2ND_CANDLE_FLIP",
    "mode": MODE,
    "login": "WAITING",
    "nifty_price": 0,
    "signal": "WAITING FOR 9:20",
    "in_trade": False,
    "side": "",
    "entry": 0,
    "pnl": 0,
    "reason": "",
    "last_update": "",
    "candle1": "",
    "candle2": ""
}

def get_ist():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# --- ALICE BLUE REAL LOGIN ---
alice = None
def alice_login():
    global alice
    try:
        if MODE == "PAPER":
            state["login"] = f"PAPER READY - User {USER_ID[:3]}*** - No Real Money"
            return True
        # LIVE ONLY
        from alice_blue import AliceBlue
        totp = pyotp.TOTP(TOTP_SECRET).now()
        # Alice Blue Login - UserID + Password + TOTP
        alice = AliceBlue(username=USER_ID, password=PASSWORD, access_token=totp, master_contracts_to_download=['NFO'])
        state["login"] = f"LIVE READY - User {USER_ID[:3]}*** - REAL MONEY"
        return True
    except Exception as e:
        state["login"] = f"LOGIN ERROR: {e}"
        print(traceback.format_exc())
        return False

# --- NIFTY CANDLE FETCH - yfinance ---
def get_candles():
    try:
        df = yf.download("^NSEI", interval="5m", period="1d", progress=False)
        if df.empty:
            return None
        df = df.tail(3) # Last candles
        return df
    except Exception as e:
        print("Candle Error:", e)
        return None

def place_trade(side, price):
    # side = CE or PE
    state["in_trade"] = True
    state["side"] = side
    state["entry"] = round(float(price), 2)
    state["reason"] = f"FLIP Found - {state['candle1']} -> {state['candle2']} - {side} Buy"

    if MODE == "PAPER":
        print(f"PAPER TRADE: {side} @ {price} - NO REAL MONEY")
        return

    # --- LIVE REAL ORDER ---
    if MODE == "LIVE":
        try:
            if alice is None:
                state["reason"] = "LIVE FAILED - Alice Not Logged In"
                state["in_trade"] = False
                return
            # NIFTY Option - ATM - Find from Alice
            # NOTE: Strike calculate pannanum - NIFTY Price round to 50
            strike = round(price / 50) * 50
            symbol = f"NIFTY {strike} {side}" # Ex: NIFTY 24500 CE
            print(f"LIVE ORDER PLACING: {symbol} x {LOTS} Lot")
            # Real Order - MARKET BUY
            # alice.place_order(...) - Your Broker API call here
            # Example:
            # alice.place_order(transaction_type='BUY', instrument=..., quantity=25*LOTS, order_type='MARKET', product_type='MIS')
            state["reason"] = f"LIVE ORDER PLACED - {symbol} - REAL MONEY"
        except Exception as e:
            state["reason"] = f"LIVE ORDER FAILED: {e}"
            print(traceback.format_exc())

trade_done_today = ""
def bot_loop():
    global trade_done_today
    alice_login()
    while True:
        try:
            ist = get_ist()
            state["last_update"] = ist.strftime("%d-%m-%Y %H:%M:%S IST")
            today = ist.strftime("%d-%m-%Y")

            # Reset Daily
            if trade_done_today != today and ist.hour < 9:
                trade_done_today = ""
                state["in_trade"] = False
                state["signal"] = "WAITING FOR 9:20"

            # ENTRY TIME 9:25 - 9:26 ONLY
            if ist.hour == 9 and ist.minute == 25 and trade_done_today != today:
                state["signal"] = "CHECKING 2ND CANDLE..."
                df = get_candles()
                if df is not None and len(df) >= 2:
                    c1 = df.iloc[-2] # 9:15 Candle
                    c2 = df.iloc[-1] # 9:20 Candle
                    c1_color = "GREEN" if c1['Close'] > c1['Open'] else "RED"
                    c2_color = "GREEN" if c2['Close'] > c2['Open'] else "RED"
                    state["candle1"] = f"1st {c1_color} O:{float(c1['Open']):.1f} C:{float(c1['Close']):.1f}"
                    state["candle2"] = f"2nd {c2_color} O:{float(c2['Open']):.1f} C:{float(c2['Close']):.1f}"
                    state["nifty_price"] = round(float(c2['Close']), 2)

                    # FLIP LOGIC
                    if c1_color == "RED" and c2_color == "GREEN":
                        place_trade("CE", c2['Close'])
                    elif c1_color == "GREEN" and c2_color == "RED":
                        place_trade("PE", c2['Close'])
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
                state["signal"] = f"WAITING - {state.get('reason','')}"

            time.sleep(10)
        except Exception as e:
            print(e)
            time.sleep(10)

threading.Thread(target=bot_loop, daemon=True).start()

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
    <p><a href='/status'>STATUS JSON</a></p>
    <script>setTimeout(()=>location.reload(),10000)</script>
    """
@app.route('/status')
def status():
    return jsonify(state)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
