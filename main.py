# ============================================================
# DHAN ALGO BOT - CORRECTED VERSION
# NIFTY Lot: 65 | SENSEX Lot: 20 | BANKNIFTY Lot: 30
# Fixed: 13-11-2026 - Lot Size + P&L Calculation
# ============================================================

import os
import time
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import pytz

# ---------------- CONFIG ----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")

IST = pytz.timezone("Asia/Kolkata")

# ---------------- ✅ CORRECT LOT SIZES - 2026 - SEBI REVISED ----------------
# NIFTY: 75 -> 65 (31 Dec 2025)
# SENSEX: 10 -> 20 (Nov 2024)
# BANKNIFTY: 35 -> 30

LOT_SIZES = {
    # NSE Indices
    "NIFTY": 65,
    "BANKNIFTY": 30,
    "FINNIFTY": 60,
    "MIDCPNIFTY": 120,
    "NIFTYNXT50": 25,
    # BSE Indices
    "SENSEX": 20,
    "BANKEX": 30,
    "SENSEX50": 70,
    # MCX - Commodity
    "GOLDM": 10,
    "GOLD": 100,
    "SILVERM": 5,
    "SILVER": 30,
    "CRUDEOIL": 100,
    "NATURALGAS": 1250,
    "COPPER": 2500,
}

# Symbol -> Yahoo Ticker Mapping
SYMBOLS = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
    "SENSEX": "^BSESN",
    "GOLDM": "GOLDM.NS",
}

# Strike Step
STRIKE_STEP = {
    "NIFTY": 50,
    "BANKNIFTY": 100,
    "FINNIFTY": 50,
    "SENSEX": 100,
    "GOLDM": 100,
}

def get_lot(symbol: str) -> int:
    """Correct lot size return pannum"""
    base = symbol.split()[0].upper()
    # GOLDM 118200 CE -> GOLDM
    for key in LOT_SIZES:
        if base.startswith(key):
            return LOT_SIZES[key]
    return 1

def calc_pnl(symbol: str, entry: float, exit_price: float) -> tuple:
    """Points + Rs P&L - Correct Lot oda"""
    lot = get_lot(symbol)
    points = round(exit_price - entry, 2)
    pnl_rs = round(points * lot, 2)
    return points, pnl_rs, lot

# ---------------- TELEGRAM ----------------
def send_telegram(msg: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
        print(f"Telegram Sent: {msg[:60]}")
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

# ---------------- SIGNAL LOGIC ----------------
def check_signal(symbol: str, df):
    """
    1 Hour Breakout + EMA Logic
    Returns: (signal_type, strength, entry, tgt, sl, strike)
    """
    if df is None or len(df) < 5:
        return None

    last = df.iloc[-1]
    prev = df.iloc[-2]
    close = float(last["Close"])
    ema9 = float(last["EMA9"])
    ema21 = float(last["EMA21"])

    # Round Strike
    step = STRIKE_STEP.get(symbol, 50)
    atm = round(close / step) * step

    # STRONG UP - Close > EMA9 > EMA21 + Breakout
    if close > ema9 > ema21 and close > float(prev["High"]):
        strike = atm  # CE Strike
        entry = round(close * 0.0045, 2)  # Approx Premium - Real la Dhan Option Chain la edukkanum
        # TGT = Entry + 80%, SL = Entry - 40% (Optiontrix Style)
        tgt = round(entry * 1.80, 2)
        sl = round(entry * 0.60, 2)
        return ("CE", "STRONG UP 🚀", entry, tgt, sl, strike)

    # STRONG DOWN - Close < EMA9 < EMA21 + Breakdown
    if close < ema9 < ema21 and close < float(prev["Low"]):
        strike = atm  # PE Strike
        entry = round(close * 0.0045, 2)
        tgt = round(entry * 1.80, 2)
        sl = round(entry * 0.60, 2)
        return ("PE", "STRONG DOWN 📉", entry, tgt, sl, strike)

    return None

# ---------------- DHAN ORDER ----------------
def place_dhan_order(symbol: str, strike: int, option_type: str, qty_lots: int = 1):
    """
    DhanHQ API - Auto Order
    Static IP Vendaam - Render la-ye Work Aagum!
    """
    if not DHAN_ACCESS_TOKEN:
        print("Dhan Token Illa - Paper Trade Mode")
        return None

    lot = get_lot(symbol)
    qty = lot * qty_lots

    url = "https://api.dhan.co/v2/orders"
    headers = {
        "access-token": DHAN_ACCESS_TOKEN,
        "client-id": DHAN_CLIENT_ID,
        "Content-Type": "application/json"
    }
    payload = {
        "dhanClientId": DHAN_CLIENT_ID,
        "transactionType": "BUY",
        "exchangeSegment": "NSE_FNO" if symbol != "SENSEX" else "BSE_FNO",
        "productType": "INTRADAY",
        "orderType": "MARKET",
        "validity": "DAY",
        "securityId": "0",  # Real la - Dhan Instrument List la SecurityId edukkanum
        "quantity": qty,
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"Dhan Order: {r.status_code} {r.text[:200]}")
        return r.json()
    except Exception as e:
        print(f"Dhan Order Error: {e}")
        return None

# ---------------- TRAILING SL ----------------
class TrailingManager:
    def __init__(self, entry: float, sl: float):
        self.entry = entry
        self.sl = sl
        self.highest = entry
        self.trailing_active = False

    def update(self, ltp: float):
        """Optiontrix Style Trailing - Profit 1000 ku Mela Vandha ON"""
        if ltp > self.highest:
            self.highest = ltp

        profit_pts = ltp - self.entry
        # Trailing ON - Profit > 40% of Entry
        if profit_pts > (self.entry * 0.40):
            self.trailing_active = True
            # SL-a - Highest - 20% ku Thooku
            new_sl = round(self.highest * 0.80, 2)
            if new_sl > self.sl:
                self.sl = new_sl
                return f"Trailing SL Updated: Rs {self.sl}"
        return None

# ---------------- MAIN BOT ----------------
sent_signals = set()
active_positions = {}  # symbol -> {entry, sl, tgt, trailing_obj}

def run_once():
    now = datetime.now(IST)
    time_str = now.strftime("%d-%m %I:%M %p")
    print(f"\n--- Check {time_str} ---")

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

        # ✅ CORRECTED MESSAGE - Lot Size Correct!
        msg = (
            f"🚨 BUY {opt_type} - {symbol} {strike} {opt_type}\n"
            f"Entry: Rs {entry} | TGT: Rs {tgt} | SL: Rs {sl}\n"
            f"Lot: {lot} | {strength}\n"
            f"Time: {time_str}"
        )
        send_telegram(msg)

        # Track Position for SL / TGT / Trailing
        active_positions[key] = {
            "symbol": symbol,
            "strike": strike,
            "opt_type": opt_type,
            "entry": entry,
            "sl": sl,
            "tgt": tgt,
            "trailing": TrailingManager(entry, sl),
            "time": time_str,
        }

        # Dhan Auto Order - Paper Trade la Comment Pannidunga!
        # place_dhan_order(symbol, strike, opt_type, qty_lots=1)

    # Check Active Positions - SL / TGT Hit-a?
    check_positions()

def check_positions():
    for key, pos in list(active_positions.items()):
        symbol = pos["symbol"]
        # Real la - Dhan Option Chain / LTP API la LTP edukkanum
        # Ippo - Spot Price la Approx Pannrom - Real Bot la Option LTP Use Pannunga!
        df = get_data(SYMBOLS[symbol], interval="5m", period="1d")
        if df is None:
            continue
        # Dummy LTP - Real Code la - Dhan Quote API Use Pannunga
        # ltp = get_option_ltp(symbol, strike)
        # For Now - Skip - SL/TGT Check will be done via WebSocket / Dhan Feed
        pass

def send_sl_hit(symbol: str, strike: int, opt_type: str, entry: float, sl: float):
    """✅ CORRECTED SL HIT - Lot Size Correct!"""
    full_symbol = f"{symbol} {strike} {opt_type}"
    points, pnl_rs, lot = calc_pnl(full_symbol, entry, sl)
    msg = (
        f"❌ SL HIT\n"
        f"{full_symbol}\n"
        f"Entry Rs {entry} → SL Rs {sl}\n"
        f"{points} Pts | Rs {pnl_rs}"
    )
    send_telegram(msg)
    print(f"SL HIT Corrected: {full_symbol} Lot={lot} P&L={pnl_rs}")

def send_tgt_hit(symbol: str, strike: int, opt_type: str, entry: float, tgt: float):
    """✅ CORRECTED TGT HIT"""
    full_symbol = f"{symbol} {strike} {opt_type}"
    points, pnl_rs, lot = calc_pnl(full_symbol, entry, tgt)
    msg = (
        f"✅ TGT HIT\n"
        f"{full_symbol}\n"
        f"Entry Rs {entry} → TGT Rs {tgt}\n"
        f"+{points} Pts | Rs +{pnl_rs}"
    )
    send_telegram(msg)

# ---------------- TEST - Screenshot Example ----------------
def test_corrected_values():
    print("=== CORRECTED CALCULATION TEST ===")
    # Screenshot Example 1 - NIFTY
    pts, pnl, lot = calc_pnl("NIFTY 25100 PE", 113.97, 68.38)
    print(f"NIFTY 25100 PE | Lot: {lot} | {pts} Pts | Rs {pnl}")
    # Expected: Lot 65 | -45.59 Pts | Rs -2963.35 ✅

    # Screenshot Example 2 - SENSEX
    pts2, pnl2, lot2 = calc_pnl("SENSEX 81400 PE", 320.91, 192.55)
    print(f"SENSEX 81400 PE | Lot: {lot2} | {pts2} Pts | Rs {pnl2}")
    # Expected: Lot 20 | -128.36 Pts | Rs -2567.20 ✅

    # GOLDM - Already Correct
    pts3, pnl3, lot3 = calc_pnl("GOLDM 118200 CE", 792.94, 475.76)
    print(f"GOLDM 118200 CE | Lot: {lot3} | {pts3} Pts | Rs {pnl3}")

if __name__ == "__main__":
    # First - Test Pannunga!
    test_corrected_values()

    # Bot Loop - Render la 5 Min ku Oru Dhadava
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"Loop Error: {e}")
        time.sleep(300)  # 5 Minutes
