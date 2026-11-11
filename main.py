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
    "NIFTY": {"spread": 2, "sl_pct": 0.20, "tgt_pct": 0.40, "emoji": "🟣", "label": "NSE"},
    "SENSEX": {"spread": 5, "sl_pct": 0.20, "tgt_pct": 0.40, "emoji": "🔵", "label": "BSE"},
    "CRUDEOILM": {"spread": 4, "sl_pct": 0.40, "tgt_pct": 0.80, "emoji": "⚫", "label": "MCX"},
    "GOLDM": {"spread": 25, "sl_pct": 0.30, "tgt_pct": 0.60, "emoji": "🟡", "label": "MCX"},
    "SILVERM": {"spread": 80, "sl_pct": 0.30, "tgt_pct": 0.60, "emoji": "⚪", "label": "MCX"},
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
            closes = [c for c in res["indicators"]["quote"][0]["close"] if c is not None]
            highs = [h for h in res["indicators"]["quote"][0]["high"] if h is not None]
            lows = [l for l in res["indicators"]["quote"][0]["low"] if l is not None]
            def ema(data,p):
                k=2/(p+1); e=data[0]
                for v in data[1:]: e=v*k+e*(1-k)
                return e
            ema9 = convert_price(name, ema(closes,9) if len(closes)>9 else raw, usdinr)
            ema21 = convert_price(name, ema(closes,21) if len(closes)>21 else raw, usdinr)
            last20_high = convert_price(name, max(highs[-20:]), usdinr) if len(highs)>=20 else price
            last20_low = convert_price(name, min(lows[-20:]), usdinr) if len(lows)>=20 else price
            prev_ema9 = convert_price(name, ema(closes[:-1],9) if len(closes)>10 else raw, usdinr)
            prev_ema21 = convert_price(name, ema(closes[:-1],21) if len(closes)>22 else raw, usdinr)
            breakout=None; btype=""
            if price > last20_high: breakout="BREAKOUT UP 🔥"; btype="UP"
            elif price < last20_low: breakout="BREAKDOWN 🔻"; btype="DOWN"
            elif prev_ema9 <= prev_ema21 and ema9 > ema21: breakout="EMA CROSS UP 🚀"; btype="UP"
            elif prev_ema9 >= prev_ema21 and ema9 < ema21: breakout="EMA CROSS DOWN 📉"; btype="DOWN"

            # ONLY OPTIONS BUYING
            if ema9 > ema21 and price > ema9:
                action="BUY CE"; signal="BUY CE"; color="green"; trend="UPTREND ▲"; strength=85
            elif ema9 < ema21 and price < ema9:
                action="BUY PE"; signal="BUY PE"; color="green"; trend="DOWNTREND ▼ PE CHANCE"; strength=82
            elif btype=="UP":
                action="BUY CE"; signal="BUY CE"; color="green"; trend="BREAKOUT UP 🔥"; strength=88
            elif btype=="DOWN":
                action="BUY PE"; signal="BUY PE"; color="green"; trend="BREAKDOWN PE 🔻"; strength=88
            else:
                action="WAIT"; signal="WAIT"; color="orange"; trend="SIDEWAYS ◐"; strength=45
            conf = min(92, max(50, strength + abs(pct)*5))
            cfg = CONFIG[name]
            bid = price-cfg["spread"]; ask = price+cfg["spread"]; live=(bid+ask)/2
            if action in ["BUY CE","BUY PE"]:
                entry=ask; sl=round(entry*(1-cfg["sl_pct"]/100),2); tgt=round(entry*(1+cfg["tgt_pct"]/100),2); tgt2=round(entry*(1+cfg["tgt_pct"]/100*2),2); option=f"{name} {action}"
            else:
                entry=live; sl=round(entry*0.998,2); tgt=round(entry*1.002,2); tgt2=round(entry*1.004,2); option=f"{name} - WAIT"
            # PROFIT RATIO = Reward / Risk = (TGT-Entry)/(Entry-SL)
            risk = abs(entry-sl) if entry!=sl else 1
            reward = abs(tgt-entry)
            profit_ratio = round(reward/risk,2) if risk else 0
            profit_pct = round(abs(tgt-entry)/entry*100,3) if entry else 0
            # SCORE for Sorting = Profit Ratio + Confidence + Breakout Bonus
            score = profit_ratio*20 + conf + (25 if breakout else 0) + abs(pct)*5
            if action=="WAIT": score = conf  # WAIT last la varanum
            out[name]={"name":name,"symbol":sym,"price":round(live,2),"live":round(live,2),"bid":round(bid,2),"ask":round(ask,2),"prev":round(prev,2),"change":round(chg,2),"pct":round(pct,2),"signal":signal,"action":action,"color":color,"trend":trend,"ema9":round(ema9,2),"ema21":round(ema21,2),"confidence":round(conf),"usdinr":round(usdinr,2),"entry":round(entry,2),"sl":sl,"tgt":tgt,"tgt2":tgt2,"option":option,"spread":round(ask-bid,2),"breakout":breakout,"breakout_type":btype,"resistance":round(last20_high,2),"support":round(last20_low,2),"profit_ratio":profit_ratio,"profit_pct":profit_pct,"score":round(score,1),"emoji":cfg["emoji"],"label":cfg["label"]}
        except:
            out[name]={"name":name,"symbol":sym,"price":0,"live":0,"bid":0,"ask":0,"prev":0,"change":0,"pct":0,"signal":"WAIT","action":"WAIT","color":"orange","trend":"Loading...","ema9":0,"ema21":0,"confidence":0,"usdinr":88.5,"entry":0,"sl":0,"tgt":0,"tgt2":0,"option":"WAIT","spread":0,"breakout":None,"breakout_type":"","resistance":0,"support":0,"profit_ratio":0,"profit_pct":0,"score":0,"emoji":CONFIG[name]["emoji"],"label":CONFIG[name]["label"]}
    # SORT - High Profit Ratio First
    sorted_out = dict(sorted(out.items(), key=lambda x: x[1]["score"], reverse=True))
    return sorted_out

def get_ai_suggestion():
    prices=get_live_prices()
    candidates={k:v for k,v in prices.items() if v["action"] in ["BUY CE","BUY PE"] and v["price"]!=0}
    if not candidates:
        best_name = list(prices.keys())[0]; d=prices[best_name]
        return {"script":best_name,"action":"WAIT","confidence":d["confidence"],"reason":f"Clear Breakout Illa. {best_name} Sideways. WAIT. Only Options Buying.","entry":d["entry"],"target":d["tgt"],"stoploss":d["sl"],"option":f"{best_name} - WAIT","trend":d["trend"],"pct":d["pct"],"all":prices,"breakout":None,"profit_ratio":0}
    best_name = list(candidates.keys())[0]  # Already Sorted - First = Highest Profit Ratio
    d=candidates[best_name]
    reason=f"🏆 #1 RANK - Highest Profit Ratio {d['profit_ratio']}:1 ! {best_name} la {d['trend']}. EMA9 {d['ema9']} vs EMA21 {d['ema21']}. "
    if d["breakout"]: reason+=f"🔥 BREAKOUT: {d['breakout']}! Res {d['resistance']} Break! "
    reason+=f"Momentum {d['pct']}%. OPTIONS BUYING - {d['action']} Mattum!"
    return {"script":best_name,"action":d["action"],"confidence":d["confidence"],"reason":reason,"entry":d["entry"],"target":d["tgt"],"stoploss":d["sl"],"option":d["option"],"trend":d["trend"],"pct":d["pct"],"all":prices,"breakout":d["breakout"],"tgt2":d["tgt2"],"bid":d["bid"],"ask":d["ask"],"resistance":d["resistance"],"support":d["support"],"profit_ratio":d["profit_ratio"],"profit_pct":d["profit_pct"]}

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
    msg=f"🚨 BREAKOUT + AI\n\n🏆 #1 RANK Profit Ratio {ai.get('profit_ratio','--')}:1\n🎯 {ai['script']} ({ai['option']})\n📊 {ai['action']} - OPTIONS BUYING ONLY\n💰 Entry: Rs {ai['entry']}\n🎯 TGT: Rs {ai['target']} | SL: Rs {ai['stoploss']}\n🔥 Conf: {ai['confidence']}%\n\n{ai['reason']}\nTime: {datetime.now()}"
    ok=send_telegram(msg)
    return "✅ Alert Sent!" if ok else "❌ Telegram Failed!"
@app.route('/ai_signal')
def ai_signal(): return breakout_alert()

@app.route('/')
def home():
    ip=get_ip(); now=datetime.now().strftime('%H:%M:%S')
    html="""
    <html><head><title>AI Bot - Options Buying Only</title><meta name='viewport' content='width=device-width, initial-scale=1'>
    <style>
    *{box-sizing:border-box} body{background:#0e1117;color:white;font-family:Arial;margin:0;padding:8px;overflow-x:hidden}
    .card{background:#131722;border-radius:10px;padding:10px;border:1px solid #222;margin-top:8px}
    .btn{display:inline-block;padding:9px 12px;border-radius:7px;color:white;text-decoration:none;font-weight:bold;margin:3px;font-size:12px}
    .b1{background:#0088cc}.b2{background:#00c853}.b3{background:#ff9800}.b4{background:#7c3aed}.b5{background:#ff1744}.b6{background:#ff6d00}
    .green{color:#00ff88}.orange{color:#ff9800}
    .top{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px}
    /* 5 SCRIPTS SAME ROW - MEDIUM SIZE */
    .grid5{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:8px}
    .script-card{background:#1a2030;border-radius:10px;padding:10px;border:1px solid #2a3348;position:relative}
    .script-card.rank1{border:2px solid #00ff88;box-shadow:0 0 12px rgba(0,255,136,0.3)}
    .rank-badge{position:absolute;top:-8px;left:8px;background:#00ff88;color:black;font-size:10px;font-weight:bold;padding:2px 7px;border-radius:10px}
    .price{font-size:19px;font-weight:bold;margin:3px 0}
    .badge{padding:4px 8px;border-radius:12px;font-size:11px;font-weight:bold;display:inline-block}
    .bg-green{background:#00ff88;color:black}.bg-orange{background:#ff9800;color:black}
    .small{font-size:11px;color:#aaa}
    .bidask{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin:6px 0}
    .ba{border-radius:7px;padding:6px;text-align:center;font-size:12px}
    .ba-bid{background:#0f2a1d;border:1px solid #00ff88}.ba-ask{background:#2a0f0f;border:1px solid #ff4444}
    .levels{display:grid;grid-template-columns:1fr 1fr 1fr;gap:5px;margin-top:6px}
    .lvl{background:#0e1117;border-radius:7px;padding:6px;text-align:center;border:1px solid #333;font-size:12px}
    .ai-box{background:linear-gradient(135deg,#1a0033,#0d1b4c);border:2px solid #7c3aed;border-radius:12px;padding:12px;margin-top:8px}
    .ai-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:8px}
    .ai-stat{background:#0e1117;border-radius:8px;padding:8px;text-align:center;border:1px solid #333;font-size:13px}
    .breakout-box{background:linear-gradient(135deg,#ff6d00,#ff1744);border-radius:12px;padding:12px;margin-top:8px;display:none}
    .live-dot{animation:blink 1s infinite} @keyframes blink{0%{opacity:1}50%{opacity:0.3}100%{opacity:1}}
    /* Tablet - 3+2, Mobile - 1 Column */
    @media(max-width:1100px){.grid5{grid-template-columns:repeat(3,1fr)}}
    @media(max-width:700px){.grid5{grid-template-columns:1fr}.ai-grid{grid-template-columns:1fr 1fr}}
    </style></head><body>
    <div class='top'><h2 style='margin:4px 0;font-size:20px'>🤖 AI BOT DASHBOARD</h2><span style='background:#1e293b;padding:6px 10px;border-radius:20px;font-size:12px'><span class='live-dot'>🟢</span> LIVE | """+now+""" | USDINR: <span id='usdinrTop'>--</span> | IP: """+ip+"""</span></div>
    <div style='background:#0f2a1d;border:1px solid #00ff88;border-radius:8px;padding:7px;margin-top:8px;text-align:center;font-size:12px'>✅ <b>OPTIONS BUYING ONLY</b> • SELL ILLA • CE BUY / PE BUY / WAIT • <b>Sorted by High Profit Ratio First 🏆</b></div>

    <div id='breakoutBox' class='breakout-box'><div style='font-size:11px;letter-spacing:1px'>🚨 BREAKOUT NOTIFICATION</div><h2 id='breakoutTitle' style='margin:6px 0;font-size:18px'>🔥 BREAKOUT!</h2><div id='breakoutDesc' style='font-size:12px;line-height:1.5'>--</div><div style='margin-top:8px;text-align:center'><a class='btn' style='background:white;color:black' href='/breakout_alert'>📩 Send Breakout Alert</a></div></div>

    <div class='ai-box'>
      <div style='font-size:11px;letter-spacing:1px;color:#c4b5fd'>🤖 AI SUGGEST BOT • OPTIONS BUYING ONLY • #1 HIGHEST PROFIT RATIO</div>
      <h2 id='aiTitle' style='margin:6px 0;font-size:19px;line-height:1.3'>🤖 AI Analyzing...</h2>
      <div id='aiReason' style='font-size:12px;color:#e0e7ff;line-height:1.5'>Analyzing...</div>
      <div style='margin-top:6px;font-size:13px'>AI Confidence: <b id='aiConf' style='color:#00ff88;font-size:22px'>--%</b> <span id='aiTrend' style='font-size:11px;color:#aaa'>--</span> <span id='aiProfitBadge' style='background:#00ff88;color:black;padding:3px 8px;border-radius:12px;font-size:11px;font-weight:bold'>--</span></div>
      <div class='ai-grid'>
        <div class='ai-stat'><div class='small'>🏆 #1 BEST SCRIPT</div><b id='aiScript' style='font-size:14px'>--</b><div class='small' id='aiOption'>--</div></div>
        <div class='ai-stat'><div class='small'>💰 ENTRY</div><b id='aiEntry' style='font-size:14px;color:#00ff88'>--</b></div>
        <div class='ai-stat'><div class='small'>🎯 TARGET</div><b id='aiTarget' style='font-size:14px;color:#00ff88'>--</b></div>
        <div class='ai-stat'><div class='small'>🛑 STOPLOSS</div><b id='aiSL' style='font-size:14px;color:#ff4444'>--</b></div>
      </div>
      <div style='margin-top:8px;text-align:center'><a class='btn b2' href='/breakout_alert'>🚨 Send AI + Breakout to Telegram</a><a class='btn b5' href='javascript:loadAI()'>🔄 Refresh</a></div>
    </div>

    <div class='card' style='border:2px solid #00ff88;text-align:center;padding:8px'><div style='font-size:11px;color:#aaa'>OVERALL MARKET - OPTIONS BUYING ONLY</div><h2 id='mainSignal' class='green' style='margin:4px 0;font-size:18px'>Loading...</h2><div id='mainSub' style='font-size:12px'>Checking...</div><div style='margin-top:4px'><span class='small' id='lastUpdate'>--</span> | <span class='small'>Sorted: High Profit Ratio → Low</span></div></div>

    <!-- 5 SCRIPTS - SAME ROW - MEDIUM SIZE - JS WILL BUILD SORTED -->
    <div style='display:flex;justify-content:space-between;align-items:center;margin-top:10px'><b style='font-size:14px'>📊 5 SCRIPTS - SAME ROW - HIGH PROFIT FIRST 🏆</b><span class='small'>#1 = Best Profit | Auto Sort Every 5 Sec</span></div>
    <div id='scriptsGrid' class='grid5'></div>

    <div class='card' style='padding:8px'><b style='font-size:13px'>💰 BOT STATUS</b><div style='display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #222;font-size:12px'><span>Mode</span><b class='green'>OPTIONS BUYING ONLY ✅</b></div><div style='display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #222;font-size:12px'><span>Chart</span><b>❌ Removed</b></div><div style='display:flex;justify-content:space-between;padding:5px 0;font-size:12px'><span>Sorting</span><b>🏆 Profit Ratio High → Low</b></div></div>
    <div style='margin-top:8px'><a class='btn b1' href='/test_telegram'>📩 Test Telegram</a><a class='btn b6' href='/breakout_alert'>🚨 Breakout Alert</a><a class='btn b3' href='/debug'>🔍 Debug</a><a class='btn b4' href='/login'>🔐 Login</a></div>

    <script>
    function fmt(n){ return 'Rs '+n.toLocaleString('en-IN',{maximumFractionDigits:0}); }
    function loadPrices(){
      fetch('/api/prices').then(r=>r.json()).then(data=>{
        let arr = Object.values(data); // Already Sorted Backend la - High Profit First
        let ce=0, pe=0, wait=0, usd='';
        let html='';
        arr.forEach((d,i)=>{
          let rank = i+1;
          let isTop = rank==1 && d.action!='WAIT';
          let badgeClass = d.action=='WAIT' ? 'bg-orange' : 'bg-green';
          let badgeText = d.action=='WAIT' ? '◐ WAIT - NO TRADE' : '✅ '+d.action+' - BUYING';
          if(d.action=='BUY CE') ce++; else if(d.action=='BUY PE') pe++; else wait++;
          usd=d.usdinr;
          html += `<div class='script-card ${isTop?'rank1':''}'>
            ${isTop?'<div class="rank-badge">🏆 #1 BEST</div>':`<div class="rank-badge" style="background:#333;color:#aaa">#${rank}</div>`}
            <div class='small'>${d.label} • ${d.breakout ? '🔥 BREAKOUT' : 'OPTIONS BUYING'}</div>
            <h3 style='margin:3px 0;font-size:15px'>${d.emoji} ${d.name}</h3>
            <div class='small'>LIVE RATE</div>
            <div class='price green'>${fmt(d.live)}</div>
            <div class='small'>${d.change>=0?'▲ + ':'▼ '}${fmt(Math.abs(d.change))} (${d.pct}%)</div>
            <div style='background:#0e1117;border:1px solid #00ff88;border-radius:7px;padding:5px;margin-top:6px;text-align:center'><div class='small'>🏆 PROFIT RATIO</div><b style='color:#00ff88;font-size:15px'>${d.profit_ratio}:1</b> <span class='small'>| Profit ${d.profit_pct}% | Conf ${d.confidence}%</span></div>
            ${d.breakout?`<div class='small' style='color:#ff9800;font-weight:bold;margin-top:4px'>🔥 ${d.breakout}</div>`:''}
            <div class='bidask'><div class='ba ba-bid'><div class='small'>🟢 BID</div><b>${fmt(d.bid)}</b></div><div class='ba ba-ask'><div class='small'>🔴 ASK</div><b>${fmt(d.ask)}</b></div></div>
            <div style='text-align:center'><span class='badge ${badgeClass}'>${badgeText}</span></div>
            <div class='levels'><div class='lvl'><div class='small'>ENTRY</div><b style='color:#00ff88'>${fmt(d.entry)}</b></div><div class='lvl'><div class='small'>🎯 TGT</div><b style='color:#00ff88'>${fmt(d.tgt)}</b></div><div class='lvl'><div class='small'>🛑 SL</div><b style='color:#ff4444'>${fmt(d.sl)}</b></div></div>
            <div class='small' style='margin-top:6px;text-align:center'>TGT2: <b style='color:#00ff88'>${fmt(d.tgt2)}</b> | Res: ${fmt(d.resistance)} | Sup: ${fmt(d.support)}</div>
          </div>`;
        });
        document.getElementById('scriptsGrid').innerHTML=html;
        document.getElementById('usdinrTop').innerText='Rs '+usd;
        let m=document.getElementById('mainSignal');
        if(ce>0||pe>0){ m.innerText='✅ BUYING: '+ce+' CE BUY + '+pe+' PE BUY | '+wait+' WAIT'; m.className='green'; }
        else { m.innerText='◐ WAIT - NO BUYING CHANCE'; m.className='orange'; }
        document.getElementById('mainSub').innerText='Sorted: #1 = Highest Profit Ratio | CE = Mela Pogum | PE = Keela Pogum | Rendumey BUYING Thaan!';
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
        document.getElementById('aiProfitBadge').innerText='🏆 Profit Ratio '+ai.profit_ratio+':1';
        document.getElementById('aiScript').innerText=ai.script; document.getElementById('aiOption').innerText=ai.option;
        document.getElementById('aiEntry').innerText=fmt(ai.entry); document.getElementById('aiTarget').innerText=fmt(ai.target); document.getElementById('aiSL').innerText=fmt(ai.stoploss);
        let box=document.getElementById('breakoutBox');
        if(ai.breakout){ box.style.display='block'; document.getElementById('breakoutTitle').innerText='🔥 BREAKOUT: '+ai.script+' - '+ai.breakout; document.getElementById('breakoutDesc').innerText=ai.script+' Resistance Rs '+ai.resistance+' Break! Ippo '+ai.action+' - Entry '+fmt(ai.entry)+' | TGT '+fmt(ai.target)+' | SL '+fmt(ai.stoploss)+' | Profit Ratio '+ai.profit_ratio+':1'; }
        else { box.style.display='none'; }
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
