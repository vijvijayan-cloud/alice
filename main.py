import os, hashlib, json, threading, time
from flask import Flask, request, redirect
from datetime import datetime, timedelta, timezone
try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except:
    IST = timezone(timedelta(hours=5, minutes=30))

def ist_now():
    return datetime.now(IST)

app = Flask(__name__)

def clean(n):
    return os.getenv(n, "").strip().replace('"', "").replace("'", "")
USER_ID = clean("ALICE_USER_ID")
APP_ID = clean("ALICE_APP_ID")
APP_SECRET = clean("ALICE_APP_SECRET")
STORE = {"session": None}

BOT = {
    "status": "STOPPED", "mode": "LIVE - ITM 1", "qty": 65,
    "high": None, "low": None, "candle_locked": False,
    "entry": None, "type": None, "strike": None, "sl": None,
    "ltp": None, "pnl": 0, "funds": 0, "funds_checked": False,
    "logs": [], "trade_done": False,
    "expiry": "17NOV26", "alice_symbol": None, "spot": 25044.65, "atm": 25050
}

def log(m):
    t = ist_now().strftime("%H:%M:%S IST")
    BOT["logs"].insert(0, f"[{t}] {m}")
    BOT["logs"] = BOT["logs"][:80]
    print(m, flush=True)

def get_alice_symbol(strike, opt_type):
    exp = "17NOV26"
    alice_sym = f"NIFTY {exp} {strike} {opt_type}"
    display_sym = f"NIFTY 17TH NOV {strike} {opt_type}"
    log(f"Symbol API:[{alice_sym}] Display:[{display_sym}]")
    BOT["alice_symbol"] = alice_sym
    return alice_sym

@app.route('/')
def home():
    auth = f"https://ant.aliceblueonline.com/?appcode={APP_ID}"
    s = STORE.get("session")
    now = ist_now().strftime("%H:%M:%S IST - %d %b %Y")
    return f"<h1>V83 - FULL FILE - DEPLOY FIX</h1><p>Time: {now}</p><p>Session: {'YES' if s else 'ILLA'}</p><p>Expiry: 17NOV26 FIXED | Spot: 25044.65 (Sample Page) | ATM: 25050 | ITM1 CE: 25000 CE | Lot: 65</p><p><a href='{auth}'><b>1. LOGIN</b></a></p><p><a href='/manual'><b>2. MANUAL</b></a></p><p><a href='/dashboard'><b>3. DASHBOARD</b></a></p><p><a href='/debug'><b>4. DEBUG</b></a></p>"

@app.route('/manual')
def manual():
    return "<h1>AuthCode</h1><form action='/exchange'><input name='authCode' placeholder='AuthCode' style='width:320px'><button>EXCHANGE</button></form><br><a href='/'>Home</a>"

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
            log("LOGIN SUCCESS")
            return "<h2 style='color:green'>SUCCESS!</h2><p><a href='/dashboard'><b>DASHBOARD</b></a></p>"
        return f"Session Illa {r.text[:400]} <a href='/'>Home</a>"
    except Exception as e:
        return f"Err {e} <a href='/'>Home</a>"

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
        if isinstance(res, list):
            res = res[0] if len(res) > 0 else {}
        return float(res.get("tradingLimit", 0))
    except Exception as e:
        log(f"Funds Err: {e}")
        return -1

def get_ltp():
    return None

def place_order_api(strike, opt_type, trans):
    import requests
    sess = STORE.get("session")
    if not sess:
        log("Order Fail: Session Illa!")
        return {"error": "No Session"}
    alice_sym = get_alice_symbol(strike, opt_type)
    qty = 65
    payload = {"userId": USER_ID, "exch": "NFO", "pCode": "MIS", "price": 0, "priceType": "MARKET", "qty": qty, "ret": "DAY", "tradingSymbol": alice_sym, "transType": trans, "trigPrice": 0, "orderTag": "VIJAYAN_ITM1", "complexity": "REGULAR", "discQty": 0}
    log(f"{trans} Payload: {payload}")
    h = {"Authorization": f"Bearer {sess}", "Content-Type": "application/json", "Accept": "application/json", "userId": USER_ID}
    try:
        r = requests.post("https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/placeOrder/executePlaceOrder", headers=h, json=payload, timeout=12)
        log(f"{trans} ORDER [{alice_sym}] Qty:{qty} Status:{r.status_code} Resp:{r.text[:1000]}")
        try:
            return r.json()
        except:
            return {"raw": r.text[:1000], "status": r.status_code}
    except Exception as e:
        log(f"Order Err {e}")
        return {"error": str(e)}

def place_buy(s, o):
    return place_order_api(s, o, "BUY")

def place_sell(s, o):
    return place_order_api(s, o, "SELL")

def bot_loop():
    while True:
        try:
            if BOT["status"] == "RUNNING":
                now = ist_now()
                if not BOT.get("funds_checked"):
                    f = get_funds()
                    BOT["funds_checked"] = True
                    BOT["funds"] = f if f != -1 else 0
                    log(f"Funds: Rs.{BOT['funds']}" if f != -1 else "Session Expire - Re-LOGIN!")
                if now.hour == 9 and 15 <= now.minute < 20 and not BOT["candle_locked"]:
                    ltp = get_ltp()
                    if ltp:
                        BOT["ltp"] = ltp
                        if BOT["high"] is None or ltp > BOT["high"]:
                            BOT["high"] = ltp
                        if BOT["low"] is None or ltp < BOT["low"]:
                            BOT["low"] = ltp
                        log(f"MARKING High:{BOT['high']} Low:{BOT['low']} Spot:{ltp}")
                    else:
                        log("MARKING... Waiting for Live Price")
                if now.hour == 9 and now.minute >= 20 and not BOT["candle_locked"] and BOT["high"]:
                    BOT["candle_locked"] = True
                    log(f"CANDLE LOCKED High:{BOT['high']} Low:{BOT['low']}")
                if BOT["candle_locked"] and not BOT["trade_done"]:
                    ltp = get_ltp()
                    if ltp:
                        BOT["ltp"] = ltp
                        if ltp > BOT["high"]:
                            atm = int(round(ltp / 50) * 50)
                            strike = atm - 50
                            BOT["atm"] = atm
                            log(f"BREAKOUT Spot {ltp} > High {BOT['high']} - ITM1 CE BUY {strike}CE")
                            place_buy(strike, "CE")
                            BOT["entry"] = ltp; BOT["type"] = "CE"; BOT["strike"] = strike; BOT["sl"] = ltp - 30; BOT["trade_done"] = True
                        elif ltp < BOT["low"]:
                            atm = int(round(ltp / 50) * 50)
                            strike = atm + 50
                            BOT["atm"] = atm
                            log(f"BREAKDOWN Spot {ltp} < Low {BOT['low']} - ITM1 PE BUY {strike}PE")
                            place_buy(strike, "PE")
                            BOT["entry"] = ltp; BOT["type"] = "PE"; BOT["strike"] = strike; BOT["sl"] = ltp - 30; BOT["trade_done"] = True
                if BOT["trade_done"] and BOT["entry"] and BOT["ltp"]:
                    profit = BOT["ltp"] - BOT["entry"]
                    new_sl = BOT["entry"] - 30 + profit
                    if new_sl > BOT["sl"]:
                        BOT["sl"] = round(new_sl, 2)
                        log(f"Trailing SL -> {BOT['sl']} Profit:{profit:.2f}")
                    BOT["pnl"] = round(profit * 65, 2)
                    if BOT["ltp"] <= BOT["sl"]:
                        log(f"SL HIT Exit @ {BOT['ltp']}")
                        place_sell(BOT["strike"], BOT["type"])
                        BOT["status"] = "CLOSED"
                if now.hour == 15 and now.minute >= 15 and BOT["trade_done"] and BOT["status"] == "RUNNING":
                    log("3:15 TIME EXIT")
                    place_sell(BOT["strike"], BOT["type"])
                    BOT["status"] = "CLOSED"
            time.sleep(5)
        except Exception as e:
            log(f"Bot Err {e}")
            time.sleep(5)

threading.Thread(target=bot_loop, daemon=True).start()

@app.route('/dashboard')
def dashboard():
    b = BOT
    logs = "<br>".join(b["logs"][:40])
    now_str = ist_now().strftime("%H:%M:%S IST - %d %b %Y")
    return f"<h1>VIJAYAN ALGO - ITM 1 - V83</h1><p><b>Time:</b> {now_str} | <b>Funds:</b> Rs.{b['funds']} | <b>Status:</b> {b['status']} | <b>Expiry:</b> 17NOV26 | <b>Lot:</b> 65</p><p><b>Spot (Sample):</b> 25044.65 | <b>ATM:</b> 25050 | <b>Alice Symbol:</b> {b['alice_symbol']}</p><p><b>High:</b> {b['high']} | <b>Low:</b> {b['low']} | <b>Entry:</b> {b['entry']} | <b>Type:</b> {b['strike']} {b['type']} | <b>SL:</b> {b['sl']}</p><hr><p><a href='/bot/start'><button style='background:green;color:white;padding:12px'>START BOT</button></a> <a href='/bot/stop'><button style='background:red;color:white;padding:12px'>STOP</button></a> <a href='/bot/exit'><button style='background:orange;padding:12px'>EXIT ALL</button></a></p><p><a href='/bot/testcandle'><button style='background:blue;color:white;padding:12px'>TEST CANDLE</button></a> <a href='/bot/testorder'><button style='background:purple;color:white;padding:12px'>TEST ORDER - 25000 CE</button></a> <a href='/debug'><button style='padding:12px'>DEBUG</button></a></p><hr><h2>Logs</h2><p>{logs}</p><p><a href='/dashboard'>Refresh</a> | <a href='/'>Home</a></p>"

@app.route('/bot/start')
def start():
    BOT["status"] = "RUNNING"
    BOT["high"] = None; BOT["low"] = None; BOT["candle_locked"] = False
    BOT["trade_done"] = False; BOT["entry"] = None; BOT["pnl"] = 0
    BOT["funds"] = 0; BOT["funds_checked"] = False
    BOT["sl"] = None; BOT["ltp"] = None; BOT["strike"] = None; BOT["type"] = None
    log("BOT STARTED")
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
    BOT["high"] = 25070; BOT["low"] = 25020; BOT["candle_locked"] = True; BOT["ltp"] = 25080
    log("TEST - Spot 25080 - ATM 25100 - ITM1 CE = 25050 CE")
    BOT["entry"] = 25080; BOT["type"] = "CE"; BOT["strike"] = 25050; BOT["sl"] = 25080 - 30; BOT["trade_done"] = True
    return redirect("/dashboard")

@app.route('/bot/testorder')
def testorder():
    sess = STORE.get("session")
    if not sess:
        log("TEST ORDER Fail: LOGIN pannunga!")
        return redirect("/dashboard")
    strike = int(request.args.get("strike", 25000))
    otype = request.args.get("type", "CE")
    log(f"TEST ORDER - BUY {strike}{otype} - 1 Lot = 65 - Sample Page: 25000 CE LTP 256.05")
    res = place_buy(strike, otype)
    log(f"TEST ORDER Resp: {str(res)[:800]}")
    return redirect("/dashboard")

@app.route('/debug')
def debug():
    import requests
    sess = STORE.get("session")
    out = [f"<h1>DEBUG</h1><p>IST: {ist_now().strftime('%H:%M:%S IST - %d %b %Y')}</p><p>Session: {'YES' if sess else 'ILLA - LOGIN pannunga!'}</p><p>Expiry: 17NOV26 | Spot Sample: 25044.65 | Lot: 65</p>"]
    if sess:
        h = {"Authorization": f"Bearer {sess}", "Content-Type": "application/json"}
        try:
            r = requests.get("https://ant.aliceblueonline.com/open-api/od/v1/limits", headers=h, params={"userId": USER_ID}, timeout=7)
            out.append(f"<p><b>Limits:</b> {r.status_code} {r.text[:600]}</p>")
        except Exception as e:
            out.append(f"<p>Err {e}</p>")
    out.append("<p><a href='/dashboard'>Dashboard</a></p>")
    return "<br>".join(out)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
