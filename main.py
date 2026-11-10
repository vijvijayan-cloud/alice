import os, json, threading, time
from flask import Flask, request, redirect
from datetime import datetime, timedelta, timezone
try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except:
    IST = timezone(timedelta(hours=5, minutes=30))

def ist_now():
    return datetime.now(IST)

app = Flask(__name__)
BOT = {"logs": []}

def log(m):
    t = ist_now().strftime("%H:%M:%S IST")
    BOT["logs"].insert(0, f"[{t}] {m}")
    BOT["logs"] = BOT["logs"][:80]
    print(m)

@app.route('/')
def home():
    return "<h1>V78 - OPTIONS CHAIN CHECK</h1><p><a href='/chain'><button style='padding:15px;background:green;color:white'>🔍 OPTIONS CHAIN FETCH PANNU</button></a></p><p><a href='/dashboard'>Dashboard</a></p>"

@app.route('/dashboard')
def dashboard():
    logs = "<br>".join(BOT["logs"][:80])
    return f"<h1>OPTIONS CHAIN</h1><p><a href='/chain'><button style='padding:12px;background:green;color:white'>🔍 CHAIN FETCH</button></a></p><hr><h2>Logs</h2><p>{logs}</p><p><a href='/dashboard'>Refresh</a></p>"

# ---------- OPTIONS CHAIN ✅ - NSE Direct - Guess Illa! ----------
@app.route('/chain')
def chain():
    import requests
    log("🔍 OPTIONS CHAIN FETCH - NSE Direct!")
    try:
        s = requests.Session()
        # NSE - Cookies Venam - Illa na Block Pannidum!
        h = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/option-chain",
        }
        # 1. Home Page - Cookie Edu!
        s.get("https://www.nseindia.com", headers=h, timeout=10)
        # 2. Option Chain API!
        r = s.get("https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY", headers=h, timeout=15)
        log(f"NSE Chain Status:{r.status_code} Len:{len(r.text)}")
        if r.status_code != 200:
            log(f"❌ NSE Block Panniduchu! Resp:{r.text[:500]}")
            return redirect("/dashboard")
        j = r.json()
        # Expiry List - Idhu thaan Unmai!
        expiries = j.get("records", {}).get("expiryDates", [])
        log(f"✅ LIVE EXPIRIES: {expiries}")
        # Underlying - Spot Price!
        spot = j.get("records", {}).get("underlyingValue", "Theriyaadhu")
        log(f"✅ NIFTY SPOT: {spot}")
        data = j.get("records", {}).get("data", [])
        # Nearest Expiry - First Expiry!
        nearest = expiries[0] if expiries else None
        log(f"✅ NEAREST EXPIRY: {nearest}")
        # 24450 CE - Nearest Expiry la Irukka?
        for row in data:
            if str(row.get("expiryDate", "")) != str(nearest):
                continue
            if int(row.get("strikePrice", 0)) != 24450:
                continue
            ce = row.get("CE", {})
            pe = row.get("PE", {})
            # Identifier - Idhu thaan Real Symbol!
            ce_id = ce.get("identifier", "CE ILLA")
            pe_id = pe.get("identifier", "PE ILLA")
            ce_ltp = ce.get("lastPrice", "?")
            log(f"✅ 24450 CE FOUND! Expiry:{nearest} | Identifier:[{ce_id}] | LTP:{ce_ltp}")
            log(f"   24450 PE Identifier:[{pe_id}]")
            # AliceBlue Symbol-a Maathu!
            # NSE Identifier: OPTIDXNIFTY17-11-2026CE24450.00
            # AliceBlue Symbol: NIFTY 17NOV26 24450 CE
            try:
                # 17-11-2026 -> 17NOV26
                dt = datetime.strptime(nearest, "%d-%b-%Y")
                alice_sym = f"NIFTY {dt.strftime('%d%b%y').upper()} 24450 CE"
                log(f"✅ ALICEBLUE SYMBOL: [{alice_sym}] | Qty: 65 | Expiry: {dt.strftime('%d%b%y').upper()}")
            except Exception as e:
                log(f"Alice Symbol Convert Err {e}")
            break
        else:
            log(f"❌ 24450 CE - Nearest Expiry {nearest} la Illa!")
            # Enna Strikes Irukku? - List pannu!
            strikes = sorted(set([int(x.get("strikePrice", 0)) for x in data if str(x.get("expiryDate", "")) == str(nearest)]))
            log(f"Available Strikes Nearest Expiry la: {strikes[:20]} ... Total {len(strikes)}")
        # ATM Strike - Spot ku Pakkathula Enna Strike?
        try:
            atm = int(round(float(spot) / 50) * 50)
            log(f"✅ ATM: {atm} | ITM 1 CE = {atm - 50} CE | ITM 1 PE = {atm + 50} PE")
        except:
            pass
    except Exception as e:
        log(f"CHAIN Err {e}")
    return redirect("/dashboard")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
