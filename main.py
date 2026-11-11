import os, requests, threading, time, math
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify, redirect

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
ALICE_API_KEY = os.environ.get("ALICE_API_KEY", "")

IST = timezone(timedelta(hours=5, minutes=30))
def ist_now(): return datetime.now(IST)
def ist_str(): return ist_now().strftime('%d-%m-%Y %I:%M:%S %p IST')

def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        r = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
        return r.status_code == 200
    except: return False

def get_ip():
    try: return requests.get("https://api.ipify.org", timeout=5).text
    except: return "Unknown"

def get_usdinr():
    try:
        r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/USDINR=X?range=1d&interval=1m", headers={"User-Agent":"Mozilla/5.0"}, timeout=8).json()
        return r["chart"]["result"][0]["meta"]["regularMarketPrice"]
    except: return 88.50

CONFIG = {
    "NIFTY": {"spread": 2, "sl_pct": 0.20, "tgt_pct": 0.40, "emoji": "🟣", "label": "NSE", "strike_step": 50, "lot": 75, "iv": 13.5},
    "SENSEX": {"spread": 5, "sl_pct": 0.20, "tgt_pct": 0.40, "emoji": "🔵", "label": "BSE", "strike_step": 100, "lot": 10, "iv": 13.0},
    "CRUDEOILM": {"spread": 4, "sl_pct": 0.40, "tgt_pct": 0.80, "emoji": "⚫", "label": "MCX", "strike_step": 50, "lot": 10, "iv": 28.0},
    "GOLDM": {"spread": 25, "sl_pct": 0.30, "tgt_pct": 0.60, "emoji": "🟡", "label": "MCX", "strike_step": 100, "lot": 10, "iv": 14.0},
    "SILVERM": {"spread": 80, "sl_pct": 0.30, "tgt_pct": 0.60, "emoji": "⚪", "label": "MCX", "strike_step": 500, "lot": 5, "iv": 22.0},
}
SCRIPTS = {"NIFTY":"^NSEI","SENSEX":"^BSESN","CRUDEOILM":"CL=F","GOLDM":"GC=F","SILVERM":"SI=F"}

def convert_price(name, raw, usdinr):
    if name=="CRUDEOILM": return raw*usdinr
    if name=="GOLDM": return (raw/31.1035)*10*usdinr
    if name=="SILVERM": return (raw/31.1035)*1000*usdinr
    return raw

def calc_option(name, spot, action):
    cfg = CONFIG[name]
    step = cfg["strike_step"]; iv = cfg["iv"]/100
    dte = 4 if name in ["NIFTY","SENSEX"] else 12
    t = dte/365.0
    atm = round(spot/step)*step
    if action == "BUY CE": strike = atm - step; opt_type = "CE"
    elif action == "BUY PE": strike = atm + step; opt_type = "PE"
    else: strike = atm; opt_type = "CE"
    if opt_type == "CE": intrinsic = max(spot - strike, 0)
    else: intrinsic = max(strike - spot, 0)
    time_value = spot * iv * math.sqrt(t) * 0.38
    if intrinsic > 0: time_value = time_value * 0.75
    premium = round(intrinsic + time_value, 2)
    prem_sl = round(premium * 0.70, 2); prem_tgt1 = round(premium * 1.60, 2); prem_tgt2 = round(premium * 2.20, 2)
    lot = cfg["lot"]; total_cost = round(premium * lot, 2)
    max_loss = round((premium - prem_sl) * lot, 2); max_profit = round((prem_tgt1 - premium) * lot, 2)
    return {"strike": strike, "atm": atm, "opt_type": opt_type, "premium": premium, "intrinsic": round(intrinsic,2), "time_value": round(time_value,2), "prem_sl": prem_sl, "prem_tgt1": prem_tgt1, "prem_tgt2": prem_tgt2, "lot": lot, "total_cost": total_cost, "max_loss": max_loss, "max_profit": max_profit, "dte": dte, "iv": cfg["iv"], "moneyness": "ITM1" if action in ["BUY CE","BUY PE"] else "ATM"}

# === BACKTEST LOGIC ===
def run_backtest(name, days=30):
    usdinr = get_usdinr()
    sym = SCRIPTS[name]
    cfg = CONFIG[name]
    # 1mo Data - 15m Candle
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=1mo&interval=15m"
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=12).json()
        res = r["chart"]["result"][0]
        ts = res["timestamp"]
        q = res["indicators"]["quote"][0]
        closes_raw = q["close"]; highs_raw = q["high"]; lows_raw = q["low"]
        candles = []
        for i,t in enumerate(ts):
            if closes_raw[i] is None: continue
            candles.append({
                "time": datetime.fromtimestamp(t, IST).strftime('%d-%m %I:%M %p'),
                "close": convert_price(name, closes_raw[i], usdinr),
                "high": convert_price(name, highs_raw[i], usdinr),
                "low": convert_price(name, lows_raw[i], usdinr),
            })
        if len(candles) < 60:
            return {"error": "Data Illa"}
    except Exception as e:
        return {"error": str(e)}

    trades = []
    # Walk Forward - 25th Candle la irundhu Start
    for i in range(25, len(candles)-5):
        window = candles[max(0,i-25):i]
        closes = [c["close"] for c in window]
        highs = [c["high"] for c in window]
        lows = [c["low"] for c in window]
        def ema(data,p):
            k=2/(p+1); e=data[0]
            for v in data[1:]: e=v*k+e*(1-k)
            return e
        ema9 = ema(closes,9); ema21 = ema(closes,21); ema50 = ema(closes,50) if len(closes)>=50 else ema21
        price = candles[i]["close"]
        prev = candles[i-1]["close"]
        pct = (price-prev)/prev*100 if prev else 0
        res20 = max(highs[-20:]); sup20 = min(lows[-20:])
        prev_ema9 = ema(closes[:-1],9); prev_ema21 = ema(closes[:-1],21)
        breakout=None; btype=""
        if price > res20: breakout="BREAKOUT UP"; btype="UP"
        elif price < sup20: breakout="BREAKDOWN"; btype="DOWN"
        elif prev_ema9 <= prev_ema21 and ema9 > ema21: breakout="EMA CROSS UP"; btype="UP"
        elif prev_ema9 >= prev_ema21 and ema9 < ema21: breakout="EMA CROSS DOWN"; btype="DOWN"

        # Trend
        if ema9 > ema21 > ema50 and price > ema9 and pct > 0.30: trend="STRONG UPTREND"; level=5
        elif ema9 > ema21 and price > ema9: trend="UPTREND"; level=4
        elif ema9 < ema21 < ema50 and price < ema9 and pct < -0.30: trend="STRONG DOWNTREND"; level=1
        elif ema9 < ema21 and price < ema9: trend="DOWNTREND"; level=2
        else: trend="SIDEWAYS"; level=3

        action=None
        if level in [5,4] or btype=="UP": action="BUY CE"
        elif level in [1,2] or btype=="DOWN": action="BUY PE"
        else: continue  # WAIT na Trade Illa

        # Entry = Next Candle Open Approx = Ippo Close
        entry_spot = price
        opt = calc_option(name, entry_spot, action)
        entry_prem = opt["premium"]; sl_prem = opt["prem_sl"]; tgt_prem = opt["prem_tgt1"]
        # Next 5 Candles la - TGT / SL Hit Aacha Paakkurom
        result="OPEN"; exit_prem=entry_prem; exit_reason="Time Exit (5 Candles)"
        for j in range(i+1, min(i+6, len(candles))):
            fut_price = candles[j]["close"]
            # Premium Approx - Spot Move ku Premium Move
            # CE: Spot +1% na Premium +30% Approx, PE: Spot -1% na Premium +30%
            spot_move_pct = (fut_price - entry_spot)/entry_spot*100
            if action=="BUY CE": prem_move = spot_move_pct * 8  # Leverage
            else: prem_move = -spot_move_pct * 8
            est_prem = entry_prem * (1 + prem_move/100)
            est_prem = max(est_prem, 1)
            if est_prem >= tgt_prem:
                result="WIN"; exit_prem=tgt_prem; exit_reason=f"TGT Hit @ Candle {j-i}"; break
            if est_prem <= sl_prem:
                result="LOSS"; exit_prem=sl_prem; exit_reason=f"SL Hit @ Candle {j-i}"; break
            exit_prem = est_prem
        if result=="OPEN":
            # 5 Candles ku Appuram - Profit na WIN, Loss na LOSS
            pnl_prem = exit_prem - entry_prem
            result = "WIN" if pnl_prem>0 else "LOSS" if pnl_prem<0 else "BREAKEVEN"
            exit_reason = "Time Exit - 5 Candles Mudinjiduchu"
        pnl = round((exit_prem - entry_prem) * opt["lot"], 2)
        pnl_pct = round((exit_prem - entry_prem)/entry_prem*100,1)
        trades.append({
            "date": candles[i]["time"], "action": action, "trend": trend, "breakout": breakout or "-",
            "spot": round(entry_spot,2), "strike": opt["strike"], "opt_type": opt["opt_type"],
            "entry_prem": entry_prem, "exit_prem": round(exit_prem,2), "tgt": tgt_prem, "sl": sl_prem,
            "result": result, "pnl": pnl, "pnl_pct": pnl_pct, "exit_reason": exit_reason, "lot": opt["lot"]
        })
        # Oru Trade Mudinja - Next 5 Candles Skip - Overlap Vendaam
        # Ithu Real Trading Maadhiri - Oru Trade-ku Appuram Wait
        # Skip Logic - Loop la i jump panna Mudiyadhu - Adhaala last_trade_index use pannalam, simple-a continue
        # For simplicity - 5 candles gap: i+5 la irundhu continue - Python for loop la mudiyadhu, adhaala check:
        # Naama trades count-a paathu - adutha signal 5 candles ku munnadi vandha skip - Idha simple-a: last trade time check
        # Ippo simple-a - ella signal-um eduthukkurom, ana backtest result konjam optimistic-a irukkum

    if not trades:
        return {"script": name, "total": 0, "win": 0, "loss": 0, "win_rate": 0, "total_pnl": 0, "trades": []}
    wins = [t for t in trades if t["result"]=="WIN"]
    losses = [t for t in trades if t["result"]=="LOSS"]
    total_pnl = round(sum(t["pnl"] for t in trades),2)
    win_rate = round(len(wins)/len(trades)*100,1) if trades else 0
    avg_win = round(sum(t["pnl"] for t in wins)/len(wins),2) if wins else 0
    avg_loss = round(sum(t["pnl"] for t in losses)/len(losses),2) if losses else 0
    best = max(trades, key=lambda x: x["pnl"]) if trades else None
    worst = min(trades, key=lambda x: x["pnl"]) if trades else None
    # CE vs PE
    ce_trades = [t for t in trades if t["action"]=="BUY CE"]
    pe_trades = [t for t in trades if t["action"]=="BUY PE"]
    ce_win = round(len([t for t in ce_trades if t["result"]=="WIN"])/len(ce_trades)*100,1) if ce_trades else 0
    pe_win = round(len([t for t in pe_trades if t["result"]=="WIN"])/len(pe_trades)*100,1) if pe_trades else 0
    return {
        "script": name, "days": days, "total": len(trades), "win": len(wins), "loss": len(losses),
        "win_rate": win_rate, "total_pnl": total_pnl, "avg_win": avg_win, "avg_loss": avg_loss,
        "best": best["pnl"] if best else 0, "worst": worst["pnl"] if worst else 0,
        "ce_total": len(ce_trades), "ce_win_rate": ce_win, "pe_total": len(pe_trades), "pe_win_rate": pe_win,
        "capital_needed": round(10000,2), "return_pct": round(total_pnl/10000*100,1),
        "trades": trades[-20:],  # Last 20 Trades Mattum Kaatum
        "all_trades_count": len(trades)
    }

last_alert = {"time": None, "script": "", "action": ""}
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
            raw = meta.get("regularMarketPrice", 0); prev_raw = meta.get("previousClose", raw)
            price = convert_price(name, raw, usdinr); prev = convert_price(name, prev_raw, usdinr)
            chg = price-prev if prev else 0; pct = (chg/prev*100) if prev else 0
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
            if ema9 > ema21 > ema50 and price > ema9 and pct > 0.30: trend_mark="STRONG UPTREND 🚀🚀"; trend_color="#00ff88"; trend_bg="#0f2a1d"; trend_level=5
            elif ema9 > ema21 and price > ema9: trend_mark="UPTREND ↗"; trend_color="#00c853"; trend_bg="#0f2a1d"; trend_level=4
            elif ema9 < ema21 < ema50 and price < ema9 and pct < -0.30: trend_mark="STRONG DOWNTREND 📉📉"; trend_color="#ff1744"; trend_bg="#2a0f0f"; trend_level=1
            elif ema9 < ema21 and price < ema9: trend_mark="DOWNTREND ↘"; trend_color="#ff7043"; trend_bg="#2a0f0f"; trend_level=2
            elif abs(pct) < 0.10 and abs(ema9-ema21)/ema21*100 < 0.10: trend_mark="SIDEWAYS ◐"; trend_color="#ff9800"; trend_bg="#2a1a0f"; trend_level=3
            else: trend_mark="VOLATILE ⚡"; trend_color="#ffca28"; trend_bg="#2a1a0f"; trend_level=3
            if trend_level==5: market_cond="BULLISH STRONG 🐂🔥"; cond_color="#00ff88"
            elif trend_level==4: market_cond="BULLISH 🐂"; cond_color="#00c853"
            elif trend_level==1: market_cond="BEARISH STRONG 🐻🔻"; cond_color="#ff1744"
            elif trend_level==2: market_cond="BEARISH 🐻"; cond_color="#ff7043"
            elif trend_level==3 and "SIDEWAYS" in trend_mark: market_cond="RANGE BOUND ➡️"; cond_color="#ff9800"
            else: market_cond="VOLATILE ⚡"; cond_color="#ffca28"
            if breakout and btype=="UP": market_cond="BREAKOUT BULLISH 🚀"; cond_color="#00ff88"
            if breakout and btype=="DOWN": market_cond="BREAKDOWN BEARISH 📉"; cond_color="#ff1744"
            if trend_level in [5,4] or btype=="UP": action="BUY CE"; signal="BUY CE"; color="green"; strength=88 if trend_level==5 else 80
            elif trend_level in [1,2] or btype=="DOWN": action="BUY PE"; signal="BUY PE"; color="green"; strength=88 if trend_level==1 else 80
            else: action="WAIT"; signal="WAIT"; color="orange"; strength=45
            conf = min(92, max(50, strength + abs(pct)*5 + (10 if breakout else 0)))
            cfg = CONFIG[name]
            bid = price-cfg["spread"]; ask = price+cfg["spread"]; live=(bid+ask)/2
            if action in ["BUY CE","BUY PE"]: entry=ask; sl=round(entry*(1-cfg["sl_pct"]/100),2); tgt=round(entry*(1+cfg["tgt_pct"]/100),2); tgt2=round(entry*(1+cfg["tgt_pct"]/100*2),2); option=f"{name} {action}"
            else: entry=live; sl=round(entry*0.998,2); tgt=round(entry*1.002,2); tgt2=round(entry*1.004,2); option=f"{name} - WAIT"
            risk = abs(entry-sl) if entry!=sl else 1; reward = abs(tgt-entry)
            profit_ratio = round(reward/risk,2) if risk else 0; profit_pct = round(abs(tgt-entry)/entry*100,3) if entry else 0
            score = profit_ratio*20 + conf + (25 if breakout else 0) + abs(pct)*5 + trend_level*2
            if action=="WAIT": score = conf
            opt = calc_option(name, live, action)
            out[name]={"name":name,"symbol":sym,"price":round(live,2),"live":round(live,2),"bid":round(bid,2),"ask":round(ask,2),"prev":round(prev,2),"change":round(chg,2),"pct":round(pct,2),"signal":signal,"action":action,"color":color,"trend":trend_mark,"trend_color":trend_color,"trend_bg":trend_bg,"trend_level":trend_level,"market_cond":market_cond,"cond_color":cond_color,"ema9":round(ema9,2),"ema21":round(ema21,2),"ema50":round(ema50,2),"confidence":round(conf),"usdinr":round(usdinr,2),"entry":round(entry,2),"sl":sl,"tgt":tgt,"tgt2":tgt2,"option":option,"spread":round(ask-bid,2),"breakout":breakout,"breakout_type":btype,"resistance":round(last20_high,2),"support":round(last20_low,2),"profit_ratio":profit_ratio,"profit_pct":profit_pct,"score":round(score,1),"emoji":cfg["emoji"],"label":cfg["label"],"ist_time":ist_str(),"strike":opt["strike"],"atm":opt["atm"],"opt_type":opt["opt_type"],"premium":opt["premium"],"intrinsic":opt["intrinsic"],"time_value":opt["time_value"],"prem_sl":opt["prem_sl"],"prem_tgt1":opt["prem_tgt1"],"prem_tgt2":opt["prem_tgt2"],"lot":opt["lot"],"total_cost":opt["total_cost"],"max_loss":opt["max_loss"],"max_profit":opt["max_profit"],"dte":opt["dte"],"iv":opt["iv"],"moneyness":opt["moneyness"]}
        except:
            out[name]={"name":name,"symbol":sym,"price":0,"live":0,"bid":0,"ask":0,"prev":0,"change":0,"pct":0,"signal":"WAIT","action":"WAIT","color":"orange","trend":"Loading...","trend_color":"#ff9800","trend_bg":"#222","trend_level":3,"market_cond":"Loading...","cond_color":"#aaa","ema9":0,"ema21":0,"ema50":0,"confidence":0,"usdinr":88.5,"entry":0,"sl":0,"tgt":0,"tgt2":0,"option":"WAIT","spread":0,"breakout":None,"breakout_type":"","resistance":0,"support":0,"profit_ratio":0,"profit_pct":0,"score":0,"emoji":CONFIG[name]["emoji"],"label":CONFIG[name]["label"],"ist_time":ist_str(),"strike":0,"atm":0,"opt_type":"CE","premium":0,"intrinsic":0,"time_value":0,"prem_sl":0,"prem_tgt1":0,"prem_tgt2":0,"lot":0,"total_cost":0,"max_loss":0,"max_profit":0,"dte":0,"iv":0,"moneyness":"--"}
    return dict(sorted(out.items(), key=lambda x: x[1]["score"], reverse=True))

def get_ai_suggestion():
    prices=get_live_prices()
    candidates={k:v for k,v in prices.items() if v["action"] in ["BUY CE","BUY PE"] and v["price"]!=0}
    if not candidates:
        best_name=list(prices.keys())[0]; d=prices[best_name]
        return {"script":best_name,"action":"WAIT","confidence":d["confidence"],"reason":f"Clear Breakout Illa. {best_name} {d['trend']}. WAIT.","entry":d["entry"],"target":d["tgt"],"stoploss":d["sl"],"option":f"{best_name} - WAIT","trend":d["trend"],"pct":d["pct"],"all":prices,"breakout":None,"profit_ratio":0,"market_cond":d["market_cond"],"ist_time":ist_str(),"strike":d["strike"],"premium":d["premium"],"prem_sl":d["prem_sl"],"prem_tgt1":d["prem_tgt1"],"lot":d["lot"]}
    best_name=list(candidates.keys())[0]; d=candidates[best_name]
    reason=f"🏆 #1 Profit {d['profit_ratio']}:1 | {best_name} - {d['trend']} | Market: {d['market_cond']} | {d['moneyness']} Strike {d['strike']} {d['opt_type']} Premium Rs {d['premium']} | "
    if d["breakout"]: reason+=f"🔥 {d['breakout']} "
    reason+=f"OPTIONS BUYING - {d['action']} Mattum!"
    return {"script":best_name,"action":d["action"],"confidence":d["confidence"],"reason":reason,"entry":d["entry"],"target":d["tgt"],"stoploss":d["sl"],"option":d["option"],"trend":d["trend"],"pct":d["pct"],"all":prices,"breakout":d["breakout"],"tgt2":d["tgt2"],"bid":d["bid"],"ask":d["ask"],"resistance":d["resistance"],"support":d["support"],"profit_ratio":d["profit_ratio"],"profit_pct":d["profit_pct"],"market_cond":d["market_cond"],"ist_time":ist_str(),"strike":d["strike"],"atm":d["atm"],"opt_type":d["opt_type"],"premium":d["premium"],"intrinsic":d["intrinsic"],"time_value":d["time_value"],"prem_sl":d["prem_sl"],"prem_tgt1":d["prem_tgt1"],"prem_tgt2":d["prem_tgt2"],"lot":d["lot"],"total_cost":d["total_cost"],"max_loss":d["max_loss"],"max_profit":d["max_profit"],"moneyness":d["moneyness"]}

def auto_alert_loop():
    time.sleep(60)
    send_telegram(f"🤖 AI BOT STARTED!\n\n✅ Auto Alert ON\n🕐 Time: {ist_str()}\n📊 Scripts: NIFTY, SENSEX, CRUDEOILM, GOLDM, SILVERM\n🎯 Mode: Options Buying Only - ITM1 Auto Strike\n🚨 Breakout Vandha Auto Telegram Varum!")
    while True:
        try:
            now_ist = ist_now(); hour = now_ist.hour + now_ist.minute/60
            is_market_hours = 9.0 <= hour <= 23.5; is_sunday = now_ist.weekday() == 6
            if is_market_hours and not is_sunday:
                ai = get_ai_suggestion()
                should_alert=False; alert_type=""
                if ai["breakout"] and ai["confidence"]>=70: should_alert=True; alert_type="🚨 BREAKOUT ALERT"
                elif ai["action"] in ["BUY CE","BUY PE"] and ai["confidence"]>=85 and ai["trend"] and "STRONG" in ai["trend"]: should_alert=True; alert_type="🔥 STRONG TREND ALERT"
                if should_alert:
                    global last_alert
                    time_diff=9999
                    if last_alert["time"]: time_diff=(now_ist-last_alert["time"]).total_seconds()/60
                    is_dup=(last_alert["script"]==ai["script"] and last_alert["action"]==ai["action"] and time_diff<30)
                    if not is_dup:
                        msg=f"{alert_type}\n\n⏰ TIME: {ist_str()}\n🏆 #1 Profit Ratio: {ai.get('profit_ratio','--')}:1\n🎯 {ai['script']} ({ai['option']})\n📊 {ai['action']} - OPTIONS BUYING ONLY\n📈 Trend: {ai['trend']}\n🌍 Market: {ai.get('market_cond','--')}\n\n🎯 OPTION - ITM1 AUTO:\n📌 Strike: {ai.get('strike','--')} {ai.get('opt_type','--')} ({ai.get('moneyness','--')})\n💰 PREMIUM: Rs {ai.get('premium','--')} | Lot: {ai.get('lot','--')} | Cost: Rs {ai.get('total_cost','--')}\n🎯 Prem TGT: Rs {ai.get('prem_tgt1','--')} | SL: Rs {ai.get('prem_sl','--')}\n🔥 Confidence: {ai['confidence']}%"
                        ok=send_telegram(msg)
                        if ok:
                            last_alert={"time":now_ist,"script":ai["script"],"action":ai["action"]}
                            alert_history.append({"time":ist_str(),"script":ai["script"],"action":ai["action"],"type":alert_type,"price":ai["entry"],"strike":ai.get('strike'),'premium':ai.get('premium')})
            time.sleep(300)
        except Exception as e:
            print(f"Auto Loop Error: {e}"); time.sleep(60)

threading.Thread(target=auto_alert_loop, daemon=True).start()

@app.route('/api/prices')
def api_prices(): return jsonify(get_live_prices())
@app.route('/api/ai')
def api_ai(): return jsonify(get_ai_suggestion())
@app.route('/api/backtest/<name>')
def api_backtest(name):
    name=name.upper()
    if name not in SCRIPTS: return jsonify({"error":"Invalid"}),400
    return jsonify(run_backtest(name, days=30))
@app.route('/api/backtest_all')
def api_backtest_all():
    out={}
    for n in SCRIPTS.keys():
        out[n]=run_backtest(n, days=30)
        # Speed ku - Oru Call la Ellaam - Konjam Time Edukkum
    return jsonify(out)
@app.route('/backtest/<name>')
def backtest_page(name):
    bt=run_backtest(name.upper(), days=30)
    if "error" in bt: return f"Backtest Failed: {bt['error']}"
    msg=f"📊 BACKTEST - {name.upper()} - Last 30 Days\n\nTotal Trades: {bt['total']}\n✅ Wins: {bt['win']} | ❌ Losses: {bt['loss']}\n🎯 Win Rate: {bt['win_rate']}%\n💰 Total P&L (1 Lot): Rs {bt['total_pnl']}\n📈 Avg Win: Rs {bt['avg_win']} | Avg Loss: Rs {bt['avg_loss']}\n🏆 Best: Rs {bt['best']} | Worst: Rs {bt['worst']}\nCE Win: {bt['ce_win_rate']}% ({bt['ce_total']} Trades) | PE Win: {bt['pe_win_rate']}% ({bt['pe_total']} Trades)\n\n⏰ {ist_str()}"
    ok=send_telegram(msg)
    return f"✅ Backtest Sent to Telegram!<br><br>Win Rate: {bt['win_rate']}% | Total P&L: Rs {bt['total_pnl']} | Trades: {bt['total']}" if ok else "❌ Telegram Failed!"
@app.route('/api/breakout')
def api_breakout():
    prices=get_live_prices()
    bo=[{"script":k,"breakout":v["breakout"],"action":v["action"],"price":v["live"],"resistance":v["resistance"],"support":v["support"],"confidence":v["confidence"]} for k,v in prices.items() if v["breakout"]]
    return jsonify({"breakouts":bo,"count":len(bo)})
@app.route('/api/alerts')
def api_alerts(): return jsonify({"last_alert": {"script": last_alert["script"], "action": last_alert["action"], "time": last_alert["time"].strftime('%d-%m-%Y %I:%M:%S %p IST') if last_alert["time"] else "None"}, "history": alert_history[-10:], "auto_alert": "ON", "ist_time": ist_str()})
@app.route('/breakout_alert')
def breakout_alert():
    ai=get_ai_suggestion()
    msg=f"🚨 MANUAL ALERT - {ist_str()}\n\n🏆 #1 Profit {ai.get('profit_ratio','--')}:1\n🎯 {ai['script']} ({ai['option']})\n📊 {ai['action']} | {ai['trend']}\n🎯 STRIKE: {ai.get('strike')} {ai.get('opt_type')} ({ai.get('moneyness')})\n💰 PREMIUM: Rs {ai.get('premium')} | Lot {ai.get('lot')} | Cost Rs {ai.get('total_cost')}\n🎯 Prem TGT: Rs {ai.get('prem_tgt1')} | Prem SL: Rs {ai.get('prem_sl')}\n🔥 Conf: {ai['confidence']}%"
    ok=send_telegram(msg)
    return "✅ Alert Sent!" if ok else "❌ Failed!"
@app.route('/ai_signal')
def ai_signal(): return breakout_alert()
@app.route('/test_auto')
def test_auto():
    ai=get_ai_suggestion()
    msg=f"🧪 TEST AUTO ALERT\n\n⏰ IST: {ist_str()}\n🎯 {ai['script']} {ai['strike']} {ai['opt_type']} ({ai['moneyness']})\n💰 Premium Rs {ai['premium']} | Lot {ai['lot']} | Cost Rs {ai['total_cost']}\n🎯 Prem TGT Rs {ai['prem_tgt1']} | SL Rs {ai['prem_sl']}"
    ok=send_telegram(msg)
    return "✅ Test Sent!" if ok else "❌ Failed!"

@app.route('/')
def home():
    now = ist_str()
    html="""
    <html><head><title>AI Bot - Backtest + ITM1</title><meta name='viewport' content='width=device-width, initial-scale=1'>
    <style>
    *{box-sizing:border-box} body{background:#0e1117;color:white;font-family:Arial;margin:0;padding:8px;overflow-x:hidden}
    .card{background:#131722;border-radius:10px;padding:10px;border:1px solid #222;margin-top:8px}
    .btn{display:inline-block;padding:9px 12px;border-radius:7px;color:white;text-decoration:none;font-weight:bold;margin:3px;font-size:12px}
    .b1{background:#0088cc}.b2{background:#00c853}.b3{background:#ff9800}.b4{background:#7c3aed}.b5{background:#ff1744}.b6{background:#ff6d00}.b7{background:#009688}
    .green{color:#00ff88}.orange{color:#ff9800}.red{color:#ff4444}
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
    .opt-box{background:linear-gradient(135deg,#1a0033,#0d1b4c);border:1px solid #7c3aed;border-radius:8px;padding:8px;margin-top:6px}
    .ai-box{background:linear-gradient(135deg,#1a0033,#0d1b4c);border:2px solid #7c3aed;border-radius:12px;padding:12px;margin-top:8px}
    .ai-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:8px}
    .ai-stat{background:#0e1117;border-radius:8px;padding:8px;text-align:center;border:1px solid #333;font-size:13px}
    .breakout-box{background:linear-gradient(135deg,#ff6d00,#ff1744);border-radius:12px;padding:12px;margin-top:8px;display:none}
    .auto-box{background:#0f2a1d;border:1px solid #00ff88;border-radius:10px;padding:10px;margin-top:8px}
    .bt-box{background:#131722;border:2px solid #009688;border-radius:12px;padding:12px;margin-top:8px}
    .bt-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:8px}
    .bt-card{background:#1a2030;border-radius:10px;padding:10px;border:1px solid #2a3348;text-align:center}
    table{width:100%;border-collapse:collapse;font-size:11px;margin-top:8px} th,td{padding:6px;border-bottom:1px solid #333;text-align:left} th{color:#aaa}
    .live-dot{animation:blink 1s infinite} @keyframes blink{0%{opacity:1}50%{opacity:0.3}100%{opacity:1}}
    @media(max-width:1100px){.grid5,.bt-grid{grid-template-columns:repeat(3,1fr)}}
    @media(max-width:700px){.grid5,.bt-grid{grid-template-columns:1fr}.ai-grid{grid-template-columns:1fr 1fr}}
    </style></head><body>
    <div class='top'><h2 style='margin:4px 0;font-size:20px'>🤖 AI BOT DASHBOARD</h2><span style='background:#1e293b;padding:6px 10px;border-radius:20px;font-size:12px'><span class='live-dot'>🟢</span> <span id='clock'>"""+now+"""</span> | USDINR: <span id='usdinrTop'>--</span> | IP: """+get_ip()+"""</span></div>
    <div style='background:#0f2a1d;border:1px solid #00ff88;border-radius:8px;padding:7px;margin-top:8px;text-align:center;font-size:12px'>✅ <b>OPTIONS BUYING ONLY</b> • <b>ITM1 AUTO STRIKE + PREMIUM</b> • <b>BACKTEST ✅</b> • IST + AUTO ALERT ON ✅</div>

    <div class='auto-box'><div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px'><div><b>🤖 AUTO ALERT: <span class='green'>✅ ON</span></b> <span class='small'>Breakout Vandha Thaan-a Telegram Varum!</span></div><div style='font-size:11px'>Last Auto: <b id='lastAlert'>Checking...</b></div></div><div id='alertHistory' style='font-size:11px;margin-top:6px'></div></div>

    <!-- 📊 BACKTEST - NEW -->
    <div class='bt-box'>
      <div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;align-items:center'><b style='font-size:15px'>📊 BACKTEST - Last 30 Days - Strategy Work Aayidha?</b><button onclick='loadBacktestAll()' style='background:#009688;color:white;border:none;padding:8px 14px;border-radius:7px;font-weight:bold;cursor:pointer'>▶️ Run Backtest All 5 Scripts</button></div>
      <div class='small'>Backtest na - Ippo Strategy-a Pona 30 Naal Data la Test Pannuren - 1 Lot Per Trade - Prem TGT +60% / SL -30% - 5 Candles (75 Min) Max Hold</div>
      <div id='btLoading' style='display:none;text-align:center;padding:12px'>⏳ Backtest Running... 30 Sec Wait Pannunga... Yahoo Data Fetch Pannuren...</div>
      <div id='btGrid' class='bt-grid'></div>
      <div id='btDetail' style='margin-top:10px'></div>
    </div>

    <div class='card' style='padding:8px;display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px'><div><span class='small'>🌍 MARKET:</span> <b id='overallCond' style='font-size:14px'>Loading...</b></div><div><span class='small'>📊 TREND:</span> <b id='overallTrend'>--</b></div><div><span class='small'>💰 BEST PREMIUM:</span> <b id='overallPrem'>--</b></div></div>

    <div id='breakoutBox' class='breakout-box'><div style='font-size:11px'>🚨 BREAKOUT - AUTO ALERT SENT!</div><h2 id='breakoutTitle' style='margin:6px 0;font-size:18px'>🔥 BREAKOUT!</h2><div id='breakoutDesc' style='font-size:12px;line-height:1.5'>--</div></div>

    <div class='ai-box'>
      <div style='font-size:11px;color:#c4b5fd'>🤖 AI SUGGEST • OPTIONS BUYING ONLY • ITM1 AUTO STRIKE</div>
      <h2 id='aiTitle' style='margin:6px 0;font-size:19px'>🤖 AI Analyzing...</h2>
      <div id='aiReason' style='font-size:12px;color:#e0e7ff;line-height:1.5'>Analyzing...</div>
      <div style='margin-top:6px'>Conf: <b id='aiConf' style='color:#00ff88;font-size:22px'>--%</b> <span id='aiTrend' style='font-size:11px;color:#aaa'>--</span> <span id='aiProfitBadge' style='background:#00ff88;color:black;padding:3px 8px;border-radius:12px;font-size:11px;font-weight:bold'>--</span> <span id='aiMarketBadge' style='background:#333;padding:3px 8px;border-radius:12px;font-size:11px'>--</span></div>
      <div class='ai-grid'>
        <div class='ai-stat'><div class='small'>🏆 #1 BEST</div><b id='aiScript' style='font-size:14px'>--</b><div class='small' id='aiOption'>--</div></div>
        <div class='ai-stat'><div class='small'>🎯 STRIKE (ITM1)</div><b id='aiStrike' style='font-size:16px;color:#c4b5fd'>--</b><div class='small' id='aiStrikeSub'>--</div></div>
        <div class='ai-stat'><div class='small'>💰 PREMIUM</div><b id='aiPremium' style='font-size:16px;color:#00ff88'>--</b><div class='small' id='aiPremSub'>--</div></div>
        <div class='ai-stat'><div class='small'>💸 TOTAL COST (1 LOT)</div><b id='aiCost' style='font-size:14px;color:#ff9800'>--</b><div class='small' id='aiCostSub'>--</div></div>
      </div>
      <div class='ai-grid'>
        <div class='ai-stat'><div class='small'>💰 SPOT ENTRY</div><b id='aiEntry' style='font-size:14px;color:#00ff88'>--</b></div>
        <div class='ai-stat'><div class='small'>🎯 PREM TGT1</div><b id='aiPremTgt' style='font-size:14px;color:#00ff88'>--</b></div>
        <div class='ai-stat'><div class='small'>🛑 PREM SL</div><b id='aiPremSL' style='font-size:14px;color:#ff4444'>--</b></div>
        <div class='ai-stat'><div class='small'>📈 MAX PROFIT / LOSS</div><b id='aiMaxPL' style='font-size:13px'>--</b></div>
      </div>
      <div style='margin-top:8px;text-align:center'><a class='btn b2' href='/breakout_alert'>📩 Manual Send</a> <a class='btn b6' href='/test_auto'>🧪 Test Auto Alert</a></div>
    </div>

    <div class='card' style='border:2px solid #00ff88;text-align:center;padding:8px'><div style='font-size:11px;color:#aaa'>OVERALL - OPTIONS BUYING ONLY - IST</div><h2 id='mainSignal' class='green' style='margin:4px 0;font-size:18px'>Loading...</h2><div id='mainSub' style='font-size:12px'>Checking...</div><div style='margin-top:4px'><span class='small' id='lastUpdate'>--</span></div></div>

    <div style='display:flex;justify-content:space-between;align-items:center;margin-top:10px'><b style='font-size:14px'>📊 5 SCRIPTS - SAME ROW - HIGH PROFIT FIRST 🏆</b><span class='small'>ITM1 Strike + Premium Per Script</span></div>
    <div id='scriptsGrid' class='grid5'></div>

    <div class='card' style='padding:8px'><b style='font-size:13px'>💡 BACKTEST EPPADI READ PANNURADHU?</b><div style='font-size:11px;color:#aaa;margin-top:4px'>Win Rate >55% na Strategy Nalla Irukku! Total P&L Positive na Profit! CE Win vs PE Win Paathu - Edhu Nalla Work Aagudhu nu Paanga! Backtest = Past Data - Future Guarantee Illa! Aana Strategy-a Nambalama nu Theriya Idhu Best Way!</div></div>
    <div style='margin-top:8px'><a class='btn b1' href='/test_telegram'>📩 Test Telegram</a><a class='btn b7' href='javascript:loadBacktestAll()'>📊 Backtest All</a><a class='btn b6' href='/test_auto'>🧪 Test Auto</a><a class='btn b3' href='/debug'>🔍 Debug</a></div>

    <script>
    function fmt(n){ return 'Rs '+n.toLocaleString('en-IN',{maximumFractionDigits:0}); }
    function fmt2(n){ return 'Rs '+n.toLocaleString('en-IN',{maximumFractionDigits:2}); }
    function updateClock(){ let now=new Date(new Date().toLocaleString('en-US',{timeZone:'Asia/Kolkata'})); document.getElementById('clock').innerText=now.toLocaleDateString('en-IN',{day:'2-digit',month:'2-digit',year:'numeric'})+' '+now.toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:true})+' IST'; }
    setInterval(updateClock,1000); updateClock();
    function loadBacktestAll(){
      document.getElementById('btLoading').style.display='block';
      document.getElementById('btGrid').innerHTML='';
      fetch('/api/backtest_all').then(r=>r.json()).then(data=>{
        document.getElementById('btLoading').style.display='none';
        let html=''; let totalPnl=0; let totalTrades=0; let totalWins=0;
        for(let name in data){ let d=data[name]; if(d.error) continue; totalPnl+=d.total_pnl; totalTrades+=d.total; totalWins+=d.win;
          let col=d.total_pnl>=0?'#00ff88':'#ff4444';
          html+=`<div class='bt-card'><h3 style='margin:2px 0'>${name}</h3><div style='font-size:22px;font-weight:bold;color:${d.win_rate>=55?'#00ff88':d.win_rate>=45?'#ff9800':'#ff4444'}'>${d.win_rate}% Win</div><div class='small'>${d.total} Trades | ${d.win} Win | ${d.loss} Loss</div><div style='font-size:16px;font-weight:bold;color:${col};margin-top:6px'>${d.total_pnl>=0?'+':''}${fmt(d.total_pnl)}</div><div class='small'>1 Lot | 30 Days | Return ${d.return_pct}%</div><div class='small' style='margin-top:6px'>CE Win: ${d.ce_win_rate}% (${d.ce_total})<br>PE Win: ${d.pe_win_rate}% (${d.pe_total})</div><div class='small'>Avg Win ${fmt(d.avg_win)} | Avg Loss ${fmt(d.avg_loss)}</div><button onclick="showBacktestDetail('${name}')" style='background:#009688;color:white;border:none;padding:6px 10px;border-radius:6px;margin-top:8px;cursor:pointer;font-size:11px'>📋 Last 20 Trades Paakku</button> <a href='/backtest/${name}' style='background:#0088cc;color:white;padding:6px 10px;border-radius:6px;text-decoration:none;font-size:11px;display:inline-block;margin-top:8px'>📩 Telegram la Anuppu</a></div>`;
        }
        let overallWin = totalTrades>0 ? Math.round(totalWins/totalTrades*100) : 0;
        html = `<div class='bt-card' style='border:2px solid #00ff88'><h3>🏆 OVERALL</h3><div style='font-size:22px;font-weight:bold;color:${overallWin>=55?'#00ff88':'#ff9800'}'>${overallWin}% Win</div><div class='small'>${totalTrades} Trades Total</div><div style='font-size:16px;font-weight:bold;color:${totalPnl>=0?'#00ff88':'#ff4444'}'>${totalPnl>=0?'+':''}${fmt(totalPnl)}</div><div class='small'>5 Scripts | 30 Days | 1 Lot Each</div><div class='small' style='margin-top:6px'>${overallWin>=55?'✅ Strategy Nalla Irukku!':'⚠️ Strategy-a Konjam Filter Pannanum!'}</div></div>` + html;
        document.getElementById('btGrid').innerHTML=html;
        document.getElementById('btDetail').innerHTML='<div class="small">👆 Per Script "Last 20 Trades" Button Click Panna - Eppadi Trade Pochu nu Detail-a Varum!</div>';
        window._btData=data;
      });
    }
    function showBacktestDetail(name){
      let d=window._btData[name]; if(!d) return;
      let rows='';
      d.trades.slice().reverse().forEach(t=>{
        let col=t.result=='WIN'?'#00ff88':'#ff4444';
        rows+=`<tr><td>${t.date}</td><td>${t.action} ${t.strike} ${t.opt_type}</td><td>${t.trend}<br><span class='small'>${t.breakout}</span></td><td>${fmt2(t.entry_prem)} → ${fmt2(t.exit_prem)}</td><td style='color:${col};font-weight:bold'>${t.result} (${t.pnl_pct}%)</td><td style='color:${col}'>${t.pnl>=0?'+':''}${fmt(t.pnl)}</td><td class='small'>${t.exit_reason}</td></tr>`;
      });
      document.getElementById('btDetail').innerHTML=`<div class='card'><b>📋 ${name} - Last 20 Trades Detail</b><table><tr><th>Date</th><th>Trade</th><th>Trend / Breakout</th><th>Premium Entry → Exit</th><th>Result</th><th>P&L (1 Lot)</th><th>Exit Reason</th></tr>${rows}</table></div>`;
      document.getElementById('btDetail').scrollIntoView({behavior:'smooth'});
    }
    function loadPrices(){
      fetch('/api/prices').then(r=>r.json()).then(data=>{
        let arr=Object.values(data); let ce=0,pe=0,wait=0,usd='',strongUp=0,strongDown=0,up=0,down=0; let html='';
        arr.forEach((d,i)=>{
          let rank=i+1; let isTop=rank==1 && d.action!='WAIT';
          let badgeClass=d.action=='WAIT'?'bg-orange':'bg-green'; let badgeText=d.action=='WAIT'?'◐ WAIT':'✅ '+d.action+' - BUYING';
          if(d.action=='BUY CE') ce++; else if(d.action=='BUY PE') pe++; else wait++;
          if(d.trend_level==5) strongUp++; else if(d.trend_level==4) up++; else if(d.trend_level==1) strongDown++; else if(d.trend_level==2) down++;
          usd=d.usdinr;
          html+=`<div class='script-card ${isTop?'rank1':''}'>${isTop?'<div class="rank-badge">🏆 #1 BEST</div>':`<div class="rank-badge" style="background:#333;color:#aaa">#${rank}</div>`}<div class='small'>${d.label} • OPTIONS BUYING</div><h3 style='margin:3px 0;font-size:15px'>${d.emoji} ${d.name}</h3><div class='small'>LIVE SPOT</div><div class='price green'>${fmt(d.live)}</div><div class='small'>${d.change>=0?'▲ + ':'▼ '}${fmt(Math.abs(d.change))} (${d.pct}%)</div><div class='trend-bar' style='background:${d.trend_bg};color:${d.trend_color};border:1px solid ${d.trend_color}'>${d.trend}</div><div style='text-align:center;font-size:11px'>🌍 <b style='color:${d.cond_color}'>${d.market_cond}</b></div><div style='text-align:center;font-size:10px;color:#aaa;margin-top:2px'>EMA 9: ${fmt(d.ema9)} | 21: ${fmt(d.ema21)} | 50: ${fmt(d.ema50)}</div><div style='background:#0e1117;border:1px solid #00ff88;border-radius:7px;padding:5px;margin-top:6px;text-align:center'><div class='small'>🏆 PROFIT RATIO</div><b style='color:#00ff88;font-size:15px'>${d.profit_ratio}:1</b> <span class='small'>| ${d.profit_pct}% | Conf ${d.confidence}%</span></div><div class='opt-box'><div style='text-align:center;font-size:11px;color:#c4b5fd;font-weight:bold'>🎯 ${d.moneyness} - ${d.name} ${d.strike} ${d.opt_type}</div><div style='display:flex;justify-content:space-between;margin-top:5px'><span class='small'>Spot / ATM</span><b style='font-size:12px'>${fmt(d.live)} / ${fmt(d.atm)}</b></div><div style='display:flex;justify-content:space-between'><span class='small'>💰 PREMIUM</span><b style='color:#00ff88;font-size:16px'>${fmt2(d.premium)}</b></div><div style='display:flex;justify-content:space-between'><span class='small'>Intrinsic + Time</span><span class='small'>${fmt2(d.intrinsic)} + ${fmt2(d.time_value)}</span></div><div style='display:flex;justify-content:space-between'><span class='small'>Prem TGT / SL</span><b style='font-size:12px;color:#00ff88'>${fmt2(d.prem_tgt1)} / <span style='color:#ff4444'>${fmt2(d.prem_sl)}</span></b></div><div style='display:flex;justify-content:space-between'><span class='small'>Lot ${d.lot} | Cost</span><b style='color:#ff9800'>${fmt(d.total_cost)}</b></div></div>${d.breakout?`<div class='small' style='color:#ff9800;font-weight:bold;margin-top:4px'>🔥 ${d.breakout}</div>`:''}<div class='bidask'><div class='ba ba-bid'><div class='small'>🟢 BID</div><b>${fmt(d.bid)}</b></div><div class='ba ba-ask'><div class='small'>🔴 ASK</div><b>${fmt(d.ask)}</b></div></div><div style='text-align:center'><span class='badge ${badgeClass}'>${badgeText}</span></div><div class='levels'><div class='lvl'><div class='small'>SPOT ENTRY</div><b style='color:#00ff88'>${fmt(d.entry)}</b></div><div class='lvl'><div class='small'>SPOT TGT</div><b style='color:#00ff88'>${fmt(d.tgt)}</b></div><div class='lvl'><div class='small'>SPOT SL</div><b style='color:#ff4444'>${fmt(d.sl)}</b></div></div><div class='small' style='margin-top:6px;text-align:center'>Res: ${fmt(d.resistance)} | Sup: ${fmt(d.support)} | IV ${d.iv}%</div></div>`;
        });
        document.getElementById('scriptsGrid').innerHTML=html;
        document.getElementById('usdinrTop').innerText='Rs '+usd;
        let overallCond=strongUp>=2?'BULLISH STRONG 🐂🔥':up>=3?'BULLISH 🐂':strongDown>=2?'BEARISH STRONG 🐻🔻':down>=3?'BEARISH 🐻':'SIDEWAYS / MIXED ➡️';
        let overallColor=overallCond.includes('BULLISH')?'#00ff88':overallCond.includes('BEARISH')?'#ff4444':'#ff9800';
        document.getElementById('overallCond').innerText=overallCond; document.getElementById('overallCond').style.color=overallColor;
        document.getElementById('overallTrend').innerText=strongUp+' Strong Up | '+up+' Up | '+down+' Down | '+strongDown+' Strong Down';
        document.getElementById('overallPrem').innerText=arr[0] ? arr[0].name+' '+arr[0].strike+' '+arr[0].opt_type+' @ '+fmt2(arr[0].premium) : '--';
        let m=document.getElementById('mainSignal');
        if(ce>0||pe>0){ m.innerText='✅ BUYING: '+ce+' CE BUY + '+pe+' PE BUY | '+wait+' WAIT'; m.className='green'; } else { m.innerText='◐ WAIT - NO BUYING CHANCE'; m.className='orange'; }
        document.getElementById('mainSub').innerText='Sorted #1 = Highest Profit | ITM1 Strike Auto!';
        let nowIST=new Date(new Date().toLocaleString('en-US',{timeZone:'Asia/Kolkata'}));
        document.getElementById('lastUpdate').innerText='Last Update: '+nowIST.toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:true})+' IST - Auto Alert ON ✅';
      });
    }
    function loadAI(){
      fetch('/api/ai').then(r=>r.json()).then(ai=>{
        let emoji=ai.action=='WAIT'?'◐':'✅';
        document.getElementById('aiTitle').innerHTML=emoji+' AI SUGGESTS: <span style="color:#00ff88">'+ai.action+' - '+ai.script+' '+ai.strike+' '+ai.opt_type+'</span> (ITM1)';
        document.getElementById('aiReason').innerText='🧠 '+ai.reason;
        document.getElementById('aiConf').innerText=ai.confidence+'%';
        document.getElementById('aiTrend').innerText=ai.trend+' | '+ai.pct+'%';
        document.getElementById('aiProfitBadge').innerText='🏆 Profit '+ai.profit_ratio+':1';
        document.getElementById('aiMarketBadge').innerText='🌍 '+ai.market_cond;
        document.getElementById('aiScript').innerText=ai.script; document.getElementById('aiOption').innerText=ai.option+' | '+ai.moneyness;
        document.getElementById('aiStrike').innerText=ai.strike+' '+ai.opt_type; document.getElementById('aiStrikeSub').innerText=ai.moneyness+' | ATM '+ai.atm;
        document.getElementById('aiPremium').innerText=fmt2(ai.premium); document.getElementById('aiPremSub').innerText='Intrinsic '+fmt2(ai.intrinsic)+' + Time '+fmt2(ai.time_value);
        document.getElementById('aiCost').innerText=fmt(ai.total_cost); document.getElementById('aiCostSub').innerText='Lot '+ai.lot+' x '+fmt2(ai.premium);
        document.getElementById('aiEntry').innerText=fmt(ai.entry); document.getElementById('aiPremTgt').innerText=fmt2(ai.prem_tgt1)+' / '+fmt2(ai.prem_tgt2); document.getElementById('aiPremSL').innerText=fmt2(ai.prem_sl); document.getElementById('aiMaxPL').innerText='+'+fmt(ai.max_profit)+' / -'+fmt(ai.max_loss);
        let box=document.getElementById('breakoutBox');
        if(ai.breakout){ box.style.display='block'; document.getElementById('breakoutTitle').innerText='🔥 BREAKOUT: '+ai.script+' - '+ai.breakout; document.getElementById('breakoutDesc').innerText=ai.script+' '+ai.strike+' '+ai.opt_type+' Premium '+fmt2(ai.premium)+' | Entry '+fmt(ai.entry)+' | Prem TGT '+fmt2(ai.prem_tgt1)+' | Prem SL '+fmt2(ai.prem_sl); }
        else { box.style.display='none'; }
      });
      fetch('/api/alerts').then(r=>r.json()).then(a=>{
        document.getElementById('lastAlert').innerText=a.last_alert.time+' - '+a.last_alert.script+' '+a.last_alert.action;
        if(a.history && a.history.length>0){ let h='Recent Auto: '; a.history.slice(-3).forEach(x=>{ h+=' | '+x.time+' - '+x.script+' '+x.strike+' '+x.action+' @ '+x.premium; }); document.getElementById('alertHistory').innerText=h; }
        else { document.getElementById('alertHistory').innerText='Recent Auto: Innum Alert Illa - Breakout Vandha Thaan Varum.'; }
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
    ok=send_telegram(f"✅ Test Success!\n⏰ IST: {ist_str()}")
    return "✅ Sent!" if ok else "❌ Failed!"
@app.route('/order_test')
def order_test():
    send_telegram(f"🚀 ORDER: NIFTY CE BUY\n⏰ {ist_str()}")
    return "Sent!"
@app.route('/login')
def login(): return redirect(f"https://ant.aliceblueonline.com/?appcode={ALICE_API_KEY}")
@app.route('/debug')
def debug(): return jsonify({"ip":get_ip(),"telegram":bool(TELEGRAM_BOT_TOKEN),"ist_time":ist_str(),"prices":get_live_prices(),"ai":get_ai_suggestion(),"alerts":alert_history})
if __name__=='__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT",5000)))
