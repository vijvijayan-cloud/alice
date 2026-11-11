import os, requests
from datetime import datetime
from flask import Flask, jsonify, redirect

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
ALICE_API_KEY = os.environ.get("ALICE_API_KEY", "")

def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        r = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
        return r.status_code == 200
    except:
        return False

def get_ip():
    try:
        return requests.get("https://api.ipify.org", timeout=5).text
    except:
        return "Unknown"

def get_usdinr():
    try:
        r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/USDINR=X?range=1d&interval=1m", headers={"User-Agent":"Mozilla/5.0"}, timeout=8).json()
        return r["chart"]["result"][0]["meta"]["regularMarketPrice"]
    except:
        return 88.50

CONFIG = {
    "NIFTY": {"spread": 2, "sl_pct": 0.20, "tgt_pct": 0.40},
    "SENSEX": {"spread": 5, "sl_pct": 0.20, "tgt_pct": 0.40},
    "CRUDEOILM": {"spread": 4, "sl_pct": 0.40, "tgt_pct": 0.80},
    "GOLDM": {"spread": 25, "sl_pct": 0.30, "tgt_pct": 0.60},
    "SILVERM": {"spread": 80, "sl_pct": 0.30, "tgt_pct": 0.60},
}
SCRIPTS = {"NIFTY":"^NSEI","SENSEX":"^BSESN","CRUDEOILM":"CL=F","GOLDM":"GC=F","SILVERM":"SI=F"}

def convert_price(name, raw, usdinr):
    if name=="CRUDEOILM": return raw*usdinr
    if name=="GOLDM": return (raw/31.1035)*10*usdinr
    if name=="SILVERM": return (raw/31.1035)*1000*usdinr
    return raw

def get_live_prices():
    usdinr = get_usdinr()
    out = {}
    for name, sym in SCRIPTS.items():
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=15m"
            r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=8).json()
            res = r["chart"]["result"][0]
            meta = res["meta"]
            raw = meta.get("regularMarketPrice", 0)
            prev_raw = meta.get("previousClose", raw)
            price = convert_price(name, raw, usdinr)
            prev = convert_price(name, prev_raw, usdinr)
            chg = price-prev if prev else 0
            pct = (chg/prev*100) if prev else 0

            closes = res["indicators"]["quote"][0]["close"]
            highs = res["indicators"]["quote"][0]["high"]
            lows = res["indicators"]["quote"][0]["low"]
            closes = [c for c in closes if c is not None]
            highs = [h for h in highs if h is not None]
            lows = [l for l in lows if l is not None]

            def ema(data,p):
                k=2/(p+1); e=data[0]
                for v in data[1:]: e=v*k+e*(1-k)
                return e
            ema9 = convert_price(name, ema(closes,9) if len(closes)>9 else raw, usdinr)
            ema21 = convert_price(name, ema(closes,21) if len(closes)>21 else raw, usdinr)

            # --- BREAKOUT LOGIC ---
            # Resistance = Last 20 candles High, Support = Last 20 Low
            last20_high = convert_price(name, max(highs[-20:]), usdinr) if len(highs)>=20 else price
            last20_low = convert_price(name, min(lows[-20:]), usdinr) if len(lows)>=20 else price
            # Prev Candle EMA Cross Check
            prev_ema9 = convert_price(name, ema(closes[:-1],9) if len(closes)>10 else raw, usdinr)
            prev_ema21 = convert_price(name, ema(closes[:-1],21) if len(closes)>22 else raw, usdinr)

            breakout = None
            breakout_type = ""
            if price > last20_high:
                breakout = "BREAKOUT UP 🔥"
                breakout_type = "UP"
            elif price < last20_low:
                breakout = "BREAKDOWN DOWN 🔻"
                breakout_type = "DOWN"
            elif prev_ema9 <= prev_ema21 and ema9 > ema21:
                breakout = "EMA CROSSOVER UP 🚀"
                breakout_type = "UP"
            elif prev_ema9 >= prev_ema21 and ema9 < ema21:
                breakout = "EMA CROSSOVER DOWN 📉"
                breakout_type = "DOWN"

            # --- ONLY OPTIONS BUYING - NO SELLING ---
            # Uptrend = CE BUY, Downtrend = PE BUY, Sideways = WAIT
            # SELL Signal-e Kidayadhu!
            if ema9 > ema21 and price > ema9:
                action = "BUY CE"
                signal = "BUY CE"
                color = "green"
                trend = "UPTREND ▲"
                strength = 85
            elif ema9 < ema21 and price < ema9:
                action = "BUY PE"
                signal = "BUY PE"
                color = "green"  # PE BUY-um Buying Thaan - Green Thaan!
                trend = "DOWNTREND ▼ - PE BUY CHANCE"
                strength = 82
            elif breakout_type == "UP":
                action = "BUY CE"
                signal = "BUY CE"
                color = "green"
                trend = "BREAKOUT UP 🔥"
                strength = 88
            elif breakout_type == "DOWN":
                action = "BUY PE"
                signal = "BUY PE"
                color = "green"
                trend = "BREAKDOWN - PE BUY 🔻"
                strength = 88
            else:
                action = "WAIT"
                signal = "WAIT"
                color = "orange"
                trend = "SIDEWAYS ◐ - WAIT"
                strength = 45

            conf = min(92, max(50, strength + abs(pct)*5))
            cfg = CONFIG[name]
            bid = price-cfg["spread"]; ask = price+cfg["spread"]; live=(bid+ask)/2

            # SL / TGT - Buying-ku Mattum
            if action in ["BUY CE","BUY PE"]:
                entry = ask
                sl = round(entry*(1-cfg["sl_pct"]/100),2)
                tgt = round(entry*(1+cfg["tgt_pct"]/100),2)
                tgt2 = round(entry*(1+cfg["tgt_pct"]/100*2),2)
                option = f"{name} {action} - OPTIONS BUYING"
            else:
                entry = live; sl = round(entry*0.998,2); tgt = round(entry*1.002,2); tgt2 = round(entry*1.004,2); option = f"{name} - WAIT"

            out[name]={"symbol":sym,"price":round(live,2),"live":round(live,2),"bid":round(bid,2),"ask":round(ask,2),"prev":round(prev,2),"change":round(chg,2),"pct":round(pct,2),"signal":signal,"action":action,"color":color,"trend":trend,"ema9":round(ema9,2),"ema21":round(ema21,2),"confidence":round(conf),"usdinr":round(usdinr,2),"entry":round(entry,2),"sl":sl,"tgt":tgt,"tgt2":tgt2,"option":option,"spread":round(ask-bid,2),"breakout":breakout,"breakout_type":breakout_type,"resistance":round(last20_high,2),"support":round(last20_low,2)}
        except:
            out[name]={"symbol":sym,"price":0,"live":0,"bid":0,"ask":0,"prev":0,"change":0,"pct":0,"signal":"WAIT","action":"WAIT","color":"orange","trend":"Loading...","ema9":0,"ema21":0,"confidence":0,"usdinr":88.5,"entry":0,"sl":0,"tgt":0,"tgt2":0,"option":"WAIT","spread":0,"breakout":None,"breakout_type":"","resistance":0,"support":0}
    return out

def get_ai_suggestion():
    prices=get_live_prices()
    # Only Buying Candidates - WAIT-a Thavirthu
    candidates = {k:v for k,v in prices.items() if v["action"] in ["BUY CE","BUY PE"] and v["price"]!=0}
    if not candidates:
        # No Buy - Best WAIT
        best_name = max(prices, key=lambda k: prices[k]["confidence"] if prices[k]["price"]!=0 else -1)
        d = prices[best_name]
        return {"script":best_name,"action":"WAIT","confidence":d["confidence"],"reason":f"Market la Clear Breakout Illa. {best_name} Sideways. WAIT Pannunga. SELL Panna Maatom - Only Options Buying Thaan.","entry":d["entry"],"target":d["tgt"],"stoploss":d["sl"],"option":f"{best_name} - WAIT","trend":d["trend"],"pct":d["pct"],"all":prices,"breakout":None}
    # Best = Highest Confidence + Breakout First
    best_name = None; best_score=-999
    for name,d in candidates.items():
        score = d["confidence"] + abs(d["pct"])*10
        if d["breakout"]: score+=25
        if score>best_score: best_score=score; best_name=name
    d = candidates[best_name]
    reason = f"{best_name} la {d['trend']}. EMA9 {d['ema9']} vs EMA21 {d['ema21']}. "
    if d["breakout"]:
        reason += f"🔥 BREAKOUT: {d['breakout']}! Resistance {d['resistance']} Break Panniduchu! "
    reason += f"Momentum {d['pct']}%. Idhu OPTIONS BUYING Chance - {d['action']} Mattum! SELL Illa!"
    return {"script":best_name,"action":d["action"],"confidence":d["confidence"],"reason":reason,"entry":d["entry"],"target":d["tgt"],"stoploss":d["sl"],"option":d["option"],"trend":d["trend"],"pct":d["pct"],"all":prices,"breakout":d["breakout"],"tgt2":d["tgt2"],"bid":d["bid"],"ask":d["ask"],"resistance":d["resistance"],"support":d["support"]}

@app.route('/api/prices')
def api_prices(): return jsonify(get_live_prices())
@app.route('/api/ai')
def api_ai(): return jsonify(get_ai_suggestion())
@app.route('/api/breakout')
def api_breakout():
    prices=get_live_prices()
    bo=[{"script":k,"breakout":v["breakout"],"action":v["action"],"price":v["live"],"resistance":v["resistance"],"support":v["support"],"confidence":v["confidence"]} for k,v in prices.items() if v["breakout"]]
    return jsonify({"breakouts":bo,"count":len(bo)})

@app.route('/breakout_alert')
def breakout_alert():
    ai=get_ai_suggestion()
    if ai["breakout"]:
        msg=f"🚨 BREAKOUT ALERT!\n\n🔥 {ai['script']} - {ai['breakout']}\n📊 Action: {ai['action']} - OPTIONS BUYING ONLY\n💰 Live: Rs {ai['entry']}\n🟢 Bid: Rs {ai['bid']} | 🔴 Ask: Rs {ai['ask']}\n🎯 TGT1: Rs {ai['target']} | TGT2: Rs {ai.get('tgt2','--')}\n🛑 SL: Rs {ai['stoploss']}\n📍 Resistance: Rs {ai['resistance']} | Support: Rs {ai['support']}\n🔥 Conf: {ai['confidence']}%\n\nTime: {datetime.now()}"
    else:
        msg=f"🤖 AI SUGGESTION - OPTIONS BUYING ONLY\n\n🎯 {ai['script']} ({ai['option']})\n📊 {ai['action']}\n💰 Entry: Rs {ai['entry']}\n🎯 TGT: Rs {ai['target']} | SL: Rs {ai['stoploss']}\n🔥 Conf: {ai['confidence']}%\n\n{ai['reason']}\nTime: {datetime.now()}"
    ok=send_telegram(msg)
    return "✅ Breakout Alert Sent to Telegram!" if ok else "❌ Telegram Failed!"

@app.route('/ai_signal')
def ai_signal(): return breakout_alert()

@app.route('/')
def home():
    ip=get_ip(); now=datetime.now().strftime('%H:%M:%S')
    html="""
    <html><head><title>AI Bot Dashboard - Options Buying Only</title><meta name='viewport' content='width=device-width, initial-scale=1'>
    <style>
    *{box-sizing:border-box} body{background:#0e1117;color:white;font-family:Arial;margin:0;padding:10px;overflow-x:hidden}
    .card{background:#131722;border-radius:12px;padding:14px;border:1px solid #222;margin-top:12px}
    .btn{display:inline-block;padding:12px 16px;border-radius:8px;color:white;text-decoration:none;font-weight:bold;margin:4px;font-size:13px}
    .b1{background:#0088cc}.b2{background:#00c853}.b3{background:#ff9800}.b4{background:#7c3aed}.b5{background:#ff1744}.b6{background:#ff6d00}
    .green{color:#00ff88}.orange{color:#ff9800}
    .top{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
    .grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
    .script-card{background:#1a2030;border-radius:14px;padding:16px;border:1px solid #2a3348}
    .price{font-size:28px;font-weight:bold;margin:4px 0}
    .badge{padding:6px 12px;border-radius:20px;font-size:13px;font-weight:bold;display:inline-block}
    .bg-green{background:#00ff88;color:black}.bg-orange{background:#ff9800;color:black}
    .small{font-size:12px;color:#aaa}
    .bidask{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:10px 0}
    .ba{border-radius:10px;padding:10px;text-align:center}
    .ba-bid{background:#0f2a1d;border:1px solid #00ff88}.ba-ask{background:#2a0f0f;border:1px solid #ff4444}
    .levels{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:10px}
    .lvl{background:#0e1117;border-radius:10px;padding:10px;text-align:center;border:1px solid #333}
    .ai-box{background:linear-gradient(135deg,#1a0033,#0d1b4c);border:2px solid #7c3aed;border-radius:16px;padding:18px;margin-top:12px}
    .ai-grid{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:10px;margin-top:12px}
    .ai-stat{background:#0e1117;border-radius:10px;padding:12px;text-align:center;border:1px solid #333}
    .breakout-box{background:linear-gradient(135deg,#ff6d00,#ff1744);border-radius:16px;padding:16px;margin-top:12px;display:none;animation:blinkBox 1s infinite}
    @keyframes blinkBox{0%{box-shadow:0 0 0 0 rgba(255,109,0,0.7)}100%{box-shadow:0 0 0 12px rgba(255,109,0,0)}}
    .live-dot{animation:blink 1s infinite} @keyframes blink{0%{opacity:1}50%{opacity:0.3}100%{opacity:1}}
    @media(max-width:700px){.grid{grid-template-columns:1fr}.ai-grid{grid-template-columns:1fr 1fr}.price{font-size:24px}}
    </style></head><body>
    <div class='top'><h2 style='margin:5px 0'>🤖 AI BOT DASHBOARD</h2><span style='background:#1e293b;padding:8px 14px;border-radius:20px;font-size:13px'><span class='live-dot'>🟢</span> LIVE | """+now+""" | USDINR: <span id='usdinrTop'>--</span> | IP: """+ip+"""</span></div>
    <div style='background:#0f2a1d;border:1px solid #00ff88;border-radius:10px;padding:10px;margin-top:12px;text-align:center;font-size:14px'>✅ <b>OPTIONS BUYING ONLY</b> • SELL / SHORT - ILLA • CE BUY (Uptrend) / PE BUY (Downtrend) / WAIT Mattum Thaan!</div>

    <!-- 🚨 BREAKOUT NOTIFICATION - NEW -->
    <div id='breakoutBox' class='breakout-box'>
      <div style='font-size:12px;letter-spacing:2px'>🚨 BREAKOUT NOTIFICATION • LIVE ALERT</div>
      <h2 id='breakoutTitle' style='margin:8px 0;font-size:24px'>🔥 BREAKOUT!</h2>
      <div id='breakoutDesc' style='font-size:14px;line-height:1.5'>--</div>
      <div style='margin-top:10px;text-align:center'><a class='btn' style='background:white;color:black' href='/breakout_alert'>📩 Send Breakout Alert to Telegram</a></div>
    </div>

    <div class='ai-box'>
      <div style='font-size:12px;letter-spacing:2px;color:#c4b5fd'>🤖 AI SUGGEST BOT • OPTIONS BUYING ONLY • BEST SCRIPT</div>
      <h2 id='aiTitle' style='margin:10px 0;font-size:22px;line-height:1.3'>🤖 AI Analyzing...</h2>
      <div id='aiReason' style='font-size:13px;color:#e0e7ff;line-height:1.6'>Analyzing...</div>
      <div style='margin-top:10px'>AI Confidence: <b id='aiConf' style='color:#00ff88;font-size:28px'>--%</b> <span id='aiTrend' style='font-size:13px;color:#aaa'>--</span> <span id='aiBreakoutBadge' style='background:#ff6d00;padding:4px 10px;border-radius:20px;font-size:12px;display:none'>🔥 BREAKOUT</span></div>
      <div class='ai-grid'>
        <div class='ai-stat'><div class='small'>🎯 BEST SCRIPT</div><b id='aiScript' style='font-size:16px'>--</b><div class='small' id='aiOption'>--</div></div>
        <div class='ai-stat'><div class='small'>💰 ENTRY (ASK)</div><b id='aiEntry' style='font-size:16px;color:#00ff88'>--</b></div>
        <div class='ai-stat'><div class='small'>🎯 TARGET</div><b id='aiTarget' style='font-size:16px;color:#00ff88'>--</b></div>
        <div class='ai-stat'><div class='small'>🛑 STOPLOSS</div><b id='aiSL' style='font-size:16px;color:#ff4444'>--</b></div>
      </div>
      <div style='margin-top:12px;text-align:center'><a class='btn b2' href='/breakout_alert'>🚨 Send Breakout + AI Signal to Telegram</a><a class='btn b5' href='javascript:loadAI()'>🔄 Refresh AI</a></div>
      <div class='small' style='text-align:center;margin-top:6px'>⚠️ Only Options Buying - SELL / SHORT Seiya Maatom. AI Suggestion Mattum Thaan.</div>
    </div>

    <div class='card' style='border:2px solid #00ff88;text-align:center'><div style='font-size:12px;color:#aaa'>OVERALL MARKET - OPTIONS BUYING ONLY</div><h2 id='mainSignal' class='green' style='margin:8px 0'>Loading...</h2><div id='mainSub' style='font-size:13px'>Checking...</div><div style='margin-top:8px'><span class='small' id='lastUpdate'>--</span></div></div>

    <div class='grid' style='margin-top:12px'>
      <div class='script-card'><div class='small'>NSE • OPTIONS BUYING</div><h3 style='margin:4px 0'>🟣 NIFTY 50</h3><div class='small'>LIVE RATE</div><div class='price green' id='price-NIFTY'>--</div><div id='chg-NIFTY' class='small'>--</div><div id='bo-NIFTY' class='small' style='color:#ff9800;font-weight:bold;margin-top:4px'></div><div class='bidask'><div class='ba ba-bid'><div class='small'>🟢 BID</div><b id='bid-NIFTY' style='font-size:18px'>--</b></div><div class='ba ba-ask'><div class='small'>🔴 ASK</div><b id='ask-NIFTY' style='font-size:18px'>--</b></div></div><div style='text-align:center'><span class='badge bg-green' id='sig-NIFTY'>--</span></div><div class='levels'><div class='lvl'><div class='small'>ENTRY</div><b id='entry-NIFTY' style='color:#00ff88'>--</b></div><div class='lvl'><div class='small'>🎯 TGT1</div><b id='tgt-NIFTY' style='color:#00ff88'>--</b></div><div class='lvl'><div class='small'>🛑 SL</div><b id='sl-NIFTY' style='color:#ff4444'>--</b></div></div><div class='small' style='margin-top:10px;text-align:center'>TGT2: <b id='tgt2-NIFTY' style='color:#00ff88'>--</b> | Res: <span id='res-NIFTY'>--</span> | Sup: <span id='sup-NIFTY'>--</span></div></div>
      <div class='script-card'><div class='small'>BSE • OPTIONS BUYING</div><h3 style='margin:4px 0'>🔵 SENSEX</h3><div class='small'>LIVE RATE</div><div class='price green' id='price-SENSEX'>--</div><div id='chg-SENSEX' class='small'>--</div><div id='bo-SENSEX' class='small' style='color:#ff9800;font-weight:bold;margin-top:4px'></div><div class='bidask'><div class='ba ba-bid'><div class='small'>🟢 BID</div><b id='bid-SENSEX' style='font-size:18px'>--</b></div><div class='ba ba-ask'><div class='small'>🔴 ASK</div><b id='ask-SENSEX' style='font-size:18px'>--</b></div></div><div style='text-align:center'><span class='badge bg-green' id='sig-SENSEX'>--</span></div><div class='levels'><div class='lvl'><div class='small'>ENTRY</div><b id='entry-SENSEX' style='color:#00ff88'>--</b></div><div class='lvl'><div class='small'>🎯 TGT1</div><b id='tgt-SENSEX' style='color:#00ff88'>--</b></div><div class='lvl'><div class='small'>🛑 SL</div><b id='sl-SENSEX' style='color:#ff4444'>--</b></div></div><div class='small' style='margin-top:10px;text-align:center'>TGT2: <b id='tgt2-SENSEX' style='color:#00ff88'>--</b> | Res: <span id='res-SENSEX'>--</span> | Sup: <span id='sup-SENSEX'>--</span></div></div>
      <div class='script-card'><div class='small'>MCX • INR per Barrel</div><h3 style='margin:4px 0'>⚫ CRUDEOILM</h3><div class='small'>LIVE RATE</div><div class='price green' id='price-CRUDEOILM'>--</div><div id='chg-CRUDEOILM' class='small'>--</div><div id='bo-CRUDEOILM' class='small' style='color:#ff9800;font-weight:bold;margin-top:4px'></div><div class='bidask'><div class='ba ba-bid'><div class='small'>🟢 BID</div><b id='bid-CRUDEOILM' style='font-size:18px'>--</b></div><div class='ba ba-ask'><div class='small'>🔴 ASK</div><b id='ask-CRUDEOILM' style='font-size:18px'>--</b></div></div><div style='text-align:center'><span class='badge bg-green' id='sig-CRUDEOILM'>--</span></div><div class='levels'><div class='lvl'><div class='small'>ENTRY</div><b id='entry-CRUDEOILM' style='color:#00ff88'>--</b></div><div class='lvl'><div class='small'>🎯 TGT1</div><b id='tgt-CRUDEOILM' style='color:#00ff88'>--</b></div><div class='lvl'><div class='small'>🛑 SL</div><b id='sl-CRUDEOILM' style='color:#ff4444'>--</b></div></div><div class='small' style='margin-top:10px;text-align:center'>TGT2: <b id='tgt2-CRUDEOILM' style='color:#00ff88'>--</b> | Res: <span id='res-CRUDEOILM'>--</span> | Sup: <span id='sup-CRUDEOILM'>--</span></div></div>
      <div class='script-card'><div class='small'>MCX • INR per 10gm</div><h3 style='margin:4px 0'>🟡 GOLDM</h3><div class='small'>LIVE RATE</div><div class='price green' id='price-GOLDM'>--</div><div id='chg-GOLDM' class='small'>--</div><div id='bo-GOLDM' class='small' style='color:#ff9800;font-weight:bold;margin-top:4px'></div><div class='bidask'><div class='ba ba-bid'><div class='small'>🟢 BID</div><b id='bid-GOLDM' style='font-size:18px'>--</b></div><div class='ba ba-ask'><div class='small'>🔴 ASK</div><b id='ask-GOLDM' style='font-size:18px'>--</b></div></div><div style='text-align:center'><span class='badge bg-green' id='sig-GOLDM'>--</span></div><div class='levels'><div class='lvl'><div class='small'>ENTRY</div><b id='entry-GOLDM' style='color:#00ff88'>--</b></div><div class='lvl'><div class='small'>🎯 TGT1</div><b id='tgt-GOLDM' style='color:#00ff88'>--</b></div><div class='lvl'><div class='small'>🛑 SL</div><b id='sl-GOLDM' style='color:#ff4444'>--</b></div></div><div class='small' style='margin-top:10px;text-align:center'>TGT2: <b id='tgt2-GOLDM' style='color:#00ff88'>--</b> | Res: <span id='res-GOLDM'>--</span> | Sup: <span id='sup-GOLDM'>--</span></div></div>
      <div class='script-card' style='grid-column:span 2'><div class='small'>MCX • INR per Kg</div><h3 style='margin:4px 0'>⚪ SILVERM</h3><div class='small'>LIVE RATE</div><div class='price green' id='price-SILVERM'>--</div><div id='chg-SILVERM' class='small'>--</div><div id='bo-SILVERM' class='small' style='color:#ff9800;font-weight:bold;margin-top:4px'></div><div class='bidask'><div class='ba ba-bid'><div class='small'>🟢 BID</div><b id='bid-SILVERM' style='font-size:18px'>--</b></div><div class='ba ba-ask'><div class='small'>🔴 ASK</div><b id='ask-SILVERM' style='font-size:18px'>--</b></div></div><div style='text-align:center'><span class='badge bg-green' id='sig-SILVERM'>--</span></div><div class='levels'><div class='lvl'><div class='small'>ENTRY</div><b id='entry-SILVERM' style='color:#00ff88'>--</b></div><div class='lvl'><div class='small'>🎯 TGT1</div><b id='tgt-SILVERM' style='color:#00ff88'>--</b></div><div class='lvl'><div class='small'>🛑 SL</div><b id='sl-SILVERM' style='color:#ff4444'>--</b></div></div><div class='small' style='margin-top:10px;text-align:center'>TGT2: <b id='tgt2-SILVERM' style='color:#00ff88'>--</b> | Res: <span id='res-SILVERM'>--</span> | Sup: <span id='sup-SILVERM'>--</span></div></div>
    </div>

    <div class='card'><b>💰 BOT STATUS</b><div style='display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #222'><span>Mode</span><b class='green'>OPTIONS BUYING ONLY ✅ - NO SELLING</b></div><div style='display:flex;justify-content:space-between;padding:8px 0'><span>Chart</span><b>❌ Removed - No Chart</b></div><div style='display:flex;justify-content:space-between;padding:8px 0'><span>Breakout Alert</span><b class='green'>✅ ACTIVE</b></div></div>
    <div style='margin-top:12px'><a class='btn b1' href='/test_telegram'>📩 Test Telegram</a><a class='btn b6' href='/breakout_alert'>🚨 Breakout Alert</a><a class='btn b3' href='/debug'>🔍 Debug</a><a class='btn b4' href='/login'>🔐 Login</a></div>
    <script>
    function fmt(n){ return 'Rs '+n.toLocaleString('en-IN',{maximumFractionDigits:0}); }
    function loadPrices(){
      fetch('/api/prices').then(r=>r.json()).then(data=>{
        let ce=0, pe=0, wait=0;
        for(let name in data){ let d=data[name]; if(d.price==0) continue;
          let peEl=document.getElementById('price-'+name); peEl.innerText=fmt(d.live); peEl.style.color=d.color=='green'?'#00ff88':'#ff9800';
          document.getElementById('chg-'+name).innerText=(d.change>=0?'▲ + ':'▼ ')+fmt(Math.abs(d.change))+' ('+d.pct+'%)';
          document.getElementById('bid-'+name).innerText=fmt(d.bid); document.getElementById('ask-'+name).innerText=fmt(d.ask);
          document.getElementById('entry-'+name).innerText=fmt(d.entry); document.getElementById('tgt-'+name).innerText=fmt(d.tgt); document.getElementById('sl-'+name).innerText=fmt(d.sl); document.getElementById('tgt2-'+name).innerText=fmt(d.tgt2);
          document.getElementById('res-'+name).innerText=fmt(d.resistance); document.getElementById('sup-'+name).innerText=fmt(d.support);
          let bo=document.getElementById('bo-'+name); if(d.breakout){ bo.innerText='🔥 '+d.breakout+' - Res '+fmt(d.resistance)+' Break!'; } else { bo.innerText='Res: '+fmt(d.resistance)+' | Sup: '+fmt(d.support); }
          let se=document.getElementById('sig-'+name);
          if(d.action=='BUY CE'){ se.innerText='✅ BUY CE - OPTIONS BUYING'; se.className='badge bg-green'; ce++; }
          else if(d.action=='BUY PE'){ se.innerText='✅ BUY PE - OPTIONS BUYING'; se.className='badge bg-green'; pe++; }
          else { se.innerText='◐ WAIT - NO TRADE'; se.className='badge bg-orange'; wait++; }
          document.getElementById('usdinrTop').innerText='Rs '+d.usdinr;
        }
        let m=document.getElementById('mainSignal');
        if(ce>0 || pe>0){ m.innerText='✅ BUYING CHANCE: '+ce+' CE BUY + '+pe+' PE BUY | '+wait+' WAIT'; m.className='green'; }
        else { m.innerText='◐ WAIT - NO BUYING CHANCE - SELL Panna Maatom'; m.className='orange'; }
        document.getElementById('mainSub').innerText='CE BUY = Price Mela Pogum | PE BUY = Price Keela Pogum | Rendumey OPTIONS BUYING Thaan - SELL Illa!';
        document.getElementById('lastUpdate').innerText='Last Update: '+new Date().toLocaleTimeString('en-IN');
      });
    }
    function loadAI(){
      fetch('/api/ai').then(r=>r.json()).then(ai=>{
        let emoji = ai.action=='WAIT' ? '◐' : '✅';
        document.getElementById('aiTitle').innerHTML=emoji+' AI SUGGESTS: <span style="color:#00ff88">'+ai.action+' - '+ai.script+'</span> (OPTIONS BUYING ONLY)';
        document.getElementById('aiReason').innerText='🧠 '+ai.reason;
        document.getElementById('aiConf').innerText=ai.confidence+'%';
        document.getElementById('aiTrend').innerText=ai.trend+' | '+ai.pct+'%';
        document.getElementById('aiScript').innerText=ai.script; document.getElementById('aiOption').innerText=ai.option;
        document.getElementById('aiEntry').innerText=fmt(ai.entry); document.getElementById('aiTarget').innerText=fmt(ai.target); document.getElementById('aiSL').innerText=fmt(ai.stoploss);
        let badge=document.getElementById('aiBreakoutBadge'); if(ai.breakout){ badge.style.display='inline-block'; badge.innerText='🔥 '+ai.breakout; } else { badge.style.display='none'; }
        // Breakout Box
        let box=document.getElementById('breakoutBox');
        if(ai.breakout){
          box.style.display='block';
          document.getElementById('breakoutTitle').innerText='🔥 BREAKOUT: '+ai.script+' - '+ai.breakout;
          document.getElementById('breakoutDesc').innerText=ai.script+' Resistance Rs '+ai.resistance+' Break Panniduchu! Ippo '+ai.action+' - Entry Rs '+ai.entry+' | TGT Rs '+ai.target+' | SL Rs '+ai.stoploss+' | Conf '+ai.confidence+'% - OPTIONS BUYING ONLY!';
        } else { box.style.display='none'; }
      });
      fetch('/api/breakout').then(r=>r.json()).then(b=>{
        if(b.count>0 && document.getElementById('breakoutBox').style.display=='none'){
          let first=b.breakouts[0];
          document.getElementById('breakoutBox').style.display='block';
          document.getElementById('breakoutTitle').innerText='🔥 BREAKOUT: '+first.script+' - '+first.breakout;
          document.getElementById('breakoutDesc').innerText=first.script+' la Breakout Vandhuruchu! '+first.action+' Chance! Price Rs '+first.price+' | Res '+first.resistance;
        }
      });
    }
    loadPrices(); loadAI();
    setInterval(loadPrices, 5000);
    setInterval(loadAI, 15000);
    </script></body></html>
    """
    return html

@app.route('/test_telegram')
def test_telegram():
    ok=send_telegram(f"✅ AI Bot Test Success! Time: {datetime.now()}")
    return "✅ Telegram Sent!" if ok else "❌ Telegram Failed!"
@app.route('/order_test')
def order_test():
    send_telegram(f"🚀 ORDER PLACED: NIFTY CE BUY 100 Qty @ 120 Time: {datetime.now()}")
    return "Order Alert Sent!"
@app.route('/login')
def login(): return redirect(f"https://ant.aliceblueonline.com/?appcode={ALICE_API_KEY}")
@app.route('/debug')
def debug(): return jsonify({"ip":get_ip(),"telegram":bool(TELEGRAM_BOT_TOKEN),"prices":get_live_prices(),"ai":get_ai_suggestion()})
if __name__=='__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT",5000)))
