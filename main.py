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
    "status": "STOPPED", "qty": 65,
    "high": None, "low": None, "candle_locked": False,
    "entry": None, "type": None, "strike": None, "sl": None,
    "ltp": None, "pnl": 0, "funds": 0, "funds_checked": False,
    "logs": [], "trade_done": False,
    "expiry": "17NOV26", "alice_symbol": None, "spot": 25044.65, "atm": 25050,
    # CRUDEOILM - Screenshot la Irukkuradhu!
    "crude_symbol": "CRUDEOILM 17NOV26 8300 PE",
    "crude_display": "CRUDEOILM 17TH NOV 8300 PE",
    "crude_strike": 8300, "crude_type": "PE", "crude_qty": 10,
    "crude_expiry": "17NOV26", "crude_buy_price": 490.00, "crude_sell_price": 502.95,
    "crude_status": "READY", "crude_pnl": 0
}

def log(m):
    t = ist_now().strftime("%H:%M:%S IST")
    BOT["logs"].insert(0, f"[{t}] {m}")
    BOT["logs"] = BOT["logs"][:80]
    print(m, flush=True)

# ---------- NIFTY ----------
def get_alice_symbol(strike, opt_type):
    exp = "17NOV26"
    alice_sym = f"NIFTY {exp} {strike} {opt_type}"
    BOT["alice_symbol"] = alice_sym
    log(f"NIFTY Symbol: [{alice_sym}]")
    return alice_sym

# ---------- CRUDEOILM ✅ - Screenshot Script! ----------
def get_crude_symbol():
    # Screenshot Display: CRUDEOILM 17TH NOV 8300 PE
    # API Format: CRUDEOILM 17NOV26 8300 PE
    api_sym = "CRUDEOILM 17NOV26 8300 PE"
    display = "CRUDEOILM 17TH NOV 8300 PE"
    log(f"CRUDE Symbol API:[{api_sym}] Display:[{display}] Qty:10 Lot:1 Exch:MCX")
    BOT["crude_symbol"] = api_sym
    return api_sym

@app.route('/')
def home():
    auth = f"https://ant.aliceblueonline.com/?appcode={APP_ID}"
    s = STORE.get("session")
    now = ist_now().strftime("%H:%M:%S IST - %d %b %Y")
    return f"<h1>V84 - NIFTY + CRUDEOILM - LIVE TRADE</h1><p>Time: {now} | Session: {'YES' if s else 'ILLA'}</p><p>NIFTY: 17NOV26 | 25000 CE | Lot 65</p><p>CRUDE: CRUDEOILM 17TH NOV 8300 PE | Lot 10 | MCX | LIMIT NRML</p><p><a href='{auth}'><b>1. LOGIN</b></a></p><p><a href='/manual'><b>2. MANUAL</b></a></p><p><a href='/dashboard'><b>3. DASHBOARD</b></a></p><p><a href='/debug'><b>4. DEBUG</b></a></p>"

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

# ---------- GENERIC ORDER - NIFTY + CRUDE Rendume! ----------
def place_order_generic(symbol, exch, qty, trans, pcode, price_type, price=0):
    import requests
    sess = STORE.get("session")
    if not sess:
        log("Order Fail: Session Illa!")
        return {"error": "No Session"}
    payload = {
        "userId": USER_ID, "exch": exch, "pCode": pcode,
        "price": price, "priceType": price_type, "qty": qty, "ret": "DAY",
        "tradingSymbol": symbol, "transType": trans,
        "trigPrice": 0, "orderTag": "VIJAYAN_LIVE", "complexity": "REGULAR", "discQty": 0
    }
    log(f"{trans} Payload: {payload}")
    h = {"Authorization": f"Bearer {sess}", "Content-Type": "application/json", "Accept": "application/json", "userId": USER_ID}
    try:
        r = requests.post("https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/placeOrder/executePlaceOrder", headers=h, json=payload, timeout=12)
        log(f"{trans} ORDER [{symbol}] Qty:{qty} Exch:{exch} Price:{price} Status:{r.status_code} Resp:{r.text[:1000]}")
        try:
            return r.json()
        except:
            return {"raw": r.text[:1000], "status": r.status_code}
    except Exception as e:
        log(f"Order Err {e}")
        return {"error": str(e)}

def place_nifty(strike, opt_type, trans):
    sym = get_alice_symbol(strike, opt_type)
    return place_order_generic(sym, "NFO", 65, trans, "MIS", "MARKET", 0)

# ---------- CRUDE LIVE TRADE ✅ - Screenshot Maadhiri - LIMIT NRML! ----------
def place_crude(trans, price):
    sym = get_crude_symbol()
    # Screenshot: MCX - LIMIT - NRML - Qty 1 Lot = 10
    # BUY Price: Neenga Kodukkuradhu - SELL Price: Neenga Kodukkuradhu
    # MARKET la Panna Koodadhu - LIMIT la thaan Pannanum - Illana Slippage!
    res = place_order_generic(sym, "MCX", 10, trans, "NRML", "LIMIT", price)
    if trans == "BUY":
        BOT["crude_status"] = f"BOUGHT @ {price}"
    else:
        BOT["crude_status"] = f"SOLD @ {price}"
        try:
            BOT["crude_pnl"] = round((price - BOT["crude_buy_price"]) * 10, 2)
        except:
            pass
    return res

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
                        log(f"NIFTY MARKING High:{BOT['high']} Low:{BOT['low']} Spot:{ltp}")
                    else:
                        log("NIFTY MARKING... Waiting for Live Price")
                if now.hour == 9 and now.minute >= 20 and not BOT["candle_locked"] and BOT["high"]:
                    BOT["candle_locked"] = True
                    log(f"NIFTY CANDLE LOCKED High:{BOT['high']} Low:{BOT['low']}")
                if BOT["candle_locked"] and not BOT["trade_done"]:
                    ltp = get_ltp()
                    if ltp:
                        BOT["ltp"] = ltp
                        if ltp > BOT["high"]:
                            atm = int(round(ltp / 50) * 50)
                            strike = atm - 50
                            BOT["atm"] = atm
                            log(f"NIFTY BREAKOUT Spot {ltp} > High {BOT['high']} - ITM1 CE BUY {strike}CE")
                            place_nifty(strike, "CE", "BUY")
                            BOT["entry"] = ltp; BOT["type"] = "CE"; BOT["strike"] = strike; BOT["sl"] = ltp - 30; BOT["trade_done"] = True
                        elif ltp < BOT["low"]:
                            atm = int(round(ltp / 50) * 50)
                            strike = atm + 50
                            BOT["atm"] = atm
                            log(f"NIFTY BREAKDOWN Spot {ltp} < Low {BOT['low']} - ITM1 PE BUY {strike}PE")
                            place_nifty(strike, "PE", "BUY")
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
                        place_nifty(BOT["strike"], BOT["type"], "SELL")
                        BOT["status"] = "CLOSED"
                if now.hour == 15 and now.minute >= 15 and BOT["trade_done"] and BOT["status"] == "RUNNING":
                    log("3:15 TIME EXIT")
                    place_nifty(BOT["strike"], BOT["type"], "SELL")
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
    return f"""
    <h1>VIJAYAN ALGO - NIFTY + CRUDEOILM - LIVE - V84</h1>
    <p><b>Time:</b> {now_str} | <b>Funds:</b> Rs.{b['funds']} | <b>NIFTY Status:</b> {b['status']}</p>
    <h2>1. NIFTY - ITM 1</h2>
    <p><b>Expiry:</b> 17NOV26 | <b>Spot:</b> 25044.65 | <b>ATM:</b> 25050 | <b>Symbol:</b> {b['alice_symbol']} | <b>High:</b> {b['high']} | <b>Low:</b> {b['low']} | <b>Entry:</b> {b['entry']} | <b>Type:</b> {b['strike']} {b['type']} | <b>SL:</b> {b['sl']} | <b>PNL:</b> Rs.{b['pnl']}</p>
    <p><a href='/bot/start'><button style='background:green;color:white;padding:12px'>START NIFTY BOT</button></a> <a href='/bot/stop'><button style='background:red;color:white;padding:12px'>STOP</button></a> <a href='/bot/exit'><button style='background:orange;padding:12px'>EXIT ALL</button></a></p>
    <p><a href='/bot/testorder'><button style='background:purple;color:white;padding:12px'>TEST NIFTY - 25000 CE</button></a></p>
    <hr>
    <h2>2. CRUDEOILM - LIVE TRADE - Screenshot Script!</h2>
    <p><b>Script:</b> {b['crude_display']} | <b>API:</b> {b['crude_symbol']} | <b>Strike:</b> 8300 PE | <b>Qty:</b> 10 (1 Lot) | <b>Exch:</b> MCX | <b>Type:</b> LIMIT NRML</p>
    <p><b>Last Trade (Screenshot):</b> BUY 490.00 -> SELL 502.95 = Profit Rs.129.50 | <b>Crude Status:</b> {b['crude_status']} | <b>Crude PNL:</b> Rs.{b['crude_pnl']}</p>
    <p><b>Manual Live Buttons - Price-a URL la Maathalam: /crude/buy?price=490 - /crude/sell?price=503</b></p>
    <p><a href='/crude/buy?price=490'><button style='background:green;color:white;padding:14px'>🟢 CRUDE BUY 8300 PE @ 490 - LIVE</button></a>
    <a href='/crude/sell?price=503'><button style='background:red;color:white;padding:14px'>🔴 CRUDE SELL 8300 PE @ 503 - LIVE</button></a></p>
    <p><a href='/crude/buy?price=480'><button style='padding:10px'>BUY @ 480</button></a> <a href='/crude/buy?price=495'><button style='padding:10px'>BUY @ 495</button></a> <a href='/crude/sell?price=510'><button style='padding:10px'>SELL @ 510</button></a> <a href='/crude/sell?price=500'><button style='padding:10px'>SELL @ 500</button></a></p>
    <hr><h2>Logs</h2><p>{logs}</p>
    <p><a href='/dashboard'>Refresh</a> | <a href='/'>Home</a> | <a href='/debug'>Debug</a></p>
    """

@app.route('/bot/start')
def start():
    BOT["status"] = "RUNNING"
    BOT["high"] = None; BOT["low"] = None; BOT["candle_locked"] = False
    BOT["trade_done"] = False; BOT["entry"] = None; BOT["pnl"] = 0
    BOT["funds"] = 0; BOT["funds_checked"] = False
    BOT["sl"] = None; BOT["ltp"] = None; BOT["strike"] = None; BOT["type"] = None
    log("NIFTY BOT STARTED")
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

@app.route('/bot/testorder')
def testorder():
    sess = STORE.get("session")
    if not sess:
        log("TEST ORDER Fail: LOGIN pannunga!")
        return redirect("/dashboard")
    strike = int(request.args.get("strike", 25000))
    otype = request.args.get("type", "CE")
    log(f"TEST NIFTY - BUY {strike}{otype} - 1 Lot = 65")
    res = place_nifty(strike, otype, "BUY")
    log(f"TEST Resp: {str(res)[:800]}")
    return redirect("/dashboard")

# ---------- CRUDE LIVE ROUTES ✅ ----------
@app.route('/crude/buy')
def crude_buy():
    sess = STORE.get("session")
    if not sess:
        log("CRUDE BUY Fail: LOGIN pannunga!")
        return redirect("/dashboard")
    try:
        price = float(request.args.get("price", 490))
    except:
        price = 490
    BOT["crude_buy_price"] = price
    log(f"🟢 CRUDE LIVE BUY - {BOT['crude_display']} - Qty 10 - LIMIT {price} - MCX NRML - Screenshot Maadhiri!")
    res = place_crude("BUY", price)
    log(f"CRUDE BUY Resp: {str(res)[:800]}")
    return redirect("/dashboard")

@app.route('/crude/sell')
def crude_sell():
    sess = STORE.get("session")
    if not sess:
        log("CRUDE SELL Fail: LOGIN pannunga!")
        return redirect("/dashboard")
    try:
        price = float(request.args.get("price", 503))
    except:
        price = 503
    # Safety - 316 Maadhiri Thappa Price Poda Koodadhu!
    if price < 400:
        log(f"⚠️ CRUDE SELL BLOCKED! Price {price} - Romma Kammi! - 316 la Rejected Aana Maadhiri Aayidum! - 400-ku Mela Podunga!")
        return redirect("/dashboard")
    BOT["crude_sell_price"] = price
    log(f"🔴 CRUDE LIVE SELL - {BOT['crude_display']} - Qty 10 - LIMIT {price} - MCX NRML")
    res = place_crude("SELL", price)
    log(f"CRUDE SELL Resp: {str(res)[:800]}")
    return redirect("/dashboard")

@app.route('/debug')
def debug():
    import requests
    sess = STORE.get("session")
    out = [f"<h1>DEBUG</h1><p>IST: {ist_now().strftime('%H:%M:%S IST - %d %b %Y')}</p><p>Session: {'YES' if sess else 'ILLA'}</p><p>NIFTY: 17NOV26 25000 CE | CRUDE: CRUDEOILM 17NOV26 8300 PE | Qty 10 | MCX LIMIT NRML</p>"]
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
