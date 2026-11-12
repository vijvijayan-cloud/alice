import os, requests, threading, time, math
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify, redirect

app = Flask(__name__)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
IST = timezone(timedelta(hours=5, minutes=30))
def ist_now(): return datetime.now(IST)
def ist_str(): return ist_now().strftime('%d-%m-%Y %I:%M %p')
def ist_short(): return ist_now().strftime('%d-%m %I:%M %p')
def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        r = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
        return r.status_code == 200
    except: return False
def get_usdinr():
    try:
        r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/USDINR=X?range=1d&interval=1m", headers={"User-Agent":"Mozilla/5.0"}, timeout=8).json()
        return r["chart"]["result"][0]["meta"]["regularMarketPrice"]
    except: return 88.50

# NIFTY + SENSEX MATTUM - MCX FULL OFF!
CONFIG = {
    "NIFTY": {"emoji": "🟣", "step": 50, "lot": 75, "iv": 13.5},
    "SENSEX": {"emoji": "🔵", "step": 100, "lot": 10, "iv": 13.0},
}
SCRIPTS = {"NIFTY":"^NSEI","SENSEX":"^BSESN"}

def calc_option(name, spot, action):
    cfg = CONFIG[name]; step = cfg["step"]; iv = cfg["iv"]/100
    t = 4/365.0; atm = round(spot/step)*step
    if action == "BUY CE": strike = atm - step; typ = "CE"
    else: strike = atm + step; typ = "PE"
    intrinsic = max(spot-strike,0) if typ=="CE" else max(strike-spot,0)
    tv = spot * iv * math.sqrt(t) * 0.38
    if intrinsic>0: tv *= 0.60
    prem = round(intrinsic+tv,2)
    return {"strike":strike,"typ":typ,"prem":prem,"sl":round(prem*0.60,2),"tgt":round(prem*1.80,2),"lot":cfg["lot"]}

def est_prem(entry_spot, fut_spot, entry_prem, action, n=1):
    chg = fut_spot-entry_spot
    pc = 0.60*chg if action=="BUY CE" else -0.60*chg
    return max(entry_prem+pc-entry_prem*0.008*n, 1)

def get_signal(closes, price, pct, e9, e21, e50, pe9, pe21, res, sup):
    b=None; bt=""
    if price>res: b="BREAKOUT"; bt="UP"
    elif price<sup: b="BREAKDOWN"; bt="DOWN"
    elif pe9<=pe21 and e9>e21: b="EMA UP"; bt="UP"
    elif pe9>=pe21 and e9<e21: b="EMA DOWN"; bt="DOWN"
    if bt=="UP" and res>0 and (price-res)/res*100>0.60: return {"action":"WAIT","trend":"LATE ❌","level":3}
    if bt=="DOWN" and sup>0 and (sup-price)/sup*100>0.60: return {"action":"WAIT","trend":"LATE ❌","level":3}
    if e9>e21>e50 and price>e9 and pct>0.30 and bt=="UP": return {"action":"BUY CE","trend":"STRONG UP 🚀","level":5,"breakout":b}
    if e9<e21<e50 and price<e9 and pct<-0.30 and bt=="DOWN": return {"action":"BUY PE","trend":"STRONG DOWN 📉","level":1,"breakout":b}
    if e9>e21 and price>e9 and price>e50 and bt=="UP" and pct>0.15: return {"action":"BUY CE","trend":"UP ↗","level":4,"breakout":b}
    if e9<e21 and price<e9 and price<e50 and bt=="DOWN" and pct<-0.15: return {"action":"BUY PE","trend":"DOWN ↘","level":2,"breakout":b}
    return {"action":"WAIT","trend":"WAIT ◐","level":3,"breakout":b}

calls = []
cid = [1]
def add_call(ai):
    c = {"id":cid[0],"time":ist_short(),"script":ai["script"],"action":ai["action"],"strike":ai["strike"],"typ":ai["typ"],"entry":ai["prem"],"tgt":ai["tgt"],"sl":ai["sl"],"lot":ai["lot"],"entry_spot":ai["entry_spot"],"status":"RUNNING","cur":ai["prem"],"pts":0,"pnl":0,"exit":"-"}
    cid[0]+=1; calls.insert(0,c)
    if len(calls)>30: calls.pop()
    return c

def update_calls(prices):
    for c in calls:
        if c["status"]!="RUNNING": continue
        live = prices.get(c["script"])
        if not live or live["live"]==0: continue
        est = est_prem(c["entry_spot"], live["live"], c["entry"], c["action"])
        c["cur"]=round(est,2); c["pts"]=round(est-c["entry"],2); c["pnl"]=round(c["pts"]*c["lot"],2)
        if est>=c["tgt"]:
            c["status"]="✅ TGT DONE"; c["exit"]=c["tgt"]; c["pts"]=round(c["tgt"]-c["entry"],2); c["pnl"]=round(c["pts"]*c["lot"],2)
            send_telegram(f"🎯 TGT DONE\n{c['script']} {c['strike']} {c['typ']}\nEntry Rs {c['entry']} → TGT Rs {c['tgt']}\n+{c['pts']} Pts | +Rs {c['pnl']}")
        elif est<=c["sl"]:
            c["status"]="❌ SL HIT"; c["exit"]=c["sl"]; c["pts"]=round(c["sl"]-c["entry"],2); c["pnl"]=round(c["pts"]*c["lot"],2)
            send_telegram(f"❌ SL HIT\n{c['script']} {c['strike']} {c['typ']}\nEntry Rs {c['entry']} → SL Rs {c['sl']}\n{c['pts']} Pts | Rs {c['pnl']}")

def backtest(name):
    try:
        url=f"https://query1.finance.yahoo.com/v8/finance/chart/{SCRIPTS[name]}?range=1mo&interval=15m"
        r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=12).json()
        res=r["chart"]["result"][0]; ts=res["timestamp"]; q=res["indicators"]["quote"][0]
        candles=[]
        for i,t in enumerate(ts):
            if q["close"][i] is None: continue
            candles.append({"time":datetime.fromtimestamp(t,IST).strftime('%d-%m %I:%M %p'),"close":q["close"][i],"high":q["high"][i],"low":q["low"][i]})
        if len(candles)<60: return {"error":"No Data"}
    except Exception as e: return {"error":str(e)}
    trades=[]; last=-10; dayc={}
    for i in range(25,len(candles)-5):
        if i<last: continue
        win=candles[max(0,i-25):i]; closes=[c["close"] for c in win]; highs=[c["high"] for c in win]; lows=[c["low"] for c in win]
        def ema(d,p):
            k=2/(p+1); e=d[0]
            for v in d[1:]: e=v*k+e*(1-k)
            return e
        e9=ema(closes,9); e21=ema(closes,21); e50=ema(closes,50) if len(closes)>=50 else e21
        price=candles[i]["close"]; prev=candles[i-1]["close"]; pct=(price-prev)/prev*100 if prev else 0
        res=max(highs[-20:]); sup=min(lows[-20:]); pe9=ema(closes[:-1],9); pe21=ema(closes[:-1],21)
        sig=get_signal(closes,price,pct,e9,e21,e50,pe9,pe21,res,sup); action=sig["action"]
        if action not in ["BUY CE","BUY PE"]: continue
        dk=candles[i]["time"][:5]
        if dayc.get(dk,0)>=2: continue
        opt=calc_option(name,price,action); ep=opt["prem"]; sl=opt["sl"]; tgt=opt["tgt"]
        result="OPEN"; exitp=ep; last_est=ep
        for j in range(i+1,min(i+12,len(candles))):
            est=est_prem(price,candles[j]["close"],ep,action,j-i); last_est=est
            if est<=sl: result="LOSS"; exitp=sl; break
            if est>=tgt: result="WIN"; exitp=tgt; break
        if result=="OPEN":
            exitp=last_est
            result="WIN" if exitp>ep*1.02 else "LOSS" if exitp<ep*0.98 else "BREAKEVEN"
        pnl=round((exitp-ep)*opt["lot"],2)
        trades.append({"date":candles[i]["time"],"action":action,"strike":opt["strike"],"typ":opt["typ"],"entry":ep,"exit":round(exitp,2),"result":result,"pnl":pnl})
        dayc[dk]=dayc.get(dk,0)+1; last=i+8
    if not trades: return {"script":name,"total":0,"win":0,"loss":0,"win_rate":0,"total_pnl":0,"trades":[]}
    wins=[t for t in trades if t["result"]=="WIN"]; losses=[t for t in trades if t["result"]=="LOSS"]
    return {"script":name,"total":len(trades),"win":len(wins),"loss":len(losses),"win_rate":round(len(wins)/len(trades)*100,1),"total_pnl":round(sum(t["pnl"] for t in trades),2),"trades":trades[-10:]}

last_alert={"time":None,"script":"","action":""}
def get_prices():
    out={}
    for name,sym in SCRIPTS.items():
        try:
            url=f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=15m"
            r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=8).json(); res=r["chart"]["result"][0]; meta=res["meta"]
            price=meta.get("regularMarketPrice",0); prev=meta.get("previousClose",price); chg=price-prev; pct=chg/prev*100 if prev else 0
            closes=[c for c in res["indicators"]["quote"][0]["close"] if c is not None]; highs=[h for h in res["indicators"]["quote"][0]["high"] if h is not None]; lows=[l for l in res["indicators"]["quote"][0]["low"] if l is not None]
            def ema(d,p):
                k=2/(p+1); e=d[0]
                for v in d[1:]: e=v*k+e*(1-k)
                return e
            e9=ema(closes,9) if len(closes)>9 else price; e21=ema(closes,21) if len(closes)>21 else price; e50=ema(closes,50) if len(closes)>50 else price
            res20=max(highs[-20:]) if len(highs)>=20 else price; sup20=min(lows[-20:]) if len(lows)>=20 else price
            pe9=ema(closes[:-1],9) if len(closes)>10 else price; pe21=ema(closes[:-1],21) if len(closes)>22 else price
            sig=get_signal(closes,price,pct,e9,e21,e50,pe9,pe21,res20,sup20)
            action=sig["action"]; trend=sig["trend"]; conf=88 if sig["level"] in [5,1] else 80 if action!="WAIT" else 45
            opt=calc_option(name,price,action) if action!="WAIT" else calc_option(name,price,"BUY CE")
            out[name]={"name":name,"live":round(price,2),"change":round(chg,2),"pct":round(pct,2),"action":action,"trend":trend,"conf":conf,"emoji":CONFIG[name]["emoji"],"strike":opt["strike"],"typ":opt["typ"],"prem":opt["prem"],"sl":opt["sl"],"tgt":opt["tgt"],"lot":opt["lot"],"entry_spot":round(price,2),"script":name}
        except:
            out[name]={"name":name,"live":0,"change":0,"pct":0,"action":"WAIT","trend":"Loading","conf":0,"emoji":CONFIG[name]["emoji"],"strike":0,"typ":"CE","prem":0,"sl":0,"tgt":0,"lot":0,"entry_spot":0,"script":name}
    return out

def get_ai():
    prices=get_prices(); cands={k:v for k,v in prices.items() if v["action"] in ["BUY CE","BUY PE"]}
    if not cands:
        n=list(prices.keys())[0]; d=prices[n]
        return {"script":n,"action":"WAIT","trend":d["trend"],"conf":d["conf"],"all":prices,"strike":d["strike"],"typ":d["typ"],"prem":d["prem"],"sl":d["sl"],"tgt":d["tgt"],"lot":d["lot"],"entry_spot":d["entry_spot"]}
    n=list(cands.keys())[0]; d=cands[n]
    return {"script":n,"action":d["action"],"trend":d["trend"],"conf":d["conf"],"all":prices,"strike":d["strike"],"typ":d["typ"],"prem":d["prem"],"sl":d["sl"],"tgt":d["tgt"],"lot":d["lot"],"entry_spot":d["entry_spot"]}

def loop():
    time.sleep(60)
    send_telegram(f"🤖 Bot Started - Simple Mode\nNIFTY + SENSEX Only | Max 2/Day")
    while True:
        try:
            now=ist_now(); h=now.hour+now.minute/60
            if 9.0<=h<=23.5 and now.weekday()!=6:
                ai=get_ai(); update_calls(ai["all"])
                if ai["action"] in ["BUY CE","BUY PE"] and ai["conf"]>=80:
                    global last_alert; td=9999
                    if last_alert["time"]: td=(now-last_alert["time"]).total_seconds()/60
                    if not (last_alert["script"]==ai["script"] and last_alert["action"]==ai["action"] and td<45):
                        c=add_call(ai)
                        # SIMPLE TELEGRAM - 5 LINES MATTUM!
                        ok=send_telegram(f"🚨 {ai['action']} - {ai['script']} {ai['strike']} {ai['typ']}\nEntry: Rs {ai['prem']} | TGT: Rs {ai['tgt']} | SL: Rs {ai['sl']}\nLot: {ai['lot']} | {ai['trend']}")
                        if ok: last_alert={"time":now,"script":ai["script"],"action":ai["action"]}
            time.sleep(120)
        except: time.sleep(60)
threading.Thread(target=loop, daemon=True).start()

@app.route('/api/prices')
def api_prices(): return jsonify(get_prices())
@app.route('/api/ai')
def api_ai(): return jsonify(get_ai())
@app.route('/api/calls')
def api_calls():
    try: update_calls(get_prices())
    except: pass
    wins=len([c for c in calls if "TGT" in c["status"]]); losses=len([c for c in calls if "SL" in c["status"]])
    pnl=sum(c["pnl"] for c in calls if c["status"]!="RUNNING")
    return jsonify({"calls":calls,"summary":{"total":len(calls),"wins":wins,"losses":losses,"pnl":round(pnl,2)}})
@app.route('/api/backtest_all')
def api_bt():
    return jsonify({n: backtest(n) for n in SCRIPTS})
@app.route('/breakout_alert')
def manual():
    ai=get_ai(); c=add_call(ai)
    # SIMPLE MANUAL - 5 LINES!
    ok=send_telegram(f"🚨 {ai['action']} - {ai['script']} {ai['strike']} {ai['typ']}\nEntry: Rs {ai['prem']} | TGT: Rs {ai['tgt']} | SL: Rs {ai['sl']}\nLot: {ai['lot']} | {ai['trend']}")
    return f"✅ Sent! Call #{c['id']}" if ok else "❌ Failed"
@app.route('/')
def home():
    now=ist_str()
    html="""
    <html><head><title>AI Bot - Simple</title><meta name='viewport' content='width=device-width, initial-scale=1'>
    <style>body{background:#0e1117;color:white;font-family:Arial;margin:0;padding:10px} .card{background:#131722;border-radius:12px;padding:12px;border:1px solid #222;margin-top:10px} .btn{display:inline-block;padding:9px 14px;border-radius:8px;color:white;text-decoration:none;font-weight:bold;margin:3px;font-size:13px} .b1{background:#0088cc}.b2{background:#00c853}.b7{background:#009688} .green{color:#00ff88}.red{color:#ff4444}.orange{color:#ff9800} .small{font-size:11px;color:#aaa} .grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px} .sc{background:#1a2030;border-radius:12px;padding:12px;border:1px solid #2a3348} table{width:100%;border-collapse:collapse;font-size:12px;margin-top:8px} th,td{padding:7px;border-bottom:1px solid #333;text-align:left} th{color:#aaa} @media(max-width:600px){.grid{grid-template-columns:1fr}} </style></head><body>
    <h2 style='margin:4px 0'>🤖 AI BOT - SIMPLE</h2><div class='small' id='clock'>"""+now+"""</div>
    <div class='card' style='border:2px solid #7c3aed'><div class='small'>🤖 AI SUGGEST</div><h2 id='aiTitle' style='margin:6px 0'>Loading...</h2><div id='aiLine' style='font-size:15px'>--</div><div style='margin-top:8px'><a class='btn b2' href='/breakout_alert'>📩 Send Call</a></div></div>
    <div id='grid' class='grid'></div>
    <div class='card' style='border:2px solid #ff9800'><b>📋 CALLS HISTORY</b> <span id='sum' class='small'></span><div id='calls'><div class='small' style='padding:10px;text-align:center'>No calls yet</div></div></div>
    <div class='card' style='border:2px solid #009688'><b>📊 BACKTEST - 30 Days</b> <button onclick='loadBT()' style='background:#009688;color:white;border:none;padding:8px 14px;border-radius:7px;font-weight:bold;cursor:pointer;float:right'>▶️ Run</button><div id='bt' style='margin-top:10px'></div></div>
    <script>
    function fmt(n){return 'Rs '+n.toLocaleString('en-IN',{maximumFractionDigits:0})} function fmt2(n){return 'Rs '+n.toLocaleString('en-IN',{maximumFractionDigits:2})}
    function loadBT(){ document.getElementById('bt').innerHTML='⏳ Running...'; fetch('/api/backtest_all').then(r=>r.json()).then(d=>{ let h=''; for(let n in d){ let x=d[n]; h+=`<div style='display:flex;justify-content:space-between;padding:8px;background:#1a2030;border-radius:8px;margin-top:6px'><b>${n}</b><span>${x.win_rate}% Win | ${x.total} Trades</span><b style='color:${x.total_pnl>=0?'#00ff88':'#ff4444'}'>${x.total_pnl>=0?'+':''}${fmt(x.total_pnl)}</b></div>`; } document.getElementById('bt').innerHTML=h; }); }
    function loadCalls(){ fetch('/api/calls').then(r=>r.json()).then(d=>{ let s=d.summary; document.getElementById('sum').innerText=`${s.total} Calls | ${s.wins} Win | ${s.losses} Loss | P&L ${fmt(s.pnl)}`; if(d.calls.length==0) return; let rows=''; d.calls.forEach(c=>{ let col=c.pnl>=0?'#00ff88':'#ff4444'; rows+=`<tr><td>${c.script} ${c.strike} ${c.typ}<br><span class='small'>${c.time}</span></td><td>Rs ${c.entry}</td><td>Rs ${c.tgt} / Rs ${c.sl}</td><td>${c.status}</td><td style='color:${col}'>${c.pts>=0?'+':''}${c.pts} Pts<br>${c.pnl>=0?'+':''}${fmt(c.pnl)}</td></tr>`; }); document.getElementById('calls').innerHTML=`<table><tr><th>Call</th><th>Entry</th><th>TGT / SL</th><th>Status</th><th>Points</th></tr>${rows}</table>`; }); }
    function loadAll(){ fetch('/api/ai').then(r=>r.json()).then(ai=>{ document.getElementById('aiTitle').innerText=ai.action=='WAIT'?'◐ WAIT - No Trade':`✅ ${ai.action} - ${ai.script} ${ai.strike} ${ai.typ}`; document.getElementById('aiLine').innerText=ai.action=='WAIT'?ai.trend:`Entry Rs ${ai.prem} | TGT Rs ${ai.tgt} | SL Rs ${ai.sl} | Lot ${ai.lot} | ${ai.trend}`; }); fetch('/api/prices').then(r=>r.json()).then(d=>{ let h=''; Object.values(d).forEach(x=>{ h+=`<div class='sc'><div class='small'>${x.emoji} ${x.name}</div><h3 style='margin:4px 0'>${fmt(x.live)}</h3><div class='small'>${x.change>=0?'▲':'▼'} ${x.pct}% | ${x.trend}</div><div style='margin-top:8px;font-size:14px'>${x.strike} ${x.typ} | Premium <b style='color:#00ff88'>${fmt2(x.prem)}</b><br>TGT <b style='color:#00ff88'>${fmt2(x.tgt)}</b> | SL <b style='color:#ff4444'>${fmt2(x.sl)}</b></div><div style='margin-top:8px;text-align:center'><b class='${x.action=='WAIT'?'orange':'green'}'>${x.action=='WAIT'?'◐ WAIT':'✅ '+x.action}</b></div></div>`; }); document.getElementById('grid').innerHTML=h; }); loadCalls(); }
    loadAll(); setInterval(loadAll,8000);
    </script></body></html>
    """
    return html
@app.route('/test_telegram')
def t():
    ok=send_telegram("✅ Test OK - Simple Mode"); return "✅ Sent!" if ok else "❌ Failed"
@app.route('/debug')
def debug(): return jsonify({"prices":get_prices(),"ai":get_ai(),"calls":calls})
if __name__=='__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT",5000)))
