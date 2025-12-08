import os, requests, yfinance as yf, pandas as pd, numpy as np
from datetime import datetime, timezone

# Load secrets from GitHub Actions environment
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID   = os.getenv("CHAT_ID", "")
WATCH_LIST = os.getenv("WATCH_LIST", "RELIANCE.NS,ICICIBANK.NS").split(",")

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

        # Last valid RSI
        if df["RSI"].dropna().empty:
            print("RSI all NaN for", sym)
            continue

        last_idx = df["RSI"].dropna().index[-1]
        last_rsi = float(df.loc[last_idx, "RSI"])
        last_close = float(df.loc[last_idx, "Close"])
        time_idx = last_idx

        results.append((sym, time_idx, last_close, last_rsi))

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
      # --- Main execution block ---
if __name__ == "__main__":
    # Now run main RSI scanner
    scan_and_alert()
