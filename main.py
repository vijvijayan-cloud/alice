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

@app.route('/')
def home():
    ip = get_ip()
    now = datetime.now().strftime('%H:%M:%S')
    html = """
    <html><head><title>AI Bot Dashboard</title><meta name='viewport' content='width=device-width, initial-scale=1'>
    <style>
    body{background:#0e1117;color:white;font-family:Arial;margin:0;padding:10px}
    .card{background:#131722;border-radius:12px;padding:14px;border:1px solid #222;margin-top:12px}
    .btn{display:inline-block;padding:12px 18px;border-radius:8px;color:white;text-decoration:none;font-weight:bold;margin:4px}
    .b1{background:#0088cc}.b2{background:#00c853}.b3{background:#ff9800}.b4{background:#7c3aed}
    .row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #222;font-size:14px}
    .green{color:#00ff88}.red{color:#ff4444}.orange{color:#ff9800}
    .signal{border:2px solid #00ff88;text-align:center}
    .top{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap}
    .tabs button{background:#1e293b;color:white;border:1px solid #333;padding:8px 14px;border-radius:20px;margin:2px;cursor:pointer}
    .tabs button.active{background:#00c853;color:black;font-weight:bold}
    select{background:#1e293b;color:white;border:1px solid #333;padding:8px;border-radius:8px}
    </style></head><body>

    <div class='top'>
    <h2 style='margin:5px 0'>🤖 AI BOT DASHBOARD</h2>
    <span style='background:#1e293b;padding:8px 14px;border-radius:20px;font-size:13px'>🟢 LIVE | TIME: """ + now + """ | IP: """ + ip + """</span>
    </div>

    <div class='card signal'>
    <div style='font-size:13px;color:#aaa;letter-spacing:2px'>OPTIONS BUYING INDICATOR</div>
    <h2 class='green' style='margin:8px 0' id='signalText'>▲ BUY SIGNAL - CALL SIDE STRONG</h2>
    <div style='font-size:14px'>EMA 9 <span class='green'>▲ Above 21</span> | EMA 21 <span class='green'>▲ Above 50</span> | Trend: <b>UPTREND</b></div>
    <div style='margin-top:10px'>
    <span style='background:#00ff88;color:black;padding:6px 12px;border-radius:6px;font-weight:bold'>EMA 9</span>
    <span style='background:#ff4444;color:white;padding:6px 12px;border-radius:6px;font-weight:bold'>EMA 21</span>
    <span style='background:#ff9800;color:black;padding:6px 12px;border-radius:6px;font-weight:bold'>EMA 50</span>
    <span id='livePrice' style='background:white;color:black;padding:6px 12px;border-radius:6px;font-weight:bold;margin-left:6px'>Loading...</span>
    </div>
    </div>

    <div class='card' style='padding:10px'>
    <div style='display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px'>
    <div class='tabs'>
    <button class='active' onclick="changeSymbol('BTCUSDT',this)">BTC / USDT</button>
    <button onclick="changeSymbol('ETHUSDT',this)">ETH / USDT</button>
    <button onclick="changeSymbol('BNBUSDT',this)">BNB / USDT</button>
    <button onclick="changeSymbol('SOLUSDT',this)">SOL / USDT</button>
    <button onclick="changeSymbol('XRPUSDT',this)">XRP / USDT</button>
    </div>
    <div>
    <select id='tf' onchange='loadChart()'>
    <option value='1m'>1m</option>
    <option value='5m'>5m</option>
    <option value='15m' selected>15m</option>
    <option value='1h'>1h</option>
    <option value='4h'>4h</option>
    </select>
    <span style='font-size:12px;color:#aaa'>Live Binance Chart - No Block</span>
    </div>
    </div>
    <div id='myChart' style='height:500px;margin-top:10px'></div>
    <div style='font-size:12px;color:#aaa;margin-top:6px'>🟢 Green Candle = BUY | 🔴 Red Candle = SELL | Chart = Binance Live Data</div>
    </div>

    <div class='card'><b>📊 WATCHLIST</b>
    <div class='row'><span>NIFTY</span><b class='green' id='w-nifty'>24,512 ▲ 0.85%</b></div>
    <div class='row'><span>BANKNIFTY</span><b class='red'>51,240 ▼ 0.32%</b></div>
    <div class='row'><span>GOLD</span><b class='green'>72,450 ▲ 0.45%</b></div>
    <div class='row'><span>CRUDE OIL</span><b class='green'>8,230 ▲ 1.2%</b></div>
    <div class='row'><span>BTCUSDT</span><b class='green' id='w-btc'>Loading...</b></div>
    <div class='row'><span>ETHUSDT</span><b id='w-eth'>Loading...</b></div>
    </div>

    <div class='card'><b>💰 BOT STATUS</b>
    <div class='row'><span>Strategy</span><b>EMA 9 / 21 / 50</b></div>
    <div class='row'><span>Last Signal</span><b class='green'>BUY @ 24,480</b></div>
    <div class='row'><span>Win Rate</span><b>68%</b></div>
    <div class='row'><span>Mode</span><b>LIVE</b></div>
    </div>

    <div class='card'><b>📈 TODAY TRADES</b>
    <div class='row'><span>NIFTY CE</span><b class='green'>+ Rs 1,250</b></div>
    <div class='row'><span>BANKNIFTY PE</span><b class='red'>- Rs 450</b></div>
    <div class='row'><span>CRUDE</span><b class='green'>+ Rs 890</b></div>
    <div class='row'><span><b>Total P&L</b></span><b class='green'><b>+ Rs 1,690</b></b></div>
    </div>

    <div style='margin-top:12px'>
    <a class='btn b1' href='/test_telegram'>📩 Test Telegram</a>
    <a class='btn b2' href='/order_test'>🚀 Test Order</a>
    <a class='btn b3' href='/debug'>🔍 Debug</a>
    <a class='btn b4' href='/login'>🔐 AliceBlue Login</a>
    </div>

    <script src='https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js'></script>
    <script>
    let currentSymbol = 'BTCUSDT';
    const chart = LightweightCharts.createChart(document.getElementById('myChart'), {layout:{background:{color:'#131722'},textColor:'white',fontFamily:'Arial'},grid:{vertLines:{color:'#222'},horzLines:{color:'#222'}},crosshair:{mode:1},rightPriceScale:{borderColor:'#333'},timeScale:{borderColor:'#333',timeVisible:true}});
    const candle = chart.addCandlestickSeries({upColor:'#00ff88',downColor:'#ff4444',wickUpColor:'#00ff88',wickDownColor:'#ff4444'});
    const ema9 = chart.addLineSeries({color:'#00ff88',lineWidth:2,title:'EMA 9'});
    const ema21 = chart.addLineSeries({color:'#ff4444',lineWidth:2,title:'EMA 21'});
    const ema50 = chart.addLineSeries({color:'#ff9800',lineWidth:2,title:'EMA 50'});

    function calcEMA(data, period){
      let k = 2/(period+1); let ema = data[0].close; let out=[];
      data.forEach((d,i)=>{ if(i==0) ema=d.close; else ema = d.close*k + ema*(1-k); out.push({time:d.time,value:ema}); });
      return out;
    }
    function loadChart(){
      let tf = document.getElementById('tf').value;
      fetch('https://api.binance.com/api/v3/klines?symbol='+currentSymbol+'&interval='+tf+'&limit=100').then(r=>r.json()).then(d=>{
        let data = d.map(x=>({time:x[0]/1000,open:parseFloat(x[1]),high:parseFloat(x[2]),low:parseFloat(x[3]),close:parseFloat(x[4])}));
        candle.setData(data);
        ema9.setData(calcEMA(data,9));
        ema21.setData(calcEMA(data,21));
        ema50.setData(calcEMA(data,50));
        let last = data[data.length-1]; let prev = data[data.length-2];
        let e9 = calcEMA(data,9).slice(-1)[0].value; let e21 = calcEMA(data,21).slice(-1)[0].value; let e50 = calcEMA(data,50).slice(-1)[0].value;
        let el = document.getElementById('signalText');
        let lp = document.getElementById('livePrice');
        lp.innerText = currentSymbol + ' : ' + last.close.toFixed(2);
        if(e9 > e21 && e21 > e50){ el.innerText='▲ BUY SIGNAL - CALL SIDE STRONG'; el.className='green'; }
        else if(e9 < e21 && e21 < e50){ el.innerText='▼ SELL SIGNAL - PUT SIDE STRONG'; el.className='red'; }
        else { el.innerText='◐ WAIT - SIDEWAYS MARKET'; el.className='orange'; }
      }).catch(e=>{ console.log(e); });
    }
    function changeSymbol(sym, btn){
      currentSymbol = sym;
      document.querySelectorAll('.tabs button').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      loadChart();
    }
    loadChart();
    setInterval(loadChart, 30000);
    fetch('https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT').then(r=>r.json()).then(d=>{ document.getElementById('w-btc').innerText = parseFloat(d.lastPrice).toFixed(2) + ' (' + parseFloat(d.priceChangePercent).toFixed(2) + '%)'; document.getElementById('w-btc').className = parseFloat(d.priceChangePercent) >=0 ? 'green' : 'red'; });
    fetch('https://api.binance.com/api/v3/ticker/24hr?symbol=ETHUSDT').then(r=>r.json()).then(d=>{ document.getElementById('w-eth').innerText = parseFloat(d.lastPrice).toFixed(2) + ' (' + parseFloat(d.priceChangePercent).toFixed(2) + '%)'; document.getElementById('w-eth').className = parseFloat(d.priceChangePercent) >=0 ? 'green' : 'red'; });
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
    return jsonify({"ip": get_ip(), "telegram": bool(TELEGRAM_BOT_TOKEN), "time": str(datetime.now())})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
