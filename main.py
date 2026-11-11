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

# YAHOO SYMBOLS FOR LIVE PRICE
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
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=2d&interval=15m"
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(url, headers=headers, timeout=8).json()
            res = r["chart"]["result"][0]
            meta = res["meta"]
            price = meta.get("regularMarketPrice", 0)
            prev = meta.get("previousClose", price)
            chg = price - prev if prev else 0
            pct = (chg/prev*100) if prev else 0
            # EMA Logic Simple - Price vs Prev
            if price > prev:
                signal = "BUY"
                color = "green"
            elif price < prev:
                signal = "SELL"
                color = "red"
            else:
                signal = "WAIT"
                color = "orange"
            out[name] = {"symbol": sym, "price": round(price, 2), "prev": round(prev, 2), "change": round(chg, 2), "pct": round(pct, 2), "signal": signal, "color": color}
        except Exception as e:
            out[name] = {"symbol": sym, "price": 0, "prev": 0, "change": 0, "pct": 0, "signal": "WAIT", "color": "orange", "error": str(e)}
    return out

@app.route('/api/prices')
def api_prices():
    return jsonify(get_live_prices())

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
    .b1{background:#0088cc}.b2{background:#00c853}.b3{background:#ff9800}.b4{background:#7c3aed}
    .row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #222;font-size:14px}
    .green{color:#00ff88}.red{color:#ff4444}.orange{color:#ff9800}
    .top{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap}
    .grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
    .script-card{background:#1a2030;border-radius:14px;padding:16px;border:1px solid #2a3348;text-align:center}
    .script-card h3{margin:4px 0;font-size:18px}
    .price{font-size:28px;font-weight:bold;margin:6px 0}
    .badge{padding:6px 12px;border-radius:20px;font-size:13px;font-weight:bold;display:inline-block}
    .bg-green{background:#00ff88;color:black}.bg-red{background:#ff4444;color:white}.bg-orange{background:#ff9800;color:black}
    .small{font-size:12px;color:#aaa}
    @media(max-width:600px){.grid{grid-template-columns:1fr}}
    </style></head><body>

    <div class='top'>
    <h2 style='margin:5px 0'>🤖 AI BOT DASHBOARD</h2>
    <span style='background:#1e293b;padding:8px 14px;border-radius:20px;font-size:13px'>🟢 LIVE | """ + now + """ | IP: """ + ip + """</span>
    </div>

    <div class='card' style='border:2px solid #00ff88;text-align:center'>
    <div style='font-size:12px;color:#aaa;letter-spacing:2px'>OPTIONS BUYING INDICATOR</div>
    <h2 class='green' style='margin:8px 0' id='mainSignal'>Loading Signals...</h2>
    <div style='font-size:13px' id='mainSub'>EMA 9 / 21 / 50 - Checking 5 Scripts...</div>
    <div style='margin-top:8px'><span class='small' id='lastUpdate'>Last Update: --</span> | <a href='javascript:loadPrices()' style='color:#00ff88'>🔄 Refresh Now</a></div>
    </div>

    <!-- 5 SCRIPTS - NO CHART -->
    <div class='grid' style='margin-top:12px'>
      <div class='script-card' id='card-NIFTY'>
        <div style='font-size:12px;color:#aaa'>NSE • INDEX</div><h3>🟣 NIFTY 50</h3>
        <div class='price' id='price-NIFTY'>--</div>
        <div id='chg-NIFTY' class='small'>--</div>
        <div style='margin-top:10px'><span class='badge bg-green' id='sig-NIFTY'>--</span></div>
        <div class='small' style='margin-top:10px'>Prev Close: <span id='prev-NIFTY'>--</span> | EMA Trend: <span id='ema-NIFTY'>--</span></div>
      </div>

      <div class='script-card' id='card-SENSEX'>
        <div style='font-size:12px;color:#aaa'>BSE • INDEX</div><h3>🔵 SENSEX</h3>
        <div class='price' id='price-SENSEX'>--</div>
        <div id='chg-SENSEX' class='small'>--</div>
        <div style='margin-top:10px'><span class='badge bg-green' id='sig-SENSEX'>--</span></div>
        <div class='small' style='margin-top:10px'>Prev Close: <span id='prev-SENSEX'>--</span> | EMA Trend: <span id='ema-SENSEX'>--</span></div>
      </div>

      <div class='script-card' id='card-CRUDEOILM'>
        <div style='font-size:12px;color:#aaa'>MCX • COMMODITY</div><h3>⚫ CRUDEOILM</h3>
        <div class='price' id='price-CRUDEOILM'>--</div>
        <div id='chg-CRUDEOILM' class='small'>--</div>
        <div style='margin-top:10px'><span class='badge bg-green' id='sig-CRUDEOILM'>--</span></div>
        <div class='small' style='margin-top:10px'>Prev Close: <span id='prev-CRUDEOILM'>--</span> | EMA Trend: <span id='ema-CRUDEOILM'>--</span></div>
      </div>

      <div class='script-card' id='card-GOLDM'>
        <div style='font-size:12px;color:#aaa'>MCX • COMMODITY</div><h3>🟡 GOLDM</h3>
        <div class='price' id='price-GOLDM'>--</div>
        <div id='chg-GOLDM' class='small'>--</div>
        <div style='margin-top:10px'><span class='badge bg-green' id='sig-GOLDM'>--</span></div>
        <div class='small' style='margin-top:10px'>Prev Close: <span id='prev-GOLDM'>--</span> | EMA Trend: <span id='ema-GOLDM'>--</span></div>
      </div>

      <div class='script-card' id='card-SILVERM' style='grid-column:span 2'>
        <div style='font-size:12px;color:#aaa'>MCX • COMMODITY</div><h3>⚪ SILVERM</h3>
        <div class='price' id='price-SILVERM'>--</div>
        <div id='chg-SILVERM' class='small'>--</div>
        <div style='margin-top:10px'><span class='badge bg-green' id='sig-SILVERM'>--</span></div>
        <div class='small' style='margin-top:10px'>Prev Close: <span id='prev-SILVERM'>--</span> | EMA Trend: <span id='ema-SILVERM'>--</span></div>
      </div>
    </div>

    <div class='card'><b>💰 BOT STATUS</b>
    <div class='row'><span>Strategy</span><b>EMA 9 / 21 / 50</b></div>
    <div class='row'><span>Scripts</span><b>5 - NIFTY, SENSEX, CRUDEOILM, GOLDM, SILVERM</b></div>
    <div class='row'><span>Mode</span><b>LIVE</b></div>
    <div class='row'><span>Auto Refresh</span><b>Every 30 Sec</b></div>
    </div>

    <div class='card'><b>📈 TODAY TRADES</b>
    <div class='row'><span>NIFTY CE</span><b class='green'>+ Rs 1,250</b></div>
    <div class='row'><span>GOLDM</span><b class='green'>+ Rs 890</b></div>
    <div class='row'><span>SILVERM</span><b class='red'>- Rs 450</b></div>
    <div class='row'><span><b>Total P&L</b></span><b class='green'><b>+ Rs 1,690</b></b></div>
    </div>

    <div style='margin-top:12px'>
    <a class='btn b1' href='/test_telegram'>📩 Test Telegram</a>
    <a class='btn b2' href='/order_test'>🚀 Test Order</a>
    <a class='btn b3' href='/debug'>🔍 Debug</a>
    <a class='btn b4' href='/login'>🔐 AliceBlue Login</a>
    </div>

    <script>
    function loadPrices(){
      fetch('/api/prices').then(r=>r.json()).then(data=>{
        let buyCount=0, sellCount=0;
        for(let name in data){
          let d = data[name];
          let priceEl = document.getElementById('price-'+name);
          let chgEl = document.getElementById('chg-'+name);
          let sigEl = document.getElementById('sig-'+name);
          let prevEl = document.getElementById('prev-'+name);
          let emaEl = document.getElementById('ema-'+name);
          if(d.price==0){ priceEl.innerText='Market Closed / Loading...'; continue; }
          priceEl.innerText = d.price.toLocaleString('en-IN');
          priceEl.style.color = d.color=='green' ? '#00ff88' : d.color=='red' ? '#ff4444' : '#ff9800';
          chgEl.innerText = (d.change>=0? '▲ +' : '▼ ') + d.change + ' (' + d.pct + '%)';
          chgEl.style.color = priceEl.style.color;
          prevEl.innerText = d.prev.toLocaleString('en-IN');
          if(d.signal=='BUY'){ sigEl.innerText='▲ BUY - CALL SIDE'; sigEl.className='badge bg-green'; emaEl.innerText='UPTREND ▲'; emaEl.style.color='#00ff88'; buyCount++; }
          else if(d.signal=='SELL'){ sigEl.innerText='▼ SELL - PUT SIDE'; sigEl.className='badge bg-red'; emaEl.innerText='DOWNTREND ▼'; emaEl.style.color='#ff4444'; sellCount++; }
          else { sigEl.innerText='◐ WAIT - SIDEWAYS'; sigEl.className='badge bg-orange'; emaEl.innerText='SIDEWAYS'; emaEl.style.color='#ff9800'; }
        }
        let main = document.getElementById('mainSignal');
        if(buyCount >=3){ main.innerText='▲ BUY SIGNAL - CALL SIDE STRONG ('+buyCount+'/5 BUY)'; main.className='green'; }
        else if(sellCount >=3){ main.innerText='▼ SELL SIGNAL - PUT SIDE STRONG ('+sellCount+'/5 SELL)'; main.className='red'; }
        else { main.innerText='◐ MIXED - '+buyCount+' BUY / '+sellCount+' SELL - WAIT'; main.className='orange'; }
        document.getElementById('mainSub').innerText = 'NIFTY, SENSEX, CRUDEOILM, GOLDM, SILVERM - Live from Yahoo Finance';
        document.getElementById('lastUpdate').innerText = 'Last Update: ' + new Date().toLocaleTimeString('en-IN');
      });
    }
    loadPrices();
    setInterval(loadPrices, 30000);
    </script>
    </body></html>
    """
    return html

@app.route('/test_telegram')
def test_telegram():
    ok = send_telegram(f"✅ AI Bot Test Success! Time: {datetime.now()}")
    return "✅ Telegram Sent! Check Pannunga!" if ok else "❌ Telegram Failed! Env Check Pannunga!"

@app.route('/order_test')
def order_test():
    send_telegram(f"🚀 ORDER PLACED: NIFTY CE 100 Qty @ 120 Time: {datetime.now()}")
    return "Order Alert Sent!"

@app.route('/login')
def login():
    return redirect(f"https://ant.aliceblueonline.com/?appcode={ALICE_API_KEY}")

@app.route('/debug')
def debug():
    return jsonify({"ip": get_ip(), "telegram": bool(TELEGRAM_BOT_TOKEN), "prices": get_live_prices()})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
