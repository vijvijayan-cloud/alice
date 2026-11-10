# V82 - FINAL - Expiry 17NOV26 FIXED - Spot 25044 - ITM1 = 25000 CE
# Contract Master Theda Vendaam - NSE Theda Vendaam - Sample Page-e Proof!

def get_alice_symbol(strike, opt_type):
    # Sample Page Format: "NIFTY 17TH NOV 25000 CE" - Display Format!
    # API Format: "NIFTY 17NOV26 25000 CE" - Order ku Idhu thaan!
    exp = "17NOV26"  # ✅ Sample Page Dropdown la Irukku - 17NOV26!
    alice_sym = f"NIFTY {exp} {strike} {opt_type}"
    display_sym = f"NIFTY 17TH NOV {strike} {opt_type}"
    log(f"✅ Symbol: API:[{alice_sym}] | Display:[{display_sym}] | Spot:25044 | Expiry:17NOV26")
    return alice_sym, None, 65

def place_order_api(strike, opt_type, trans):
    import requests
    sess = STORE.get("session")
    if not sess:
        log("Order Fail: LOGIN pannunga!")
        return {"error": "No Session"}
    alice_sym, token, lot = get_alice_symbol(strike, opt_type)
    qty = 65  # ✅ NIFTY Lot 65 FIXED!
    payload = {
        "userId": USER_ID, "exch": "NFO", "pCode": "MIS",
        "price": 0, "priceType": "MARKET", "qty": qty, "ret": "DAY",
        "tradingSymbol": alice_sym, "transType": trans,
        "trigPrice": 0, "orderTag": "VIJAYAN_ITM1",
        "complexity": "REGULAR", "discQty": 0
    }
    log(f"{trans} Payload: {payload}")
    h = {"Authorization": f"Bearer {sess}", "Content-Type": "application/json", "Accept": "application/json", "userId": USER_ID}
    try:
        r = requests.post(
            "https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/placeOrder/executePlaceOrder",
            headers=h, json=payload, timeout=12
        )
        log(f"{trans} ORDER [{alice_sym}] Qty:{qty} Status:{r.status_code} Resp:{r.text[:1000]}")
        try:
            return r.json()
        except:
            return {"raw": r.text[:1000], "status": r.status_code}
    except Exception as e:
        log(f"Order Err {e}")
        return {"error": str(e)}

# Test Order - DEFAULT-A 25000 CE - 24450 ILLA!
@app.route('/bot/testorder')
def testorder():
    sess = STORE.get("session")
    if not sess:
        log("TEST ORDER Fail: LOGIN pannunga!")
        return redirect("/dashboard")
    strike = int(request.args.get("strike", 25000))  # ✅ 25000 - Sample Page la Irukkuradhu!
    otype = request.args.get("type", "CE")
    log(f"🧪 TEST ORDER - BUY {strike}{otype} - Spot 25044 - ITM1 CE = 25000 CE - LTP 256.05 (Sample Page)")
    res = place_buy(strike, otype)
    log(f"🧪 TEST ORDER Resp: {str(res)[:800]}")
    return redirect("/dashboard")
