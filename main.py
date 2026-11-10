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
STORE = {"session": None, "crude_token": None}

BOT = {
    "status": "STOPPED", "qty": 65, "high": None, "low": None, "candle_locked": False,
    "entry": None, "type": None, "strike": None, "sl": None, "ltp": None, "pnl": 0,
    "funds": 0, "funds_checked": False, "logs": [], "trade_done": False,
    "expiry": "17NOV26", "alice_symbol": None, "spot": 25044.65, "atm": 25050,
    "crude_symbol": "CRUDEOILM 17NOV26 8300 PE",
    "crude_display": "CRUDEOILM 17TH NOV 8300 PE",
    "crude_status": "READY", "crude_pnl": 0, "last_error": ""
}

def log(m):
    t = ist_now().strftime("%H:%M:%S IST")
    BOT["logs"].insert(0, f"[{t}] {m}")
    BOT["logs"] = BOT["logs"][:80]
    print(m, flush=True)

def get_alice_symbol(strike, opt_type):
    sym = f"NIFTY 17NOV26 {strike} {opt_type}"
    BOT["alice_symbol"] = sym
    return sym

def get_crude_symbol():
    return "CRUDEOILM 17NOV26 8300 PE"

@app.route('/')
def home():
    auth = f"https://ant.aliceblueonline.com/?appcode={APP_ID}"
    s = STORE.get("session")
    now = ist_now().strftime("%H:%M:%S IST - %d %b %Y")
    return f"<h1>V85 - CRUDE FIX - TOKEN + REAL ERROR</h1><p>Time: {now} | Session: {'YES' if s else 'ILLA'}</p><p>NIFTY: 17NOV26 | CRUDE: CRUDEOILM 17TH NOV 8300 PE | Lot 10 | MCX LIMIT NRML</p><p><a href='{auth}'><b>1. LOGIN</b></a></p><p><a href='/manual'><b>2. MANUAL</b></a></p><p><a href='/dashboard'><b>3. DASHBOARD</b></a></p><p><a href='/debug'><b>4. DEBUG - Funds + Token Check</b></a></p>"

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
            BOT["funds_checked"] = False
            log("LOGIN SUCCESS - Fresh Session!")
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
        log(f"Funds Status:{r.status_code} Raw:{r.text[:500]}")
        j = r.json()
        res = j.get("result", {})
        if isinstance(res, list):
            res = res[0] if len(res) > 0 else {}
        # AliceBlue - tradingLimit / available / cash - Ella Field-um Paaru!
        funds = res.get("tradingLimit", res.get("available", res.get("cash", 0)))
        log(f"Funds Parsed: {funds} | Full Keys: {list(res.keys())}")
        return float(funds)
    except Exception as e:
        log(f"Funds Err: {e}")
        return -1

def get_ltp():
    return None

# ---------- V85 FIX ✅ - REAL ERROR + TOKEN TRY + FUNDS BLOCK! ----------
def place_order_generic(symbol, exch, qty, trans, pcode, price_type, price=0):
    import requests
    sess = STORE.get("session")
    if not sess:
        log("Order Fail: Session Illa - LOGIN pannunga!")
        return {"error": "No Session"}
    # 1. FUNDS CHECK - Munnadiye Block Pannu - 400 Varadha Thadukkanum!
    f = get_funds()
    BOT["funds"] = f if f != -1 else BOT["funds"]
    need = price * qty if price_type == "LIMIT" else 0
    log(f"FUNDS CHECK: Available Rs.{BOT['funds']} | Need Approx Rs.{need} for {symbol} @ {price} x {qty}")
    if f != -1 and f < 500 and exch == "MCX":
        log(f"⚠️ FUNDS LOW Rs.{f} - Order Pogadhu! - AliceBlue 400 Kodukkum! - Funds Add Pannunga / Settlement Wait Pannunga!")
        BOT["last_error"] = f"Funds Low Rs.{f} - Order Blocked - No API Call!"
        # Ippavum Try Pannalam - Aana Log la Clear-a Theriyum!
    payload = {
        "userId": USER_ID, "exch": exch, "pCode": pcode,
        "price": price, "priceType": price_type, "qty": qty, "ret": "DAY",
        "tradingSymbol": symbol, "transType": trans,
        "trigPrice": 0, "orderTag": "VIJAYAN_LIVE", "complexity": "REGULAR", "discQty": 0
    }
    # Token Irundha - Anuppu!
    if STORE.get("crude_token") and exch == "MCX":
        payload["symbolId"] = STORE["crude_token"]
    log(f"{trans} Payload: {payload}")
    h = {"Authorization": f"Bearer {sess}", "Content-Type": "application/json", "Accept": "application/json", "userId": USER_ID}
    try:
        # 2. REAL ERROR - Headers + Text Ellam Log Pannu - Empty Illa!
        r = requests.post("https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/placeOrder/executePlaceOrder", headers=h, json=payload, timeout=12)
        log(f"{trans} ORDER [{symbol}] Status:{r.status_code} Headers:{dict(r.headers)}")
        log(f"{trans} ORDER Raw Resp Len:{len(r.text)} Raw:[{r.text[:2000]}]")
        BOT["last_error"] = f"Status {r.status_code} Resp [{r.text[:500]}]"
        # 3. Alternative - Open API Try Pannu - Old API 400 na!
        if r.status_code == 400:
            log("⚠️ Old API 400 - New Open API la Try Panren!")
            try:
                payload2 = {"userId": USER_ID, "exchange": exch, "tradingSymbol": symbol, "qty": qty, "transactionType": trans, "priceType": price_type, "productType": pcode, "price": price, "triggerPrice": 0, "validity": "DAY"}
                r2 = requests.post("https://ant.aliceblueonline.com/open-api/od/v1/orders/place", headers=h, json=payload2, timeout=12)
                log(f"New API Status:{r2.status_code} Resp:[{r2.text[:2000]}]")
                BOT["last_error"] = f"Old 400 | New {r2.status_code} [{r2.text[:500]}]"
                try:
                    return r2.json()
                except:
                    return {"raw": r2.text[:1000], "status": r2.status_code}
            except Exception as e2:
                log(f"New API Err {e2}")
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

def place_crude(trans, price):
    sym = get_crude_symbol()
    res = place_order_generic(sym, "MCX", 10, trans, "NRML", "LIMIT", price)
    if trans == "BUY":
        BOT["crude_status"] = f"BUY Try @ {price} - {BOT['last_error'][:100]}"
    else:
        BOT["crude_status"] = f"SELL Try @ {price} - {BOT['last_error'][:100]}"
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
                        log(f"NIFTY MARKING High:{BOT['high']} Low:{BOT['low']}")
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
                            log(f"NIFTY BREAKOUT {strike}CE")
                            place_nifty(strike, "CE", "BUY")
                            BOT["entry"] = ltp; BOT["type"] = "CE"; BOT["strike"] = strike; BOT["sl"] = ltp - 30; BOT["trade_done"] = True
                        elif ltp < BOT["low"]:
                            atm = int(round(ltp / 50) * 50)
                            strike = atm + 50
                            BOT["atm"] = atm
                            log(f"NIFTY BREAKDOWN {strike}PE")
                            place_nifty(strike, "PE", "BUY")
                            BOT["entry"] = ltp; BOT["type"] = "PE"; BOT["strike"] = strike; BOT["sl"] = ltp - 30; BOT["trade_done"] = True
                if BOT["trade_done"] and BOT["entry"] and BOT["ltp"]:
                    profit = BOT["ltp"] - BOT["entry"]
                    new_sl = BOT["entry"] - 30 + profit
                    if new_sl > BOT["sl"]:
                        BOT["sl"] = round(new_sl, 2)
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
    <h1>VIJAYAN ALGO - NIFTY + CRUDEOILM - V85 FIX</h1>
    <p><b>Time:</b> {now_str} | <b>Funds:</b> Rs.{b['funds']} | <b>NIFTY Status:</b> {b['status']} | <b>Last Error:</b> {b['last_error']}</p>
    <h2>1. NIFTY - ITM 1</h2>
    <p><b>Expiry:</b> 17NOV26 | <b>Symbol:</b> {b['alice_symbol']} | <b>PNL:</b> Rs.{b['pnl']}</p>
    <p><a href='/bot/start'><button style='background:green;color:white;padding:12px'>START NIFTY BOT</button></a> <a href='/bot/stop'><button style='background:red;color:white;padding:12px'>STOP</button></a> <a href='/bot/testorder'><button style='background:purple;color:white;padding:12px'>TEST NIFTY - 25000 CE</button></a></p>
    <hr><h2>2. CRUDEOILM - LIVE - 8300 PE</h2>
    <p><b>Script:</b> {b['crude_symbol']} | <b>Qty:</b> 10 | <b>MCX LIMIT NRML</b> | <b>Status:</b> {b['crude_status']}</p>
    <p><a href='/crude/buy?price=490'><button style='background:green;color:white;padding:14px'>CRUDE BUY @ 490</button></a> <a href='/crude/sell?price=503'><button style='background:red;color:white;padding:14px'>CRUDE SELL @ 503</button></a></p>
    <p><a href='/crude/buy?price=480'><button>BUY @ 480</button></a> <a href='/crude/sell?price=510'><button>SELL @ 510</button></a> <a href='/debug'><button>DEBUG - Funds Check</button></a></p>
    <hr><h2>Logs - Real Error Ippo Theriyum!</h2><p>{logs}</p>
    <p><a href='/dashboard'>Refresh</a> | <a href='/'>Home</a></p>
    """

@app.route('/bot/start')
def start():
    BOT["status"] = "RUNNING"; BOT["high"] = None; BOT["low"] = None; BOT["candle_locked"] = False; BOT["trade_done"] = False; BOT["entry"] = None; BOT["pnl"] = 0; BOT["funds"] = 0; BOT["funds_checked"] = False; BOT["sl"] = None; BOT["ltp"] = None; BOT["strike"] = None; BOT["type"] = None
    log("NIFTY BOT STARTED"); return redirect("/dashboard")
@app.route('/bot/stop')
def stop():
    BOT["status"] = "STOPPED"; log("BOT STOPPED"); return redirect("/dashboard")
@app.route('/bot/testorder')
def testorder():
    if not STORE.get("session"):
        log("TEST Fail: LOGIN pannunga!"); return redirect("/dashboard")
    log("TEST NIFTY - BUY 25000CE"); res = place_nifty(25000, "CE", "BUY"); log(f"TEST Resp: {str(res)[:800]}"); return redirect("/dashboard")
@app.route('/crude/buy')
def crude_buy():
    if not STORE.get("session"):
        log("CRUDE BUY Fail: LOGIN pannunga!"); return redirect("/dashboard")
    try:
        price = float(request.args.get("price", 490))
    except:
        price = 490
    log(f"CRUDE LIVE BUY - {get_crude_symbol()} - Qty 10 - LIMIT {price} - MCX NRML")
    res = place_crude("BUY", price); log(f"CRUDE BUY Resp: {str(res)[:800]}"); return redirect("/dashboard")
@app.route('/crude/sell')
def crude_sell():
    if not STORE.get("session"):
        log("CRUDE SELL Fail: LOGIN pannunga!"); return redirect("/dashboard")
    try:
        price = float(request.args.get("price", 503))
    except:
        price = 503
    if price < 400:
        log(f"SELL BLOCKED Price {price} - 400-ku Keela Poda Koodadhu!"); return redirect("/dashboard")
    log(f"CRUDE LIVE SELL - {get_crude_symbol()} - Qty 10 - LIMIT {price}")
    res = place_crude("SELL", price); log(f"CRUDE SELL Resp: {str(res)[:800]}"); return redirect("/dashboard")
@app.route('/debug')
def debug():
    import requests
    sess = STORE.get("session")
    out = [f"<h1>DEBUG V85</h1><p>IST: {ist_now().strftime('%H:%M:%S IST - %d %b %Y')}</p><p>Session: {'YES' if sess else 'ILLA - LOGIN pannunga!'}</p><p>Funds (Dashboard): Rs.{BOT['funds']} | Last Error: {BOT['last_error']}</p><p>CRUDE: CRUDEOILM 17NOV26 8300 PE | NIFTY: 17NOV26 25000 CE</p>"]
    if sess:
        h = {"Authorization": f"Bearer {sess}", "Content-Type": "application/json"}
        try:
            r = requests.get("https://ant.aliceblueonline.com/open-api/od/v1/limits", headers=h, params={"userId": USER_ID}, timeout=7)
            out.append(f"<p><b>Limits Status:</b> {r.status_code}</p><p><b>Raw:</b> {r.text[:1000]}</p>")
        except Exception as e:
            out.append(f"<p>Err {e}</p>")
    out.append("<p><a href='/dashboard'>Dashboard</a></p>")
    return "<br>".join(out)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
