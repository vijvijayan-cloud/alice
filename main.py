import os, hashlib, json, threading, time, math
from flask import Flask, request, redirect
from datetime import datetime
app = Flask(__name__)

def clean(n):
    return os.getenv(n, "").strip().replace('"', "").replace("'", "")
USER_ID = clean("ALICE_USER_ID")
APP_ID = clean("ALICE_APP_ID")
APP_SECRET = clean("ALICE_APP_SECRET")
STORE = {"session": None}

BOT = {
    "status": "STOPPED",
    "mode": "LIVE - FULLY AUTO",
    "symbol": "NIFTY",
    "qty": 65,
    "high": None,
    "low": None,
    "candle_locked": False,
    "entry": None,
    "type": None,
    "strike": None,
    "sl": None,
    "ltp": None,
    "pnl": 0,
    "funds": 0,
    "funds_checked": False,
    "order_id": None,
    "logs": [],
    "trade_done": False
}

def log(m):
    t = datetime.now().strftime("%H:%M:%S")
    BOT["logs"].insert(0, f"[{t}] {m}")
    BOT["logs"] = BOT["logs"][:60]
    print(m)

# ---------- HOME / LOGIN ----------
@app.route('/')
def home():
    auth = f"https://ant.aliceblueonline.com/?appcode={APP_ID}"
    s = STORE.get("session")
    return f"<h1>V63 - FULLY AUTO BOT - FUNDS FIXED</h1><p>Session: {'YES' if s else 'ILLA'}</p><p><a href='{auth}'><b>1. LOGIN</b></a></p><p><a href='/manual'><b>2. MANUAL</b></a></p><p><a href='/dashboard'><b>3. DASHBOARD</b></a></p><p><a href='/debug'><b>4. DEBUG</b></a></p><p><b>Morning LOGIN pannitu - START BOT pannunga - Appuram Bot thana paathukkum!</b></p>"

@app.route('/manual')
def manual():
    return """<h1>AuthCode</h1><form action='/exchange'><input name='authCode' placeholder='AuthCode' style='width:320px'><button>EXCHANGE</button></form><br><a href='/'>Home</a>"""

@app.route('/callback')
def callback():
    c = request.args.get("authCode") or request.args.get("code")
    return redirect(f"/exchange?authCode={c}") if c else "No Code <a href='/'>Home</a>"

@app.route('/exchange')
def exchange():
    import requests
    code = request.args.get("authCode", "").strip()
    if not code:
        return "<h1>AuthCode Illa</h1><a href='/'>Home</a>"
    try:
        REST = "https://ant.aliceblueonline.com/rest/AliceBlueAPIService"
        cs = hashlib.sha256(f"{USER_ID}{code}{APP_SECRET}".encode()).hexdigest()
        r = requests.post(f"{REST}/sso/getUserDetails", json={"checkSum": cs, "userId": USER_ID}, timeout=10)
        sess = r.json().get("userSession")
        if sess:
            STORE["session"] = str(sess)
            return "<h2 style='color:green'>SUCCESS!</h2><p><a href='/dashboard'><b>DASHBOARD - START BOT</b></a></p>"
        return f"Session Illa {r.text[:400]} <a href='/'>Home</a>"
    except Exception as e:
        return f"Err {e} <a href='/'>Home</a>"

# ---------- API HELPERS - FUNDS FIXED ✅ ----------
def get_funds():
    import requests
    sess = STORE.get("session")
    if not sess:
        log("Funds Fail: Session Illa - LOGIN pannunga!")
        return -1
    try:
        h = {"Authorization": f"Bearer {sess}", "Content-Type": "application/json"}
        r = requests.get("https://ant.aliceblueonline.com/open-api/od/v1/limits", headers=h, params={"userId": USER_ID}, timeout=7)
        j = r.json()
        log(f"Funds Raw: {str(j)[:200]}")
        res = j.get("result", {})
        # FIX: result List-a Vandha - First Item-a Edu! - AliceBlue List Anuppudhu!
        if isinstance(res, list):
            if len(res) > 0:
                res = res[0]
            else:
                return 0
        return float(res.get("tradingLimit", 0))
    except Exception as e:
        log(f"Funds Err: {e}")
        return -1

def get_ltp():
    import requests
    sess = STORE.get("session")
    if not sess:
        return None
    try:
        h = {"Authorization": f"Bearer {sess}", "Content-Type": "application/json"}
        r = requests.get("https://ant.aliceblueonline.com/open-api/od/v1/quotes", headers=h, params={"userId": USER_ID}, timeout=5)
        return None
    except:
        return None

def place_buy(strike, opt_type):
    import requests
    sess = STORE.get("session")
    if not sess:
        return {"error": "No Session"}
    h = {"Authorization": f"Bearer {sess}", "Content-Type": "application/json"}
    payload = {"userId": USER_ID, "exchange": "NFO", "tradingSymbol": f"NIFTY{strike}{opt_type}", "quantity": 65, "transactionType": "BUY", "orderType": "MARKET", "productType": "INTRADAY", "validity": "DAY", "price": "0", "triggerPrice": "0", "disclosedQuantity": "0"}
    try:
        r = requests.post("https://ant.aliceblueonline.com/open-api/od/v1/orders/place", headers=h, json=payload, timeout=10)
        log(f"BUY ORDER {strike}{opt_type} Resp:{r.text[:400]}")
        return r.json()
    except Exception as e:
        log(f"Order Err {e}")
        return {"error": str(e)}

def place_sell(strike, opt_type):
    import requests
    sess = STORE.get("session")
    if not sess:
        return {"error": "No Session"}
    h = {"Authorization": f"Bearer {sess}", "Content-Type": "application/json"}
    payload = {"userId": USER_ID, "exchange": "NFO", "tradingSymbol": f"NIFTY{strike}{opt_type}", "quantity": 65, "transactionType": "SELL", "orderType": "MARKET", "productType": "INTRADAY", "validity": "DAY", "price": "0", "triggerPrice": "0", "disclosedQuantity": "0"}
    try:
        r = requests.post("https://ant.aliceblueonline.com/open-api/od/v1/orders/place", headers=h, json=payload, timeout=10)
        log(f"SELL ORDER {strike}{opt_type} Resp:{r.text[:400]}")
        return r.json()
    except Exception as e:
        log(f"Sell Err {e}")
        return {"error": str(e)}

# ---------- BOT LOOP - FULLY AUTO ----------
def bot_loop():
    while True:
        try:
            if BOT["status"] == "RUNNING":
                now = datetime.now()
                # 1. FUNDS - 1 Time mattum
                if not BOT.get("funds_checked"):
                    f = get_funds()
                    BOT["funds_checked"] = True
                    if f == -1:
                        log("Session Expire - Re-LOGIN pannunga!")
                        BOT["funds"] = 0
                    else:
                        BOT["funds"] = f
                        log(f"Funds: Rs.{BOT['funds']}")
                # 2. 9:15 - 9:20 - AUTO MARK FIRST CANDLE
                if now.hour == 9 and 15 <= now.minute < 20 and not BOT["candle_locked"]:
                    ltp = get_ltp()
                    if ltp:
                        BOT["ltp"] = ltp
                        if BOT["high"] is None or ltp > BOT["high"]:
                            BOT["high"] = ltp
                        if BOT["low"] is None or ltp < BOT["low"]:
                            BOT["low"] = ltp
                        log(f"MARKING... High:{BOT['high']} Low:{BOT['low']} LTP:{ltp}")
                    else:
                        log("MARKING... Waiting for Live Price - Quote Connect Pannanum")
                # 3. 9:20 - LOCK CANDLE
                if now.hour == 9 and now.minute >= 20 and not BOT["candle_locked"] and BOT["high"]:
                    BOT["candle_locked"] = True
                    log(f"CANDLE LOCKED ✅ High:{BOT['high']} Low:{BOT['low']} - Waiting for Breakout...")
                # 4. BREAKOUT CHECK - 9:20 to 3:15
                if BOT["candle_locked"] and not BOT["trade_done"]:
                    ltp = get_ltp()
                    if ltp:
                        BOT["ltp"] = ltp
                        if ltp > BOT["high"]:
                            strike = int(round(ltp / 50) * 50)
                            log(f"🚀 BREAKOUT! LTP {ltp} > High {BOT['high']} - CE BUY {strike}CE")
                            res = place_buy(strike, "CE")
                            BOT["entry"] = ltp; BOT["type"] = "CE"; BOT["strike"] = strike; BOT["sl"] = ltp - 30; BOT["trade_done"] = True
                        elif ltp < BOT["low"]:
                            strike = int(round(ltp / 50) * 50)
                            log(f"🔻 BREAKDOWN! LTP {ltp} < Low {BOT['low']} - PE BUY {strike}PE")
                            res = place_buy(strike, "PE")
                            BOT["entry"] = ltp; BOT["type"] = "PE"; BOT["strike"] = strike; BOT["sl"] = ltp - 30; BOT["trade_done"] = True
                # 5. TRAILING SL - 1 Point ku 1 Point
                if BOT["trade_done"] and BOT["entry"] and BOT["ltp"]:
                    profit = BOT["ltp"] - BOT["entry"]
                    new_sl = BOT["entry"] - 30 + profit
                    if new_sl > BOT["sl"]:
                        BOT["sl"] = round(new_sl, 2)
                        log(f"Trailing SL Moved -> {BOT['sl']} Profit:{profit:.2f}")
                    BOT["pnl"] = round(profit * 65, 2)
                    if BOT["ltp"] <= BOT["sl"]:
                        log(f"🛑 SL HIT! Auto Exit @ {BOT['ltp']}")
                        place_sell(BOT["strike"], BOT["type"])
                        BOT["status"] = "CLOSED"
                # 6. 3:15 - TIME EXIT
                if now.hour == 15 and now.minute >= 15 and BOT["trade_done"] and BOT["status"] == "RUNNING":
                    log("⏰ 3:15 TIME EXIT - Auto Square Off!")
                    place_sell(BOT["strike"], BOT["type"])
                    BOT["status"] = "CLOSED"
            time.sleep(5)
        except Exception as e:
            log(f"Bot Err {e}")
            time.sleep(5)

threading.Thread(target=bot_loop, daemon=True).start()

# ---------- DASHBOARD ----------
@app.route('/dashboard')
def dashboard():
    b = BOT
    logs = "<br>".join(b["logs"][:25])
    return f"""
    <h1>VIJAYAN ALGO - FULLY AUTO - NIFTY MOMENTUM</h1>
    <p><b>Funds:</b> Rs.{b['funds']} | <b>Mode:</b> {b['mode']} | <b>Status:</b> {b['status']}</p>
    <table border=1 cellpadding=8><tr><th>Strategy</th><th>Status</th><th>PNL</th><th>Broker</th></tr>
    <tr><td>VIJAYAN NIFTY MOMENTUM - 1 LOT - 5MIN BREAKOUT - AUTO</td><td>{b['status']}</td><td>Rs.{b['pnl']}</td><td>ALICEBLUE</td></tr></table>
    <h2>Live Status</h2>
    <p><b>First Candle High:</b> {b['high']} {'✅ LOCKED' if b['candle_locked'] else '🔴 MARKING...'} | <b>Low:</b> {b['low']} {'✅ LOCKED' if b['candle_locked'] else '🔴 MARKING...'}</p>
    <p><b>Entry:</b> {b['entry']} | <b>Type:</b> {b['strike']} {b['type']} | <b>LTP:</b> {b['ltp']} | <b>SL:</b> {b['sl']} (30 Points + Trailing 1)</p>
    <p><b>Trade Done:</b> {b['trade_done']} | <b>Order ID:</b> {b['order_id']}</p>
    <hr><p><a href='/bot/start'><button style='background:green;color:white;padding:12px'>▶️ START BOT - FULLY AUTO</button></a>
    <a href='/bot/stop'><button style='background:red;color:white;padding:12px'>⏹️ STOP BOT</button></a>
    <a href='/bot/exit'><button style='background:orange;padding:12px'>🚪 EXIT ALL</button></a></p>
    <p><a href='/bot/testcandle'><button style='background:blue;color:white;padding:12px'>🧪 TEST MODE - Fake Candle Test - Evening la Test Pannalam!</button></a>
    <a href='/debug'><button style='padding:12px'>🔍 DEBUG - Session / Funds Check</button></a></p>
    <hr><h2>Logs - Bot Enna Pannudhu?</h2><p>{logs}</p>
    <p><a href='/dashboard'>🔄 Refresh</a> | <a href='/'>Home</a></p>
    """

@app.route('/bot/start')
def start():
    BOT["status"] = "RUNNING"
    BOT["high"] = None; BOT["low"] = None; BOT["candle_locked"] = False
    BOT["trade_done"] = False; BOT["entry"] = None; BOT["pnl"] = 0
    BOT["funds"] = 0; BOT["funds_checked"] = False
    BOT["sl"] = None; BOT["ltp"] = None; BOT["strike"] = None; BOT["type"] = None
    log("BOT STARTED - FULLY AUTO - Morning 9:15 la Mark pannum!")
    return redirect("/dashboard")

@app.route('/bot/stop')
def stop():
    BOT["status"] = "STOPPED"
    log("BOT STOPPED")
    return redirect("/dashboard")

@app.route('/bot/exit')
def exitall():
    import requests
    sess = STORE.get("session")
    if sess:
        h = {"Authorization": f"Bearer {sess}", "Content-Type": "application/json"}
        try:
            r = requests.post("https://ant.aliceblueonline.com/open-api/od/v1/orders/positions/sqroff", headers=h, json={"userId": USER_ID}, timeout=8)
            log(f"EXIT ALL: {r.text[:200]}")
        except Exception as e:
            log(f"Exit Err {e}")
    BOT["status"] = "CLOSED"
    return redirect("/dashboard")

@app.route('/bot/testcandle')
def testcandle():
    BOT["high"] = 24510; BOT["low"] = 24460; BOT["candle_locked"] = True; BOT["ltp"] = 24520
    log("🧪 TEST MODE - Fake Candle Set High:24510 Low:24460 LTP:24520 - Breakout Test!")
    log("🧪 TEST: LTP 24520 > High 24510 - CE BUY Trigger aaganum - Test mattum - Real Order Pogadhu!")
    BOT["entry"] = 24520; BOT["type"] = "CE"; BOT["strike"] = 24500; BOT["sl"] = 24520 - 30; BOT["trade_done"] = True
    log(f"🧪 TEST ENTRY CE 24500 @ 24520 SL:{BOT['sl']} - Trailing Test Ready!")
    return redirect("/dashboard")

@app.route('/debug')
def debug():
    import requests
    sess = STORE.get("session")
    out = [f"<h1>DEBUG</h1><p>Session: {'YES - ' + sess[:20] + '...' if sess else 'ILLA - LOGIN pannunga!'}</p>"]
    if sess:
        h = {"Authorization": f"Bearer {sess}", "Content-Type": "application/json"}
        try:
            r = requests.get("https://ant.aliceblueonline.com/open-api/od/v1/limits", headers=h, params={"userId": USER_ID}, timeout=7)
            out.append(f"<p><b>Limits Status:</b> {r.status_code}</p><p><b>Raw:</b> {r.text[:600]}</p>")
        except Exception as e:
            out.append(f"<p>Err {e}</p>")
    out.append("<p><a href='/dashboard'>Dashboard</a> | <a href='/'>Home</a></p>")
    return "<br>".join(out)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
