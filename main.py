import os, requests, threading, time, math
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify

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

CONFIG = {
    "NIFTY": {"emoji": "🟣", "step": 50, "lot": 75, "iv": 13.5, "dte": 4, "max_day": 2, "min_pct": 0.30},
    "SENSEX": {"emoji": "🔵", "step": 100, "lot": 10, "iv": 13.0, "dte": 4, "max_day": 2, "min_pct": 0.30},
    "CRUDEOILM": {"emoji": "⚫", "step": 50, "lot": 10, "iv": 28.0, "dte": 12, "max_day": 1, "min_pct": 0.80},
    "GOLDM": {"emoji": "🟡", "step": 100, "lot": 10, "iv": 14.0, "dte": 12, "max_day": 1, "min_pct": 0.60},
    "SILVERM": {"emoji": "⚪", "step": 500, "lot": 5, "iv": 22.0, "dte": 12, "max_day": 1, "min_pct": 1.00},
}
ORDER = ["NIFTY","SENSEX","CRUDEOILM","GOLDM","SILVERM"]
SCRIPTS = {"NIFTY":"^NSEI","SENSEX":"^BSESN","CRUDEOILM":"CL=F","GOLDM":"GC=F","SILVERM":"SI=F"}
def convert_price(name, raw, usdinr):
    if name=="CRUDEOILM": return raw*usdinr
    if name=="GOLDM": return (raw/31.1035)*10*usdinr
    if name=="SILVERM": return (raw/31.1035)*1000*usdinr
    return raw

def calc_option(name, spot, action):
    cfg = CONFIG[name]; step = cfg["step"]; iv = cfg["iv"]/100
    dte = cfg["dte"]; t = dte/365.0; atm = round(spot/step)*step
    if action == "BUY CE": strike = atm - step; typ = "CE"
    else: strike = atm + step; typ = "PE"
    intrinsic = max(spot-strike,0) if typ=="CE" else max(strike-spot,0)
    tv = spot * iv * math.sqrt(t) * 0.38
    if intrinsic>0: tv *= 0.60
    prem = round(intrinsic+tv,2)
    return {"strike":strike,"typ":typ,"prem":prem,"sl":round(prem*0.60,2),"tgt":round(prem*1.80,2),"lot":cfg["lot"],"tag":"","dte":dte}

def est_prem(entry_spot, fut_spot, entry_prem, action, n=1):
    chg = fut_spot-entry_spot
    pc = 0.60*chg if action=="BUY CE" else -0.60*chg
    return max(entry_prem+pc-entry_prem*0.008*n, 1)

def get_signal(name, closes, price, pct, e9, e21, pe9, pe21, res, sup):
    cfg = CONFIG[name]
    b=None; bt=""
    if price>res: b="BREAKOUT"; bt="UP"
    elif price<sup: b="BREAKDOWN"; bt="DOWN"
    elif pe9<=pe21 and e9>e21: b="EMA UP"; bt="UP"
    elif pe9>=pe21 and e9<e21: b="EMA DOWN"; bt="DOWN"
    mp = cfg["min_pct"]
    if e9>e21 and price>e9 and pct>mp*0.5 and bt=="UP":
        return {"action":"BUY CE","trend":"STRONG UP 🚀","level":5}
    if e9<e21 and price<e9 and pct<-mp*0.5 and bt=="DOWN":
        return {"action":"BUY PE","trend":"STRONG DOWN 📉","level":1}
    if bt=="UP" and res>0 and (price-res)/res*100>0.60: return {"action":"WAIT","trend":"LATE ❌","level":3}
    if bt=="DOWN" and sup>0 and (sup-price)/sup*100>0.60: return {"action":"WAIT","trend":"LATE ❌","level":3}
    if e9>e21 and price>e9 and bt=="UP" and pct>mp*0.5: return {"action":"BUY CE","trend":"UP ↗","level":4}
    if e9<e21 and price<e9 and bt=="DOWN" and pct<-mp*0.5: return {"action":"BUY PE","trend":"DOWN ↘","level":2}
    return {"action":"WAIT","trend":"WAIT ◐","level":3}

def calc_atr(highs, lows, closes, period=14):
    if len(closes) < period+1: return 0
    trs=[]
    for i in range(1, len(closes)):
        h=highs[i]; l=lows[i]; pc=closes[i-1]
        trs.append(max(h-l, abs(h-pc), abs(l-pc)))
    return sum(trs[-period:])/period if len(trs)>=period else sum(trs)/len(trs)

def get_volume_action(price, pct, vol, avg_vol):
    if vol==0 or avg_vol==0: return "Normal"
    ratio = vol/avg_vol
    if pct>0 and ratio<0.80: return "Profit Taking / Unwinding ⚠️"
    if pct>0 and ratio>=1.20: return "Accumulation ✅"
    if pct<0 and ratio>=1.20: return "Distribution / Selling 🔴"
    if pct<0 and ratio<0.80: return "Weak Selling / No Interest"
    if pct>0: return "Buying Interest ↗"
    if pct<0: return "Selling Pressure ↘"
    return "Normal"

def calc_probability(price, pct, e9, e21, res, sup):
    call = 10; put = 10; no_trade = 10
    if e9>e21: call += 40
    elif e9<e21: put += 40
    else: no_trade += 40
    if price>e21: call += 20
    elif price<e21: put += 20
    else: no_trade += 20
    if pct>0.30: call += 20
    elif pct<-0.30: put += 20
    elif abs(pct)<0.10: no_trade += 20
    else:
        if pct>0: call += 10; no_trade += 10
        else: put += 10; no_trade += 10
    if price>res: call += 20
    elif price<sup: put += 20
    else: no_trade += 20
    total = call+put+no_trade
    p_call = round(call/total*100); p_put = round(put/total*100); p_no = 100-p_call-p_put
    if p_call>=p_put and p_call>=p_no: best="CALL"
    elif p_put>=p_call and p_put>=p_no: best="PUT"
    else: best="NO TRADE"
    return {"call":p_call,"put":p_put,"no_trade":p_no,"best":best}

calls = []
cid = [1]
daily = {}
def add_call(data):
    c = {"id":cid[0],"time":ist_short(),"script":data["script"],"action":data["action"],"strike":data["strike"],"typ":data["typ"],"entry":data["prem"],"tgt":data["tgt"],"sl":data["sl"],"lot":data["lot"],"entry_spot":data["entry_spot"],"tag":"","status":"🟢 RUNNING","cur":data["prem"],"pts":0,"pnl":0,"exit":"-"}
    cid[0]+=1; calls.insert(0,c)
    if len(calls)>30: calls.pop()
    today=ist_now().strftime('%d-%m-%Y'); k=f"{today}_{data['script']}"; daily[k]=daily.get(k,0)+1
    return c

def update_calls(prices):
    for c in calls:
        if "RUNNING" not in c["status"]: continue
        live = prices.get(c["script"])
        if not live or live["live"]==0: continue
        est = est_prem(c["entry_spot"], live["live"], c["entry"], c["action"])
        c["cur"]=round(est,2); c["pts"]=round(est-c["entry"],2); c["pnl"]=round(c["pts"]*c["lot"],2)
        if est>=c["tgt"]:
            c["status"]="✅ TGT DONE"; c["exit"]=c["tgt"]; c["pts"]=round(c["tgt"]-c["entry"],2); c["pnl"]=round(c["pts"]*c["lot"],2); c["cur"]=c["tgt"]
            send_telegram(f"🎯 TGT DONE\n{c['script']} {c['strike']} {c['typ']}\nEntry Rs {c['entry']} → TGT Rs {c['tgt']}\n+{c['pts']} Pts | +Rs {c['pnl']}")
        elif est<=c["sl"]:
            c["status"]="❌ SL HIT"; c["exit"]=c["sl"]; c["pts"]=round(c["sl"]-c["entry"],2); c["pnl"]=round(c["pts"]*c["lot"],2); c["cur"]=c["sl"]
            send_telegram(f"❌ SL HIT\n{c['script']} {c['strike']} {c['typ']}\nEntry Rs {c['entry']} → SL Rs {c['sl']}\n{c['pts']} Pts | Rs {c['pnl']}")

last_alert={"time":None,"script":"","action":""}
def get_prices():
    usdinr=get_usdinr(); out={}
    for name in ORDER:
        sym=SCRIPTS[name]
        try:
            url=f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=15m"
            r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=8).json(); res=r["chart"]["result"][0]; meta=res["meta"]
            raw=meta.get("regularMarketPrice",0); prev_raw=meta.get("previousClose",raw)
            price=convert_price(name,raw,usdinr); prev=convert_price(name,prev_raw,usdinr); chg=price-prev; pct=chg/prev*100 if prev else 0
            q=res["indicators"]["quote"][0]
            closes=[convert_price(name,c,usdinr) for c in q["close"] if c is not None]
            highs=[convert_price(name,h,usdinr) for h in q["high"] if h is not None]
            lows=[convert_price(name,l,usdinr) for l in q["low"] if l is not None]
            vols=[v for v in q.get("volume",[]) if v is not None]
            def ema(d,p):
                k=2/(p+1); e=d[0]
                for v in d[1:]: e=v*k+e*(1-k)
                return e
            e9=ema(closes,9) if len(closes)>9 else price; e21=ema(closes,21) if len(closes)>21 else price
            res20=max(highs[-20:]) if len(highs)>=20 else price; sup20=min(lows[-20:]) if len(lows)>=20 else price
            pe9=ema(closes[:-1],9) if len(closes)>10 else price; pe21=ema(closes[:-1],21) if len(closes)>22 else price
            sig=get_signal(name,closes,price,pct,e9,e21,pe9,pe21,res20,sup20)
            action=sig["action"]; trend=sig["trend"]; conf=88 if sig["level"] in [5,1] else 80 if action!="WAIT" else 45
            opt=calc_option(name,price,action if action!="WAIT" else "BUY CE")
            if price>e21 and e9>e21: trend_struct="Bullish Bias (Above 21 EMA)"
            elif price<e21 and e9<e21: trend_struct="Bearish Bias (Below 21 EMA)"
            else: trend_struct="Sideways / No Bias"
            atr=calc_atr(highs, lows, closes, 14)
            sl_dist=round(atr*1.30,2)
            vol_now=vols[-1] if vols else 0
            avg_vol=sum(vols[-20:])/len(vols[-20:]) if len(vols)>=5 else 0
            vol_action=get_volume_action(price, pct, vol_now, avg_vol)
            if action=="BUY CE": signal_label="CALL BUY (Bullish Alignment)"
            elif action=="BUY PE": signal_label="PUT BUY (Bearish Alignment)"
            else: signal_label="WAIT - No Alignment"
            prob=calc_probability(price, pct, e9, e21, res20, sup20)
            out[name]={"name":name,"live":round(price,2),"change":round(chg,2),"pct":round(pct,2),"action":action,"trend":trend,"conf":conf,"emoji":CONFIG[name]["emoji"],"strike":opt["strike"],"typ":opt["typ"],"prem":opt["prem"],"sl":opt["sl"],"tgt":opt["tgt"],"lot":opt["lot"],"entry_spot":round(price,2),"script":name,"tag":"","dte":opt["dte"],"signal_label":signal_label,"trend_struct":trend_struct,"atr":round(atr,2),"sl_dist":sl_dist,"vol_action":vol_action,"prob_call":prob["call"],"prob_put":prob["put"],"prob_no":prob["no_trade"],"prob_best":prob["best"]}
        except:
            out[name]={"name":name,"live":0,"change":0,"pct":0,"action":"WAIT","trend":"Loading","conf":0,"emoji":CONFIG[name]["emoji"],"strike":0,"typ":"CE","prem":0,"sl":0,"tgt":0,"lot":0,"entry_spot":0,"script":name,"tag":"","dte":0,"signal_label":"WAIT","trend_struct":"-","atr":0,"sl_dist":0,"vol_action":"-","prob_call":0,"prob_put":0,"prob_no":100,"prob_best":"NO TRADE"}
    return out

def get_ai():
    prices=get_prices()
    for n in ORDER:
        d=prices[n]
        if d["action"] in ["BUY CE","BUY PE"]:
            return {"script":n,"action":d["action"],"trend":d["trend"],"conf":d["conf"],"all":prices,"strike":d["strike"],"typ":d["typ"],"prem":d["prem"],"sl":d["sl"],"tgt":d["tgt"],"lot":d["lot"],"entry_spot":d["entry_spot"],"tag":""}
    n=ORDER[0]; d=prices[n]
    return {"script":n,"action":"WAIT","trend":d["trend"],"conf":d["conf"],"all":prices,"strike":d["strike"],"typ":d["typ"],"prem":d["prem"],"sl":d["sl"],"tgt":d["tgt"],"lot":d["lot"],"entry_spot":d["entry_spot"],"tag":""}

def loop():
    time.sleep(60)
    send_telegram(f"Bot Started!")
    while True:
        try:
            now=ist_now(); h=now.hour+now.minute/60
            if 9.0<=h<=23.5 and now.weekday()!=6:
                ai=get_ai(); update_calls(ai["all"])
                if ai["action"] in ["BUY CE","BUY PE"] and ai["conf"]>=80:
                    today=now.strftime('%d-%m-%Y'); k=f"{today}_{ai['script']}"
                    if daily.get(k,0) >= CONFIG[ai["script"]]["max_day"]: time.sleep(120); continue
                    global last_alert; td=9999
                    if last_alert["time"]: td=(now-last_alert["time"]).total_seconds()/60
                    if not (last_alert["script"]==ai["script"] and last_alert["action"]==ai["action"] and td<45):
                        c=add_call(ai)
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
    wins=len([c for c in calls if "TGT" in c["status"]]); losses=len([c for c in calls if "SL HIT" in c["status"]])
    pnl=sum(c["pnl"] for c in calls if "RUNNING" not in c["status"])
    return jsonify({"calls":calls,"summary":{"total":len(calls),"wins":wins,"losses":losses,"pnl":round(pnl,2)}})
@app.route('/api/calls/clear')
def clear_calls():
    calls.clear(); return jsonify({"ok":True})
@app.route('/')
def home():
    now=ist_str()
    html="""
    <html><head><title>Trading Dashboard</title><meta name='viewport' content='width=device-width, initial-scale=1'>
    <style>body{background:#0e1117;color:white;font-family:Arial;margin:0;padding:10px} .card{background:#131722;border-radius:12px;padding:12px;border:1px solid #222;margin-top:10px} .green{color:#00ff88}.red{color:#ff4444}.orange{color:#ff9800} .yellow{color:#ffeb3b}.cyan{color:#00e5ff} .small{font-size:11px;color:#aaa} .row1{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px} .row2{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-top:10px} .sc{border-radius:12px;padding:10px;border:2px solid #2a3348} table{width:100%;border-collapse:collapse;font-size:12px;margin-top:8px} th,td{padding:7px;border-bottom:1px solid #333;text-align:left} th{color:#aaa} .dash{width:100%;border-collapse:collapse;font-size:12px;margin-top:8px} .dash td{padding:7px 8px;border:1px solid #2a3348} .dash td:first-child{color:#ccc;font-weight:bold;width:38%;background:rgba(0,0,0,0.25)} .bar{height:10px;border-radius:10px;overflow:hidden;display:flex;margin-top:6px} .bar div{height:100%} @media(max-width:700px){.row1{grid-template-columns:1fr}.row2{grid-template-columns:1fr}} </style></head><body>
    <div class='small'>"""+now+""" | EMA 9/21 Only | Card Colour = Probability | TGT/SL Popup la Mattum</div>
    <div id='row1' class='row1'></div>
    <div id='row2' class='row2'></div>
    <div class='card' style='border:2px solid #ff9800'><div style='display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap'><b>📋 CALLS HISTORY - Call Vandha Apram Mattum</b><button onclick='clearCalls()' style='background:#333;color:white;border:none;padding:6px 10px;border-radius:6px;cursor:pointer'>🗑️ Clear</button></div><div id='sum' class='small' style='margin-top:4px'></div><div id='calls'><div class='small' style='padding:10px;text-align:center'>No calls yet - Signal Vandha Thaan Call Varum!</div></div></div>
    <script>
    function fmt(n){return 'Rs '+n.toLocaleString('en-IN',{maximumFractionDigits:0})} function fmt2(n){return 'Rs '+n.toLocaleString('en-IN',{maximumFractionDigits:2})}
    function clearCalls(){ if(confirm('Clear Calls History?')){ fetch('/api/calls/clear').then(()=>loadCalls()); } }
    function loadCalls(){ fetch('/api/calls').then(r=>r.json()).then(d=>{ let s=d.summary; document.getElementById('sum').innerText=`${s.total} Calls | ${s.wins} Win (TGT) | ${s.losses} Loss (SL) | Total P&L ${fmt(s.pnl)}`; if(d.calls.length==0){ document.getElementById('calls').innerHTML='<div class="small" style="padding:10px;text-align:center">No calls yet - Signal Vandha Thaan Call Varum!</div>'; return; } let rows=''; d.calls.forEach(c=>{ let col=c.pnl>=0?'#00ff88':'#ff4444'; rows+=`<tr><td><b>#${c.id} ${c.script}</b><br>${c.action} ${c.strike} ${c.typ}<br><span class='small'>${c.time} | Lot ${c.lot}</span></td><td><b>Entry<br>${fmt2(c.entry)}</b><br><span class='small'>Live ${fmt2(c.cur)}</span></td><td><b style='color:#00ff88'>TGT ${fmt2(c.tgt)}</b><br><b style='color:#ff4444'>SL ${fmt2(c.sl)}</b></td><td><b>${c.status}</b><br><span class='small'>Exit: ${c.exit=='-'?'-':fmt2(c.exit)}</span></td><td style='color:${col};font-weight:bold'>${c.pts>=0?'+':''}${c.pts} Pts<br>${c.pnl>=0?'+':''}${fmt(c.pnl)}</td></tr>`; }); document.getElementById('calls').innerHTML=`<table><tr><th>Call</th><th>Entry / Live</th><th>🎯 TGT / 🛑 SL</th><th>Status / Exit</th><th>Points / P&L</th></tr>${rows}</table>`; }); }
    function cardHtml(x){
      let sigColor=x.action=='BUY CE'?'#00c853':x.action=='BUY PE'?'#ff1744':'#333';
      let sigText=x.action=='WAIT'?'WAIT - No Alignment':x.signal_label;
      let probColor=x.prob_best=='CALL'?'#00c853':x.prob_best=='PUT'?'#ff1744':'#ff9800';
      // === PROBABILITY BACKGROUND COLOUR ===
      let bg='#1a2030'; let border='#2a3348';
      let bestVal=x.prob_best=='CALL'?x.prob_call:x.prob_best=='PUT'?x.prob_put:x.prob_no;
      if(x.prob_best=='CALL' && x.prob_call>=60){ bg='#0f3d22'; border='#00c853'; }
      else if(x.prob_best=='CALL' && x.prob_call>=50){ bg='#14301f'; border='#2e9e5b'; }
      else if(x.prob_best=='PUT' && x.prob_put>=60){ bg='#3d1212'; border='#ff1744'; }
      else if(x.prob_best=='PUT' && x.prob_put>=50){ bg='#301414'; border='#c62828'; }
      else if(x.prob_best=='NO TRADE' && x.prob_no>=50){ bg='#3a2a0a'; border='#ff9800'; }
      else if(x.prob_best=='NO TRADE'){ bg='#2a2416'; border='#8a6d2b'; }
      return `<div class='sc' style='background:${bg};border-color:${border}'><div style='text-align:center;padding:6px'><b style='font-size:16px'>${x.emoji} ${x.name}</b><h3 style='margin:4px 0'>${fmt(x.live)}</h3><div class='small'>${x.change>=0?'▲':'▼'} ${x.pct}% | ${x.trend}</div></div><table class='dash'><tr><td>Signal</td><td style='background:${sigColor};font-weight:bold;color:white'>${x.action=='WAIT'?'◐ ':x.action=='BUY CE'?'🟢 ':'🔴 '}${sigText}</td></tr><tr><td>Trend Structure</td><td style='font-weight:bold'>${x.trend_struct}</td></tr><tr><td>ATR (14) / SL</td><td style='color:#ffeb3b;font-weight:bold'>${x.atr} pts | SL: ${x.sl_dist} pts</td></tr><tr><td>Volume Action</td><td style='color:#00e5ff;font-weight:bold'>${x.vol_action} <span class='small'>(Info Only)</span></td></tr><tr><td>Probability</td><td><b style='color:${probColor}'>${x.prob_best} - ${bestVal}%</b><br><span style='color:#00ff88'>🟢 CALL ${x.prob_call}%</span> | <span style='color:#ff4444'>🔴 PUT ${x.prob_put}%</span> | <span style='color:#ff9800'>◐ NO TRADE ${x.prob_no}%</span><div class='bar'><div style='width:${x.prob_call}%;background:#00c853'></div><div style='width:${x.prob_put}%;background:#ff1744'></div><div style='width:${x.prob_no}%;background:#ff9800'></div></div><div class='small' style='margin-top:4px'>Up: CALL | Down: PUT | Consolidation: NO TRADE</div></td></tr></table></div>`;
    }
    function loadAll(){ fetch('/api/prices').then(r=>r.json()).then(d=>{ let order=['NIFTY','SENSEX','CRUDEOILM','GOLDM','SILVERM']; let r1=''; let r2=''; order.forEach((n,i)=>{ let x=d[n]; if(!x) return; if(i<2) r1+=cardHtml(x); else r2+=cardHtml(x); }); document.getElementById('row1').innerHTML=r1; document.getElementById('row2').innerHTML=r2; }); loadCalls(); }
    loadAll(); setInterval(loadAll,8000);
    </script></body></html>
    """
    return html
@app.route('/test_telegram')
def t():
    ok=send_telegram("✅ Test OK!"); return "✅ Sent!" if ok else "❌ Failed"
@app.route('/debug')
def debug(): return jsonify({"prices":get_prices(),"ai":get_ai(),"calls":calls})
if __name__=='__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT",5000)))
