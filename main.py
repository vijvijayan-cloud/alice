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
STORE = {"session": None, "out_ip": "Checking..."}
BOT = {"status": "STOPPED", "qty": 65, "high": None, "low": None, "candle_locked": False, "entry": None, "type": None, "strike": None, "sl": None, "ltp": None, "pnl": 0, "funds": 0, "funds_checked": False, "logs": [], "trade_done": False, "expiry": "17NOV26", "alice_symbol": None, "spot": 25044.65, "atm": 25050, "crude_symbol": "CRUDEOILM 17NOV26 8300 PE", "crude_display": "CRUDEOILM 17TH NOV 8300 PE", "crude_status": "READY", "crude_pnl": 0, "last_error": "", "read_only": "Unknown"}
def log(m):
    t = ist_now().strftime("%H:%M:%S IST")
    BOT["logs"].insert(0, f"[{t}] {m}")
    BOT["logs"] = BOT["logs"][:80]
    print(m, flush=True)
def get_out_ip():
    import requests
    try:
        r = requests.get("https://api.ipify.org?format=json", timeout=5)
        STORE["out_ip"] = r.json().get("ip", "Unknown")
        log(f"Render Outbound IP: {STORE['out_ip']} - Idha AliceBlue la Whitelist Pannunga!")
    except Exception as e:
        STORE["out_ip"] = f"Err {e}"
    return STORE["out_ip"]
threading.Thread(target=get_out_ip, daemon=True).start()
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
    return f"<h1>V87 - IP + READ-ONLY CHECK</h1><p>Time: {now} | Session: {'YES' if s else 'ILLA'}</p><p><b>Render IP: {STORE['out_ip']}</b> - Idha AliceBlue Developer Portal la Whitelist Pannunga!</p><p>Funds: Rs.{BOT['funds']} | Read-Only?: {BOT['read_only']}</p><p><a href='{auth}'><b>1. LOGIN</b></a></p><p><a href='/manual'><b>2. MANUAL</b></a></p><p><a href='/dashboard'><b>3. DASHBOARD</b></a></p><p><a href='/debug'><b>4. DEBUG - IP + Orderbook Check</b></a></p>"
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
        j = r.json()
        sess = j.get("userSession")
        log(f"Login Resp Keys: {list(j.keys())} | Session: {'YES' if sess else 'NO'} | Full: {str(j)[:500]}")
        if sess:
            STORE["session"] = str(sess)
            BOT["funds_checked"] = False
            log("LOGIN SUCCESS - Aana Idhu SSO View Session-a Irukkalam - Trading Session Illa!")
            return "<h2 style='color:green'>SUCCESS!</h2><p><a href='/dashboard'><b>DASHBOARD</b></a></p>"
        return f"Session Illa {r.text[:400]} <a href='/'>Home</a>"
    except Exception as e:
        return f"Err {e} <a href='/'>Home</a>"
def get_funds():
    import requests
    sess = STORE.get("session")
    if not sess:
        return -1
    try:
        h = {"Authorization": f"Bearer {sess}", "Content-Type": "application/json"}
        r = requests.get("https://ant.aliceblueonline.com/open-api/od/v1/limits", headers=h, params={"userId": USER_ID}, timeout=7)
        j = r.json()
        res = j.get("result", {})
        if isinstance(res, list):
            res = res[0] if len(res) > 0 else {}
        funds = float(res.get("tradingLimit", 0))
        BOT["funds"] = funds
        log(f"Funds REAL: Rs.{funds}")
        return funds
    except Exception as e:
        log(f"Funds Err: {e}")
        return -1
def get_ltp():
    return None
def check_read_only():
    import requests
    sess = STORE.get("session")
    if not sess:
        return "No Session"
    h = {"Authorization": f"Bearer {sess}", "Content-Type": "application/json"}
    # Orderbook GET - Read-Only Session la kooda Velai Seiyum - Order POST mattum Fail Aagum!
    try:
        r = requests.get("https://ant.aliceblueonline.com/open-api/od/v1/orders/book", headers=h, params={"userId": USER_ID}, timeout=7)
        log(f"Orderbook Check Status:{r.status_code} Resp:[{r.text[:500]}]")
        if r.status_code == 200:
            BOT["read_only"] = "GET Works (Funds/Orderbook) - POST Blocked = Read-Only / IP Block!"
        else:
            BOT["read_only"] = f"Orderbook {r.status_code}"
    except Exception as e:
        log(f"Orderbook Err {e}")
    return BOT["read_only"]
def place_order_generic(symbol, exch, qty, trans, pcode, price_type, price=0):
    import requests
    sess = STORE.get("session")
    if not sess:
        log("Order Fail: Session Illa!")
        return {"error": "No Session"}
    f = get_funds()
    BOT["funds"] = f if f != -1 else BOT["funds"]
    need = price * qty if price_type == "LIMIT" else 0
    log(f"FUNDS: Rs.{BOT['funds']} | Need Rs.{need} | Render IP: {STORE['out_ip']} | If 400 Empty = IP Block / Read-Only!")
    h = {"Authorization": f"Bearer {sess}", "Content-Type": "application/json", "Accept": "application/json", "userId": USER_ID}
    payload_v2 = {"userId": USER_ID, "exchange": exch, "tradingSymbol": symbol, "qty": qty, "transactionType": trans, "priceType": price_type, "productType": pcode, "price": price, "triggerPrice": 0, "validity": "DAY", "orderTag": "VIJAYAN_LIVE"}
    log(f"V2 Payload: {payload_v2}")
    url_v2 = "https://ant.aliceblueonline.com/open-api/od/v1/orders/placeorder"
    try:
        r = requests.post(url_v2, headers=h, json=payload_v2, timeout=15)
        log(f"V2 ORDER [{symbol}] Status:{r.status_code} Raw:[{r.text[:2000]}] Headers:{dict(r.headers)}")
        BOT["last_error"] = f"V2 {r.status_code} [{r.text[:500]}]"
        if r.status_code == 400 and r.text.strip() == "":
            log("⚠️ 400 EMPTY = AliceBlue IP Block / Read-Only User! - Code Thappu Illa! - AliceBlue Portal la IP Whitelist + Trading Enable Pannunga!")
            BOT["read_only"] = "CONFIRMED: 400 Empty = IP Block / Read-Only!"
        try:
            return r.json()
        except:
            return {"raw": r.text[:1000], "status": r.status_code}
    except Exception as e:
        log(f"V2 Order Err {e}")
        return {"error": str(e)}
def place_nifty(strike, opt_type, trans):
    return place_order_generic(get_alice_symbol(strike, opt_type), "NFO", 65, trans, "MIS", "MARKET", 0)
def place_crude(trans, price):
    res = place_order_generic(get_crude_symbol(), "MCX", 10, trans, "NRML", "LIMIT", price)
    BOT["crude_status"] = f"{trans} Try @ {price} - {BOT['last_error'][:120]}"
    return res
def bot_loop():
    while True:
        try:
            if BOT["status"] == "RUNNING":
                now = ist_now()
                if not BOT.get("funds_checked"):
                    f = get_funds(); BOT["funds_checked"] = True; BOT["funds"] = f if f != -1 else 0
                    log(f"Funds: Rs.{BOT['funds']}")
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
                            atm = int(round(ltp / 50) * 50); strike = atm - 50; BOT["atm"] = atm
                            log(f"NIFTY BREAKOUT {strike}CE"); place_nifty(strike, "CE", "BUY")
                            BOT["entry"] = ltp; BOT["type"] = "CE"; BOT["strike"] = strike; BOT["sl"] = ltp - 30; BOT["trade_done"] = True
                        elif ltp < BOT["low"]:
                            atm = int(round(ltp / 50) * 50); strike = atm + 50; BOT["atm"] = atm
                            log(f"NIFTY BREAKDOWN {strike}PE"); place_nifty(strike, "PE", "BUY")
                            BOT["entry"] = ltp; BOT["type"] = "PE"; BOT["strike"] = strike; BOT["sl"] = ltp - 30; BOT["trade_done"] = True
                if BOT["trade_done"] and BOT["entry"] and BOT["ltp"]:
                    profit = BOT["ltp"] - BOT["entry"]
                    new_sl = BOT["entry"] - 30 + profit
                    if new_sl > BOT["sl"]:
                        BOT["sl"] = round(new_sl, 2)
                    BOT["pnl"] = round(profit * 65, 2)
                    if BOT["ltp"] <= BOT["sl"]:
                        log(f"SL HIT Exit @ {BOT['ltp']}"); place_nifty(BOT["strike"], BOT["type"], "SELL"); BOT["status"] = "CLOSED"
                if now.hour == 15 and now.minute >= 15 and BOT["trade_done"] and BOT["status"] == "RUNNING":
                    log("3:15 TIME EXIT"); place_nifty(BOT["strike"], BOT["type"], "SELL"); BOT["status"] = "CLOSED"
            time.sleep(5)
        except Exception as e:
            log(f"Bot Err {e}"); time.sleep(5)
threading.Thread(target=bot_loop, daemon=True).start()
@app.route('/dashboard')
def dashboard():
    b = BOT
    logs = "<br>".join(b["logs"][:40])
    now_str = ist_now().strftime("%H:%M:%S IST - %d %b %Y")
    return f"""
    <h1>VIJAYAN ALGO - V87 - IP BLOCK CHECK</h1>
    <p><b>Time:</b> {now_str} | <b>Funds:</b> Rs.{b['funds']} | <b>Status:</b> {b['status']} | <b>Last:</b> {b['last_error']}</p>
    <p style='background:yellow;padding:10px'><b>Render IP: {STORE['out_ip']}</b> - Idha AliceBlue Portal la Whitelist Pannunga! | <b>Read-Only?:</b> {b['read_only']}</p>
    <h2>1. NIFTY</h2><p>Symbol: {b['alice_symbol']} | PNL: Rs.{b['pnl']}</p>
    <p><a href='/bot/start'><button style='background:green;color:white;padding:12px'>START NIFTY BOT</button></a> <a href='/bot/stop'><button style='background:red;color:white;padding:12px'>STOP</button></a></p>
    <hr><h2>2. CRUDEOILM - 8300 PE</h2><p>Script: {b['crude_symbol']} | Status: {b['crude_status']}</p>
    <p><a href='/crude/buy?price=490'><button style='background:green;color:white;padding:14px'>CRUDE BUY @ 490</button></a> <a href='/crude/sell?price=503'><button style='background:red;color:white;padding:14px'>CRUDE SELL @ 503</button></a> <a href='/debug'><button>DEBUG - IP Check</button></a></p>
    <hr><h2>Logs</h2><p>{logs}</p><p><a href='/dashboard'>Refresh</a> | <a href='/'>Home</a></p>
    """
@app.route('/bot/start')
def start():
    BOT["status"] = "RUNNING"; BOT["high"] = None; BOT["low"] = None; BOT["candle_locked"] = False; BOT["trade_done"] = False; BOT["entry"] = None; BOT["pnl"] = 0; BOT["funds_checked"] = False; BOT["sl"] = None; BOT["ltp"] = None; BOT["strike"] = None; BOT["type"] = None
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
    log(f"CRUDE BUY - {get_crude_symbol()} - Qty 10 - LIMIT {price}")
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
        log(f"SELL BLOCKED Price {price}"); return redirect("/dashboard")
    log(f"CRUDE SELL - {get_crude_symbol()} - Qty 10 - LIMIT {price}")
    res = place_crude("SELL", price); log(f"CRUDE SELL Resp: {str(res)[:800]}"); return redirect("/dashboard")
@app.route('/debug')
def debug():
    import requests
    sess = STORE.get("session")
    ip = get_out_ip()
    ro = check_read_only() if sess else "No Session"
    out = [f"<h1>DEBUG V87 - IP BLOCK PROOF</h1><p>IST: {ist_now().strftime('%H:%M:%S IST - %d %b %Y')}</p><p>Session: {'YES' if sess else 'ILLA'}</p><p><b>Render Outbound IP: {ip}</b> - Idha Copy Panni AliceBlue Portal la Whitelist Pannunga!</p><p>Funds: Rs.{BOT['funds']} | Read-Only Check: {ro} | Last: {BOT['last_error']}</p><p><b>Funds GET 200 + Order POST 400 Empty = IP Block / Read-Only - Code Thappu Illa!</b></p><p>Steps: 1. develop-api.aliceblueonline.com - App Open Pannunga 2. Trading Enable ON 3. IP {ip} Add Pannunga 4. Fresh LOGIN 5. CRUDE BUY Test Pannunga</p>"]
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
