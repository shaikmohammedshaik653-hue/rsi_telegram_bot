# rsi_alert.py
# RSI scanner + Telegram notifier (daily)
import os
import requests
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timezone

# --- Config via env (must match your GitHub Secrets names) ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID   = os.getenv("CHAT_ID", "")
WATCH_LIST = os.getenv("WATCH_LIST", "RELIANCE.NS,HDFCBANK.NS").split(",")

RSI_THR = 70
PERIOD = "2y"
INTERVAL = "1d"

# --- Telegram sender with logging ---
def send_telegram(msg: str):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ Telegram creds missing. BOT_TOKEN present?", bool(BOT_TOKEN), "CHAT_ID present?", bool(CHAT_ID))
        return None
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, data={"chat_id": CHAT_ID, "text": msg[:4000]})
        print("Telegram send status:", r.status_code)
        try:
            j = r.json()
            print("Telegram response:", j)
            return j
        except Exception:
            print("Telegram response (raw):", r.text)
            return None
    except Exception as e:
        print("Telegram request exception:", e)
        return None

# --- RSI calculation ---
def rsi(series: pd.Series, n=14):
    d = series.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

# --- Scanner ---
def scan_and_alert():
    results = []
    for sym in WATCH_LIST:
        sym = sym.strip()
        if not sym:
            continue
        print("Downloading", sym)
        try:
            df = yf.download(sym, period=PERIOD, interval=INTERVAL, auto_adjust=True, progress=False)
        except Exception as e:
            print("yfinance download error for", sym, e)
            continue

        if df is None or df.empty:
            print("No data for", sym)
            continue

        close = df["Close"]
        df["RSI"] = rsi(close)

        # ensure we have at least one non-nan RSI
        if df["RSI"].dropna().empty:
            print("RSI all NaN for", sym, "- skipping")
            continue

        # get last valid values (avoid Series)
        last_idx = df["RSI"].dropna().index[-1]
        last_rsi = float(df.loc[last_idx, "RSI"])
        last_close = float(df.loc[last_idx, "Close"])
        time_idx = last_idx  # pandas Timestamp

        results.append((sym, time_idx, last_close, last_rsi))

        # If RSI > threshold -> send
        if last_rsi > RSI_THR:
            msg = (
                f"🔔 {sym} RSI > {RSI_THR}\n"
                f"Time: {getattr(time_idx, 'date', lambda: time_idx)()}\n"
                f"Close: {last_close:.2f}\n"
                f"RSI: {last_rsi:.1f}"
            )
            print("Prepared message:", msg)
            send_telegram(msg)
            print("Alert sent for", sym)
        else:
            print(f"No alert for {sym} (RSI={last_rsi:.1f})")

    print("Scan done at", datetime.now(timezone.utc).astimezone().isoformat())
    for r in results:
        print(r)

# --- Main: temporary safe test + normal run ---
if __name__ == "__main__":
    # TEMP TEST: send one test message from GitHub Actions to verify connection.
    # AFTER you confirm test message received, remove or comment out the next line.
    try:

    except Exception as e:
        print("Test send failed:", e)

    # Now run the normal scan (will send alerts only if RSI > threshold)
    scan_and_alert()
    
