# ---------- ALICE BLUE LOGIN - ALL VERSION FIX ----------
alice = None
def alice_login():
    global alice
    try:
        if MODE == "PAPER":
            state["login"] = f"PAPER READY - User {USER_ID[:3]}*** - No Real Money"
            return True

        from alice_blue import AliceBlue
        import inspect
        print("AliceBlue Methods:", [m for m in dir(AliceBlue) if 'login' in m.lower() or 'session' in m.lower() or 'token' in m.lower()])

        if not TOTP_SECRET or not APP_ID or not APP_SECRET:
            state["login"] = "LIVE ERROR - APP_ID / APP_SECRET / TOTP Missing"
            return False

        totp = pyotp.TOTP(TOTP_SECRET).now()
        
        # Try 1 - Pazhaya Method
        if hasattr(AliceBlue, 'login_and_get_access_token'):
            access_token = AliceBlue.login_and_get_access_token(
                username=USER_ID, password=PASSWORD, twoFA=totp,
                api_secret=APP_SECRET, app_id=APP_ID
            )
            alice = AliceBlue(username=USER_ID, access_token=access_token)
            state["login"] = f"LIVE READY - User {USER_ID[:3]}*** - REAL MONEY"
            return True

        # Try 2 - Pudhu Method - sessionID
        if hasattr(AliceBlue, 'login_and_get_sessionID'):
            session_id = AliceBlue.login_and_get_sessionID(
                username=USER_ID, password=PASSWORD, twoFA=totp,
                api_secret=APP_SECRET, app_id=APP_ID
            )
            alice = AliceBlue(username=USER_ID, session_id=session_id)
            state["login"] = f"LIVE READY - User {USER_ID[:3]}*** - REAL MONEY"
            return True

        # Try 3 - Pudhu Method - get_access_token
        if hasattr(AliceBlue, 'login_and_get_access_token_v2'):
            access_token = AliceBlue.login_and_get_access_token_v2(
                username=USER_ID, password=PASSWORD, twoFA=totp,
                api_secret=APP_SECRET, app_id=APP_ID
            )
            alice = AliceBlue(username=USER_ID, access_token=access_token)
            state["login"] = f"LIVE READY - User {USER_ID[:3]}*** - REAL MONEY"
            return True

        state["login"] = f"LIVE ERROR - No Login Method Found - Methods: {dir(AliceBlue)}"
        return False

    except Exception as e:
        state["login"] = f"LOGIN ERROR: {e}"
        print(traceback.format_exc())
        return False
