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
    html = "<html><head><title>AI Bot Dashboard</title><meta name='viewport' content='width=device-width, initial-scale=1'>"
    html += "<style>body{background:#0e1117;color:white;font-family:Arial;margin:0;padding:10px}.card{background:#131722;border-radius:12px;padding:14px;border:1px solid #222;margin-top:12px}.btn{display:inline-block;padding:12px 18px;border-radius:8px;color:white;text-decoration:none;font-weight:bold;margin:4px}.b1{background:#0088cc}.b2{background:#00c853}.b3{background:#ff9800}.row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #222}.green{color:#00ff88}.red{color:#ff4444}</style></head><body>"
    html += f"<h2>🤖 AI BOT DASHBOARD</h2><div>Render IP: {ip} | Time: {datetime.now().strftime('%H:%M:%S')}</div>"
    html += "<div class='card' style='border:2px solid #00ff88;text-align:center'><div>OPTIONS BUYING INDICATOR</div><h2 class='green'>▲ BUY SIGNAL - CALL SIDE STRONG</h2><div>EMA 9 Above 21 | EMA 21 Above 50 | Trend: UPTREND</div></div>"
    html += "<div class='card' style='padding:0;overflow:hidden'><div id='tv' style='height:500px'></div></div>"
    html += "<div class='card'><b>📊 WATCHLIST</b><div class='row'><span>NIFTY</span><b class='green'>24,512 ▲ 0.85%</b></div><div class='row'><span>BANKNIFTY</span><b class='red'>51,240 ▼ 0.32%</b></div><div class='row'><span>GOLD</span><b class='green'>72,450 ▲ 0.45%</b></div><div class='row'><span>CRUDE OIL</span><b class='green'>8,230 ▲ 1.2%</b></div></div>"
    html += "<div class='card'><b>💰 BOT STATUS</b><div class='row'><span>Strategy</span><b>EMA 9/21/50</b></div><div class='row'><span>Last Signal</span><b class='green'>BUY @ 24,480</b></div></div>"
    html += "<div style='margin-top:12px'><a class='btn b1' href='/test_telegram'>📩 Test Telegram</a><a class='btn b2' href='/order_test'>🚀 Test Order</a><a class='btn b3' href='/debug'>🔍 Debug</a></div>"
    html += "<script src='https://s3.tradingview.com/tv.js'></script><script>new TradingView.widget({width:'100%',height:500,symbol:'NSE:NIFTY',interval:'15',timezone:'Asia/Kolkata',theme:'dark',style:'1',locale:'en',container_id:'tv',allow_symbol_change:true});</script>"
    html += "</body></html>"
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
    return jsonify({"ip": get_ip(), "telegram": bool(TELEGRAM_BOT_TOKEN), "time": str(datetime.now())})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
