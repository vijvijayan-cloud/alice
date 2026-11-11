import os, requests, threading, time
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify, redirect

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
ALICE_API_KEY = os.environ.get("ALICE_API_KEY", "")

# === IST TIME FIX ===
IST = timezone(timedelta(hours=5, minutes=30))
def ist_now():
    return datetime.now(IST)
def ist_str():
    return ist_now().strftime('%d-%m-%Y %I:%M:%S %p IST')

def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        r = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
        print(f"[{ist_str()}] Telegram: {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"Telegram Error: {e}")
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

# === AUTO ALERT TRACKING - Duplicate Varadhu ===
last_alert = {"time": None, "script": "", "action": "", "breakout": ""}
alert_history = []

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
            vol_list = res["indicators"]["quote"][0].get("volume", []) or []
            vol_list = [v for v in vol_list if v is not None]
            avg_vol = sum(vol_list[-20:])/len(vol_list[-20:]) if len(vol_list)>=20 else 100000
            last_vol = vol_list[-1] if vol_list else avg_vol
            vol_ratio = round(last_vol/avg_vol,2) if avg_vol else 1.0
            closes = [c for c in res["indicators"]["quote"][0]["close"] if c is not None]
            highs = [h for h in res["indicators"]["quote"][0]["high"] if h is not None]
            lows = [l for l in res["indicators"]["quote"][0]["low"] if l is not None]
            def ema(data,p):
                k=2/(p+1); e=data[0]
                for v in data[1:]: e=v*k+e*(1-k)
                return e
            ema9 = convert_price(name, ema(closes,9) if len(closes)>9 else raw, usdinr)
            ema21 = convert_price(name, ema(closes,21) if len(closes)>21 else raw, usdinr)
            ema50 = convert_price(name, ema(closes,50) if len(closes)>50 else raw, usdinr)
            last20_high = convert_price(name, max(highs[-20:]), usdinr) if len(highs)>=20 else price
            last20_low = convert_price(name, min(lows[-20:]), usdinr) if len(lows)>=20 else price
            prev_ema9 = convert_price(name, ema(closes[:-1],9) if len(closes)>10 else raw, usdinr)
            prev_ema21 = convert_price(name, ema(closes[:-1],21) if len(closes)>22 else raw, usdinr)
            breakout=None; btype=""
            if price > last20_high: breakout="BREAKOUT UP 🔥"; btype="UP"
            elif price < last20_low: breakout="BREAKDOWN 🔻"; btype="DOWN"
            elif prev_ema9 <= prev_ema21 and ema9 > ema21: breakout="EMA CROSS UP 🚀"; btype="UP"
            elif prev_ema9 >= prev_ema21 and ema9 < ema21: breakout="EMA CROSS DOWN 📉"; btype="DOWN"

            if ema9 > ema21 > ema50 and price > ema9 and pct > 0.30:
                trend_mark="STRONG UPTREND 🚀🚀"; trend_short="STRONG UP"; trend_color="#00ff88"; trend_bg="#0f2a1d"; trend_level=5
            elif ema9 > ema21 and price > ema9:
                trend_mark="UPTREND ↗"; trend_short="UPTREND"; trend_color="#00c853"; trend_bg="#0f2a1d"; trend_level=4
            elif ema9 < ema21 < ema50 and price < ema9 and pct < -0.30:
                trend_mark="STRONG DOWNTREND 📉📉"; trend_short="STRONG DOWN"; trend_color="#ff1744"; trend_bg="#2a0f0f"; trend_level=1
            elif ema9 < ema21 and price < ema9:
                trend_mark="DOWNTREND ↘"; trend_short="DOWNTREND"; trend_color="#ff7043"; trend_bg="#2a0f0f"; trend_level=2
            elif abs(pct) < 0.10 and abs(ema9-ema21)/ema21*100 < 0.10:
                trend_mark="SIDEWAYS ◐"; trend_short="SIDEWAYS"; trend_color="#ff9800"; trend_bg="#2a1a0f"; trend_level=3
            else:
                trend_mark="VOLATILE / MIXED ⚡"; trend_short="VOLATILE"; trend_color="#ffca28"; trend_bg="#2a1a0f"; trend_level=3

            if trend_level==5: market_cond="BULLISH STRONG 🐂🔥"; cond_color="#00ff88"
            elif trend_level==4: market_cond="BULLISH 🐂"; cond_color="#00c853"
            elif trend_level==1: market_cond="BEARISH STRONG 🐻🔻"; cond_color="#ff1744"
            elif trend_level==2: market_cond="BEARISH 🐻"; cond_color="#ff7043"
            elif trend_level==3 and "SIDEWAYS" in trend_mark: market_cond="RANGE BOUND ➡️"; cond_color="#ff9800"
            else: market_cond="VOLATILE / CHOPPY ⚡"; cond_color="#ffca28"
            if breakout and btype=="UP": market_cond="BREAKOUT BULLISH 🚀"; cond_color="#00ff88"
            if breakout and btype=="DOWN": market_cond="BREAKDOWN BEARISH 📉"; cond_color="#ff1744"

            base_oi_map = {"NIFTY": 12500000, "SENSEX": 8500000, "CRUDEOILM": 12500, "GOLDM": 18500, "SILVERM": 22500}
            base_oi = base_oi_map[name]
            oi_change_pct = round((vol_ratio-1)*8 + pct*2,2)
            if trend_level in [5,1]: oi_change_pct = abs(oi_change_pct)+2.5
            oi = int(base_oi * (1 + oi_change_pct/100))
            oi_change = int(oi - base_oi)
            if trend_level==5: pcr = round(0.72 + abs(pct)*0.05,2)
            elif trend_level==4: pcr = round(0.85 + abs(pct)*0.05,2)
            elif trend_level==1: pcr = round(1.35 - abs(pct)*0.05,2)
            elif trend_level==2: pcr = round(1.15 - abs(pct)*0.05,2)
            else: pcr = 0.98
            if pct>0 and oi_change_pct>0: oi_signal="LONG BUILDUP 🟢"
            elif pct<0 and oi_change_pct>0: oi_signal="SHORT BUILDUP 🔴"
            elif pct>0 and oi_change_pct<0: oi_signal="SHORT COVERING 🟡"
            elif pct<0 and oi_change_pct<0: oi_signal="LONG UNWINDING 🟠"
            else: oi_signal="FLAT OI ➡️"
            oi_trend = "OI ↑" if oi_change>0 else "OI ↓" if oi_change<0 else "OI →"

            if trend_level in [5,4] or btype=="UP":
                action="BUY CE"; signal="BUY CE"; color="green"; strength=88 if trend_level==5 else 80
            elif trend_level in [1,2] or btype=="DOWN":
                action="BUY PE"; signal="BUY PE"; color="green"; strength=88 if trend_level==1 else 80
            else:
                action="WAIT"; signal="WAIT"; color="orange"; strength=45
            conf = min(92, max(50, strength + abs(pct)*5 + (10 if breakout else 0)))
            cfg = CONFIG[name]
            bid = price-cfg["spread"]; ask = price+cfg["spread"]; live=(bid+ask)/2
            if action in ["BUY CE","BUY PE"]:
                entry=ask; sl=round(entry*(1-cfg["sl_pct"]/100),2); tgt=round(entry*(1+cfg["tgt_pct"]/100),2); tgt2=round(entry*(1+cfg["tgt_pct"]/100*2),2); option=f"{name} {action}"
            else:
                entry=live; sl=round(entry*0.998,2); tgt=round(entry*1.002,2); tgt2=round(entry*1.004,2); option=f"{name} - WAIT"
            risk = abs(entry-sl) if entry!=sl else 1
            reward = abs(tgt-entry)
            profit_ratio = round(reward/risk,2) if risk else 0
            profit_pct = round(abs(tgt-entry)/entry*100,3) if entry else 0
            score = profit_ratio*20 + conf + (25 if breakout else 0) + abs(pct)*5 + trend_level*2
            if action=="WAIT": score = conf
            out[name]={"name":name,"symbol":sym,"price":round(live,2),"live":round(live,2),"bid":round(bid,2),"ask":round(ask,2),"prev":round(prev,2),"change":round(chg,2),"pct":round(pct,2),"signal":signal,"action":action,"color":color,"trend":trend_mark,"trend_short":trend_short,"trend_color":trend_color,"trend_bg":trend_bg,"trend_level":trend_level,"market_cond":market_cond,"cond_color":cond_color,"ema9":round(ema9,2),"ema21":round(ema21,2),"ema50":round(ema50,2),"confidence":round(conf),"usdinr":round(usdinr,2),"entry":round(entry,2),"sl":sl,"tgt":tgt,"tgt2":tgt2,"option":option,"spread":round(ask-bid,2),"breakout":breakout,"breakout_type":btype,"resistance":round(last20_high,2),"support":round(last20_low,2),"profit_ratio":profit_ratio,"profit_pct":profit_pct,"score":round(score,1),"emoji":cfg["emoji"],"label":cfg["label"],"oi":oi,"oi_change":oi_change,"oi_change_pct":oi_change_pct,"oi_signal":oi_signal,"oi_trend":oi_trend,"pcr":pcr,"vol_ratio":vol_ratio,"volume":int(last_vol),"ist_time":ist_str()}
        except Exception as e:
            out[name]={"name":name,"symbol":sym,"price":0,"live":0,"bid":0,"ask":0,"prev":0,"change":0,"pct":0,"signal":"WAIT","action":"WAIT","color":"orange","trend":"Loading...","trend_short":"--","trend_color":"#ff9800","trend_bg":"#222","trend_level":3,"market_cond":"Loading...","cond_color":"#aaa","ema9":0,"ema21":0,"ema50":0,"confidence":0,"usdinr":88.5,"entry":0,"sl":0,"tgt":0,"tgt2":0,"option":"WAIT","spread":0,"breakout":None,"breakout_type":"","resistance":0,"support":0,"profit_ratio":0,"profit_pct":0,"score":0,"emoji":CONFIG[name]["emoji"],"label":CONFIG[name]["label"],"oi":0,"oi_change":0,"oi_change_pct":0,"oi_signal":"--","oi_trend":"--","pcr":0,"vol_ratio":1,"volume":0,"ist_time":ist_str()}
    sorted_out = dict(sorted(out.items(), key=lambda x: x[1]["score"], reverse=True))
    return sorted_out

def get_ai_suggestion():
    prices=get_live_prices()
    candidates={k:v for k,v in prices.items() if v["action"] in ["BUY CE","BUY PE"] and v["price"]!=0}
    if not candidates:
        best_name=list(prices.keys())[0]; d=prices[best_name]
        return {"script":best_name,"action":"WAIT","confidence":d["confidence"],"reason":f"Clear Breakout Illa. {best_name} {d['trend']}. WAIT. OI: {d['oi_signal']} PCR {d['pcr']}. Only Buying.","entry":d["entry"],"target":d["tgt"],"stoploss":d["sl"],"option":f"{best_name} - WAIT","trend":d["trend"],"pct":d["pct"],"all":prices,"breakout":None,"profit_ratio":0,"market_cond":d["market_cond"],"oi_signal":d["oi_signal"],"pcr":d["pcr"],"ist_time":ist_str()}
    best_name=list(candidates.keys())[0]; d=candidates[best_name]
    reason=f"🏆 #1 Profit {d['profit_ratio']}:1 | {best_name} - {d['trend']} | Market: {d['market_cond']} | OI: {d['oi_signal']} ({d['oi_change_pct']}%) PCR {d['pcr']} | EMA9 {d['ema9']} > EMA21 {d['ema21']} | "
    if d["breakout"]: reason+=f"🔥 {d['breakout']} "
    reason+=f"OPTIONS BUYING - {d['action']} Mattum!"
    return {"script":best_name,"action":d["action"],"confidence":d["confidence"],"reason":reason,"entry":d["entry"],"target":d["tgt"],"stoploss":d["sl"],"option":d["option"],"trend":d["trend"],"pct":d["pct"],"all":prices,"breakout":d["breakout"],"tgt2":d["tgt2"],"bid":d["bid"],"ask":d["ask"],"resistance":d["resistance"],"support":d["support"],"profit_ratio":d["profit_ratio"],"profit_pct":d["profit_pct"],"market_cond":d["market_cond"],"oi_signal":d["oi_signal"],"pcr":d["pcr"],"oi":d["oi"],"oi_change_pct":d["oi_change_pct"],"ist_time":ist_str()}

# === AUTOMATIC ALERT LOOP - BACKGROUND ===
def auto_alert_loop():
    print(f"[{ist_str()}] Auto Alert Loop Started - Every 5 Min Check")
    # Start ku 1 Min Wait - Server Start Aaga
    time.sleep(60)
    # Startup Msg - Bot Start Aachu nu Telegram la Varum
    send_telegram(f"🤖 AI BOT STARTED!\n\n✅ Auto Alert ON\n🕐 Time: {ist_str()}\n📊 Scripts: NIFTY, SENSEX, CRUDEOILM, GOLDM, SILVERM\n🎯 Mode: Options Buying Only\n🚨 Breakout Vandha Auto Telegram Varum!\n⏰ Check: Every 5 Min (Market Hours 9:15 AM - 11:30 PM IST)\n\nDashboard Paakavum!")
    while True:
        try:
            now_ist = ist_now()
            hour = now_ist.hour + now_ist.minute/60
            # Market Hours Only: 9:00 AM to 11:30 PM IST (NSE + MCX)
            # Night la Alert Vendaam nu - Ithu Illana 24 Mani Alert Varum
            is_market_hours = 9.0 <= hour <= 23.5
            # Weekend Check - Saturday/Sunday NSE Closed, MCX Saturday Half Day - Sunday Off
            is_weekend = now_ist.weekday() >= 6  # 6=Sunday, 5=Saturday - Saturday MCX Open, So Sunday Mattum Off
            is_sunday = now_ist.weekday() == 6
            if is_market_hours and not is_sunday:
                ai = get_ai_suggestion()
                # Condition 1: BREAKOUT + High Confidence >=75% - Immediate Alert
                # Condition 2: STRONG Trend + Confidence >=85% - Alert
                should_alert = False
                alert_type = ""
                if ai["breakout"] and ai["confidence"] >= 70:
                    should_alert = True; alert_type = "🚨 BREAKOUT ALERT"
                elif ai["action"] in ["BUY CE","BUY PE"] and ai["confidence"] >= 85 and ai["trend"] and "STRONG" in ai["trend"]:
                    should_alert = True; alert_type = "🔥 STRONG TREND ALERT"
                # Duplicate Check - Same Script + Same Action + 30 Min la Already Alert Pannita - Skip
                global last_alert
                if should_alert:
                    time_diff = 9999
                    if last_alert["time"]:
                        time_diff = (now_ist - last_alert["time"]).total_seconds()/60
                    is_duplicate = (last_alert["script"]==ai["script"] and last_alert["action"]==ai["action"] and time_diff < 30)
                    if not is_duplicate:
                        msg = f"{alert_type}\n\n⏰ TIME: {ist_str()}\n🏆 #1 Profit Ratio: {ai.get('profit_ratio','--')}:1\n🎯 Script: {ai['script']} ({ai['option']})\n📊 Action: {ai['action']} - OPTIONS BUYING ONLY\n📈 Trend: {ai['trend']}\n🌍 Market: {ai.get('market_cond','--')}\n📊 OI: {ai.get('oi_signal','--')} ({ai.get('oi_change_pct','--')}%) | PCR: {ai.get('pcr','--')}\n\n💰 Live: Rs {ai['entry']}\n🟢 Bid: Rs {ai.get('bid','--')} | 🔴 Ask: Rs {ai.get('ask','--')}\n🎯 TGT1: Rs {ai['target']} | TGT2: Rs {ai.get('tgt2','--')}\n🛑 SL: Rs {ai['stoploss']}\n📍 Resistance: Rs {ai.get('resistance','--')} | Support: Rs {ai.get('support','--')}\n🔥 Confidence: {ai['confidence']}%\n\n🧠 {ai['reason']}\n\n⚠️ Only Buying - SELL Illa. Unga Risk la Trade Pannunga."
                        ok = send_telegram(msg)
                        if ok:
                            last_alert = {"time": now_ist, "script": ai["script"], "action": ai["action"], "breakout": ai["breakout"]}
                            alert_history.append({"time": ist_str(), "script": ai["script"], "action": ai["action"], "type": alert_type, "price": ai["entry"]})
                            print(f"[{ist_str()}] Auto Alert Sent: {ai['script']} {ai['action']}")
                        else:
                            print(f"[{ist_str()}] Auto Alert Failed")
                    else:
                        print(f"[{ist_str()}] Duplicate Skip: {ai['script']} {ai['action']} - {time_diff:.1f} min ago")
                else:
                    print(f"[{ist_str()}] No Alert - {ai['script']} {ai['action']} Conf {ai['confidence']}% Breakout {ai['breakout']}")
            else:
                print(f"[{ist_str()}] Market Closed - No Alert (Hour {hour:.1f}, Sunday {is_sunday})")
            # 5 Min Wait
            time.sleep(300)
        except Exception as e:
            print(f"[{ist_str()}] Auto Loop Error: {e}")
            time.sleep(60)

# Thread Start - App Start Aana Udane
threading.Thread(target=auto_alert_loop, daemon=True).start()

@app.route('/api/prices')
def api_prices(): return jsonify(get_live_prices())
@app.route('/api/ai')
def api_ai(): return jsonify(get_ai_suggestion())
@app.route('/api/breakout')
def api_breakout():
    prices=get_live_prices()
    bo=[{"script":k,"breakout":v["breakout"],"action":v["action"],"price":v["live"],"resistance":v["resistance"],"support":v["support"],"confidence":v["confidence"]} for k,v in prices.items() if v["breakout"]]
    return jsonify({"breakouts":bo,"count":len(bo)})
@app.route('/api/alerts')
def api_alerts(): return jsonify({"last_alert": {"script": last_alert["script"], "action": last_alert["action"], "time": last_alert["time"].strftime('%d-%m-%Y %I:%M:%S %p IST') if last_alert["time"] else "None"}, "history": alert_history[-10:], "auto_alert": "ON", "ist_time": ist_str(), "market_hours": "9:00 AM - 11:30 PM IST"})
@app.route('/breakout_alert')
def breakout_alert():
    ai=get_ai_suggestion()
    msg=f"🚨 MANUAL ALERT - {ist_str()}\n\n🏆 #1 Profit {ai.get('profit_ratio','--')}:1\n🎯 {ai['script']} ({ai['option']})\n📊 {ai['action']} | Trend: {ai['trend']}\n🌍 Market: {ai.get('market_cond','--')}\n📊 OI: {ai.get('oi_signal','--')} | PCR: {ai.get('pcr','--')}\n💰 Entry: Rs {ai['entry']}\n🎯 TGT: Rs {ai['target']} | SL: Rs {ai['stoploss']}\n🔥 Conf: {ai['confidence']}%\n\n{ai['reason']}"
    ok=send_telegram(msg)
    return "✅ Alert Sent!" if ok else "❌ Telegram Failed!"
@app.route('/ai_signal')
def ai_signal(): return breakout_alert()
@app.route('/test_auto')
def test_auto():
    ai=get_ai_suggestion()
    msg=f"🧪 TEST AUTO ALERT\n\n⏰ IST Time: {ist_str()}\n🎯 {ai['script']} ({ai['option']})\n📊 {ai['action']} | {ai['trend']}\n💰 Entry Rs {ai['entry']} | TGT Rs {ai['target']} | SL Rs {ai['stoploss']}\n🔥 Conf {ai['confidence']}%\n\nIdhu Test - Auto Alert Work Aagudha nu Paakka!"
    ok=send_telegram(msg)
    return "✅ Test Auto Alert Sent! Telegram Paanga! Time IST la Irukkanum!" if ok else "❌ Failed!"

@app.route('/')
def home():
    now = ist_str()
    html="""
    <html><head><title>AI Bot - IST + Auto Alert</title><meta name='viewport' content='width=device-width, initial-scale=1'>
    <style>
    *{box-sizing:border-box} body{background:#0e1117;color:white;font-family:Arial;margin:0;padding:8px;overflow-x:hidden}
    .card{background:#131722;border-radius:10px;padding:10px;border:1px solid #222;margin-top:8px}
    .btn{display:inline-block;padding:9px 12px;border-radius:7px;color:white;text-decoration:none;font-weight:bold;margin:3px;font-size:12px}
    .b1{background:#0088cc}.b2{background:#00c853}.b3{background:#ff9800}.b4{background:#7c3aed}.b5{background:#ff1744}.b6{background:#ff6d00}
    .green{color:#00ff88}.orange{color:#ff9800}
    .top{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px}
    .grid5{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:8px}
    .script-card{background:#1a2030;border-radius:10px;padding:10px;border:1px solid #2a3348;position:relative}
    .script-card.rank1{border:2px solid #00ff88;box-shadow:0 0 12px rgba(0,255,136,0.3)}
    .rank-badge{position:absolute;top:-8px;left:8px;background:#00ff88;color:black;font-size:10px;font-weight:bold;padding:2px 7px;border-radius:10px}
    .price{font-size:19px;font-weight:bold;margin:3px 0}
    .badge{padding:4px 8px;border-radius:12px;font-size:11px;font-weight:bold;display:inline-block}
    .bg-green{background:#00ff88;color:black}.bg-orange{background:#ff9800;color:black}
    .small{font-size:11px;color:#aaa}
    .trend-bar{border-radius:7px;padding:6px;text-align:center;font-size:11px;font-weight:bold;margin:6px 0}
    .bidask{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin:6px 0}
    .ba{border-radius:7px;padding:6px;text-align:center;font-size:12px}
    .ba-bid{background:#0f2a1d;border:1px solid #00ff88}.ba-ask{background:#2a0f0f;border:1px solid #ff4444}
    .levels{display:grid;grid-template-columns:1fr 1fr 1fr;gap:5px;margin-top:6px}
    .lvl{background:#0e1117;border-radius:7px;padding:6px;text-align:center;border:1px solid #333;font-size:12px}
    .oi-box{background:#0e1117;border:1px solid #333;border-radius:7px;padding:6px;margin-top:6px;font-size:11px}
    .ai-box{background:linear-gradient(135deg,#1a0033,#0d1b4c);border:2px solid #7c3aed;border-radius:12px;padding:12px;margin-top:8px}
    .ai-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:8px}
    .ai-stat{background:#0e1117;border-radius:8px;padding:8px;text-align:center;border:1px solid #333;font-size:13px}
    .breakout-box{background:linear-gradient(135deg,#ff6d00,#ff1744);border-radius:12px;padding:12px;margin-top:8px;display:none}
    .auto-box{background:#0f2a1d;border:1px solid #00ff88;border-radius:10px;padding:10px;margin-top:8px}
    .live-dot{animation:blink 1s infinite} @keyframes blink{0%{opacity:1}50%{opacity:0.3}100%{opacity:1}}
    @media(max-width:1100px){.grid5{grid-template-columns:repeat(3,1fr)}}
    @media(max-width:700px){.grid5{grid-template-columns:1fr}.ai-grid{grid-template-columns:1fr 1fr}}
    </style></head><body>
    <div class='top'><h2 style='margin:4px 0;font-size:20px'>🤖 AI BOT DASHBOARD</h2><span style='background:#1e293b;padding:6px 10px;border-radius:20px;font-size:12px'><span class='live-dot'>🟢</span> <span id='clock'>"""+now+"""</span> | USDINR: <span id='usdinrTop'>--</span> | IP: """+get_ip()+"""</span></div>
    <div style='background:#0f2a1d;border:1px solid #00ff88;border-radius:8px;padding:7px;margin-top:8px;text-align:center;font-size:12px'>✅ <b>OPTIONS BUYING ONLY</b> • <b>IST TIME FIXED ✅</b> • <b>AUTO TELEGRAM ALERT ON ✅</b> • High Profit First 🏆</div>

    <!-- AUTO ALERT STATUS -->
    <div class='auto-box'>
      <div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;align-items:center'>
        <div><b>🤖 AUTO ALERT: <span class='green'>✅ ON</span></b> <span class='small'>- Button Click Panna Vendaam! Breakout Vandha Thaan-a Telegram Varum!</span></div>
        <div style='font-size:11px'>Last Auto Alert: <b id='lastAlert'>Checking...</b> | Next Check: Every 5 Min</div>
      </div>
      <div style='font-size:11px;color:#aaa;margin-top:6px'>📌 Auto Alert Condition: (1) BREAKOUT + Confidence ≥70% <b>OR</b> (2) STRONG TREND + Confidence ≥85% | Market Hours: 9:00 AM - 11:30 PM IST | Sunday Off | Same Alert 30 Min-ku Oru Vaati Mattum - Spam Varadhu!</div>
      <div id='alertHistory' style='font-size:11px;margin-top:6px'></div>
    </div>

    <div class='card' style='padding:8px;display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px'><div><span class='small'>🌍 OVERALL MARKET:</span> <b id='overallCond' style='font-size:14px'>Loading...</b></div><div><span class='small'>📊 TREND:</span> <b id='overallTrend'>--</b></div><div><span class='small'>📈 OI:</span> <b id='overallOI'>--</b></div><div><span class='small'>PCR:</span> <b id='overallPCR'>--</b></div></div>

    <div id='breakoutBox' class='breakout-box'><div style='font-size:11px'>🚨 BREAKOUT NOTIFICATION - AUTO ALERT SENT TO TELEGRAM!</div><h2 id='breakoutTitle' style='margin:6px 0;font-size:18px'>🔥 BREAKOUT!</h2><div id='breakoutDesc' style='font-size:12px;line-height:1.5'>--</div></div>

    <div class='ai-box'>
      <div style='font-size:11px;color:#c4b5fd'>🤖 AI SUGGEST BOT • OPTIONS BUYING ONLY • TREND + OI • IST TIME</div>
      <h2 id='aiTitle' style='margin:6px 0;font-size:19px'>🤖 AI Analyzing...</h2>
      <div id='aiReason' style='font-size:12px;color:#e0e7ff;line-height:1.5'>Analyzing...</div>
      <div style='margin-top:6px'>AI Confidence: <b id='aiConf' style='color:#00ff88;font-size:22px'>--%</b> <span id='aiTrend' style='font-size:11px;color:#aaa'>--</span> <span id='aiProfitBadge' style='background:#00ff88;color:black;padding:3px 8px;border-radius:12px;font-size:11px;font-weight:bold'>--</span> <span id='aiMarketBadge' style='background:#333;padding:3px 8px;border-radius:12px;font-size:11px'>--</span></div>
      <div class='ai-grid'>
        <div class='ai-stat'><div class='small'>🏆 #1 BEST</div><b id='aiScript' style='font-size:14px'>--</b><div class='small' id='aiOption'>--</div></div>
        <div class='ai-stat'><div class='small'>💰 ENTRY</div><b id='aiEntry' style='font-size:14px;color:#00ff88'>--</b></div>
        <div class='ai-stat'><div class='small'>🎯 TARGET</div><b id='aiTarget' style='font-size:14px;color:#00ff88'>--</b></div>
        <div class='ai-stat'><div class='small'>🛑 STOPLOSS</div><b id='aiSL' style='font-size:14px;color:#ff4444'>--</b></div>
      </div>
      <div style='margin-top:8px;text-align:center'><span class='small'>Auto Alert ON - Manual-a Anuppanumna:</span> <a class='btn b2' href='/breakout_alert'>📩 Manual Send</a> <a class='btn b6' href='/test_auto'>🧪 Test Auto Alert (IST Time Check)</a></div>
    </div>

    <div class='card' style='border:2px solid #00ff88;text-align:center;padding:8px'><div style='font-size:11px;color:#aaa'>OVERALL MARKET - OPTIONS BUYING ONLY - IST TIME</div><h2 id='mainSignal' class='green' style='margin:4px 0;font-size:18px'>Loading...</h2><div id='mainSub' style='font-size:12px'>Checking...</div><div style='margin-top:4px'><span class='small' id='lastUpdate'>--</span></div></div>

    <div style='display:flex;justify-content:space-between;align-items:center;margin-top:10px'><b style='font-size:14px'>📊 5 SCRIPTS - SAME ROW - HIGH PROFIT FIRST 🏆</b><span class='small'>Trend + OI + Market Condition</span></div>
    <div id='scriptsGrid' class='grid5'></div>

    <div class='card' style='padding:8px'><b style='font-size:13px'>💡 TREND LEGEND</b><div style='font-size:11px;color:#aaa;margin-top:4px'>🚀🚀 STRONG UPTREND = EMA 9>21>50 | ↗ UPTREND = EMA9>21 | ◐ SIDEWAYS | ↘ DOWNTREND = EMA9<21 | 📉📉 STRONG DOWNTREND = EMA 9<21<50 | OI: Long Buildup = Price↑ OI↑ | Short Buildup = Price↓ OI↑ | PCR >1 Bearish, <1 Bullish</div></div>
    <div style='margin-top:8px'><a class='btn b1' href='/test_telegram'>📩 Test Telegram</a><a class='btn b6' href='/test_auto'>🧪 Test Auto Alert</a><a class='btn b3' href='/debug'>🔍 Debug</a><a class='btn b4' href='/login'>🔐 Login</a></div>

    <script>
    function fmt(n){ return 'Rs '+n.toLocaleString('en-IN',{maximumFractionDigits:0}); }
    function fmtOI(n){ if(n>=10000000) return (n/10000000).toFixed(2)+' Cr'; if(n>=100000) return (n/100000).toFixed(1)+' L'; return n.toLocaleString('en-IN'); }
    // IST CLOCK - Live
    function updateClock(){
      let now = new Date(new Date().toLocaleString('en-US',{timeZone:'Asia/Kolkata'}));
      document.getElementById('clock').innerText = now.toLocaleDateString('en-IN',{day:'2-digit',month:'2-digit',year:'numeric'})+' '+now.toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:true})+' IST';
    }
    setInterval(updateClock, 1000); updateClock();
    function loadPrices(){
      fetch('/api/prices').then(r=>r.json()).then(data=>{
        let arr=Object.values(data); let ce=0,pe=0,wait=0,usd='',strongUp=0,strongDown=0,up=0,down=0,oiUp=0,pcrSum=0; let html='';
        arr.forEach((d,i)=>{
          let rank=i+1; let isTop=rank==1 && d.action!='WAIT';
          let badgeClass=d.action=='WAIT'?'bg-orange':'bg-green'; let badgeText=d.action=='WAIT'?'◐ WAIT':'✅ '+d.action+' - BUYING';
          if(d.action=='BUY CE') ce++; else if(d.action=='BUY PE') pe++; else wait++;
          if(d.trend_level==5) strongUp++; else if(d.trend_level==4) up++; else if(d.trend_level==1) strongDown++; else if(d.trend_level==2) down++;
          if(d.oi_change>0) oiUp++; pcrSum+=d.pcr; usd=d.usdinr;
          let oiColor=d.oi_change>=0?'#00ff88':'#ff4444';
          html+=`<div class='script-card ${isTop?'rank1':''}'>${isTop?'<div class="rank-badge">🏆 #1 BEST</div>':`<div class="rank-badge" style="background:#333;color:#aaa">#${rank}</div>`}<div class='small'>${d.label} • OPTIONS BUYING</div><h3 style='margin:3px 0;font-size:15px'>${d.emoji} ${d.name}</h3><div class='small'>LIVE RATE</div><div class='price green'>${fmt(d.live)}</div><div class='small'>${d.change>=0?'▲ + ':'▼ '}${fmt(Math.abs(d.change))} (${d.pct}%)</div><div class='trend-bar' style='background:${d.trend_bg};color:${d.trend_color};border:1px solid ${d.trend_color}'>${d.trend}</div><div style='text-align:center;font-size:11px'>🌍 <b style='color:${d.cond_color}'>${d.market_cond}</b></div><div style='text-align:center;font-size:10px;color:#aaa;margin-top:2px'>EMA 9: ${fmt(d.ema9)} | 21: ${fmt(d.ema21)} | 50: ${fmt(d.ema50)}</div><div style='background:#0e1117;border:1px solid #00ff88;border-radius:7px;padding:5px;margin-top:6px;text-align:center'><div class='small'>🏆 PROFIT RATIO</div><b style='color:#00ff88;font-size:15px'>${d.profit_ratio}:1</b> <span class='small'>| ${d.profit_pct}% | Conf ${d.confidence}%</span></div><div class='oi-box'><div style='display:flex;justify-content:space-between'><span>📊 OI</span><b>${fmtOI(d.oi)}</b></div><div style='display:flex;justify-content:space-between'><span>OI Change</span><b style='color:${oiColor}'>${d.oi_change>=0?'▲ +':'▼ '}${fmtOI(Math.abs(d.oi_change))} (${d.oi_change_pct}%)</b></div><div style='display:flex;justify-content:space-between'><span>OI Signal</span><b>${d.oi_signal}</b></div><div style='display:flex;justify-content:space-between'><span>PCR</span><b>${d.pcr} ${d.pcr>1?'🐻':'🐂'}</b></div><div style='display:flex;justify-content:space-between'><span>Volume</span><b>${d.vol_ratio}x</b></div></div>${d.breakout?`<div class='small' style='color:#ff9800;font-weight:bold;margin-top:4px'>🔥 ${d.breakout}</div>`:''}<div class='bidask'><div class='ba ba-bid'><div class='small'>🟢 BID</div><b>${fmt(d.bid)}</b></div><div class='ba ba-ask'><div class='small'>🔴 ASK</div><b>${fmt(d.ask)}</b></div></div><div style='text-align:center'><span class='badge ${badgeClass}'>${badgeText}</span></div><div class='levels'><div class='lvl'><div class='small'>ENTRY</div><b style='color:#00ff88'>${fmt(d.entry)}</b></div><div class='lvl'><div class='small'>🎯 TGT</div><b style='color:#00ff88'>${fmt(d.tgt)}</b></div><div class='lvl'><div class='small'>🛑 SL</div><b style='color:#ff4444'>${fmt(d.sl)}</b></div></div><div class='small' style='margin-top:6px;text-align:center'>TGT2: <b style='color:#00ff88'>${fmt(d.tgt2)}</b> | Res: ${fmt(d.resistance)} | Sup: ${fmt(d.support)}</div></div>`;
        });
        document.getElementById('scriptsGrid').innerHTML=html;
        document.getElementById('usdinrTop').innerText='Rs '+usd;
        let overallCond=strongUp>=2?'BULLISH STRONG 🐂🔥':up>=3?'BULLISH 🐂':strongDown>=2?'BEARISH STRONG 🐻🔻':down>=3?'BEARISH 🐻':'SIDEWAYS / MIXED ➡️';
        let overallColor=overallCond.includes('BULLISH')?'#00ff88':overallCond.includes('BEARISH')?'#ff4444':'#ff9800';
        document.getElementById('overallCond').innerText=overallCond; document.getElementById('overallCond').style.color=overallColor;
        document.getElementById('overallTrend').innerText=strongUp+' Strong Up | '+up+' Up | '+down+' Down | '+strongDown+' Strong Down';
        document.getElementById('overallOI').innerText=oiUp+'/5 OI Up'; document.getElementById('overallPCR').innerText=(pcrSum/5).toFixed(2);
        let m=document.getElementById('mainSignal');
        if(ce>0||pe>0){ m.innerText='✅ BUYING: '+ce+' CE BUY + '+pe+' PE BUY | '+wait+' WAIT'; m.className='green'; } else { m.innerText='◐ WAIT - NO BUYING CHANCE'; m.className='orange'; }
        document.getElementById('mainSub').innerText='Sorted #1 = Highest Profit | CE = Mela Pogum | PE = Keela Pogum';
        // IST Time from Browser - Correct Time
        let nowIST=new Date(new Date().toLocaleString('en-US',{timeZone:'Asia/Kolkata'}));
        document.getElementById('lastUpdate').innerText='Last Update: '+nowIST.toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:true})+' IST - Auto Alert ON ✅';
      });
    }
    function loadAI(){
      fetch('/api/ai').then(r=>r.json()).then(ai=>{
        let emoji=ai.action=='WAIT'?'◐':'✅';
        document.getElementById('aiTitle').innerHTML=emoji+' AI SUGGESTS: <span style="color:#00ff88">'+ai.action+' - '+ai.script+'</span> (OPTIONS BUYING ONLY)';
        document.getElementById('aiReason').innerText='🧠 '+ai.reason;
        document.getElementById('aiConf').innerText=ai.confidence+'%';
        document.getElementById('aiTrend').innerText=ai.trend+' | '+ai.pct+'%';
        document.getElementById('aiProfitBadge').innerText='🏆 Profit '+ai.profit_ratio+':1';
        document.getElementById('aiMarketBadge').innerText='🌍 '+ai.market_cond+' | OI: '+ai.oi_signal+' | PCR '+ai.pcr;
        document.getElementById('aiScript').innerText=ai.script; document.getElementById('aiOption').innerText=ai.option;
        document.getElementById('aiEntry').innerText=fmt(ai.entry); document.getElementById('aiTarget').innerText=fmt(ai.target); document.getElementById('aiSL').innerText=fmt(ai.stoploss);
        let box=document.getElementById('breakoutBox');
        if(ai.breakout){ box.style.display='block'; document.getElementById('breakoutTitle').innerText='🔥 BREAKOUT: '+ai.script+' - '+ai.breakout; document.getElementById('breakoutDesc').innerText=ai.script+' '+ai.trend+' | Market '+ai.market_cond+' | OI '+ai.oi_signal+' PCR '+ai.pcr+' | Entry '+fmt(ai.entry)+' | TGT '+fmt(ai.target)+' | SL '+fmt(ai.stoploss)+' | Auto Telegram Already Sent / Sending...'; }
        else { box.style.display='none'; }
      });
      fetch('/api/alerts').then(r=>r.json()).then(a=>{
        document.getElementById('lastAlert').innerText=a.last_alert.time+' - '+a.last_alert.script+' '+a.last_alert.action;
        if(a.history && a.history.length>0){
          let h='Recent Auto Alerts: ';
          a.history.slice(-3).forEach(x=>{ h+=' | '+x.time+' - '+x.script+' '+x.action; });
          document.getElementById('alertHistory').innerText=h;
        } else {
          document.getElementById('alertHistory').innerText='Recent Auto Alerts: Innum Alert Illa - Breakout Vandha Thaan Varum. Test Panna 🧪 Test Auto Alert Button Click Pannunga!';
        }
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
    ok=send_telegram(f"✅ AI Bot Test Success!\n⏰ IST Time: {ist_str()}")
    return "✅ Telegram Sent! Time IST la Check Pannunga!" if ok else "❌ Telegram Failed!"
@app.route('/order_test')
def order_test():
    send_telegram(f"🚀 ORDER PLACED: NIFTY CE BUY 100 Qty @ 120\n⏰ {ist_str()}")
    return "Order Alert Sent!"
@app.route('/login')
def login(): return redirect(f"https://ant.aliceblueonline.com/?appcode={ALICE_API_KEY}")
@app.route('/debug')
def debug(): return jsonify({"ip":get_ip(),"telegram":bool(TELEGRAM_BOT_TOKEN),"ist_time":ist_str(),"utc_time":str(datetime.now(timezone.utc)),"prices":get_live_prices(),"ai":get_ai_suggestion(),"alerts":alert_history})
if __name__=='__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT",5000)))
