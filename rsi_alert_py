# rsi_alert.py
# Simple RSI scanner + Telegram notifier (daily)
import os, requests, yfinance as yf, pandas as pd, numpy as np
from datetime import datetime, timezone

# Config via env (set these in GitHub repo secrets)
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID   = os.getenv("CHAT_ID", "")
WATCH_LIST = os.getenv("WATCH_LIST", "RELIANCE.NS,HDFCBANK.NS").split(",")

RSI_THR = 70
PERIOD = "2y"
INTERVAL = "1d"

def send_telegram(msg: str):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ Telegram creds missing.")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg[:4000]})
    except Exception as e:
        print("Telegram error:", e)

def rsi(series: pd.Series, n=14):
    d = series.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def scan_and_alert():
    results = []
    for sym in WATCH_LIST:
        sym = sym.strip()
        if not sym:
            continue
        print("Downloading", sym)
        df = yf.download(sym, period=PERIOD, interval=INTERVAL, auto_adjust=True, progress=False)
        if df.empty:
            print("No data for", sym)
            continue
        close = df["Close"]
        df["RSI"] = rsi(close)
        # check last row RSI > threshold
        last_rsi = df["RSI"].iloc[-1]
        last_close = close.iloc[-1]
        time = df.index[-1]
        results.append((sym, time, float(last_close), float(last_rsi)))
        # If RSI > threshold -> send
        if last_rsi > RSI_THR:
            msg = f"🔔 {sym} RSI > {RSI_THR}\nTime: {time.date()}\nClose: {last_close:.2f}\nRSI: {last_rsi:.1f}"
            send_telegram(msg)
            print("Alert sent for", sym)
    # optional: print summary
    print("Scan done at", datetime.now(timezone.utc).astimezone().isoformat())
    for r in results:
        print(r)

if __name__ == "__main__":
    scan_and_alert()
