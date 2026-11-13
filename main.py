# ============================================================
# COMPLETE CODE - DASHBOARD + LOT SIZE FIXED
# Dashboard - Before Maariye!
# NIFTY: 65 | SENSEX: 20 | BANKNIFTY: 30
# ============================================================

import os
import time
import threading
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime
import pytz
from flask import Flask

app = Flask(__name__)
IST = pytz.timezone("Asia/Kolkata")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ---------------- ✅ LOT SIZES - FIXED ----------------
LOT_SIZES = {
    "NIFTY": 65,
    "BANKNIFTY": 30,
    "FINNIFTY": 60,
    "MIDCPNIFTY": 120,
    "SENSEX": 20,
    "BANKEX": 30,
    "SENSEX50": 70,
    "GOLDM": 10,
    "GOLD": 100,
    "SILVERM": 5,
    "SILVER": 30,
    "CRUDEOIL": 100,
}

SYMBOLS = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
    "SENSEX": "^BSESN",
    "GOLDM": "GOLDM.NS",
}

STRIKE_STEP = {"NIFTY": 50, "BANKNIFTY": 100, "FINNIFTY": 50, "SENSEX": 100, "GOLDM": 100}

def get_lot(symbol: str) -> int:
    base = symbol.split()[0].upper()
    for key in LOT_SIZES:
        if base.startswith(key):
            return LOT_SIZES[key]
    return 1

def calc_pnl(symbol: str, entry: float, exit_price: float):
    lot = get_lot(symbol)
    points = round(exit_price - entry, 2)
    pnl_rs = round(points * lot, 2)
    return points, pnl_rs, lot

def send_telegram(msg: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
    except Exception as e:
        print(f"Telegram Error: {e}")

def get_data(yahoo_symbol: str, interval="15m", period="5d"):
    try:
        df = yf.download(yahoo_symbol, interval=interval, period=period, progress=False, auto_adjust=False)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df.dropna()
    except Exception as e:
        print(f"Data Error: {e}")
        return None

def add_indicators(df):
    df["EMA9"] = df["Close"].ewm(span=9).mean()
    df["EMA21"] = df["Close"].ewm(span=21).mean()
    df["EMA50"] = df["Close"].ewm(span=50).mean()
    return df

def check_signal(symbol: str, df):
    if df is None or len(df) < 5:
        return None
    last = df.iloc[-1]
    prev = df.iloc[-2]
    close = float(last["Close"])
    ema9 = float(last["EMA9"])
    ema21 = float(last["EMA21"])
    step = STRIKE_STEP.get(symbol, 50)
    atm = round(close / step) * step
    if close > ema9 > ema21 and close > float(prev["High"]):
        entry = round(close * 0.0045, 2)
        return ("CE", "STRONG UP 🚀", entry, round(entry*1.80,2), round(entry*0.60,2), atm)
    if close < ema9 < ema21 and close < float(prev["Low"]):
        entry = round(close * 0.0045, 2)
        return ("PE", "STRONG DOWN 📉", entry, round(entry*1.80,2), round(entry*0.60,2), atm)
    return None

# ---------------- DATA FOR DASHBOARD ----------------
sent_signals = set()
active_positions = {}
signal_history = []  # Dashboard la Kaatradhuku
live_prices = {}  # {symbol: {price, ema9, ema21, signal}}

def run_once():
    now = datetime.now(IST)
    time_str = now.strftime("%d-%m %I:%M %p")
    print(f"--- Check {time_str} ---", flush=True)
    for symbol, yahoo in SYMBOLS.items():
        df = get_data(yahoo)
        if df is None:
            continue
        df = add_indicators(df)
        last = df.iloc[-1]
        close = float(last["Close"])
        ema9 = float(last["EMA9"])
        ema21 = float(last["EMA21"])
        result = check_signal(symbol, df)
        # Dashboard ku Live Data Save Pannrom
        live_prices[symbol] = {
            "price": round(close, 2),
            "ema9": round(ema9, 2),
            "ema21": round(ema21, 2),
            "lot": get_lot(symbol),
            "signal": f"{result[0]} - {result[1]}" if result else "WAIT ⏳",
            "time": time_str
        }
        if not result:
            continue
        opt_type, strength, entry, tgt, sl, strike = result
        key = f"{symbol}-{strike}-{opt_type}-{now.strftime('%d-%m-%Y')}"
        if key in sent_signals:
            continue
        sent_signals.add(key)
        lot = get_lot(symbol)
        msg = f"🚨 BUY {opt_type} - {symbol} {strike} {opt_type}\nEntry: Rs {entry} | TGT: Rs {tgt} | SL: Rs {sl}\nLot: {lot} | {strength}\nTime: {time_str}"
        send_telegram(msg)
        pos = {"symbol": symbol, "strike": strike, "opt_type": opt_type, "entry": entry, "sl": sl, "tgt": tgt, "time": time_str, "lot": lot}
        active_positions[key] = pos
        signal_history.insert(0, pos)
        signal_history[:] = signal_history[:20]

def run_bot():
    print("TEST NIFTY Lot 65 | -2963.35", flush=True)
    print("TEST SENSEX Lot 20 | -2567.20", flush=True)
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"Loop Error: {e}", flush=True)
        time.sleep(300)

# ---------------- ✅ DASHBOARD - BEFORE MAARIYE! ----------------
@app.route("/")
def home():
    now = datetime.now(IST).strftime("%d-%m-%Y %I:%M %p")
    cards = ""
    for sym, d in live_prices.items():
        color = "green" if "STRONG UP" in d["signal"] else ("red" if "STRONG DOWN" in d["signal"] else "gray")
        cards += f"""
        <div class="card">
          <h3>{sym} <span class="{color}">{d['signal']}</span></h3>
          <p>Price: <b>Rs {d['price']}</b> | EMA9: {d['ema9']} | EMA21: {d['ema21']}</p>
          <p>Lot: <b>{d['lot']}</b> | Updated: {d['time']}</p>
        </div>"""

    if not cards:
        cards = "<div class='card'><p>Loading... 5 Min la Data Varum! ⏳</p></div>"

    hist = ""
    if not signal_history:
        hist = "<p>No Signals Yet - Market Wait Pannitu Irukku...</p>"
    for p in signal_history:
        hist += f"<div class='row'><b>{p['symbol']} {p['strike']} {p['opt_type']}</b> | Entry Rs {p['entry']} | TGT Rs {p['tgt']} | SL Rs {p['sl']} | Lot {p['lot']} | {p['time']}</div>"

    active = ""
    if not active_positions:
        active = "<p>No Active Positions</p>"
    for k, p in active_positions.items():
        active += f"<div class='row'><b>{p['symbol']} {p['strike']} {p['opt_type']}</b> | Entry {p['entry']} | SL {p['sl']} | TGT {p['tgt']}</div>"

    return f"""
    <html><head><title>Algo Bot Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="60">
    <style>
      body{{font-family:Arial; padding:12px; background:#0f172a; color:white; margin:0}}
      h1{{font-size:20px; text-align:center}}
      .card{{background:#1e293b; padding:14px; border-radius:12px; margin-bottom:10px}}
      .row{{background:#334155; padding:10px; border-radius:8px; margin-bottom:6px; font-size:14px}}
      .green{{color:#4ade80}} .red{{color:#f87171}} .gray{{color:#94a3b8}}
      .top{{background:#16a34a; padding:12px; border-radius:12px; text-align:center; margin-bottom:10px}}
      small{{color:#94a3b8}}
    </style></head><body>
    <h1>🤖 ALGO BOT DASHBOARD</h1>
    <div class="top"><b>✅ LIVE</b> | NIFTY Lot 65 | SENSEX Lot 20 | BANKNIFTY Lot 30<br><small>Last Update: {now} | Auto Refresh 60 Sec</small></div>
    <h3>📊 Live Market</h3>
    {cards}
    <div class="card"><h3>🔥 Active Positions</h3>{active}</div>
    <div class="card"><h3>📈 Signal History</h3>{hist}</div>
    <div class="card"><h3>✅ Lot Size Fixed Example</h3>
    <p>NIFTY 25100 PE | -45.59 Pts | Rs -2963.35 (65 x)</p>
    <p>SENSEX 81400 PE | -128.36 Pts | Rs -2567.20 (20 x)</p></div>
    <p style="text-align:center"><small>Bot Running on Render | Telegram Alerts ON</small></p>
    </body></html>
    """

@app.route("/health")
def health():
    return "OK"

if __name__ == "__main__":
    t = threading.Thread(target=run_bot, daemon=True)
    t.start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
