import os, requests, random
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

SCRIPTS = {
    "NIFTY": "^NSEI",
    "SENSEX": "^BSESN",
    "CRUDEOILM": "CL=F",
    "GOLDM": "GC=F",
    "SILVERM": "SI=F",
}

def get_live_prices():
    out = {}
    for name, sym in SCRIPTS.items():
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=15m"
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(url, headers=headers, timeout=8).json()
            res = r["chart"]["result"][0]
            meta = res["meta"]
            price = meta.get("regularMarketPrice", 0)
            prev = meta.get("previousClose", price)
            chg = price - prev if prev else 0
            pct = (chg/prev*100) if prev else 0
            # Get last candles for EMA logic
            closes = res["indicators"]["quote"][0]["close"]
            closes = [c for c in closes if c is not None]
            def ema(data, p):
                k=2/(p+1); e=data[0]
                for v in data[1:]: e=v*k+e*(1-k)
                return e
            ema9 = ema(closes,9) if len(closes)>9 else price
            ema21 = ema(closes,21) if len(closes)>21 else price
            ema50 = ema(closes,50) if len(closes)>50 else price
            if ema9 > ema21 > ema50:
                signal="BUY"; color="green"; trend="UPTREND ▲"; strength=85
            elif ema9 < ema21 < ema50:
                signal="SELL"; color="red"; trend="DOWNTREND ▼"; strength=82
            elif ema9 > ema21:
                signal="BUY"; color="green"; trend="MILD UPTREND ↗"; strength=62
            elif ema9 < ema21:
                signal="SELL"; color="red"; trend="MILD DOWNTREND ↘"; strength=60
            else:
                signal="WAIT"; color="orange"; trend="SIDEWAYS ◐"; strength=45
            # Confidence based on pct + trend
            conf = min(92, max(48, strength + abs(pct)*8))
            out[name] = {"symbol": sym, "price": round(price,2), "prev": round(prev,2), "change": round(chg,2), "pct": round(pct,2), "signal": signal, "color": color, "trend": trend, "ema9": round(ema9,2), "ema21": round(ema21,2), "ema50": round(ema50,2), "confidence": round(conf)}
        except Exception as e:
            out[name] = {"symbol": sym, "price": 0, "prev": 0, "change": 0, "pct": 0, "signal": "WAIT", "color": "orange", "trend": "Loading...", "ema9":0,"ema21":0,"ema50":0,"confidence":0}
    return out

def get_ai_suggestion():
    prices = get_live_prices()
    # AI Logic: Strongest Trend + Highest Confidence + Highest Momentum
    best = None
    best_score = -999
    for name, d in prices.items():
        if d["price"]==0: continue
        score = d["confidence"] + abs(d["pct"])*10
        if d["signal"]=="BUY": score+=10
        if d["signal"]=="SELL": score+=10
        if score > best_score:
            best_score = score
            best = (name, d)
    if not best:
        return {"script": "NIFTY", "action": "WAIT", "confidence": 0, "reason": "Market Data Loading...", "entry": 0, "target": 0, "stoploss": 0, "all": prices}
    name, d = best
    price = d["price"]
    # Target / SL Logic
    if d["signal"]=="BUY":
        target = round(price*1.004,2) if name in ["NIFTY","SENSEX"] else round(price*1.008,2)
        sl = round(price*0.998,2) if name in ["NIFTY","SENSEX"] else round(price*0.996,2)
        option = f"{name} CE BUY"
        reason = f"{name} la EMA 9 > EMA 21 > EMA 50. Strong Uptrend. Price {price} Prev Close {d['prev']} ku mela irukku. Momentum {d['pct']}% - AI Confidence {d['confidence']}%."
    elif d["signal"]=="SELL":
        target = round(price*0.996,2) if name in ["NIFTY","SENSEX"] else round(price*0.992,2)
        sl = round(price*1.002,2) if name in ["NIFTY","SENSEX"] else round(price*1.004,2)
        option = f"{name} PE BUY"
        reason = f"{name} la EMA 9 < EMA 21 < EMA 50. Strong Downtrend. Price {price} Prev Close {d['prev']} ku keela irukku. Momentum {d['pct']}% - AI Confidence {d['confidence']}%."
    else:
        target = round(price*1.002,2); sl = round(price*0.998,2)
        option = f"{name} - WAIT"
        reason = f"{name} la Sideways Market. EMA Mixed. Clear Trend Illa. Wait Panni Next Signal-kaga Kaathirukkanum."
    return {"script": name, "action": d["signal"], "confidence": d["confidence"], "reason": reason, "entry": price, "target": target, "stoploss": sl, "option": option, "trend": d["trend"], "pct": d["pct"], "all": prices}

@app.route('/api/prices')
def api_prices():
    return jsonify(get_live_prices())

@app.route('/api/ai')
def api_ai():
    return jsonify(get_ai_suggestion())

@app.route('/ai_signal')
def ai_signal():
    ai = get_ai_suggestion()
    msg = f"🤖 AI SUGGESTION BOT\\n\\n🎯 Script: {ai['script']} ({ai['option']})\\n📊 Action: {ai['action']}\\n💰 Entry: {ai['entry']}\\n🎯 Target: {ai['target']}\\n🛑 Stoploss: {ai['stoploss']}\\n🔥 Confidence: {ai['confidence']}%\\n📈 Trend: {ai['trend']}\\n\\n🧠 Reason: {ai['reason']}\\n\\nTime: {datetime.now()}"
    ok = send_telegram(msg)
    return "✅ AI Signal Sent to Telegram!" if ok else "❌ Telegram Failed!"

@app.route('/')
def home():
    ip = get_ip()
    now = datetime.now().strftime('%H:%M:%S')
    html = """
    <html><head><title>AI Bot Dashboard</title><meta name='viewport' content='width=device-width, initial-scale=1'>
    <style>
    body{background:#0e1117;color:white;font-family:Arial;margin:0;padding:10px}
    .card{background:#131722;border-radius:12px;padding:14px;border:1px solid #222;margin-top:12px}
    .btn{display:inline-block;padding:12px 16px;border-radius:8px;color:white;text-decoration:none;font-weight:bold;margin:4px;font-size:14px}
    .b1{background:#0088cc}.b2{background:#00c853}.b3{background:#ff9800}.b4{background:#7c3aed}.b5{background:#ff1744}
    .row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #222;font-size:14px}
    .green{color:#00ff88}.red{color:#ff4444}.orange{color:#ff9800}
    .top{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap}
    .grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
    .script-card{background:#1a2030;border-radius:14px;padding:16px;border:1px solid #2a3348;text-align:center}
    .price{font-size:26px;font-weight:bold;margin:6px 0}
    .badge{padding:6px 12px;border-radius:20px;font-size:13px;font-weight:bold;display:inline-block}
    .bg-green{background:#00ff88;color:black}.bg-red{background:#ff4444;color:white}.bg-orange{background:#ff9800;color:black}
    .small{font-size:12px;color:#aaa}
    .ai-box{background:linear-gradient(135deg,#1a0033,#0d1b4c);border:2px solid #7c3aed;border-radius:16px;padding:18px;margin-top:12px}
    .ai-grid{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:10px;margin-top:12px}
    .ai-stat{background:#0e1117;border-radius:10px;padding:12px;text-align:center;border:1px solid #333}
    @media(max-width:600px){.grid{grid-template-columns:1fr}.ai-grid{grid-template-columns:1fr 1fr}}
    </style></head><body>

    <div class='top'>
    <h2 style='margin:5px 0'>🤖 AI BOT DASHBOARD</h2>
    <span style='background:#1e293b;padding:8px 14px;border-radius:20px;font-size:13px'>🟢 LIVE | """ + now + """ | IP: """ + ip + """</span>
    </div>

    <!-- 🤖 AI SUGGEST BOT - NEW -->
    <div class='ai-box'>
      <div style='display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap'>
        <div><span style='font-size:12px;letter-spacing:2px;color:#c4b5fd'>🤖 AI SUGGEST BOT • POWERED BY EMA 9/21/50 + MOMENTUM</span>
        <h2 id='aiTitle' style='margin:6px 0;font-size:24px'>🤖 AI Analyzing... Please Wait...</h2>
        <div id='aiReason' style='font-size:14px;color:#e0e7ff;line-height:1.5'>5 Scripts-a Analyze Pannitu Irukken...</div>
        </div>
        <div style='text-align:center'>
          <div style='font-size:11px;color:#aaa'>AI CONFIDENCE</div>
          <div id='aiConf' style='font-size:36px;font-weight:bold;color:#00ff88'>--%</div>
          <div id='aiTrend' style='font-size:12px'>--</div>
        </div>
      </div>
      <div class='ai-grid'>
        <div class='ai-stat'><div class='small'>🎯 BEST SCRIPT</div><b id='aiScript' style='font-size:18px'>--</b><div class='small' id='aiOption'>--</div></div>
        <div class='ai-stat'><div class='small'>💰 ENTRY PRICE</div><b id='aiEntry' style='font-size:18px;color:#00ff88'>--</b></div>
        <div class='ai-stat'><div class='small'>🎯 TARGET</div><b id='aiTarget' style='font-size:18px;color:#00ff88'>--</b></div>
        <div class='ai-stat'><div class='small'>🛑 STOPLOSS</div><b id='aiSL' style='font-size:18px;color:#ff4444'>--</b></div>
      </div>
      <div style='margin-top:14px;text-align:center'>
        <a class='btn b2' href='/ai_signal'>📩 Send AI Signal to Telegram</a>
        <a class='btn b5' href='javascript:loadAI()'>🔄 Refresh AI Suggestion</a>
      </div>
      <div class='small' style='text-align:center;margin-top:6px'>⚠️ AI Suggestion Mattum Thaan - Idhu Financial Advice Illa. Unga Risk la Trade Pannunga.</div>
    </div>

    <div class='card' style='border:2px solid #00ff88;text-align:center'>
    <div style='font-size:12px;color:#aaa;letter-spacing:2px'>OPTIONS BUYING INDICATOR</div>
    <h2 class='green' style='margin:8px 0' id='mainSignal'>Loading...</h2>
    <div style='font-size:13px' id='mainSub'>EMA 9 / 21 / 50 - Checking 5 Scripts...</div>
    <div style='margin-top:8px'><span class='small' id='lastUpdate'>Last Update: --</span> | <a href='javascript:loadPrices()' style='color:#00ff88'>🔄 Refresh Now</a></div>
    </div>

    <div class='grid' style='margin-top:12px'>
      <div class='script-card'><div class='small'>NSE • INDEX</div><h3>🟣 NIFTY 50</h3><div class='price' id='price-NIFTY'>--</div><div id='chg-NIFTY' class='small'>--</div><div style='margin-top:10px'><span class='badge bg-green' id='sig-NIFTY'>--</span></div><div class='small' style='margin-top:10px'>Prev: <span id='prev-NIFTY'>--</span> | EMA 9: <span id='ema9-NIFTY'>--</span> | Conf: <span id='conf-NIFTY'>--</span></div></div>
      <div class='script-card'><div class='small'>BSE • INDEX</div><h3>🔵 SENSEX</h3><div class='price' id='price-SENSEX'>--</div><div id='chg-SENSEX' class='small'>--</div><div style='margin-top:10px'><span class='badge bg-green' id='sig-SENSEX'>--</span></div><div class='small' style='margin-top:10px'>Prev: <span id='prev-SENSEX'>--</span> | EMA 9: <span id='ema9-SENSEX'>--</span> | Conf: <span id='conf-SENSEX'>--</span></div></div>
      <div class='script-card'><div class='small'>MCX • COMMODITY</div><h3>⚫ CRUDEOILM</h3><div class='price' id='price-CRUDEOILM'>--</div><div id='chg-CRUDEOILM' class='small'>--</div><div style='margin-top:10px'><span class='badge bg-green' id='sig-CRUDEOILM'>--</span></div><div class='small' style='margin-top:10px'>Prev: <span id='prev-CRUDEOILM'>--</span> | EMA 9: <span id='ema9-CRUDEOILM'>--</span> | Conf: <span id='conf-CRUDEOILM'>--</span></div></div>
      <div class='script-card'><div class='small'>MCX • COMMODITY</div><h3>🟡 GOLDM</h3><div class='price' id='price-GOLDM'>--</div><div id='chg-GOLDM' class='small'>--</div><div style='margin-top:10px'><span class='badge bg-green' id='sig-GOLDM'>--</span></div><div class='small' style='margin-top:10px'>Prev: <span id='prev-GOLDM'>--</span> | EMA 9: <span id='ema9-GOLDM'>--</span> | Conf: <span id='conf-GOLDM'>--</span></div></div>
      <div class='script-card' style='grid-column:span 2'><div class='small'>MCX • COMMODITY</div><h3>⚪ SILVERM</h3><div class='price' id='price-SILVERM'>--</div><div id='chg-SILVERM' class='small'>--</div><div style='margin-top:10px'><span class='badge bg-green' id='sig-SILVERM'>--</span></div><div class='small' style='margin-top:10px'>Prev: <span id='prev-SILVERM'>--</span> | EMA 9: <span id='ema9-SILVERM'>--</span> | Conf: <span id='conf-SILVERM'>--</span></div></div>
    </div>

    <div class='card'><b>💰 BOT STATUS</b>
    <div class='row'><span>Strategy</span><b>EMA 9 / 21 / 50 + AI Momentum</b></div>
    <div class='row'><span>Scripts</span><b>5 - NIFTY, SENSEX, CRUDEOILM, GOLDM, SILVERM</b></div>
    <div class='row'><span>AI Suggest</span><b class='green'>✅ ACTIVE</b></div>
    <div class='row'><span>Auto Refresh</span><b>Every 30 Sec</b></div>
    </div>

    <div style='margin-top:12px'>
    <a class='btn b1' href='/test_telegram'>📩 Test Telegram</a>
    <a class='btn b2' href='/ai_signal'>🤖 AI Signal</a>
    <a class='btn b3' href='/debug'>🔍 Debug</a>
    <a class='btn b4' href='/login'>🔐 AliceBlue Login</a>
    </div>

    <script>
    function loadPrices(){
      fetch('/api/prices').then(r=>r.json()).then(data=>{
        let buy=0, sell=0;
        for(let name in data){
          let d=data[name];
          let pe=document.getElementById('price-'+name); let ce=document.getElementById('chg-'+name); let se=document.getElementById('sig-'+name);
          if(d.price==0){ pe.innerText='Loading...'; continue; }
          pe.innerText=d.price.toLocaleString('en-IN'); pe.style.color=d.color=='green'?'#00ff88':d.color=='red'?'#ff4444':'#ff9800';
          ce.innerText=(d.change>=0?'▲ +':'▼ ')+d.change+' ('+d.pct+'%)'; ce.style.color=pe.style.color;
          document.getElementById('prev-'+name).innerText=d.prev.toLocaleString('en-IN');
          document.getElementById('ema9-'+name).innerText=d.ema9.toLocaleString('en-IN');
          document.getElementById('conf-'+name).innerText=d.confidence+'%';
          if(d.signal=='BUY'){ se.innerText='▲ BUY - CALL SIDE'; se.className='badge bg-green'; buy++; }
          else if(d.signal=='SELL'){ se.innerText='▼ SELL - PUT SIDE'; se.className='badge bg-red'; sell++; }
          else { se.innerText='◐ WAIT'; se.className='badge bg-orange'; }
        }
        let m=document.getElementById('mainSignal');
        if(buy>=3){ m.innerText='▲ BUY SIGNAL - CALL SIDE STRONG ('+buy+'/5)'; m.className='green'; }
        else if(sell>=3){ m.innerText='▼ SELL SIGNAL - PUT SIDE STRONG ('+sell+'/5)'; m.className='red'; }
        else { m.innerText='◐ MIXED - '+buy+' BUY / '+sell+' SELL - WAIT'; m.className='orange'; }
        document.getElementById('lastUpdate').innerText='Last Update: '+new Date().toLocaleTimeString('en-IN');
      });
    }
    function loadAI(){
      document.getElementById('aiTitle').innerText='🤖 AI Analyzing...';
      fetch('/api/ai').then(r=>r.json()).then(ai=>{
        let emoji = ai.action=='BUY' ? '▲' : ai.action=='SELL' ? '▼' : '◐';
        let color = ai.action=='BUY' ? '#00ff88' : ai.action=='SELL' ? '#ff4444' : '#ff9800';
        document.getElementById('aiTitle').innerHTML = emoji+' AI SUGGESTS: <span style="color:'+color+'">'+ai.action+' - '+ai.script+'</span>';
        document.getElementById('aiReason').innerText = '🧠 '+ai.reason;
        document.getElementById('aiConf').innerText = ai.confidence+'%';
        document.getElementById('aiConf').style.color = color;
        document.getElementById('aiTrend').innerText = ai.trend + ' | Momentum ' + ai.pct + '%';
        document.getElementById('aiScript').innerText = ai.script;
        document.getElementById('aiOption').innerText = ai.option;
        document.getElementById('aiEntry').innerText = ai.entry.toLocaleString('en-IN');
        document.getElementById('aiTarget').innerText = ai.target.toLocaleString('en-IN');
        document.getElementById('aiSL').innerText = ai.stoploss.toLocaleString('en-IN');
      });
    }
    loadPrices(); loadAI();
    setInterval(()=>{ loadPrices(); loadAI(); }, 30000);
    </script>
    </body></html>
    """
    return html

@app.route('/test_telegram')
def test_telegram():
    ok = send_telegram(f"✅ AI Bot Test Success! Time: {datetime.now()}")
    return "✅ Telegram Sent!" if ok else "❌ Telegram Failed!"

@app.route('/order_test')
def order_test():
    send_telegram(f"🚀 ORDER PLACED: NIFTY CE 100 Qty @ 120 Time: {datetime.now()}")
    return "Order Alert Sent!"

@app.route('/login')
def login():
    return redirect(f"https://ant.aliceblueonline.com/?appcode={ALICE_API_KEY}")

@app.route('/debug')
def debug():
    return jsonify({"ip": get_ip(), "telegram": bool(TELEGRAM_BOT_TOKEN), "ai": get_ai_suggestion()})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
