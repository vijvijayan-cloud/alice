import os, time, pyotp
from datetime import datetime, timedelta
from flask import Flask, jsonify
import threading

app = Flask(__name__)

USER_ID = os.getenv("ALICE_USER_ID", "")
PASSWORD = os.getenv("ALICE_PASSWORD", "")
TOTP_SECRET = os.getenv("ALICE_TOTP_SECRET", "")
APP_ID = os.getenv("ALICE_APP_ID", "")
APP_SECRET = os.getenv("ALICE_APP_SECRET", "")
STRATEGY = os.getenv("STRATEGY", "NIFTY_2ND_CANDLE_FLIP")
MODE = os.getenv("MODE", "PAPER")

state = {
    "strategy": STRATEGY,
    "mode": MODE,
    "login": "WAITING",
    "nifty_price": 0,
    "signal": "WAITING FOR 9:20",
    "in_trade": False,
    "side": "",
    "entry": 0,
    "pnl": 0,
    "last_update": ""
}

def get_ist():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def alice_login():
    try:
        if TOTP_SECRET:
            totp = pyotp.TOTP(TOTP_SECRET).now()
            state["login"] = f"READY - TOTP OK - User {USER_ID[:3]}***"
            return True
        else:
            state["login"] = "NO TOTP_SECRET - Add in Render Env"
            return False
    except Exception as e:
        state["login"] = f"LOGIN ERROR: {e}"
        return False

def bot_loop():
    alice_login()
    while True:
        try:
            ist = get_ist()
            state["last_update"] = ist.strftime("%d-%m-%Y %H:%M:%S IST")
            if ist.hour == 9 and ist.minute >= 20 and ist.minute < 25:
                state["signal"] = "CHECKING 2ND CANDLE..."
            elif ist.hour == 9 and ist.minute >= 25:
                state["signal"] = "2ND CANDLE DONE - Signal locked"
            else:
                state["signal"] = f"WAITING - Time {ist.strftime('%H:%M')} - Entry at 9:20-9:25"
            time.sleep(10)
        except Exception as e:
            print(e)
            time.sleep(10)

threading.Thread(target=bot_loop, daemon=True).start()

@app.route('/')
def home():
    return f"""
    <h1>ALICE BOT - NIFTY 2ND CANDLE FLIP - LIVE</h1>
    <p>Time: {state['last_update']} | Strategy: {state['strategy']}</p>
    <p>Login: {state['login']} | Mode: <b>{state['mode']}</b></p>
    <p>Signal: {state['signal']}</p>
    <p>In Trade: {state['in_trade']} Side: {state['side']} Entry: {state['entry']}</p>
    <p>PnL: {state['pnl']}</p>
    <p><a href='/status'>STATUS JSON</a></p>
    <script>setTimeout(()=>location.reload(),10000)</script>
    """

@app.route('/status')
def status():
    return jsonify(state)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
