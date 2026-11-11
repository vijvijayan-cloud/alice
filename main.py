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
def ist_short(): return ist_now().strftime('%d-%m %I:%M %p')
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
    cfg = CONFIG[name]; step = cfg["strike_step"]; iv = cfg["iv"]/100
    dte = 4 if name in ["NIFTY","SENSEX"] else 12; t = dte/365.0
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
    trail_levels = [
        {"trigger": round(premium*1.20,2), "new_sl": round(premium*1.00,2), "label": "Trail 1: +20% -> SL = Entry"},
        {"trigger": round(premium*1.40,2), "new_sl": round(premium*1.20,2), "label": "Trail 2: +40% -> SL = +20% Lock"},
        {"trigger": round(premium*1.60,2), "new_sl": round(premium*1.40,2), "label": "Trail 3: +60% -> SL = +40% Lock"},
        {"trigger": round(premium*2.00,2), "new_sl": round(premium*1.60,2), "label": "Trail 4: +100% -> SL = +60% Lock"},
    ]
    return {"strike": strike, "atm": atm, "opt_type": opt_type, "premium": premium, "intrinsic": round(intrinsic,2), "time_value": round(time_value,2), "prem_sl": prem_sl, "prem_tgt1": prem_tgt1, "prem_tgt2": prem_tgt2, "lot": lot, "total_cost": total_cost, "max_loss": max_loss, "max_profit": max_profit, "dte": dte, "iv": cfg["iv"], "moneyness": "ITM1" if action in ["BUY CE","BUY PE"] else "ATM", "trail_levels": trail_levels}
def calc_trailing(entry_prem, current_prem, initial_sl):
    if current_prem >= entry_prem*2.00: return {"trail_sl": round(entry_prem*1.60,2), "stage": "Trail 4 🔥", "locked_profit": round((entry_prem*1.60-entry_prem),2), "locked_pct": 60, "status": "TGT2 Cross!"}
    elif current_prem >= entry_prem*1.60: return {"trail_sl": round(entry_prem*1.40,2), "stage": "Trail 3 ✅", "locked_profit": round((entry_prem*1.40-entry_prem),2), "locked_pct": 40, "status": "TGT1 Hit!"}
    elif current_prem >= entry_prem*1.40: return {"trail_sl": round(entry_prem*1.20,2), "stage": "Trail 2 ✅", "locked_profit": round((entry_prem*1.20-entry_prem),2), "locked_pct": 20, "status": "Profit Lock 20%!"}
    elif current_prem >= entry_prem*1.20: return {"trail_sl": round(entry_prem*1.00,2), "stage": "Trail 1 ✅", "locked_profit": 0, "locked_pct": 0, "status": "Breakeven!"}
    else: return {"trail_sl": initial_sl, "stage": "No Trail Yet", "locked_profit": round((initial_sl-entry_prem),2), "locked_pct": -30, "status": "Initial SL"}

# === CALLS HISTORY - NEW ===
calls_history = []
# Format: {id, time, script, action, strike, opt_type, entry_spot, entry_prem, tgt, sl, tgt2, lot, status, exit_prem, exit_time, points, pnl, pnl_pct, trail_sl, max_prem, source}
call_id_counter = [1]
def add_call(ai, source="AUTO"):
    cid = call_id_counter[0]; call_id_counter[0]+=1
    c = {
        "id": cid, "time": ist_short(), "full_time": ist_str(),
        "script": ai["script"], "action": ai["action"], "strike": ai.get("strike",0), "opt_type": ai.get("opt_type",""),
        "moneyness": ai.get("moneyness","ITM1"), "entry_spot": ai.get("entry",0),
        "entry_prem": ai.get("premium",0), "tgt": ai.get("prem_tgt1",0), "tgt2": ai.get("prem_tgt2",0), "sl": ai.get("prem_sl",0),
        "lot": ai.get("lot",1), "status": "RUNNING", "exit_prem": None, "exit_time": "-", "points": 0, "pnl": 0, "pnl_pct": 0,
        "current_prem": ai.get("premium",0), "trail_sl": ai.get("prem_sl",0), "max_prem": ai.get("premium",0),
        "source": source, "trend": ai.get("trend",""), "confidence": ai.get("confidence",0)
    }
    calls_history.insert(0, c)
    if len(calls_history) > 50: calls_history.pop()
    return c

def update_calls_history(live_prices):
    # Ella RUNNING Call-um - Ippo Price vachu TGT/SL Hit Aacha Check Pannurom
    for c in calls_history:
        if c["status"] != "RUNNING": continue
        live = live_prices.get(c["script"])
        if not live or live["live"]==0: continue
        # Premium Estimate - Spot Move vachu
        entry_spot = c["entry_spot"]; cur_spot = live["live"]
        if entry_spot==0: continue
        spot_move = (cur_spot - entry_spot)/entry_spot*100
        if c["action"]=="BUY CE": prem_move = spot_move*8
        else: prem_move = -spot_move*8
        est_prem = max(c["entry_prem"]*(1+prem_move/100), 1)
        c["current_prem"] = round(est_prem,2)
        c["max_prem"] = max(c["max_prem"], est_prem)
        # Trailing Update
        tr = calc_trailing(c["entry_prem"], est_prem, c["sl"])
        if tr["trail_sl"] > c["trail_sl"]: c["trail_sl"] = tr["trail_sl"]
        # TGT2 Hit?
        if est_prem >= c["tgt2"]:
            c["status"]="TGT2 DONE 🎯🎯"; c["exit_prem"]=c["tgt2"]; c["exit_time"]=ist_short()
            c["points"]=round(c["tgt2"]-c["entry_prem"],2); c["pnl"]=round(c["points"]*c["lot"],2); c["pnl_pct"]=round(c["points"]/c["entry_prem"]*100,1)
            send_telegram(f"🎯🎯 TGT2 DONE!\n\n⏰ {ist_str()}\n🎯 {c['script']} {c['strike']} {c['opt_type']} {c['action']}\n💰 Entry: Rs {c['entry_prem']} → Exit: Rs {c['tgt2']}\n📈 Points: +{c['points']} Pts (+{c['pnl_pct']}%)\n💸 P&L (1 Lot): +Rs {c['pnl']}\n⏱️ Call Time: {c['time']}")
        elif est_prem >= c["tgt"]:
            c["status"]="TGT DONE ✅"; c["exit_prem"]=c["tgt"]; c["exit_time"]=ist_short()
            c["points"]=round(c["tgt"]-c["entry_prem"],2); c["pnl"]=round(c["points"]*c["lot"],2); c["pnl_pct"]=round(c["points"]/c["entry_prem"]*100,1)
            send_telegram(f"🎯 TGT DONE!\n\n⏰ {ist_str()}\n🎯 {c['script']} {c['strike']} {c['opt_type']} {c['action']}\n💰 Entry: Rs {c['entry_prem']} → TGT: Rs {c['tgt']}\n📈 Points: +{c['points']} Pts (+{c['pnl_pct']}%)\n💸 P&L (1 Lot): +Rs {c['pnl']}\n⏱️ Call Time: {c['time']}\n💡 Trail SL: Rs {c['trail_sl']} - 50% Hold Panna Innum Profit Varalam!")
        elif est_prem <= c["trail_sl"]:
            # Trailing SL Hit na - Profit/BE, Initial SL Hit na - Loss
            if c["trail_sl"] > c["entry_prem"]:
                c["status"]="TRAIL SL HIT 🛡️"; c["exit_prem"]=c["trail_sl"]; c["exit_time"]=ist_short()
                c["points"]=round(c["trail_sl"]-c["entry_prem"],2); c["pnl"]=round(c["points"]*c["lot"],2); c["pnl_pct"]=round(c["points"]/c["entry_prem"]*100,1)
                send_telegram(f"🛡️ TRAILING SL HIT - Profit Lock!\n\n⏰ {ist_str()}\n🎯 {c['script']} {c['strike']} {c['opt_type']}\n💰 Entry: Rs {c['entry_prem']} → Trail SL: Rs {c['trail_sl']}\n📈 Points: +{c['points']} Pts (+{c['pnl_pct']}%)\n💸 P&L: +Rs {c['pnl']}")
            elif c["trail_sl"] == c["entry_prem"]:
                c["status"]="BREAKEVEN ➖"; c["exit_prem"]=c["trail_sl"]; c["exit_time"]=ist_short()
                c["points"]=0; c["pnl"]=0; c["pnl_pct"]=0
                send_telegram(f"➖ BREAKEVEN - No Loss!\n\n⏰ {ist_str()}\n🎯 {c['script']} {c['strike']} {c['opt_type']}\n💰 Entry Rs {c['entry_prem']} = Exit Rs {c['trail_sl']} - Trailing Saved Loss!")
            else:
                c["status"]="SL HIT ❌"; c["exit_prem"]=c["sl"]; c["exit_time"]=ist_short()
                c["points"]=round(c["sl"]-c["entry_prem"],2); c["pnl"]=round(c["points"]*c["lot"],2); c["pnl_pct"]=round(c["points"]/c["entry_prem"]*100,1)
                send_telegram(f"❌ SL HIT!\n\n⏰ {ist_str()}\n🎯 {c['script']} {c['strike']} {c['opt_type']} {c['action']}\n💰 Entry: Rs {c['entry_prem']} → SL: Rs {c['sl']}\n📉 Points: {c['points']} Pts ({c['pnl_pct']}%)\n💸 P&L (1 Lot): Rs {c['pnl']}\n⏱️ Call Time: {c['time']}")
        else:
            # Innum Running - Points Update
            c["points"]=round(est_prem-c["entry_prem"],2); c["pnl"]=round(c["points"]*c["lot"],2); c["pnl_pct"]=round(c["points"]/c["entry_prem"]*100,1)
    return calls_history

def get_calls_summary():
    done = [c for c in calls_history if c["status"] not in ["RUNNING"]]
    wins = [c for c in calls_history if "TGT" in c["status"] or "TRAIL" in c["status"]]
    losses = [c for c in calls_history if "SL HIT" in c["status"]]
    running = [c for c in calls_history if c["status"]=="RUNNING"]
    total_pnl = round(sum(c["pnl"] for c in calls_history if c["status"]!="RUNNING"),2)
    total_points = round(sum(c["points"] for c in calls_history if c["status"]!="RUNNING"),2)
    win_rate = round(len(wins)/len(done)*100,1) if done else 0
    return {"total_calls": len(calls_history), "done": len(done), "running": len(running), "wins": len(wins), "losses": len(losses), "win_rate": win_rate, "total_pnl": total_pnl, "total_points": total_points}

def run_backtest(name, days=30, use_trailing=True):
    usdinr = get_usdinr(); sym = SCRIPTS[name]
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=1mo&interval=15m"
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=12).json()
        res = r["chart"]["result"][0]; ts = res["timestamp"]; q = res["indicators"]["quote"][0]
        candles=[]
        for i,t in enumerate(ts):
            if q["close"][i] is None: continue
            candles.append({"time": datetime.fromtimestamp(t, IST).strftime('%d-%m %I:%M %p'), "close": convert_price(name, q["close"][i], usdinr), "high": convert_price(name, q["high"][i], usdinr), "low": convert_price(name, q["low"][i], usdinr)})
        if len(candles)<60: return {"error":"Data Illa"}
    except Exception as e: return {"error": str(e)}
    trades=[]; last_trade_end=-10
    for i in range(25, len(candles)-5):
        if i < last_trade_end: continue
        window = candles[max(0,i-25):i]; closes=[c["close"] for c in window]; highs=[c["high"] for c in window]; lows=[c["low"] for c in window]
        def ema(data,p):
            k=2/(p+1); e=data[0]
            for v in data[1:]: e=v*k+e*(1-k)
            return e
        ema9=ema(closes,9); ema21=ema(closes,21); ema50=ema(closes,50) if len(closes)>=50 else ema21
        price=candles[i]["close"]; prev=candles[i-1]["close"]; pct=(price-prev)/prev*100 if prev else 0
        res20=max(highs[-20:]); sup20=min(lows[-20:]); prev_ema9=ema(closes[:-1],9); prev_ema21=ema(closes[:-1],21)
        breakout=None; btype=""
        if price>res20: breakout="BREAKOUT UP"; btype="UP"
        elif price<sup20: breakout="BREAKDOWN"; btype="DOWN"
        elif prev_ema9<=prev_ema21 and ema9>ema21: breakout="EMA CROSS UP"; btype="UP"
        elif prev_ema9>=prev_ema21 and ema9<ema21: breakout="EMA CROSS DOWN"; btype="DOWN"
        if ema9>ema21>ema50 and price>ema9 and pct>0.30: trend="STRONG UPTREND"; level=5
        elif ema9>ema21 and price>ema9: trend="UPTREND"; level=4
        elif ema9<ema21<ema50 and price<ema9 and pct<-0.30: trend="STRONG DOWNTREND"; level=1
        elif ema9<ema21 and price<ema9: trend="DOWNTREND"; level=2
        else: trend="SIDEWAYS"; level=3
        if name=="GOLDM" and level in [1,2]: continue
        if (level==5 and btype=="UP") or (level==5 and pct>0.5): action="BUY CE"
        elif (level==1 and btype=="DOWN") or (level==1 and pct<-0.5): action="BUY PE"
        elif level==4 and breakout and btype=="UP": action="BUY CE"
        elif level==2 and breakout and btype=="DOWN": action="BUY PE"
        else: continue
        entry_spot=price; opt=calc_option(name, entry_spot, action); entry_prem=opt["premium"]; sl_prem=opt["prem_sl"]; tgt_prem=opt["prem_tgt1"]
        result="OPEN"; exit_prem=entry_prem; exit_reason="Time Exit"; trail_used="No Trail"; max_prem=entry_prem; cur_sl=sl_prem; last_est=entry_prem; hit_trail=False
        for j in range(i+1, min(i+10, len(candles))):
            fut_price=candles[j]["close"]; spot_move=(fut_price-entry_spot)/entry_spot*100
            if action=="BUY CE": prem_move=spot_move*8
            else: prem_move=-spot_move*8
            est_prem=max(entry_prem*(1+prem_move/100),1); last_est=est_prem; max_prem=max(max_prem, est_prem)
            if use_trailing:
                tr=calc_trailing(entry_prem, est_prem, sl_prem)
                if tr["trail_sl"] > cur_sl: cur_sl=tr["trail_sl"]; trail_used=tr["stage"]; hit_trail=True
            if est_prem <= cur_sl:
                if cur_sl > entry_prem: result="WIN"
                elif cur_sl == entry_prem: result="BREAKEVEN"
                else: result="LOSS"
                exit_prem=cur_sl; exit_reason=f"{'Trailing' if hit_trail else 'Initial'} SL Hit @ {j-i} - {trail_used}"; break
            if est_prem >= opt["prem_tgt2"]: result="WIN"; exit_prem=opt["prem_tgt2"]; exit_reason=f"TGT2 Hit @ {j-i}"; break
        if result=="OPEN":
            exit_prem=last_est
            if exit_prem < cur_sl: exit_prem=cur_sl
            if exit_prem > entry_prem*1.02: result="WIN"
            elif exit_prem < entry_prem*0.98: result="LOSS"
            else: result="BREAKEVEN"
            exit_reason=f"Time Exit - Last {round(last_est,2)} - {trail_used}"
        pnl=round((exit_prem-entry_prem)*opt["lot"],2); pnl_pct=round((exit_prem-entry_prem)/entry_prem*100,1)
        trades.append({"date":candles[i]["time"],"action":action,"trend":trend,"breakout":breakout or "-","spot":round(entry_spot,2),"strike":opt["strike"],"opt_type":opt["opt_type"],"entry_prem":entry_prem,"exit_prem":round(exit_prem,2),"tgt":tgt_prem,"sl":sl_prem,"trail_sl":round(cur_sl,2),"trail_used":trail_used,"max_prem":round(max_prem,2),"result":result,"pnl":pnl,"pnl_pct":pnl_pct,"exit_reason":exit_reason,"lot":opt["lot"]})
        last_trade_end=i+6
    if not trades: return {"script":name,"total":0,"win":0,"loss":0,"win_rate":0,"total_pnl":0,"trades":[]}
    wins=[t for t in trades if t["result"]=="WIN"]; losses=[t for t in trades if t["result"]=="LOSS"]; be=[t for t in trades if t["result"]=="BREAKEVEN"]
    total_pnl=round(sum(t["pnl"] for t in trades),2); win_rate=round(len(wins)/len(trades)*100,1) if trades else 0
    avg_win=round(sum(t["pnl"] for t in wins)/len(wins),2) if wins else 0; avg_loss=round(sum(t["pnl"] for t in losses)/len(losses),2) if losses else 0
    return {"script":name,"days":days,"total":len(trades),"win":len(wins),"loss":len(losses),"breakeven":len(be),"win_rate":win_rate,"total_pnl":total_pnl,"avg_win":avg_win,"avg_loss":avg_loss,"best":max(trades,key=lambda x:x["pnl"])["pnl"] if trades else 0,"worst":min(trades,key=lambda x:x["pnl"])["pnl"] if trades else 0,"ce_total":len([t for t in trades if t["action"]=="BUY CE"]),"ce_win_rate":round(len([t for t in trades if t["action"]=="BUY CE" and t["result"]=="WIN"])/len([t for t in trades if t["action"]=="BUY CE"])*100,1) if len([t for t in trades if t["action"]=="BUY CE"])>0 else 0,"pe_total":len([t for t in trades if t["action"]=="BUY PE"]),"pe_win_rate":round(len([t for t in trades if t["action"]=="BUY PE" and t["result"]=="WIN"])/len([t for t in trades if t["action"]=="BUY PE"])*100,1) if len([t for t in trades if t["action"]=="BUY PE"])>0 else 0,"trailing_saved":len(be),"use_trailing":use_trailing,"trades":trades[-20:],"all_trades_count":len(trades)}

last_alert={"time":None,"script":"","action":""}; alert_history=[]
def get_live_prices():
    usdinr=get_usdinr(); out={}
    for name,sym in SCRIPTS.items():
        try:
            url=f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=15m"
            r=requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=8).json(); res=r["chart"]["result"][0]; meta=res["meta"]
            raw=meta.get("regularMarketPrice",0); prev_raw=meta.get("previousClose",raw)
            price=convert_price(name,raw,usdinr); prev=convert_price(name,prev_raw,usdinr); chg=price-prev if prev else 0; pct=(chg/prev*100) if prev else 0
            closes=[c for c in res["indicators"]["quote"][0]["close"] if c is not None]; highs=[h for h in res["indicators"]["quote"][0]["high"] if h is not None]; lows=[l for l in res["indicators"]["quote"][0]["low"] if l is not None]
            def ema(data,p):
                k=2/(p+1); e=data[0]
                for v in data[1:]: e=v*k+e*(1-k)
                return e
            ema9=convert_price(name,ema(closes,9) if len(closes)>9 else raw,usdinr); ema21=convert_price(name,ema(closes,21) if len(closes)>21 else raw,usdinr); ema50=convert_price(name,ema(closes,50) if len(closes)>50 else raw,usdinr)
            last20_high=convert_price(name,max(highs[-20:]),usdinr) if len(highs)>=20 else price; last20_low=convert_price(name,min(lows[-20:]),usdinr) if len(lows)>=20 else price
            prev_ema9=convert_price(name,ema(closes[:-1],9) if len(closes)>10 else raw,usdinr); prev_ema21=convert_price(name,ema(closes[:-1],21) if len(closes)>22 else raw,usdinr)
            breakout=None; btype=""
            if price>last20_high: breakout="BREAKOUT UP 🔥"; btype="UP"
            elif price<last20_low: breakout="BREAKDOWN 🔻"; btype="DOWN"
            elif prev_ema9<=prev_ema21 and ema9>ema21: breakout="EMA CROSS UP 🚀"; btype="UP"
            elif prev_ema9>=prev_ema21 and ema9<ema21: breakout="EMA CROSS DOWN 📉"; btype="DOWN"
            if ema9>ema21>ema50 and price>ema9 and pct>0.30: trend_mark="STRONG UPTREND 🚀🚀"; trend_color="#00ff88"; trend_bg="#0f2a1d"; trend_level=5
            elif ema9>ema21 and price>ema9: trend_mark="UPTREND ↗"; trend_color="#00c853"; trend_bg="#0f2a1d"; trend_level=4
            elif ema9<ema21<ema50 and price<ema9 and pct<-0.30: trend_mark="STRONG DOWNTREND 📉📉"; trend_color="#ff1744"; trend_bg="#2a0f0f"; trend_level=1
            elif ema9<ema21 and price<ema9: trend_mark="DOWNTREND ↘"; trend_color="#ff7043"; trend_bg="#2a0f0f"; trend_level=2
            elif abs(pct)<0.10 and abs(ema9-ema21)/ema21*100<0.10: trend_mark="SIDEWAYS ◐"; trend_color="#ff9800"; trend_bg="#2a1a0f"; trend_level=3
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
            conf=min(92,max(50,strength+abs(pct)*5+(10 if breakout else 0))); cfg=CONFIG[name]
            live=price
            if action in ["BUY CE","BUY PE"]: entry=live; sl=round(entry*(1-cfg["sl_pct"]/100),2); tgt=round(entry*(1+cfg["tgt_pct"]/100),2); tgt2=round(entry*(1+cfg["tgt_pct"]/100*2),2); option=f"{name} {action}"
            else: entry=live; sl=round(entry*0.998,2); tgt=round(entry*1.002,2); tgt2=round(entry*1.004,2); option=f"{name} - WAIT"
            risk=abs(entry-sl) if entry!=sl else 1; reward=abs(tgt-entry); profit_ratio=round(reward/risk,2) if risk else 0; profit_pct=round(abs(tgt-entry)/entry*100,3) if entry else 0
            score=profit_ratio*20+conf+(25 if breakout else 0)+abs(pct)*5+trend_level*2
            if action=="WAIT": score=conf
            opt=calc_option(name,live,action)
            out[name]={"name":name,"symbol":sym,"price":round(live,2),"live":round(live,2),"prev":round(prev,2),"change":round(chg,2),"pct":round(pct,2),"signal":signal,"action":action,"color":color,"trend":trend_mark,"trend_color":trend_color,"trend_bg":trend_bg,"trend_level":trend_level,"market_cond":market_cond,"cond_color":cond_color,"ema9":round(ema9,2),"ema21":round(ema21,2),"ema50":round(ema50,2),"confidence":round(conf),"usdinr":round(usdinr,2),"entry":round(entry,2),"sl":sl,"tgt":tgt,"tgt2":tgt2,"option":option,"breakout":breakout,"breakout_type":btype,"resistance":round(last20_high,2),"support":round(last20_low,2),"profit_ratio":profit_ratio,"profit_pct":profit_pct,"score":round(score,1),"emoji":cfg["emoji"],"label":cfg["label"],"ist_time":ist_str(),"strike":opt["strike"],"atm":opt["atm"],"opt_type":opt["opt_type"],"premium":opt["premium"],"intrinsic":opt["intrinsic"],"time_value":opt["time_value"],"prem_sl":opt["prem_sl"],"prem_tgt1":opt["prem_tgt1"],"prem_tgt2":opt["prem_tgt2"],"lot":opt["lot"],"total_cost":opt["total_cost"],"max_loss":opt["max_loss"],"max_profit":opt["max_profit"],"dte":opt["dte"],"iv":opt["iv"],"moneyness":opt["moneyness"],"trail_levels":opt["trail_levels"]}
        except:
            out[name]={"name":name,"symbol":sym,"price":0,"live":0,"prev":0,"change":0,"pct":0,"signal":"WAIT","action":"WAIT","color":"orange","trend":"Loading...","trend_color":"#ff9800","trend_bg":"#222","trend_level":3,"market_cond":"Loading...","cond_color":"#aaa","ema9":0,"ema21":0,"ema50":0,"confidence":0,"usdinr":88.5,"entry":0,"sl":0,"tgt":0,"tgt2":0,"option":"WAIT","breakout":None,"breakout_type":"","resistance":0,"support":0,"profit_ratio":0,"profit_pct":0,"score":0,"emoji":CONFIG[name]["emoji"],"label":CONFIG[name]["label"],"ist_time":ist_str(),"strike":0,"atm":0,"opt_type":"CE","premium":0,"intrinsic":0,"time_value":0,"prem_sl":0,"prem_tgt1":0,"prem_tgt2":0,"lot":0,"total_cost":0,"max_loss":0,"max_profit":0,"dte":0,"iv":0,"moneyness":"--","trail_levels":[]}
    return dict(sorted(out.items(), key=lambda x: x[1]["score"], reverse=True))
def get_ai_suggestion():
    prices=get_live_prices(); candidates={k:v for k,v in prices.items() if v["action"] in ["BUY CE","BUY PE"] and v["price"]!=0}
    if not candidates:
        best_name=list(prices.keys())[0]; d=prices[best_name]
        return {"script":best_name,"action":"WAIT","confidence":d["confidence"],"reason":f"Clear Breakout Illa. {best_name} {d['trend']}. WAIT.","entry":d["entry"],"target":d["tgt"],"stoploss":d["sl"],"option":f"{best_name} - WAIT","trend":d["trend"],"pct":d["pct"],"all":prices,"breakout":None,"profit_ratio":0,"market_cond":d["market_cond"],"ist_time":ist_str(),"strike":d["strike"],"premium":d["premium"],"prem_sl":d["prem_sl"],"prem_tgt1":d["prem_tgt1"],"lot":d["lot"],"trail_levels":d["trail_levels"]}
    best_name=list(candidates.keys())[0]; d=candidates[best_name]
    reason=f"🏆 #1 Profit {d['profit_ratio']}:1 | {best_name} - {d['trend']} | Market: {d['market_cond']} | {d['moneyness']} Strike {d['strike']} {d['opt_type']} Premium Rs {d['premium']} | Trailing ON! | "
    if d["breakout"]: reason+=f"🔥 {d['breakout']} "
    reason+=f"OPTIONS BUYING - {d['action']} Mattum!"
    return {"script":best_name,"action":d["action"],"confidence":d["confidence"],"reason":reason,"entry":d["entry"],"target":d["tgt"],"stoploss":d["sl"],"option":d["option"],"trend":d["trend"],"pct":d["pct"],"all":prices,"breakout":d["breakout"],"tgt2":d["tgt2"],"resistance":d["resistance"],"support":d["support"],"profit_ratio":d["profit_ratio"],"profit_pct":d["profit_pct"],"market_cond":d["market_cond"],"ist_time":ist_str(),"strike":d["strike"],"atm":d["atm"],"opt_type":d["opt_type"],"premium":d["premium"],"intrinsic":d["intrinsic"],"time_value":d["time_value"],"prem_sl":d["prem_sl"],"prem_tgt1":d["prem_tgt1"],"prem_tgt2":d["prem_tgt2"],"lot":d["lot"],"total_cost":d["total_cost"],"max_loss":d["max_loss"],"max_profit":d["max_profit"],"moneyness":d["moneyness"],"trail_levels":d["trail_levels"]}
def auto_alert_loop():
    time.sleep(60)
    send_telegram(f"🤖 AI BOT STARTED!\n\n✅ Auto Alert + Trailing + Calls History ON\n🕐 Time: {ist_str()}\n🎯 Mode: Options Buying Only - ITM1 + Trailing SL")
    while True:
        try:
            now_ist=ist_now(); hour=now_ist.hour+now_ist.minute/60; is_market_hours=9.0<=hour<=23.5; is_sunday=now_ist.weekday()==6
            if is_market_hours and not is_sunday:
                ai=get_ai_suggestion()
                # Calls History Update - Ella RUNNING Call-um Check Pannu
                update_calls_history(ai["all"])
                should_alert=False; alert_type=""
                if ai["breakout"] and ai["confidence"]>=70: should_alert=True; alert_type="🚨 BREAKOUT ALERT"
                elif ai["action"] in ["BUY CE","BUY PE"] and ai["confidence"]>=85 and ai["trend"] and "STRONG" in ai["trend"]: should_alert=True; alert_type="🔥 STRONG TREND ALERT"
                if should_alert:
                    global last_alert; time_diff=9999
                    if last_alert["time"]: time_diff=(now_ist-last_alert["time"]).total_seconds()/60
                    is_dup=(last_alert["script"]==ai["script"] and last_alert["action"]==ai["action"] and time_diff<30)
                    if not is_dup:
                        # CALLS HISTORY la Add Pannu!
                        new_call = add_call(ai, source="AUTO")
                        trail_txt="\n".join([f"  {t['label']} | Trigger Rs {t['trigger']} -> SL Rs {t['new_sl']}" for t in ai.get("trail_levels",[])])
                        msg=f"{alert_type}\n\n⏰ TIME: {ist_str()}\n🆔 Call #{new_call['id']}\n🏆 Profit: {ai.get('profit_ratio','--')}:1\n🎯 {ai['script']} ({ai['option']})\n📊 {ai['action']} | {ai['trend']}\n\n🎯 OPTION - ITM1:\n📌 Strike: {ai.get('strike')} {ai.get('opt_type')}\n💰 ENTRY PREMIUM: Rs {ai.get('premium')} | Lot {ai.get('lot')} | Cost Rs {ai.get('total_cost')}\n🎯 TGT: Rs {ai.get('prem_tgt1')} | TGT2: Rs {ai.get('prem_tgt2')} | SL: Rs {ai.get('prem_sl')}\n\n📈 TRAILING:\n{trail_txt}\n\n📋 Calls History la Track Aagum - TGT/SL Hit Aana Telegram Varum!"
                        ok=send_telegram(msg)
                        if ok: last_alert={"time":now_ist,"script":ai["script"],"action":ai["action"]}; alert_history.append({"time":ist_str(),"script":ai["script"],"action":ai["action"],"type":alert_type,"price":ai["entry"],"strike":ai.get('strike'),'premium':ai.get('premium')})
            time.sleep(120)
        except Exception as e: print(f"Auto Error {e}"); time.sleep(60)
threading.Thread(target=auto_alert_loop, daemon=True).start()
@app.route('/api/prices')
def api_prices(): return jsonify(get_live_prices())
@app.route('/api/ai')
def api_ai(): return jsonify(get_ai_suggestion())
@app.route('/api/calls')
def api_calls():
    # Live Prices vachu Update Panni Anuppu
    try:
        prices = get_live_prices()
        update_calls_history(prices)
    except: pass
    return jsonify({"calls": calls_history, "summary": get_calls_summary()})
@app.route('/api/calls/clear')
def api_calls_clear():
    calls_history.clear()
    return jsonify({"ok": True, "msg": "Calls History Cleared"})
@app.route('/api/backtest/<name>')
def api_backtest(name):
    name=name.upper()
    if name not in SCRIPTS: return jsonify({"error":"Invalid"}),400
    return jsonify(run_backtest(name, days=30, use_trailing=True))
@app.route('/api/backtest_all')
def api_backtest_all():
    out={}
    for n in SCRIPTS.keys(): out[n]=run_backtest(n, days=30, use_trailing=True)
    return jsonify(out)
@app.route('/api/trail/<name>/<entry>/<current>')
def api_trail(name, entry, current):
    try:
        entry=float(entry); current=float(current)
        tr=calc_trailing(entry, current, round(entry*0.7,2))
        return jsonify({"entry":entry,"current":current,"trail_sl":tr["trail_sl"],"stage":tr["stage"],"locked_profit":tr["locked_profit"],"locked_pct":tr["locked_pct"],"status":tr["status"],"pnl_pct":round((current-entry)/entry*100,1)})
    except Exception as e: return jsonify({"error":str(e)})
@app.route('/backtest/<name>')
def backtest_page(name):
    bt=run_backtest(name.upper(), days=30, use_trailing=True)
    if "error" in bt: return f"Failed: {bt['error']}"
    msg=f"📊 BACKTEST + TRAILING - {name.upper()}\n\nTotal: {bt['total']} | Win: {bt['win']} | Loss: {bt['loss']} | BE: {bt['breakeven']}\n🎯 Win Rate: {bt['win_rate']}%\n💰 Total P&L: Rs {bt['total_pnl']}\n🛡️ Trailing Saved: {bt['trailing_saved']} Trades Breakeven!\n⏰ {ist_str()}"
    ok=send_telegram(msg); return f"✅ Sent! Win {bt['win_rate']}% P&L Rs {bt['total_pnl']}" if ok else "❌ Failed!"
@app.route('/api/breakout')
def api_breakout():
    prices=get_live_prices(); bo=[{"script":k,"breakout":v["breakout"],"action":v["action"],"price":v["live"],"resistance":v["resistance"],"support":v["support"],"confidence":v["confidence"]} for k,v in prices.items() if v["breakout"]]
    return jsonify({"breakouts":bo,"count":len(bo)})
@app.route('/api/alerts')
def api_alerts(): return jsonify({"last_alert": {"script": last_alert["script"], "action": last_alert["action"], "time": last_alert["time"].strftime('%d-%m-%Y %I:%M:%S %p IST') if last_alert["time"] else "None"}, "history": alert_history[-10:], "auto_alert": "ON", "ist_time": ist_str()})
@app.route('/breakout_alert')
def breakout_alert():
    ai=get_ai_suggestion()
    # MANUAL Call-um History la Add!
    new_call = add_call(ai, source="MANUAL")
    trail_txt="\n".join([f"{t['label']}" for t in ai.get("trail_levels",[])])
    msg=f"🚨 MANUAL CALL #{new_call['id']} - {ist_str()}\n\n🎯 {ai['script']} {ai.get('strike')} {ai.get('opt_type')} {ai['action']}\n💰 ENTRY Premium Rs {ai.get('premium')} | Lot {ai.get('lot')}\n🎯 TGT Rs {ai.get('prem_tgt1')} | TGT2 Rs {ai.get('prem_tgt2')} | SL Rs {ai.get('prem_sl')}\n\n📈 TRAILING:\n{trail_txt}\n\n📋 Calls History la Track Aagum!"
    ok=send_telegram(msg); return f"✅ Call #{new_call['id']} Sent + History la Added!" if ok else "❌ Failed!"
@app.route('/ai_signal')
def ai_signal(): return breakout_alert()
@app.route('/test_auto')
def test_auto():
    ai=get_ai_suggestion(); msg=f"🧪 TEST TRAILING\n\n⏰ {ist_str()}\n🎯 {ai['script']} {ai['strike']} {ai['opt_type']}\n💰 Premium Rs {ai['premium']}\n📈 Trail:\n"+"\n".join([f"{t['label']}" for t in ai.get("trail_levels",[])])
    ok=send_telegram(msg); return "✅ Sent!" if ok else "❌ Failed!"
@app.route('/')
def home():
    now=ist_str()
    html="""
    <html><head><title>AI Bot - Calls History</title><meta name='viewport' content='width=device-width, initial-scale=1'>
    <style>
    *{box-sizing:border-box} body{background:#0e1117;color:white;font-family:Arial;margin:0;padding:8px;overflow-x:hidden}
    .card{background:#131722;border-radius:10px;padding:10px;border:1px solid #222;margin-top:8px}
    .btn{display:inline-block;padding:9px 12px;border-radius:7px;color:white;text-decoration:none;font-weight:bold;margin:3px;font-size:12px}
    .b1{background:#0088cc}.b2{background:#00c853}.b3{background:#ff9800}.b4{background:#7c3aed}.b5{background:#ff1744}.b6{background:#ff6d00}.b7{background:#009688}.b8{background:#333}
    .green{color:#00ff88}.red{color:#ff4444}.orange{color:#ff9800}
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
    .levels{display:grid;grid-template-columns:1fr 1fr 1fr;gap:5px;margin-top:6px}
    .lvl{background:#0e1117;border-radius:7px;padding:6px;text-align:center;border:1px solid #333;font-size:12px}
    .opt-box{background:linear-gradient(135deg,#1a0033,#0d1b4c);border:1px solid #7c3aed;border-radius:8px;padding:8px;margin-top:6px}
    .trail-box{background:#0f2a1d;border:1px solid #00ff88;border-radius:8px;padding:7px;margin-top:6px;font-size:11px}
    .ai-box{background:linear-gradient(135deg,#1a0033,#0d1b4c);border:2px solid #7c3aed;border-radius:12px;padding:12px;margin-top:8px}
    .ai-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:8px}
    .ai-stat{background:#0e1117;border-radius:8px;padding:8px;text-align:center;border:1px solid #333;font-size:13px}
    .breakout-box{background:linear-gradient(135deg,#ff6d00,#ff1744);border-radius:12px;padding:12px;margin-top:8px;display:none}
    .bt-box{background:#131722;border:2px solid #009688;border-radius:12px;padding:12px;margin-top:8px}
    .bt-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:8px}
    .bt-card{background:#1a2030;border-radius:10px;padding:10px;border:1px solid #2a3348;text-align:center}
    .calls-box{background:#131722;border:2px solid #ff9800;border-radius:12px;padding:12px;margin-top:8px}
    .calls-summary{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:8px}
    .sum-card{background:#1a2030;border-radius:10px;padding:10px;text-align:center;border:1px solid #2a3348}
    table{width:100%;border-collapse:collapse;font-size:11px;margin-top:8px} th,td{padding:6px;border-bottom:1px solid #333;text-align:left} th{color:#aaa}
    .status-tgt{background:#00ff88;color:black;padding:3px 7px;border-radius:10px;font-weight:bold;font-size:11px}
    .status-sl{background:#ff4444;color:white;padding:3px 7px;border-radius:10px;font-weight:bold;font-size:11px}
    .status-run{background:#ff9800;color:black;padding:3px 7px;border-radius:10px;font-weight:bold;font-size:11px}
    .status-trail{background:#00bcd4;color:white;padding:3px 7px;border-radius:10px;font-weight:bold;font-size:11px}
    .live-dot{animation:blink 1s infinite} @keyframes blink{0%{opacity:1}50%{opacity:0.3}100%{opacity:1}}
    @media(max-width:1100px){.grid5,.bt-grid,.calls-summary{grid-template-columns:repeat(3,1fr)}}
    @media(max-width:700px){.grid5,.bt-grid,.calls-summary{grid-template-columns:1fr}.ai-grid{grid-template-columns:1fr 1fr} table{font-size:10px} th,td{padding:4px}}
    </style></head><body>
    <div class='top'><h2 style='margin:4px 0;font-size:20px'>🤖 AI BOT DASHBOARD</h2><span style='background:#1e293b;padding:6px 10px;border-radius:20px;font-size:12px'><span class='live-dot'>🟢</span> <span id='clock'>"""+now+"""</span> | USDINR: <span id='usdinrTop'>--</span></span></div>
    <div class='ai-box'>
      <div style='font-size:11px;color:#c4b5fd'>🤖 AI SUGGEST • OPTIONS BUYING ONLY • ITM1 + TRAILING</div>
      <h2 id='aiTitle' style='margin:6px 0;font-size:19px'>🤖 AI Analyzing...</h2>
      <div id='aiReason' style='font-size:12px;color:#e0e7ff;line-height:1.5'>Analyzing...</div>
      <div style='margin-top:6px'>Conf: <b id='aiConf' style='color:#00ff88;font-size:22px'>--%</b> <span id='aiTrend' style='font-size:11px;color:#aaa'>--</span> <span id='aiProfitBadge' style='background:#00ff88;color:black;padding:3px 8px;border-radius:12px;font-size:11px;font-weight:bold'>--</span></div>
      <div class='ai-grid'>
        <div class='ai-stat'><div class='small'>🏆 #1 BEST</div><b id='aiScript' style='font-size:14px'>--</b><div class='small' id='aiOption'>--</div></div>
        <div class='ai-stat'><div class='small'>🎯 STRIKE (ITM1)</div><b id='aiStrike' style='font-size:16px;color:#c4b5fd'>--</b></div>
        <div class='ai-stat'><div class='small'>💰 PREMIUM</div><b id='aiPremium' style='font-size:16px;color:#00ff88'>--</b></div>
        <div class='ai-stat'><div class='small'>💸 TOTAL COST</div><b id='aiCost' style='font-size:14px;color:#ff9800'>--</b></div>
      </div>
      <div class='ai-grid'>
        <div class='ai-stat'><div class='small'>💰 SPOT ENTRY</div><b id='aiEntry' style='font-size:14px;color:#00ff88'>--</b></div>
        <div class='ai-stat'><div class='small'>🎯 PREM TGT1</div><b id='aiPremTgt' style='font-size:14px;color:#00ff88'>--</b></div>
        <div class='ai-stat'><div class='small'>🛑 PREM SL</div><b id='aiPremSL' style='font-size:14px;color:#ff4444'>--</b></div>
        <div class='ai-stat'><div class='small'>📈 MAX P / L</div><b id='aiMaxPL' style='font-size:13px'>--</b></div>
      </div>
      <div style='margin-top:8px;text-align:center'><a class='btn b2' href='/breakout_alert'>📩 Send Call + Add to History</a> <a class='btn b6' href='/test_auto'>🧪 Test Alert</a></div>
    </div>
    <div id='breakoutBox' class='breakout-box'><div style='font-size:11px'>🚨 BREAKOUT - AUTO ALERT SENT!</div><h2 id='breakoutTitle' style='margin:6px 0;font-size:18px'>🔥 BREAKOUT!</h2><div id='breakoutDesc' style='font-size:12px;line-height:1.5'>--</div></div>

    <!-- 📋 CALLS HISTORY - NEW -->
    <div class='calls-box'>
      <div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;align-items:center'><b style='font-size:15px'>📋 CALLS HISTORY - TGT Done / SL Hit / Points</b><div><button onclick='loadCalls()' style='background:#ff9800;color:black;border:none;padding:7px 12px;border-radius:7px;font-weight:bold;cursor:pointer'>🔄 Refresh</button> <button onclick='clearCalls()' style='background:#333;color:white;border:none;padding:7px 12px;border-radius:7px;cursor:pointer'>🗑️ Clear</button></div></div>
      <div class='small'>Auto Alert Vandha Thaan-a History la Add Aagum! TGT/SL Hit Aana Thaan-a Telegram Varum + Status Maarum!</div>
      <div class='calls-summary'>
        <div class='sum-card'><div class='small'>📋 TOTAL CALLS</div><b id='sumTotal' style='font-size:20px'>0</b></div>
        <div class='sum-card'><div class='small'>✅ WINS (TGT)</div><b id='sumWins' style='font-size:20px;color:#00ff88'>0</b></div>
        <div class='sum-card'><div class='small'>❌ LOSSES (SL)</div><b id='sumLoss' style='font-size:20px;color:#ff4444'>0</b></div>
        <div class='sum-card'><div class='small'>🎯 WIN RATE</div><b id='sumWinRate' style='font-size:20px;color:#ff9800'>0%</b></div>
        <div class='sum-card'><div class='small'>💰 TOTAL P&L (1 Lot)</div><b id='sumPnl' style='font-size:18px'>Rs 0</b><div class='small' id='sumPoints'>0 Pts</div></div>
      </div>
      <div id='callsTable'><div style='text-align:center;padding:12px;color:#aaa'>Innum Call Illa - Breakout Vandha Auto Add Aagum! Manual-a Add Panna Mela "Send Call" Button Click Pannunga!</div></div>
    </div>

    <div id='scriptsGrid' class='grid5'></div>
    <div class='bt-box'><div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;align-items:center'><b style='font-size:15px'>📊 BACKTEST - Last 30 Days</b><button onclick='loadBacktestAll()' style='background:#009688;color:white;border:none;padding:8px 14px;border-radius:7px;font-weight:bold;cursor:pointer'>▶️ Run Backtest</button></div><div id='btLoading' style='display:none;text-align:center;padding:12px'>⏳ Running... 30 Sec Wait...</div><div id='btGrid' class='bt-grid'></div><div id='btDetail' style='margin-top:10px'></div></div>
    <div style='margin-top:8px;text-align:center'><a class='btn b1' href='/test_telegram'>📩 Test Telegram</a><a class='btn b7' href='javascript:loadBacktestAll()'>📊 Backtest</a><a class='btn b6' href='/test_auto'>🧪 Test Alert</a><a class='btn b3' href='/debug'>🔍 Debug</a></div>
    <div class='small' style='text-align:center;margin-top:6px' id='lastUpdate'>--</div>
    <script>
    function fmt(n){ return 'Rs '+n.toLocaleString('en-IN',{maximumFractionDigits:0}); }
    function fmt2(n){ return 'Rs '+n.toLocaleString('en-IN',{maximumFractionDigits:2}); }
    function updateClock(){ let now=new Date(new Date().toLocaleString('en-US',{timeZone:'Asia/Kolkata'})); document.getElementById('clock').innerText=now.toLocaleDateString('en-IN',{day:'2-digit',month:'2-digit',year:'numeric'})+' '+now.toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:true})+' IST'; }
    setInterval(updateClock,1000); updateClock();
    function statusClass(s){ if(s.includes('TGT')) return 'status-tgt'; if(s.includes('SL HIT')) return 'status-sl'; if(s.includes('TRAIL')) return 'status-trail'; return 'status-run'; }
    function loadCalls(){
      fetch('/api/calls').then(r=>r.json()).then(data=>{
        let s=data.summary;
        document.getElementById('sumTotal').innerText=s.total_calls;
        document.getElementById('sumWins').innerText=s.wins;
        document.getElementById('sumLoss').innerText=s.losses;
        document.getElementById('sumWinRate').innerText=s.win_rate+'%';
        let pnlEl=document.getElementById('sumPnl'); pnlEl.innerText=(s.total_pnl>=0?'+':'')+fmt(s.total_pnl); pnlEl.style.color=s.total_pnl>=0?'#00ff88':'#ff4444';
        document.getElementById('sumPoints').innerText=(s.total_points>=0?'+':'')+s.total_points+' Pts | '+s.running+' Running';
        if(data.calls.length==0){ document.getElementById('callsTable').innerHTML='<div style="text-align:center;padding:12px;color:#aaa">Innum Call Illa - Breakout Vandha Auto Add Aagum!</div>'; return; }
        let rows='';
        data.calls.forEach(c=>{
          let col=c.pnl>=0?'#00ff88':'#ff4444';
          let exitTxt=c.status=='RUNNING' ? fmt2(c.current_prem)+' (Live)' : fmt2(c.exit_prem)+' @ '+c.exit_time;
          rows+=`<tr><td>#${c.id}<br><span class='small'>${c.time}</span><br><span class='small'>${c.source}</span></td><td><b>${c.script}</b><br>${c.action} ${c.strike} ${c.opt_type}<br><span class='small'>${c.trend}</span></td><td>Entry<br><b>${fmt2(c.entry_prem)}</b><br><span class='small'>Lot ${c.lot}</span></td><td>TGT<br><b style='color:#00ff88'>${fmt2(c.tgt)}</b><br><span class='small'>TGT2 ${fmt2(c.tgt2)}</span></td><td>SL<br><b style='color:#ff4444'>${fmt2(c.sl)}</b><br><span class='small'>Trail ${fmt2(c.trail_sl)}</span></td><td><span class='${statusClass(c.status)}'>${c.status}</span><br><span class='small'>Exit: ${exitTxt}</span></td><td style='color:${col};font-weight:bold'>${c.points>=0?'+':''}${c.points} Pts<br>${c.pnl>=0?'+':''}${fmt(c.pnl)}<br><span class='small'>${c.pnl_pct}%</span></td></tr>`;
        });
        document.getElementById('callsTable').innerHTML=`<table><tr><th>Call / Time</th><th>Script</th><th>Entry</th><th>TGT</th><th>SL</th><th>Status / Exit</th><th>Points / P&L (1 Lot)</th></tr>${rows}</table>`;
      });
    }
    function clearCalls(){ if(confirm('Calls History Full Clear Pannava?')){ fetch('/api/calls/clear').then(()=>loadCalls()); } }
    function loadBacktestAll(){
      document.getElementById('btLoading').style.display='block'; document.getElementById('btGrid').innerHTML='';
      fetch('/api/backtest_all').then(r=>r.json()).then(data=>{
        document.getElementById('btLoading').style.display='none'; let html=''; let totalPnl=0; let totalTrades=0; let totalWins=0; let totalBE=0;
        for(let name in data){ let d=data[name]; if(d.error) continue; totalPnl+=d.total_pnl; totalTrades+=d.total; totalWins+=d.win; totalBE+=d.breakeven||0; let col=d.total_pnl>=0?'#00ff88':'#ff4444';
          html+=`<div class='bt-card'><h3 style='margin:2px 0'>${name}</h3><div style='font-size:22px;font-weight:bold;color:${d.win_rate>=55?'#00ff88':d.win_rate>=45?'#ff9800':'#ff4444'}'>${d.win_rate}% Win</div><div class='small'>${d.total} Trades | ${d.win} Win | ${d.loss} Loss | ${d.breakeven} BE</div><div style='font-size:16px;font-weight:bold;color:${col};margin-top:6px'>${d.total_pnl>=0?'+':''}${fmt(d.total_pnl)}</div><div class='small'>1 Lot | 30 Days | Trailing ON ✅</div><div class='small' style='margin-top:6px'>🛡️ Saved: ${d.trailing_saved} BE<br>CE ${d.ce_win_rate}% | PE ${d.pe_win_rate}%</div><button onclick="showBacktestDetail('${name}')" style='background:#009688;color:white;border:none;padding:6px 10px;border-radius:6px;margin-top:8px;cursor:pointer;font-size:11px'>📋 Last 20 Trades</button></div>`;
        }
        let overallWin=totalTrades>0?Math.round(totalWins/totalTrades*100):0;
        html=`<div class='bt-card' style='border:2px solid #00ff88'><h3>🏆 OVERALL</h3><div style='font-size:22px;font-weight:bold;color:${overallWin>=55?'#00ff88':'#ff9800'}'>${overallWin}% Win</div><div class='small'>${totalTrades} Trades | ${totalBE} BE Saved!</div><div style='font-size:16px;font-weight:bold;color:${totalPnl>=0?'#00ff88':'#ff4444'}'>${totalPnl>=0?'+':''}${fmt(totalPnl)}</div><div class='small'>5 Scripts | 30 Days</div></div>`+html;
        document.getElementById('btGrid').innerHTML=html; window._btData=data;
      });
    }
    function showBacktestDetail(name){
      let d=window._btData[name]; if(!d) return; let rows='';
      d.trades.slice().reverse().forEach(t=>{ let col=t.result=='WIN'?'#00ff88':t.result=='BREAKEVEN'?'#ff9800':'#ff4444'; rows+=`<tr><td>${t.date}</td><td>${t.action} ${t.strike} ${t.opt_type}</td><td>${t.trend}</td><td>${fmt2(t.entry_prem)} → ${fmt2(t.exit_prem)}<br><span class='small'>Trail SL ${fmt2(t.trail_sl)}</span></td><td style='color:${col};font-weight:bold'>${t.result} (${t.pnl_pct}%)</td><td style='color:${col}'>${t.pnl>=0?'+':''}${fmt(t.pnl)}</td><td class='small'>${t.exit_reason}</td></tr>`; });
      document.getElementById('btDetail').innerHTML=`<div class='card'><b>📋 ${name} - Last 20 Trades</b><table><tr><th>Date</th><th>Trade</th><th>Trend</th><th>Premium</th><th>Result</th><th>P&L</th><th>Exit</th></tr>${rows}</table></div>`; document.getElementById('btDetail').scrollIntoView({behavior:'smooth'});
    }
    function loadPrices(){
      fetch('/api/prices').then(r=>r.json()).then(data=>{
        let arr=Object.values(data); let usd=''; let html='';
        arr.forEach((d,i)=>{
          let rank=i+1; let isTop=rank==1 && d.action!='WAIT'; let badgeClass=d.action=='WAIT'?'bg-orange':'bg-green'; let badgeText=d.action=='WAIT'?'◐ WAIT':'✅ '+d.action+' - BUYING'; usd=d.usdinr;
          let trailHtml=d.trail_levels.map(t=>`<div style='display:flex;justify-content:space-between'><span>${t.label.split(':')[0]}</span><b>Trig ${fmt2(t.trigger)} → SL ${fmt2(t.new_sl)}</b></div>`).join('');
          html+=`<div class='script-card ${isTop?'rank1':''}'>${isTop?'<div class="rank-badge">🏆 #1 BEST</div>':`<div class="rank-badge" style="background:#333;color:#aaa">#${rank}</div>`}<div class='small'>${d.label} • OPTIONS BUYING</div><h3 style='margin:3px 0;font-size:15px'>${d.emoji} ${d.name}</h3><div class='small'>LIVE SPOT</div><div class='price green'>${fmt(d.live)}</div><div class='small'>${d.change>=0?'▲ + ':'▼ '}${fmt(Math.abs(d.change))} (${d.pct}%)</div><div class='trend-bar' style='background:${d.trend_bg};color:${d.trend_color};border:1px solid ${d.trend_color}'>${d.trend}</div><div style='text-align:center;font-size:11px'>🌍 <b style='color:${d.cond_color}'>${d.market_cond}</b></div><div style='text-align:center;font-size:10px;color:#aaa;margin-top:2px'>EMA 9: ${fmt(d.ema9)} | 21: ${fmt(d.ema21)} | 50: ${fmt(d.ema50)}</div><div style='background:#0e1117;border:1px solid #00ff88;border-radius:7px;padding:5px;margin-top:6px;text-align:center'><div class='small'>🏆 PROFIT RATIO</div><b style='color:#00ff88;font-size:15px'>${d.profit_ratio}:1</b> <span class='small'>| ${d.profit_pct}% | Conf ${d.confidence}%</span></div><div class='opt-box'><div style='text-align:center;font-size:11px;color:#c4b5fd;font-weight:bold'>🎯 ${d.moneyness} - ${d.name} ${d.strike} ${d.opt_type}</div><div style='display:flex;justify-content:space-between;margin-top:5px'><span class='small'>Spot / ATM</span><b style='font-size:12px'>${fmt(d.live)} / ${fmt(d.atm)}</b></div><div style='display:flex;justify-content:space-between'><span class='small'>💰 PREMIUM</span><b style='color:#00ff88;font-size:16px'>${fmt2(d.premium)}</b></div><div style='display:flex;justify-content:space-between'><span class='small'>Prem TGT / SL</span><b style='font-size:12px;color:#00ff88'>${fmt2(d.prem_tgt1)} / <span style='color:#ff4444'>${fmt2(d.prem_sl)}</span></b></div><div style='display:flex;justify-content:space-between'><span class='small'>Lot ${d.lot} | Cost</span><b style='color:#ff9800'>${fmt(d.total_cost)}</b></div></div><div class='trail-box'><b>📈 TRAILING</b><div style='margin-top:4px'>${trailHtml}</div></div>${d.breakout?`<div class='small' style='color:#ff9800;font-weight:bold;margin-top:4px'>🔥 ${d.breakout}</div>`:''}<div style='text-align:center;margin-top:8px'><span class='badge ${badgeClass}'>${badgeText}</span></div><div class='levels'><div class='lvl'><div class='small'>SPOT ENTRY</div><b style='color:#00ff88'>${fmt(d.entry)}</b></div><div class='lvl'><div class='small'>SPOT TGT</div><b style='color:#00ff88'>${fmt(d.tgt)}</b></div><div class='lvl'><div class='small'>SPOT SL</div><b style='color:#ff4444'>${fmt(d.sl)}</b></div></div><div class='small' style='margin-top:6px;text-align:center'>Res: ${fmt(d.resistance)} | Sup: ${fmt(d.support)}</div></div>`;
        });
        document.getElementById('scriptsGrid').innerHTML=html; document.getElementById('usdinrTop').innerText='Rs '+usd;
        let nowIST=new Date(new Date().toLocaleString('en-US',{timeZone:'Asia/Kolkata'})); document.getElementById('lastUpdate').innerText='Last Update: '+nowIST.toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:true})+' IST';
      });
    }
    function loadAI(){
      fetch('/api/ai').then(r=>r.json()).then(ai=>{
        let emoji=ai.action=='WAIT'?'◐':'✅'; document.getElementById('aiTitle').innerHTML=emoji+' AI SUGGESTS: <span style="color:#00ff88">'+ai.action+' - '+ai.script+' '+ai.strike+' '+ai.opt_type+'</span> (ITM1 + Trailing)';
        document.getElementById('aiReason').innerText='🧠 '+ai.reason; document.getElementById('aiConf').innerText=ai.confidence+'%'; document.getElementById('aiTrend').innerText=ai.trend+' | '+ai.pct+'%'; document.getElementById('aiProfitBadge').innerText='🏆 Profit '+ai.profit_ratio+':1';
        document.getElementById('aiScript').innerText=ai.script; document.getElementById('aiOption').innerText=ai.option+' | '+ai.moneyness; document.getElementById('aiStrike').innerText=ai.strike+' '+ai.opt_type;
        document.getElementById('aiPremium').innerText=fmt2(ai.premium); document.getElementById('aiCost').innerText=fmt(ai.total_cost);
        document.getElementById('aiEntry').innerText=fmt(ai.entry); document.getElementById('aiPremTgt').innerText=fmt2(ai.prem_tgt1)+' / '+fmt2(ai.prem_tgt2); document.getElementById('aiPremSL').innerText=fmt2(ai.prem_sl); document.getElementById('aiMaxPL').innerText='+'+fmt(ai.max_profit)+' / -'+fmt(ai.max_loss);
        let box=document.getElementById('breakoutBox'); if(ai.breakout){ box.style.display='block'; document.getElementById('breakoutTitle').innerText='🔥 BREAKOUT: '+ai.script+' - '+ai.breakout; document.getElementById('breakoutDesc').innerText=ai.script+' '+ai.strike+' '+ai.opt_type+' Premium '+fmt2(ai.premium)+' | Entry '+fmt(ai.entry)+' | Prem TGT '+fmt2(ai.prem_tgt1)+' | Prem SL '+fmt2(ai.prem_sl); } else { box.style.display='none'; }
      });
    }
    loadPrices(); loadAI(); loadCalls(); setInterval(loadPrices, 5000); setInterval(loadAI, 15000); setInterval(loadCalls, 15000);
    </script></body></html>
    """
    return html
@app.route('/test_telegram')
def test_telegram():
    ok=send_telegram(f"✅ Test Success!\n⏰ IST: {ist_str()}"); return "✅ Sent!" if ok else "❌ Failed!"
@app.route('/order_test')
def order_test():
    send_telegram(f"🚀 ORDER: NIFTY CE BUY\n⏰ {ist_str()}"); return "Sent!"
@app.route('/login')
def login(): return redirect(f"https://ant.aliceblueonline.com/?appcode={ALICE_API_KEY}")
@app.route('/debug')
def debug(): return jsonify({"ip":get_ip(),"telegram":bool(TELEGRAM_BOT_TOKEN),"ist_time":ist_str(),"prices":get_live_prices(),"ai":get_ai_suggestion(),"alerts":alert_history,"calls":calls_history})
if __name__=='__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT",5000)))
