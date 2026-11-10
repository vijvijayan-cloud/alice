import os, hashlib, json, threading, time
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

def clean(n):
    return os.getenv(n, "").strip().replace('"', "").replace("'", "")
USER_ID = clean("ALICE_USER_ID")
APP_ID = clean("ALICE_APP_ID")
APP_SECRET = clean("ALICE_APP_SECRET")
STORE = {"session": None}
BOT = {"logs": [], "status": "STOPPED", "funds": 0}

def log(m):
    t = ist_now().strftime("%H:%M:%S IST")
    BOT["logs"].insert(0, f"[{t}] {m}")
    BOT["logs"] = BOT["logs"][:80]
    print(m)

@app.route('/')
def home():
    return f"<h1>V77 - CHECK NOW</h1><p><a href='/check_symbol'><button style='padding:15px;background:green;color:white'>🔍 CHECK NOW - 24450 CE Symbol Enna?</button></a></p><p><a href='/dashboard'>Dashboard</a></p>"

@app.route('/dashboard')
def dashboard():
    logs = "<br>".join(BOT["logs"][:80])
    return f"<h1>CHECK NOW</h1><p><a href='/check_symbol'><button style='padding:12px;background:green;color:white'>🔍 CHECK NOW</button></a></p><hr><h2>Logs</h2><p>{logs}</p><p><a href='/dashboard'>Refresh</a></p>"

# ---------- CHECK NOW ✅ - Expiry Guess Illa - Strike 24450 CE nu Mattum Thedu! ----------
@app.route('/check_symbol')
def check_symbol():
    import requests
    log("🔍 CHECK NOW START - Strike 24450 CE - Expiry Guess Illa!")
    try:
        r = requests.get("https://v2api.aliceblueonline.com/restpy/contract_master?exch=NFO", timeout=25)
        log(f"Contract Master Status:{r.status_code} Len:{len(r.text)}")
        txt = r.text
        found = []
        total = 0
        for line in txt.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            total += 1
            try:
                j = json.loads(line)
            except:
                continue
            # 1. OPTIDX mattum
            if j.get("instrument_type") != "OPTIDX":
                continue
            # 2. CE mattum
            if str(j.get("option_type", "")).upper() != "CE":
                continue
            # 3. Strike 24450 mattum
            try:
                if int(float(str(j.get("strike_price", "0")))) != 24450:
                    continue
            except:
                continue
            # 4. NIFTY mattum - BANKNIFTY / FINNIFTY / MIDCP - Ellam SKIP!
            fname = str(j.get("formatted_ins_name", "")).strip()
            if not fname.upper().startswith("NIFTY "):
                continue
            # Kedaichiduchu!
            # Expiry Timestamp-a Date-a Maathu!
            try:
                exp_ms = int(j.get("expiry_date", 0))
                exp_dt = datetime.fromtimestamp(exp_ms/1000, tz=IST)
                exp_str = exp_dt.strftime("%d %b %Y - %A - %d%b%y")
            except Exception as e:
                exp_str = f"Expiry Decode Fail {j.get('expiry_date')} Err {e}"
            # Token - Ella Field-um Paaru!
            token = j.get("token") or j.get("instrument_token") or j.get("Token") or j.get("exchange_token") or "TOKEN FIELD ILLA"
            lot = j.get("lot_size", "LOT ILLA")
            log(f"✅ FOUND! Name:[{fname}] | Expiry:{exp_str} | Token:{token} | Lot:{lot} | Full:{str(j)[:600]}")
            found.append(j)
            if len(found) >= 10:
                break
        log(f"Total JSON Lines Checked: {total} | NIFTY 24450 CE Found: {len(found)}")
        if len(found) == 0:
            log("❌ 24450 CE - NIFTY la Illa! - Strike / Expiry Vera? - Adutha Check: 24500 CE Paakren!")
            # Fallback - 24500 CE Check pannu - Adhu Irukka?
            for line in txt.splitlines():
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    j = json.loads(line)
                except:
                    continue
                if j.get("instrument_type") != "OPTIDX":
                    continue
                if str(j.get("option_type", "")).upper() != "CE":
                    continue
                try:
                    if int(float(str(j.get("strike_price", "0")))) != 24500:
                        continue
                except:
                    continue
                fname = str(j.get("formatted_ins_name", "")).strip()
                if not fname.upper().startswith("NIFTY "):
                    continue
                log(f"Fallback 24500 CE Found: [{fname}] Full:{str(j)[:400]}")
                break
    except Exception as e:
        log(f"CHECK Err {e}")
    return redirect("/dashboard")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
