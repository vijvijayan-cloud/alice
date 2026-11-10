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
STORE = {"session": None, "master_cache": None, "master_time": None, "symbol_cache": {}}

BOT = {
    "status": "STOPPED", "mode": "LIVE - FULLY AUTO - ITM 1", "symbol": "NIFTY", "qty": 65,
    "high": None, "low": None, "candle_locked": False, "entry": None, "type": None,
    "strike": None, "sl": None, "ltp": None, "pnl": 0, "funds": 0, "funds_checked": False,
    "order_id": None, "logs": [], "trade_done": False, "expiry": None,
    "alice_symbol": None, "spot": None, "atm": None, "chain_expiries": [], "chain_source": None
}

def log(m):
    t = ist_now().strftime("%H:%M:%S IST")
    BOT["logs"].insert(0, f"[{t}] {m}")
    BOT["logs"] = BOT["logs"][:100]
    print(m)

# ---------- MASTER FETCH ✅ - AliceBlue Contract Master - Render la Block Aagaadhu! ----------
def fetch_master():
    import requests
    if STORE.get("master_cache") and STORE.get("master_time"):
        if (ist_now() - STORE["master_time"]).total_seconds() < 300:
            return STORE["master_cache"]
    try:
        urls = [
            "https://v2api.aliceblueonline.com/restpy/contract_master?exch=NFO",
            "https://ant.aliceblueonline.com/restpy/contract_master?exch=NFO",
        ]
        for url in urls:
            try:
                r = requests.get(url, timeout=30)
                log(f"Master {url} Status:{r.status_code} Len:{len(r.text)}")
                if r.status_code == 200 and len(r.text) > 1000:
                    STORE["master_cache"] = r.text
                    STORE["master_time"] = ist_now()
                    return r.text
            except Exception as e:
                log(f"Master Err {url} {e}")
        return None
    except Exception as e:
        log(f"fetch_master Err {e}")
        return None

def parse_master_nifty():
    # Master la irundhu - NIFTY OPTIDX Lines-a Mattum Edu - List-a Return Pannu!
    txt = fetch_master()
    if not txt:
        return []
    out = []
    for line in txt.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            j = json.loads(line)
        except:
            continue
        if j.get("instrument_type") != "OPTIDX":
            continue
        fname = str(j.get("formatted_ins_name", "")).strip()
        # STRICT - "NIFTY " nu Start Aaganum - BANKNIFTY / FINNIFTY / MIDCP - SKIP!
        if not fname.upper().startswith("NIFTY "):
            continue
        out.append(j)
    log(f"Master la NIFTY OPTIDX Total: {len(out)}")
    return out

def get_expiry_from_master():
    # Master la irundhu - Ella Expiry-um Edu - Nearest Expiry Edu!
    rows = parse_master_nifty()
    if not rows:
        log("Expiry: Master la NIFTY Illa - Fallback Tuesday!")
        today = ist_now()
        days_ahead = (1 - today.weekday()) % 7
        exp = today if days_ahead == 0 else today + timedelta(days=days_ahead)
        return exp.strftime("%d%b%y").upper(), None
    # Expiry Timestamp -> Date
    exps = {}
    for j in rows:
        try:
            exp_ms = int(j.get("expiry_date", 0))
            if exp_ms <= 0:
                continue
            dt = datetime.fromtimestamp(exp_ms/1000, tz=IST)
            # Past Expiry-a Skip pannu!
            if dt.date() < ist_now().date():
                continue
            key = dt.strftime("%d%b%y").upper()
            exps[key] = dt
        except:
            continue
    sorted_exps = sorted(exps.items(), key=lambda x: x[1])
    exp_list = [k for k, v in sorted_exps]
    BOT["chain_expiries"] = exp_list
    BOT["chain_source"] = "AliceBlue Contract Master (NSE 404 Fallback)"
    log(f"✅ EXPIRIES FROM MASTER: {exp_list}")
    if not sorted_exps:
        return "13NOV26", None
    nearest = sorted_exps[0][0]
    nearest_dt = sorted_exps[0][1]
    BOT["expiry"] = nearest
    log(f"✅ NEAREST EXPIRY: {nearest} = {nearest_dt.strftime('%d %b %Y %A')}")
    return nearest, nearest_dt

def get_alice_symbol(strike, opt_type):
    # Master la irundhu - Strike + Type + Nearest Expiry - 3-um Match Pannu!
    exp_str, exp_dt = get_expiry_from_master()
    alice_sym = f"NIFTY {exp_str} {strike} {opt_type}"
    rows = parse_master_nifty()
    for j in rows:
        try:
            if str(j.get("option_type", "")).upper() != opt_type:
                continue
            if int(float(str(j.get("strike_price", "0")))) != int(strike):
                continue
            # Expiry Match - Timestamp-a Date-a Maathi Compare Pannu!
            try:
                exp_ms = int(j.get("expiry_date", 0))
                dt = datetime.fromtimestamp(exp_ms/1000, tz=IST)
                if dt.strftime("%d%b%y").upper() != exp_str:
                    continue
            except:
                continue
            fname = str(j.get("formatted_ins_name", "")).strip()
            token = j.get("token") or j.get("instrument_token") or j.get("Token") or j.get("exchange_token") or None
            lot = j.get("lot_size", "65")
            log(f"✅ MASTER MATCH! Strike {strike} {opt_type} | Expiry:{exp_str} | Name:[{fname}] | Token:{token} | Lot:{lot} | Alice:[{alice_sym}]")
            BOT["alice_symbol"] = fname
            STORE["symbol_cache"][f"{strike}{opt_type}"] = token
            return fname, token, lot
        except Exception as e:
            continue
    log(f"⚠️ Master la {strike} {opt_type} Expiry {exp_str} la Kedaikkala - Alice Symbol mattum: [{alice_sym}]")
    BOT["alice_symbol"] = alice_sym
    return alice_sym, None, 65

def get_spot():
    # Spot - NIFTY Index - Contract Master la Illa - Funds / Chain la irundhu Edukkalaam - Ippo Master la Spot Illa!
    # Bot ku Spot - AliceBlue Quote la irundhu Edukkanum - Adhu Vera Work - Ippo 0 Return!
    return None

@app.route('/')
def home():
    auth = f"https://ant.aliceblueonline.com/?appcode={APP_ID}"
    s = STORE.get("session")
    now = ist_now().strftime("%H:%M:%S IST - %d %b %Y")
    return f"<h1>V80 - FULL BOT - MASTER FALLBACK - ITM 1</h1><p>Server Time (IST): {now}</p><p>Session: {'YES' if s else 'ILLA'} | Expiry: {BOT['expiry'] or 'Master la irundhu...'} | Lot: 65 FIXED | Source: {BOT['chain_source'] or '...'}</p><p><a href='{auth}'><b>1. LOGIN</b></a></p><p><a href='/manual'><b>2. MANUAL</b></a></p><p><a href='/dashboard'><b>3. DASHBOARD</b></a></p><p><a href='/debug'><b>4. DEBUG</b></a></p><p><a href='/chain'><b>5. CHAIN / MASTER CHECK</b></a></p><p><b>Strategy: NIFTY 1 Lot = 65 - ITM 1 - First 5Min Breakout - SL 30 + Trailing 1 - Expiry: Master la irundhu!</b></p>"

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
            log("✅ LOGIN SUCCESS!")
            return "<h2 style='color:green'>SUCCESS!</h2><p><a href='/dashboard'><b>DASHBOARD - START BOT</b></a></p>"
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
            if len(res) > 0:
                res = res[0]
            else:
                return 0
        return float(res.get("tradingLimit", 0))
    except Exception as e:
        log(f"Funds Err: {e}")
        return -1

def get_ltp():
    # LTP - Spot - Ippo Master la Spot Illa - Bot Loop la - Chain / Quote Connect Panna Venum - Ippo None!
    # Test ku - Manual Spot Use Pannalam - Bot Loop la Waiting nu Varum!
    return None

def place_order_api(strike, opt_type, trans):
    import requests
    sess = STORE.get("session")
    if not sess:
        log("Order Fail: Session Illa!")
        return {"error": "No Session"}
    alice_sym, token, lot = get_alice_symbol(strike, opt_type)
    qty = 65
    payload = {"userId": USER_ID, "exch": "NFO", "pCode": "MIS", "price": 0, "priceType": "MARKET", "qty": qty, "ret": "DAY", "tradingSymbol": alice_sym, "transType": trans, "trigPrice": 0, "orderTag": "VIJAYAN_ITM1", "complexity": "REGULAR", "discQty": 0}
    if token:
        payload["symbolId"] = token
        payload["token"] = token
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

def place_buy(strike, opt_type):
    return place_order_api(strike, opt_type, "BUY")

def place_sell(strike, opt_type):
    return place_order_api(strike, opt_type, "SELL")

def bot_loop():
    while True:
        try:
            if BOT["status"] == "RUNNING":
                now = ist_now()
                if not BOT.get("funds_checked"):
                    f = get_funds()
                    BOT["funds_checked"] = True
                    if f == -1:
                        log("Session Expire - Re-LOGIN pannunga!")
                        BOT["funds"] = 0
                    else:
                        BOT["funds"] = f
                        log(f"Funds: Rs.{BOT['funds']}")
                if now.hour == 9 and 15 <= now.minute < 20 and not BOT["candle_locked"]:
                    ltp = get_ltp()
                    if ltp:
                        BOT["ltp"] = ltp
                        if BOT["high"] is None or ltp > BOT["high"]:
                            BOT["high"] = ltp
                        if BOT["low"] is None or ltp < BOT["low"]:
                            BOT["low"] = ltp
                        log(f"MARKING... High:{BOT['high']} Low:{BOT['low']} Spot:{ltp}")
                    else:
                        log("MARKING... Waiting for Live Price - Quote Connect Pannanum")
                if now.hour == 9 and now.minute >= 20 and not BOT["candle_locked"] and BOT["high"]:
                    BOT["candle_locked"] = True
                    log(f"CANDLE LOCKED ✅ High:{BOT['high']} Low:{BOT['low']} - Waiting for Breakout...")
                if BOT["candle_locked"] and not BOT["trade_done"]:
                    ltp = get_ltp()
                    if ltp:
                        BOT["ltp"] = ltp
                        if ltp > BOT["high"]:
                            atm = int(round(ltp / 50) * 50)
                            strike = atm - 50
                            BOT["atm"] = atm
                            log(f"🚀 BREAKOUT! Spot {ltp} > High {BOT['high']} - ITM 1 CE BUY {strike}CE (ATM {atm} - 50)")
                            res = place_buy(strike, "CE")
                            BOT["entry"] = ltp; BOT["type"] = "CE"; BOT["strike"] = strike; BOT["sl"] = ltp - 30; BOT["trade_done"] = True
                        elif ltp < BOT["low"]:
                            atm = int(round(ltp / 50) * 50)
                            strike = atm + 50
                            BOT["atm"] = atm
                            log(f"🔻 BREAKDOWN! Spot {ltp} < Low {BOT['low']} - ITM 1 PE BUY {strike}PE (ATM {atm} + 50)")
                            res = place_buy(strike, "PE")
                            BOT["entry"] = ltp; BOT["type"] = "PE"; BOT["strike"] = strike; BOT["sl"] = ltp - 30; BOT["trade_done"] = True
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
                if now.hour == 15 and now.minute >= 15 and BOT["trade_done"] and BOT["status"] == "RUNNING":
                    log("⏰ 3:15 TIME EXIT - Auto Square Off!")
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
    return f"""
    <h1>VIJAYAN ALGO - FULLY AUTO - ITM 1 - NIFTY MOMENTUM</h1>
    <p><b>Server Time (IST):</b> {now_str} | <b>Funds:</b> Rs.{b['funds']} | <b>Mode:</b> {b['mode']} | <b>Status:</b> {b['status']} | <b>Expiry:</b> {b['expiry'] or 'Master la irundhu...'} | <b>Lot:</b> 65 | <b>Source:</b> {b['chain_source'] or '...'}</p>
    <table border=1 cellpadding=8><tr><th>Strategy</th><th>Status</th><th>PNL</th><th>Broker</th></tr>
    <tr><td>VIJAYAN NIFTY MOMENTUM - 1 LOT = 65 - ITM 1 - 5MIN BREAKOUT - AUTO - MASTER EXPIRY</td><td>{b['status']}</td><td>Rs.{b['pnl']}</td><td>ALICEBLUE</td></tr></table>
    <h2>Live Status</h2>
    <p><b>Spot:</b> {b['spot']} | <b>ATM:</b> {b['atm']} | <b>Alice Symbol:</b> {b['alice_symbol']}</p>
    <p><b>Expiries From Master:</b> {b['chain_expiries']}</p>
    <p><b>First Candle High:</b> {b['high']} {'✅ LOCKED' if b['candle_locked'] else '🔴 MARKING...'} | <b>Low:</b> {b['low']} {'✅ LOCKED' if b['candle_locked'] else '🔴 MARKING...'}</p>
    <p><b>Entry:</b> {b['entry']} | <b>Type:</b> {b['strike']} {b['type']} | <b>Spot LTP:</b> {b['ltp']} | <b>SL:</b> {b['sl']} (30 Points + Trailing 1)</p>
    <p><b>Trade Done:</b> {b['trade_done']} | <b>Strike Logic:</b> CE = ATM - 50 | PE = ATM + 50</p>
    <hr><p><a href='/bot/start'><button style='background:green;color:white;padding:12px'>▶️ START BOT - FULLY AUTO - ITM 1</button></a>
    <a href='/bot/stop'><button style='background:red;color:white;padding:12px'>⏹️ STOP BOT</button></a>
    <a href='/bot/exit'><button style='background:orange;padding:12px'>🚪 EXIT ALL</button></a></p>
    <p><a href='/bot/testcandle'><button style='background:blue;color:white;padding:12px'>🧪 TEST MODE - Fake Candle Test</button></a>
    <a href='/bot/testorder'><button style='background:purple;color:white;padding:12px'>🧪 IPPAVE TEST ORDER - 24450 CE - Real API Call!</button></a>
    <a href='/chain'><button style='background:teal;color:white;padding:12px'>🔍 CHAIN / MASTER CHECK</button></a>
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
    BOT["atm"] = None; BOT["alice_symbol"] = None
    log("BOT STARTED - FULLY AUTO - ITM 1 - Morning 9:15 la Mark pannum! - Expiry Master la irundhu!")
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
    log("🧪 TEST MODE - ITM 1 Test!")
    log("🧪 Spot 24520 - ATM 24500 - ITM 1 CE = 24450 CE")
    BOT["entry"] = 24520; BOT["type"] = "CE"; BOT["strike"] = 24450; BOT["sl"] = 24520 - 30; BOT["trade_done"] = True
    log(f"🧪 TEST ENTRY ITM 1 CE 24450 @ 24520 SL:{BOT['sl']} - Trailing Test Ready!")
    return redirect("/dashboard")

@app.route('/bot/testorder')
def testorder():
    sess = STORE.get("session")
    if not sess:
        log("TEST ORDER Fail: LOGIN pannunga!")
        return redirect("/dashboard")
    strike = int(request.args.get("strike", 24450))
    otype = request.args.get("type", "CE")
    log(f"🧪 IPPAVE TEST ORDER - BUY {strike}{otype} - 1 Lot = 65 - Master la irundhu Symbol Edukkuren!")
    res = place_buy(strike, otype)
    log(f"🧪 TEST ORDER Final Resp: {str(res)[:800]}")
    return redirect("/dashboard")

@app.route('/chain')
def chain():
    # NSE Try Pannu - 404 Vandha - Master ku Po!
    import requests
    log("🔍 CHAIN CHECK - NSE Try Panren - 404 Vandha Master ku Poven!")
    try:
        s = requests.Session()
        h = {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Referer": "https://www.nseindia.com/option-chain"}
        s.get("https://www.nseindia.com", headers=h, timeout=8)
        r = s.get("https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY", headers=h, timeout=10)
        log(f"NSE Chain Status:{r.status_code} Len:{len(r.text)} Resp:{r.text[:200]}")
        if r.status_code == 200:
            j = r.json()
            log(f"✅ NSE CHAIN OK - Expiries: {j.get('records', {}).get('expiryDates', [])}")
            return redirect("/dashboard")
        else:
            log(f"⚠️ NSE 404 / Block - Render IP Block! - Master ku Poren!")
    except Exception as e:
        log(f"NSE Chain Err {e} - Master ku Poren!")
    # Fallback - Master!
    exp_str, exp_dt = get_expiry_from_master()
    alice_sym, token, lot = get_alice_symbol(24450, "CE")
    log(f"🔍 MASTER RESULT - 24450 CE - Alice:[{alice_sym}] Token:{token} Lot:{lot} Expiry:{exp_str}")
    try:
        # ATM - Spot Theriyaadhaala - 24450 ku Pakkathula Enna Strikes Irukku - List pannu!
        rows = parse_master_nifty()
        strikes = sorted(set([int(float(str(x.get("strike_price", 0)))) for x in rows if str(x.get("option_type", "")).upper() == "CE"]))
        # Nearest Expiry Strikes mattum!
        log(f"Master la CE Strikes Sample: {strikes[:30]} Total:{len(strikes)}")
    except Exception as e:
        log(f"Strike List Err {e}")
    return redirect("/dashboard")

@app.route('/debug')
def debug():
    import requests
    sess = STORE.get("session")
    out = [f"<h1>DEBUG</h1><p>IST Now: {ist_now().strftime('%H:%M:%S IST - %d %b %Y')}</p><p>Session: {'YES - ' + sess[:20] + '...' if sess else 'ILLA - LOGIN pannunga!'}</p><p>Expiry: {BOT['expiry']} | Spot: {BOT['spot']} | Lot: 65 FIXED</p><p>Expiries: {BOT['chain_expiries']} | Source: {BOT['chain_source']}</p>"]
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
