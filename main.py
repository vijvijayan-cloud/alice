# ============================================================
# COMPLETE CODE - LOT SIZE FIXED
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

@app.route("/")
def home():
    return "Bot Running! NIFTY Lot 65 | SENSEX Lot 20"

@app.route("/health")
def health():
    return "OK"

# ---------------- CONFIG ----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
IST = pytz.timezone("Asia/Kolkata")

# ---------------- ✅ FIXED LOT SIZES ----------------
# OLD: NIFTY 75, SENSEX 10, BANKNIFTY 35 - WRONG
# NEW: Correct 2026 Lot Sizes
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

STRIKE_STEP = {
    "NIFTY": 50,
    "BANKNIFTY": 100,
    "FINNIFTY": 50,
    "SENSEX": 100,
    "GOLDM": 100,
}

# ---------------- LOT + PNL - FIXED ----------------
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

# ---------------- TELEGRAM ----------------
def send_telegram(msg: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"Telegram Skip: {msg[:50]}")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
        print(f"Telegram: {msg[:70]}")
    except Exception as e:
        print(f"Telegram Error: {e}")

# ---------------- DATA ----------------
def get_data(yahoo_symbol: str, interval="15m", period="5d"):
    try:
        df = yf.download(yahoo_symbol, interval=interval, period=period, progress=False, auto_adjust=False)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        return df
    except Exception as e:
        print(f"Data Error {yahoo_symbol}: {e}")
        return None

def add_indicators(df):
    df["EMA9"] = df["Close"].ewm(span=9).mean()
    df["EMA21"] = df["Close"].ewm(span=21).mean()
    df["EMA50"] = df["Close"].ewm(span=50).mean()
    return df

# ---------------- SIGNAL ----------------
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
        tgt = round(entry * 1.80, 2)
        sl = round(entry * 0.60, 2)
        return ("CE", "STRONG UP 🚀", entry, tgt, sl, atm)

    if close < ema9 < ema21 and close < float(prev["Low"]):
        entry = round(close * 0.0045, 2)
        tgt = round(entry * 1.80, 2)
        sl = round(entry * 0.60, 2)
        return ("PE", "STRONG DOWN 📉", entry, tgt, sl, atm)
    return None

# ---------------- TRAILING SL ----------------
class TrailingManager:
    def __init__(self, entry: float, sl: float):
        self.entry = entry
        self.sl = sl
        self.highest = entry

    def update(self, ltp: float):
        if ltp > self.highest:
            self.highest = ltp
        if (ltp - self.entry) > (self.entry * 0.40):
            new_sl = round(self.highest * 0.80, 2)
            if new_sl > self.sl:
                self.sl = new_sl
                return f"Trailing SL Updated: Rs {self.sl}"
        return None

# ---------------- POSITIONS ----------------
sent_signals = set()
active_positions = {}

def send_sl_hit(symbol: str, strike: int, opt_type: str, entry: float, sl: float):
    full = f"{symbol} {strike} {opt_type}"
    points, pnl_rs, lot = calc_pnl(full, entry, sl)
    msg = f"❌ SL HIT\n{full}\nEntry Rs {entry} → SL Rs {sl}\n{points} Pts | Rs {pnl_rs}"
    send_telegram(msg)

def send_tgt_hit(symbol: str, strike: int, opt_type: str, entry: float, tgt: float):
    full = f"{symbol} {strike} {opt_type}"
    points, pnl_rs, lot = calc_pnl(full, entry, tgt)
    msg = f"✅ TGT HIT\n{full}\nEntry Rs {entry} → TGT Rs {tgt}\n+{points} Pts | Rs +{pnl_rs}"
    send_telegram(msg)

def run_once():
    now = datetime.now(IST)
    time_str = now.strftime("%d-%m %I:%M %p")
    print(f"--- Check {time_str} ---", flush=True)
    for symbol, yahoo in SYMBOLS.items():
        df = get_data(yahoo)
        if df is None:
            continue
        df = add_indicators(df)
        result = check_signal(symbol, df)
        if not result:
            continue
        opt_type, strength, entry, tgt, sl, strike = result
        key = f"{symbol}-{strike}-{opt_type}-{now.strftime('%d-%m-%Y')}"
        if key in sent_signals:
            continue
        sent_signals.add(key)
        lot = get_lot(symbol)
        msg = (
            f"🚨 BUY {opt_type} - {symbol} {strike} {opt_type}\n"
            f"Entry: Rs {entry} | TGT: Rs {tgt} | SL: Rs {sl}\n"
            f"Lot: {lot} | {strength}\n"
            f"Time: {time_str}"
        )
        send_telegram(msg)
        active_positions[key] = {
            "symbol": symbol,
            "strike": strike,
            "opt_type": opt_type,
            "entry": entry,
            "sl": sl,
            "tgt": tgt,
            "trailing": TrailingManager(entry, sl),
        }

def run_bot():
    # Test - Logs la Correct-a Varudha-nu Paakalam!
    pts, pnl, lot = calc_pnl("NIFTY 25100 PE", 113.97, 68.38)
    print(f"TEST NIFTY 25100 PE | Lot: {lot} | {pts} Pts | Rs {pnl}", flush=True)
    pts2, pnl2, lot2 = calc_pnl("SENSEX 81400 PE", 320.91, 192.55)
    print(f"TEST SENSEX 81400 PE | Lot: {lot2} | {pts2} Pts | Rs {pnl2}", flush=True)
    send_telegram("🤖 Bot Started! NIFTY Lot 65 | SENSEX Lot 20 - Fixed ✅")
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"Loop Error: {e}", flush=True)
        time.sleep(300)

if __name__ == "__main__":
    t = threading.Thread(target=run_bot, daemon=True)
    t.start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
