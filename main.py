import os, time, threading
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify

app = Flask(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
def ist_now(): return datetime.now(IST)
def ist_str(): return ist_now().strftime('%d-%m-%Y %I:%M %p')

# ===== DHAN BOT STATUS - Screenshot la Irundha Same Fields =====
STATE = {
    "dhan": "Not Checked",
    "last_msg": "",
    "live": True,
    "open_trade": None,
    "status": "BOTH LIVE BOT RUNNING",
    "trade_1015": False,
    "trade_920": False,
    "qty": 65,
    "pnl_today": 0,
    "trade1_pnl": 0,
    "trade2_pnl": 0,
}

# ===== DHAN CONFIG - UNGA FINAL SETTINGS =====
TRADE1_TIME = "09:20"
TRADE1_SL = 2000
TRADE1_TGT = 2000
TRADE1_TRAILING = False

TRADE2_TIME = "10:15"
TRADE2_SL = 2000
TRADE2_TGT = None
TRADE2_TRAILING = True
QTY = 65

@app.route('/api/status')
def api_status():
    return jsonify(STATE)

@app.route('/api/prices')
def api_prices():
    # Dashboard ku - Same Status Thaan
    return jsonify(STATE)

@app.route('/')
def home():
    now = ist_str()
    html = """
    <html><head><title>DHAN BOT - Dashboard</title><meta name='viewport' content='width=device-width, initial-scale=1'>
    <style>
    *{box-sizing:border-box}
    body{background:#070a12;color:#fff;font-family:Arial;margin:0;padding:12px}
    .top{background:linear-gradient(90deg,#0f172a,#1e293b);border:1px solid #26314d;border-radius:16px;padding:14px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px}
    .top h2{margin:0;font-size:20px} .top small{color:#94a3b8}
    .live{background:#052e1a;color:#4ade80;padding:6px 14px;border-radius:20px;font-weight:bold;font-size:13px}
    .grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-top:12px}
    @media(max-width:700px){.grid{grid-template-columns:1fr}}
    .card{background:#101826;border:1px solid #26314d;border-radius:16px;padding:14px}
    .card h3{margin:0 0 8px 0;font-size:15px}
    .big{font-size:26px;font-weight:bold;margin:6px 0}
    .green{color:#22c55e} .red{color:#ef4444} .yellow{color:#facc15}
    .pill{display:inline-block;padding:5px 12px;border-radius:20px;font-size:12px;font-weight:bold}
    .small{font-size:11px;color:#94a3b8}
    .box{background:#0b1220;border:1px solid #26314d;border-radius:12px;padding:12px;margin-top:12px}
    table{width:100%;border-collapse:collapse;font-size:13px;margin-top:8px}
    th,td{padding:9px;border-bottom:1px solid #26314d;text-align:left} th{color:#94a3b8}
    </style></head><body>
    <div class='top'><div><h2>🚀 DHAN BOT <span style='font-size:13px;color:#94a3b8'>| BOTH LIVE</span></h2><small>""" + now + """ | Auto Refresh 8s</small></div><div class='live' id='liveDot'>● LIVE</div></div>

    <div class='grid'>
      <div class='card' style='border-color:#22c55e'><h3>📈 Trade 1 - 9:20 ORB</h3><span class='pill' style='background:#052e1a;color:#4ade80'>FIXED SL 2000 • FIXED TGT 2000</span><div class='big' id='t1Status'>WAITING</div><div class='small'>Trailing Illa - SL / TGT Fixed</div><div class='small' style='margin-top:6px'>P&L: <b id='t1Pnl' class='green'>Rs 0</b></div></div>
      <div class='card' style='border-color:#f59e0b'><h3>🔥 Trade 2 - 10:15 BREAKOUT</h3><span class='pill' style='background:#3a2a0a;color:#facc15'>TRAILING SL 2000 • NO TARGET</span><div class='big' id='t2Status'>WAITING</div><div class='small'>Profit Poga Poga SL Mela Pogum</div><div class='small' style='margin-top:6px'>P&L: <b id='t2Pnl' class='green'>Rs 0</b></div></div>
      <div class='card'><h3>💰 Today P&L</h3><div class='big' id='todayPnl'>Rs 0</div><div class='small' id='todayInfo'>Qty 65 | Dhan: <span id='dhanStat'>Not Checked</span></div><div class='small' style='margin-top:6px' id='lastMsg'></div></div>
    </div>

    <div class='box'><b>📋 LIVE STATUS</b><table><tr><th>Item</th><th>Value</th></tr><tr><td>Bot Status</td><td id='botStatus'>BOTH LIVE BOT RUNNING</td></tr><tr><td>Dhan Connection</td><td id='dhanConn'>Not Checked</td></tr><tr><td>Open Trade</td><td id='openTrade'>None</td></tr><tr><td>Trade 9:20</td><td id='tr920'>False</td></tr><tr><td>Trade 10:15</td><td id='tr1015'>False</td></tr></table></div>

    <div class='box'><b>⚙️ CONFIG</b><table><tr><th>Trade</th><th>Time</th><th>SL</th><th>Target</th><th>Trailing</th></tr><tr><td>Trade 1</td><td>9:20</td><td>2000</td><td>2000</td><td>No</td></tr><tr><td>Trade 2</td><td>10:15</td><td>2000</td><td>No Target</td><td>Yes</td></tr></table><div class='small' style='margin-top:8px'>Qty: 65 | Max Loss: 2000 per Trade</div></div>

    <script>
    function fmt(n){return 'Rs '+Number(n).toLocaleString('en-IN',{maximumFractionDigits:0})}
    function load(){
      fetch('/api/status').then(r=>r.json()).then(d=>{
        document.getElementById('botStatus').innerText=d.status;
        document.getElementById('dhanConn').innerText=d.dhan;
        document.getElementById('dhanStat').innerText=d.dhan;
        document.getElementById('openTrade').innerText=d.open_trade?JSON.stringify(d.open_trade):'None';
        document.getElementById('tr920').innerText=d.trade_920;
        document.getElementById('tr1015').innerText=d.trade_1015;
        document.getElementById('t1Status').innerText=d.trade_920?'🟢 RUNNING':'WAITING';
        document.getElementById('t2Status').innerText=d.trade_1015?'🟢 RUNNING':'WAITING';
        document.getElementById('t1Status').style.color=d.trade_920?'#22c55e':'#fff';
        document.getElementById('t2Status').style.color=d.trade_1015?'#22c55e':'#fff';
        document.getElementById('todayPnl').innerText=fmt(d.pnl_today||0);
        document.getElementById('todayPnl').style.color=(d.pnl_today||0)>=0?'#22c55e':'#ef4444';
        document.getElementById('t1Pnl').innerText=fmt(d.trade1_pnl||0);
        document.getElementById('t2Pnl').innerText=fmt(d.trade2_pnl||0);
        document.getElementById('lastMsg').innerText=d.last_msg?('Last: '+d.last_msg):'';
        document.getElementById('liveDot').innerText=d.live?'● LIVE':'○ OFFLINE';
      });
    }
    load(); setInterval(load,8000);
    </script></body></html>
    """
    return html

@app.route('/health')
def health():
    return jsonify({"ok": True, "time": ist_str()})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
