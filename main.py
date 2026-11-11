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
            closes = [c for c in closes if c is not None]
            def ema(data,p):
                k=2/(p+1); e=data[0]
                for v in data[1:]: e=v*k+e*(1-k)
                return e
            ema9 = convert_price(name, ema(closes,9) if len(closes)>9 else raw, usdinr)
            ema21 = convert_price(name, ema(closes,21) if len(closes)>21 else raw, usdinr)
            if ema9>ema21: signal="BUY"; color="green"; trend="UPTREND ▲"; strength=80
            elif ema9<ema21: signal="SELL"; color="red"; trend="DOWNTREND ▼"; strength=80
            else: signal="WAIT"; color="orange"; trend="SIDEWAYS ◐"; strength=45
            conf = min(92,max(50,strength+abs(pct)*5))
            cfg = CONFIG[name]
            bid = price-cfg["spread"]; ask = price+cfg["spread"]; live=(bid+ask)/2
            if signal=="BUY":
                entry=ask; sl=round(entry*(1-cfg["sl_pct"]/100),2); tgt=round(entry*(1+cfg["tgt_pct"]/100),2); tgt2=round(entry*(1+cfg["tgt_pct"]/100*2),2); option=f"{name} CE BUY"
            elif signal=="SELL":
                entry=bid; sl=round(entry*(1+cfg["sl_pct"]/100),2); tgt=round(entry*(1-cfg["tgt_pct"]/100),2); tgt2=round(entry*(1-cfg["tgt_pct"]/100*2),2); option=f"{name} PE BUY"
            else:
                entry=live; sl=round(entry*0.998,2); tgt=round(entry*1.002,2); tgt2=round(entry*1.004,2); option=f"{name} - WAIT"
            out[name]={"symbol":sym,"price":round(live,2),"live":round(live,2),"bid":round(bid,2),"ask":round(ask,2),"prev":round(prev,2),"change":round(chg,2),"pct":round(pct,2),"signal":signal,"color":color,"trend":trend,"ema9":round(ema9,2),"ema21":round(ema21,2),"confidence":round(conf),"usdinr":round(usdinr,2),"entry":round(entry,2),"sl":sl,"tgt":tgt,"tgt2":tgt2,"option":option,"spread":round(ask-bid,2)}
        except:
            out[name]={"symbol":sym,"price":0,"live":0,"bid":0,"ask":0,"prev":0,"change":0,"pct":0,"signal":"WAIT","color":"orange","trend":"Loading...","ema9":0,"ema21":0,"confidence":0,"usdinr":88.5,"entry":0,"sl":0,"tgt":0,"tgt2":0,"option":"WAIT","spread":0}
    return out

def get_ai_suggestion():
    prices=get_live_prices()
    best=None; best_score=-999
    for name,d in prices.items():
        if d["price"]==0: continue
        score=d["confidence"]+abs(d["pct"])*10
        if score>best_score: best_score=score; best=(name,d)
    if not best: return {"script":"NIFTY","action":"WAIT","confidence":0,"reason":"Loading...","entry":0,"target":0,"stoploss":0,"all":prices}
    name,d=best
    return {"script":name,"action":d["signal"],"confidence":d["confidence"],"reason":f"{name} la EMA9 {d['ema9']} vs EMA21 {d['ema21']} - {d['trend']} - Momentum {d['pct']}% - Bid {d['bid']} Ask {d['ask']}","entry":d["entry"],"target":d["tgt"],"stoploss":d["sl"],"option":d["option"],"trend":d["trend"],"pct":d["pct"],"all":prices}

# --- CHART API - YAHOO -> CANDLES ---
@app.route('/api/chart/<name>')
def api_chart(name):
    name=name.upper()
    if name not in SCRIPTS: return jsonify({"error":"Invalid"}),400
    tf = requests.args.get("tf","15m")
    # Map TF: 1m,5m,15m,1h,1d
    ytf = {"1m":"1m","5m":"5m","15m":"15m","1h":"60m","1d":"1d"}.get(tf,"15m")
    rng = "1d" if tf in ["1m","5m"] else "5d" if tf in ["15m","1h"] else "1mo"
    try:
        usdinr=get_usdinr()
        sym=SCRIPTS[name]
        url=f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range={rng}&interval={ytf}"
        r=requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10).json()
        res=r["chart"]["result"][0]
        ts=res["timestamp"]
        q=res["indicators"]["quote"][0]
        candles=[]
        for i,t in enumerate(ts):
            if q["open"][i] is None: continue
            candles.append({"time":t,"open":round(convert_price(name,q["open"][i],usdinr),2),"high":round(convert_price(name,q["high"][i],usdinr),2),"low":round(convert_price(name,q["low"][i],usdinr),2),"close":round(convert_price(name,q["close"][i],usdinr),2)})
        return jsonify({"candles":candles,"name":name,"usdinr":usdinr})
    except Exception as e:
        return jsonify({"candles":[],"error":str(e)})

@app.route('/api/prices')
def api_prices(): return jsonify(get_live_prices())
@app.route('/api/ai')
def api_ai(): return jsonify(get_ai_suggestion())
@app.route('/ai_signal')
def ai_signal():
    ai=get_ai_suggestion(); d=ai["all"][ai["script"]] if ai["script"] in ai["all"] else {}
    msg=f"🤖 AI SUGGESTION\n\n🎯 {ai['script']} ({ai['option']})\n📊 {ai['action']} | Conf {ai['confidence']}%\n💰 Live: Rs {ai['entry']}\n🟢 Bid: Rs {d.get('bid','--')} | 🔴 Ask: Rs {d.get('ask','--')}\n🎯 TGT1: Rs {ai['target']} | TGT2: Rs {d.get('tgt2','--')}\n🛑 SL: Rs {ai['stoploss']}\n\n🧠 {ai['reason']}\nTime: {datetime.now()}"
    ok=send_telegram(msg)
    return "✅ AI Signal Sent!" if ok else "❌ Telegram Failed!"

@app.route('/')
def home():
    ip=get_ip(); now=datetime.now().strftime('%H:%M:%S')
    html="""
    <html><head><title>AI Bot Dashboard</title><meta name='viewport' content='width=device-width, initial-scale=1'>
    <style>
    *{box-sizing:border-box} body{background:#0e1117;color:white;font-family:Arial;margin:0;padding:10px;overflow-x:hidden}
    .card{background:#131722;border-radius:12px;padding:14px;border:1px solid #222;margin-top:12px}
    .btn{display:inline-block;padding:11px 14px;border-radius:8px;color:white;text-decoration:none;font-weight:bold;margin:4px;font-size:13px}
    .b1{background:#0088cc}.b2{background:#00c853}.b3{background:#ff9800}.b4{background:#7c3aed}.b5{background:#ff1744}
    .green{color:#00ff88}.red{color:#ff4444}.orange{color:#ff9800}
    .top{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
    .grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
    .script-card{background:#1a2030;border-radius:14px;padding:16px;border:1px solid #2a3348}
    .price{font-size:28px;font-weight:bold;margin:4px 0}
    .badge{padding:6px 12px;border-radius:20px;font-size:13px;font-weight:bold;display:inline-block}
    .bg-green{background:#00ff88;color:black}.bg-red{background:#ff4444;color:white}.bg-orange{background:#ff9800;color:black}
    .small{font-size:12px;color:#aaa}
    .bidask{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:10px 0}
    .ba{border-radius:10px;padding:10px;text-align:center}
    .ba-bid{background:#0f2a1d;border:1px solid #00ff88}.ba-ask{background:#2a0f0f;border:1px solid #ff4444}
    .levels{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:10px}
    .lvl{background:#0e1117;border-radius:10px;padding:10px;text-align:center;border:1px solid #333}
    .ai-box{background:linear-gradient(135deg,#1a0033,#0d1b4c);border:2px solid #7c3aed;border-radius:16px;padding:18px;margin-top:12px}
    .ai-grid{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:10px;margin-top:12px}
    .ai-stat{background:#0e1117;border-radius:10px;padding:12px;text-align:center;border:1px solid #333}
    .tabs button{background:#1e293b;color:white;border:1px solid #333;padding:9px 14px;border-radius:20px;margin:2px;cursor:pointer;font-weight:bold}
    .tabs button.active{background:#00c853;color:black}
    select{background:#1e293b;color:white;border:1px solid #333;padding:8px;border-radius:8px}
    .live-dot{animation:blink 1s infinite} @keyframes blink{0%{opacity:1}50%{opacity:0.3}100%{opacity:1}}
    @media(max-width:700px){.grid{grid-template-columns:1fr}.ai-grid{grid-template-columns:1fr 1fr}.price{font-size:24px}}
    </style></head><body>
    <div class='top'><h2 style='margin:5px 0'>🤖 AI BOT DASHBOARD</h2><span style='background:#1e293b;padding:8px 14px;border-radius:20px;font-size:13px'><span class='live-dot'>🟢</span> LIVE | """+now+""" | USDINR: <span id='usdinrTop'>--</span> | IP: """+ip+"""</span></div>

    <div class='ai-box'>
      <div style='font-size:12px;letter-spacing:2px;color:#c4b5fd'>🤖 AI SUGGEST BOT • BEST SCRIPT ONLY</div>
      <h2 id='aiTitle' style='margin:10px 0;font-size:22px;line-height:1.3'>🤖 AI Analyzing...</h2>
      <div id='aiReason' style='font-size:13px;color:#e0e7ff;line-height:1.6'>Analyzing...</div>
      <div style='margin-top:10px'>AI Confidence: <b id='aiConf' style='color:#00ff88;font-size:28px'>--%</b> <span id='aiTrend' style='font-size:13px;color:#aaa'>--</span></div>
      <div class='ai-grid'>
        <div class='ai-stat'><div class='small'>🎯 BEST SCRIPT</div><b id='aiScript' style='font-size:16px'>--</b><div class='small' id='aiOption'>--</div></div>
        <div class='ai-stat'><div class='small'>💰 ENTRY</div><b id='aiEntry' style='font-size:16px;color:#00ff88'>--</b></div>
        <div class='ai-stat'><div class='small'>🎯 TARGET</div><b id='aiTarget' style='font-size:16px;color:#00ff88'>--</b></div>
        <div class='ai-stat'><div class='small'>🛑 STOPLOSS</div><b id='aiSL' style='font-size:16px;color:#ff4444'>--</b></div>
      </div>
      <div style='margin-top:12px;text-align:center'><a class='btn b2' href='/ai_signal'>📩 Send AI Signal to Telegram</a><a class='btn b5' href='javascript:loadAI()'>🔄 Refresh AI</a></div>
    </div>

    <!-- 📈 CHART - NEW - SONTHA CHART - BLOCK ILLA -->
    <div class='card' style='padding:12px'>
      <div style='display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px'>
        <div><b style='font-size:16px'>📈 LIVE CHART - <span id='chartName'>NIFTY</span></b> <span class='small' id='chartPrice'>--</span></div>
        <div>
          <select id='tf' onchange='loadChart()'><option value='1m'>1m</option><option value='5m'>5m</option><option value='15m' selected>15m</option><option value='1h'>1h</option><option value='1d'>1D</option></select>
        </div>
      </div>
      <div class='tabs' style='margin-top:10px'>
        <button class='active' onclick="changeChart('NIFTY',this)">🟣 NIFTY</button>
        <button onclick="changeChart('SENSEX',this)">🔵 SENSEX</button>
        <button onclick="changeChart('CRUDEOILM',this)">⚫ CRUDEOILM</button>
        <button onclick="changeChart('GOLDM',this)">🟡 GOLDM</button>
        <button onclick="changeChart('SILVERM',this)">⚪ SILVERM</button>
      </div>
      <div id='myChart' style='height:420px;margin-top:10px'></div>
      <div style='font-size:12px;color:#aaa;margin-top:6px'>🟢 Green Candle = UP | 🔴 Red Candle = DOWN | 🟢 Green Line = EMA 9 | 🔴 Red Line = EMA 21 | Chart = Yahoo Live Data → MCX INR Convert | Click Card Keela Irukkura Script-a Click Panna Chart Maarum!</div>
      <div style='display:flex;gap:8px;flex-wrap:wrap;margin-top:8px'><span class='small'>EMA 9: <b id='chartEma9' style='color:#00ff88'>--</b></span><span class='small'>EMA 21: <b id='chartEma21' style='color:#ff4444'>--</b></span><span class='small'>Signal: <b id='chartSignal'>--</b></span></div>
    </div>

    <div class='card' style='border:2px solid #00ff88;text-align:center'><div style='font-size:12px;color:#aaa'>OVERALL MARKET</div><h2 id='mainSignal' class='green' style='margin:8px 0'>Loading...</h2><div id='mainSub' style='font-size:13px'>Checking...</div><div style='margin-top:8px'><span class='small' id='lastUpdate'>--</span></div></div>

    <div class='grid' style='margin-top:12px'>
      <div class='script-card' onclick="changeChart('NIFTY',null)" style='cursor:pointer'><div class='small'>NSE • INDEX • Click Chart Paakka 👆</div><h3 style='margin:4px 0'>🟣 NIFTY 50</h3><div class='small'>LIVE RATE</div><div class='price green' id='price-NIFTY'>--</div><div id='chg-NIFTY' class='small'>--</div><div class='bidask'><div class='ba ba-bid'><div class='small'>🟢 BID</div><b id='bid-NIFTY' style='font-size:18px'>--</b></div><div class='ba ba-ask'><div class='small'>🔴 ASK</div><b id='ask-NIFTY' style='font-size:18px'>--</b></div></div><div style='text-align:center'><span class='badge bg-green' id='sig-NIFTY'>--</span></div><div class='levels'><div class='lvl'><div class='small'>ENTRY</div><b id='entry-NIFTY' style='color:#00ff88'>--</b></div><div class='lvl'><div class='small'>🎯 TGT1</div><b id='tgt-NIFTY' style='color:#00ff88'>--</b></div><div class='lvl'><div class='small'>🛑 SL</div><b id='sl-NIFTY' style='color:#ff4444'>--</b></div></div><div class='small' style='margin-top:10px;text-align:center'>TGT2: <b id='tgt2-NIFTY' style='color:#00ff88'>--</b> | Prev: <span id='prev-NIFTY'>--</span></div></div>
      <div class='script-card' onclick="changeChart('SENSEX',null)" style='cursor:pointer'><div class='small'>BSE • INDEX • Click Chart Paakka 👆</div><h3 style='margin:4px 0'>🔵 SENSEX</h3><div class='small'>LIVE RATE</div><div class='price green' id='price-SENSEX'>--</div><div id='chg-SENSEX' class='small'>--</div><div class='bidask'><div class='ba ba-bid'><div class='small'>🟢 BID</div><b id='bid-SENSEX' style='font-size:18px'>--</b></div><div class='ba ba-ask'><div class='small'>🔴 ASK</div><b id='ask-SENSEX' style='font-size:18px'>--</b></div></div><div style='text-align:center'><span class='badge bg-green' id='sig-SENSEX'>--</span></div><div class='levels'><div class='lvl'><div class='small'>ENTRY</div><b id='entry-SENSEX' style='color:#00ff88'>--</b></div><div class='lvl'><div class='small'>🎯 TGT1</div><b id='tgt-SENSEX' style='color:#00ff88'>--</b></div><div class='lvl'><div class='small'>🛑 SL</div><b id='sl-SENSEX' style='color:#ff4444'>--</b></div></div><div class='small' style='margin-top:10px;text-align:center'>TGT2: <b id='tgt2-SENSEX' style='color:#00ff88'>--</b> | Prev: <span id='prev-SENSEX'>--</span></div></div>
      <div class='script-card' onclick="changeChart('CRUDEOILM',null)" style='cursor:pointer'><div class='small'>MCX • INR per Barrel • Click 👆</div><h3 style='margin:4px 0'>⚫ CRUDEOILM</h3><div class='small'>LIVE RATE</div><div class='price green' id='price-CRUDEOILM'>--</div><div id='chg-CRUDEOILM' class='small'>--</div><div class='bidask'><div class='ba ba-bid'><div class='small'>🟢 BID</div><b id='bid-CRUDEOILM' style='font-size:18px'>--</b></div><div class='ba ba-ask'><div class='small'>🔴 ASK</div><b id='ask-CRUDEOILM' style='font-size:18px'>--</b></div></div><div style='text-align:center'><span class='badge bg-green' id='sig-CRUDEOILM'>--</span></div><div class='levels'><div class='lvl'><div class='small'>ENTRY</div><b id='entry-CRUDEOILM' style='color:#00ff88'>--</b></div><div class='lvl'><div class='small'>🎯 TGT1</div><b id='tgt-CRUDEOILM' style='color:#00ff88'>--</b></div><div class='lvl'><div class='small'>🛑 SL</div><b id='sl-CRUDEOILM' style='color:#ff4444'>--</b></div></div><div class='small' style='margin-top:10px;text-align:center'>TGT2: <b id='tgt2-CRUDEOILM' style='color:#00ff88'>--</b> | Prev: <span id='prev-CRUDEOILM'>--</span></div></div>
      <div class='script-card' onclick="changeChart('GOLDM',null)" style='cursor:pointer'><div class='small'>MCX • INR per 10gm • Click 👆</div><h3 style='margin:4px 0'>🟡 GOLDM</h3><div class='small'>LIVE RATE</div><div class='price green' id='price-GOLDM'>--</div><div id='chg-GOLDM' class='small'>--</div><div class='bidask'><div class='ba ba-bid'><div class='small'>🟢 BID</div><b id='bid-GOLDM' style='font-size:18px'>--</b></div><div class='ba ba-ask'><div class='small'>🔴 ASK</div><b id='ask-GOLDM' style='font-size:18px'>--</b></div></div><div style='text-align:center'><span class='badge bg-green' id='sig-GOLDM'>--</span></div><div class='levels'><div class='lvl'><div class='small'>ENTRY</div><b id='entry-GOLDM' style='color:#00ff88'>--</b></div><div class='lvl'><div class='small'>🎯 TGT1</div><b id='tgt-GOLDM' style='color:#00ff88'>--</b></div><div class='lvl'><div class='small'>🛑 SL</div><b id='sl-GOLDM' style='color:#ff4444'>--</b></div></div><div class='small' style='margin-top:10px;text-align:center'>TGT2: <b id='tgt2-GOLDM' style='color:#00ff88'>--</b> | Prev: <span id='prev-GOLDM'>--</span></div></div>
      <div class='script-card' onclick="changeChart('SILVERM',null)" style='cursor:pointer;grid-column:span 2'><div class='small'>MCX • INR per Kg • Click 👆</div><h3 style='margin:4px 0'>⚪ SILVERM</h3><div class='small'>LIVE RATE</div><div class='price green' id='price-SILVERM'>--</div><div id='chg-SILVERM' class='small'>--</div><div class='bidask'><div class='ba ba-bid'><div class='small'>🟢 BID</div><b id='bid-SILVERM' style='font-size:18px'>--</b></div><div class='ba ba-ask'><div class='small'>🔴 ASK</div><b id='ask-SILVERM' style='font-size:18px'>--</b></div></div><div style='text-align:center'><span class='badge bg-green' id='sig-SILVERM'>--</span></div><div class='levels'><div class='lvl'><div class='small'>ENTRY</div><b id='entry-SILVERM' style='color:#00ff88'>--</b></div><div class='lvl'><div class='small'>🎯 TGT1</div><b id='tgt-SILVERM' style='color:#00ff88'>--</b></div><div class='lvl'><div class='small'>🛑 SL</div><b id='sl-SILVERM' style='color:#ff4444'>--</b></div></div><div class='small' style='margin-top:10px;text-align:center'>TGT2: <b id='tgt2-SILVERM' style='color:#00ff88'>--</b> | Prev: <span id='prev-SILVERM'>--</span></div></div>
    </div>

    <div class='card'><b>💰 BOT STATUS</b><div style='display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #222'><span>Chart</span><b class='green'>✅ LIVE - Yahoo → MCX INR</b></div><div style='display:flex;justify-content:space-between;padding:8px 0'><span>Auto Refresh</span><b>Price 5 Sec | Chart 30 Sec</b></div></div>
    <div style='margin-top:12px'><a class='btn b1' href='/test_telegram'>📩 Test Telegram</a><a class='btn b2' href='/ai_signal'>🤖 AI Signal</a><a class='btn b3' href='/debug'>🔍 Debug</a><a class='btn b4' href='/login'>🔐 Login</a></div>

    <script src='https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js'></script>
    <script>
    let currentChart='NIFTY';
    const chart = LightweightCharts.createChart(document.getElementById('myChart'), {layout:{background:{color:'#131722'},textColor:'white',fontFamily:'Arial'},grid:{vertLines:{color:'#222'},horzLines:{color:'#222'}},crosshair:{mode:1},rightPriceScale:{borderColor:'#333'},timeScale:{borderColor:'#333',timeVisible:true}});
    const candle = chart.addCandlestickSeries({upColor:'#00ff88',downColor:'#ff4444',wickUpColor:'#00ff88',wickDownColor:'#ff4444'});
    const ema9Line = chart.addLineSeries({color:'#00ff88',lineWidth:2,title:'EMA 9'});
    const ema21Line = chart.addLineSeries({color:'#ff4444',lineWidth:2,title:'EMA 21'});
    function calcEMA(data,p){ let k=2/(p+1); let e=data[0].close; let out=[]; data.forEach((d,i)=>{ if(i==0) e=d.close; else e=d.close*k+e*(1-k); out.push({time:d.time,value:e}); }); return out; }
    function loadChart(){
      let tf=document.getElementById('tf').value;
      document.getElementById('chartName').innerText=currentChart;
      fetch('/api/chart/'+currentChart+'?tf='+tf).then(r=>r.json()).then(res=>{
        let data=res.candles; if(!data||data.length==0) return;
        candle.setData(data);
        let e9=calcEMA(data,9); let e21=calcEMA(data,21);
        ema9Line.setData(e9); ema21Line.setData(e21);
        let last=data[data.length-1];
        document.getElementById('chartPrice').innerText='Rs '+last.close.toLocaleString('en-IN');
        document.getElementById('chartEma9').innerText='Rs '+e9[e9.length-1].value.toLocaleString('en-IN',{maximumFractionDigits:0});
        document.getElementById('chartEma21').innerText='Rs '+e21[e21.length-1].value.toLocaleString('en-IN',{maximumFractionDigits:0});
        let sig=document.getElementById('chartSignal');
        if(e9[e9.length-1].value > e21[e21.length-1].value){ sig.innerText='▲ BUY'; sig.style.color='#00ff88'; } else { sig.innerText='▼ SELL'; sig.style.color='#ff4444'; }
      });
    }
    function changeChart(sym,btn){
      currentChart=sym;
      document.querySelectorAll('.tabs button').forEach(b=>b.classList.remove('active'));
      if(btn) btn.classList.add('active');
      else { document.querySelectorAll('.tabs button').forEach(b=>{ if(b.innerText.includes(sym)) b.classList.add('active'); }); }
      loadChart();
      document.getElementById('myChart').scrollIntoView({behavior:'smooth'});
    }
    function fmt(n){ return 'Rs '+n.toLocaleString('en-IN',{maximumFractionDigits:0}); }
    function loadPrices(){
      fetch('/api/prices').then(r=>r.json()).then(data=>{
        let buy=0,sell=0,usd='';
        for(let name in data){ let d=data[name]; if(d.price==0) continue;
          let pe=document.getElementById('price-'+name); pe.innerText=fmt(d.live); pe.style.color=d.color=='green'?'#00ff88':d.color=='red'?'#ff4444':'#ff9800';
          document.getElementById('chg-'+name).innerText=(d.change>=0?'▲ + ':'▼ ')+fmt(Math.abs(d.change))+' ('+d.pct+'%)';
          document.getElementById('bid-'+name).innerText=fmt(d.bid); document.getElementById('ask-'+name).innerText=fmt(d.ask);
          document.getElementById('entry-'+name).innerText=fmt(d.entry); document.getElementById('tgt-'+name).innerText=fmt(d.tgt); document.getElementById('sl-'+name).innerText=fmt(d.sl); document.getElementById('tgt2-'+name).innerText=fmt(d.tgt2);
          document.getElementById('prev-'+name).innerText=fmt(d.prev);
          let se=document.getElementById('sig-'+name);
          if(d.signal=='BUY'){ se.innerText='▲ BUY - '+d.option; se.className='badge bg-green'; buy++; }
          else if(d.signal=='SELL'){ se.innerText='▼ SELL - '+d.option; se.className='badge bg-red'; sell++; }
          else { se.innerText='◐ WAIT'; se.className='badge bg-orange'; }
          usd=d.usdinr;
        }
        document.getElementById('usdinrTop').innerText='Rs '+usd;
        let m=document.getElementById('mainSignal');
        if(buy>=3){ m.innerText='▲ BUY - CALL SIDE STRONG ('+buy+'/5)'; m.className='green'; }
        else if(sell>=3){ m.innerText='▼ SELL - PUT SIDE STRONG ('+sell+'/5)'; m.className='red'; }
        else { m.innerText='◐ MIXED - '+buy+' BUY / '+sell+' SELL'; m.className='orange'; }
        document.getElementById('lastUpdate').innerText='Last Update: '+new Date().toLocaleTimeString('en-IN');
      });
    }
    function loadAI(){
      fetch('/api/ai').then(r=>r.json()).then(ai=>{
        let emoji=ai.action=='BUY'?'▲':ai.action=='SELL'?'▼':'◐'; let color=ai.action=='BUY'?'#00ff88':ai.action=='SELL'?'#ff4444':'#ff9800';
        document.getElementById('aiTitle').innerHTML=emoji+' AI SUGGESTS: <span style="color:'+color+'">'+ai.action+' - '+ai.script+'</span>';
        document.getElementById('aiReason').innerText='🧠 '+ai.reason;
        document.getElementById('aiConf').innerText=ai.confidence+'%'; document.getElementById('aiConf').style.color=color;
        document.getElementById('aiTrend').innerText=ai.trend+' | '+ai.pct+'%';
        document.getElementById('aiScript').innerText=ai.script; document.getElementById('aiOption').innerText=ai.option;
        document.getElementById('aiEntry').innerText=fmt(ai.entry); document.getElementById('aiTarget').innerText=fmt(ai.target); document.getElementById('aiSL').innerText=fmt(ai.stoploss);
      });
    }
    loadPrices(); loadAI(); loadChart();
    setInterval(loadPrices, 5000);
    setInterval(()=>{ loadAI(); loadChart(); }, 30000);
    </script></body></html>
    """
    return html

@app.route('/test_telegram')
def test_telegram():
    ok=send_telegram(f"✅ AI Bot Test Success! Time: {datetime.now()}")
    return "✅ Telegram Sent!" if ok else "❌ Telegram Failed!"
@app.route('/order_test')
def order_test():
    send_telegram(f"🚀 ORDER PLACED: NIFTY CE 100 Qty @ 120 Time: {datetime.now()}")
    return "Order Alert Sent!"
@app.route('/login')
def login(): return redirect(f"https://ant.aliceblueonline.com/?appcode={ALICE_API_KEY}")
@app.route('/debug')
def debug(): return jsonify({"ip":get_ip(),"telegram":bool(TELEGRAM_BOT_TOKEN),"prices":get_live_prices()})
if __name__=='__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT",5000)))
