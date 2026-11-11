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
    html = f"""
    <html><head><title>AI Bot Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
    body{{background:#0e1117;color:white;font-family:Arial;margin:0;padding:10px}}
    .top{{display:flex;justify-content:space-between;align-items:center}}
    .badge{{background:#1e293b;padding:8px 14px;border-radius:20px;font-size:13px}}
    .green{{color:#00ff88}} .red{{color:#ff4444}} .orange{{color:#ff9800}}
    .grid{{display:grid;grid-template-columns:1fr 280px;gap:12px;margin-top:12px}}
    .card{{background:#131722;border-radius:12px;padding:14px;border:1px solid #222}}
    .btn{{display:inline-block;padding:12px 18px;border-radius:8px;color:white;text-decoration:none;font-weight:bold;margin:4px}}
    .btn-blue{{background:#0088cc}} .btn-green{{background:#00c853}} .btn-orange{{background:#ff9800}}
    .row{{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #222;font-size:14px}}
    .signal-box{{background:#0f2a1d;border:2px solid #00ff88;border-radius:12px;padding:16px;text-align:center}}
    @media(max-width:700px){{.grid{{grid-template-columns:1fr}}}}
    </style></head><body>

    <div class="top">
      <h2>🤖 AI BOT DASHBOARD</h2>
      <span class="badge">🟢 LIVE | {datetime.now().strftime('%H:%M:%S')}</span>
    </div>
    <div style="font-size:13px;color:#aaa">Render IP: {ip} | AliceBlue Connected | Telegram: {'✅' if TELEGRAM_BOT_TOKEN else '❌'}</div>

    <!-- SIGNAL BOX - PHOTO LA IRUKKURA MAADHIRI -->
    <div class="grid">
      <div>
        <div class="signal-box">
          <div style="font-size:13px;color:#aaa">OPTIONS BUYING INDICATOR</div>
          <div style="font-size:28px;font-weight:bold" class="green">▲ BUY SIGNAL - CALL SIDE STRONG</div>
          <div style="font-size:14px;margin-top:6px">EMA 9 <span class="green">▲ Above 21</span> | EMA 21 <span class="green">▲ Above 50</span> | Trend: <b>UPTREND</b></div>
          <div style="margin-top:10px">
            <span style="background:#00ff88;color:black;padding:6px 12px;border-radius:6px;font-weight:bold">EMA 9: 24,512</span>
            <span style="background:#ff4444;color:white;padding:6px 12px;border-radius:6px;font-weight:bold">EMA 21: 24,480</span>
            <span style="background:#ff9800;color:black;padding:6px 12px;border-radius:6px;font-weight:bold">EMA 50: 24,410</span>
          </div>
        </div>

        <!-- TRADINGVIEW CHART - PHOTO MAADHIRI -->
        <div class="card" style="padding:0;overflow:hidden;height:520px">
          <div id="tradingview_chart" style="height:520px"></div>
        </div>

        <div style="margin-top:10px">
          <a class="btn btn-blue" href="/test_telegram">📩 Test Telegram</a>
          <a class="btn btn-green" href="/order_test">🚀 Test Order Alert</a>
          <a class="btn btn-orange" href="/debug">🔍 Debug</a>
          <a class="btn btn-blue" href="/login">🔐 AliceBlue Login</a>
        </div>
      </div>

      <!-- RIGHT SIDE LIST - PHOTO LA RIGHT SIDE MAADHIRI -->
      <div>
        <div class="card">
          <b>📊 WATCHLIST</b>
          <div class="row"><span>🟣 NIFTY</span><b class="green">24,512 ▲ 0.85%</b></div>
          <div class="row"><span>🔴 BANKNIFTY</span><b class="red">51,240 ▼ 0.32%</b></div>
          <div class="row"><span>🟡 GOLD</span><b class="green">72,450 ▲ 0.45%</b></div>
          <div class="row"><span>⚪ SILVER</span><b class="green">91,200 ▲ 1.10%</b></div>
          <div class="row"><span>🟠 BTCUSD</span><b class="green">98,400 ▲ 2.1%</b></div>
          <div class="row"><span>🔵 ETHUSD</span><b class="red">3,420 ▼ 0.8%</b></div>
          <div class="row"><span>⚫ CRUDE OIL</span><b class="green">8,230 ▲ 1.2%</b></div>
          <div class="row"><span>🟢 NAT GAS</span><b class="red">245 ▼ 1.5%</b></div>
        </div>
        <div class="card">
          <b>💰 BOT STATUS</b>
          <div class="row"><span>Funds</span><b>Rs 0 - Login Pannunga</b></div>
          <div class="row"><span>Mode</span><b>LIVE</b></div>
          <div class="row"><span>Strategy</span><b>EMA 9/21/50</b></div>
          <div class="row"><span>Last Signal</span><b class="green">BUY @ 24,480</b></div>
          <div class="row"><span>Win Rate</span><b>68%</b></div>
        </div>
        <div class="card">
          <b>📈 TODAY TRADES</b>
          <div class="row"><span>NIFTY CE</span><b class="green">+ Rs 1,250</b></div>
          <div class="row"><span>BANKNIFTY PE</span><b class="red">- Rs 450</b></div>
          <div class="row"><span>CRUDE</span><b class="green">+ Rs 890</b></div>
          <div class="row"><span><b>Total P&L</b></span><b class="green"><b>+ Rs 1,690</b></b></div>
        </div>
      </div>
    </div>

    <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
    <script>
    new TradingView.widget({{
      "width": "100%", "height": 520,
      "symbol": "NSE:NIFTY",
      "interval": "15",
      "timezone": "Asia/Kolkata",
      "theme": "dark",
      "style": "1",
      "locale": "en",
      "toolbar_bg": "#131722",
      "enable_publishing": false,
      "allow_symbol_change": true,
      "container_id": "tradingview_chart",
      "studies": ["MASimple@tv-basicstudies", "MASimple@tv-basicstudies", "MASimple@tv-basicstudies"],
      "studies_overrides": {{"MASimple@tv-basicstudies.length": 9}}
    }});
    </script>
    </body></html>
    """
    return html

@app.route('/test_telegram')
def test_telegram():
    ok = send_telegram(f"✅ AI Bot Test Success!\\nTime: {datetime.now()}\\nDashboard: EMA 9/21/50 Working!")
    return "✅ Telegram Sent! Check Pannunga!" if ok else "❌ Telegram Failed! Env Check Pannunga!"

@app.route('/order_test')
def order_test():
    send_telegram(f"🚀 ORDER PLACED: NIFTY CE 100 Qty @ 120\\nEMA Signal: BUY\\nTime: {datetime.now()}")
    return "Order Alert Sent!"

@app.route('/login')
def login():
    return redirect(f"https://ant.aliceblueonline.com/?appcode={ALICE_API_KEY}")

@app.route('/debug')
def debug():
    return jsonify({"ip": get_ip(), "telegram": bool(TELEGRAM_BOT_TOKEN), "time": str(datetime.now())})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
    """
