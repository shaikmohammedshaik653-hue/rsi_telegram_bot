import os
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timezone

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")
WATCH_LIST = os.getenvWATCH_LIST = [
    "RELIANCE.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS","TCS.NS",
    "LT.NS","SBIN.NS","BHARTIARTL.NS","KOTAKBANK.NS","ITC.NS",
    "HINDUNILVR.NS","AXISBANK.NS","BAJFINANCE.NS","ASIANPAINT.NS",
    "MARUTI.NS","M&M.NS","SUNPHARMA.NS","TITAN.NS","NTPC.NS",
    "TATASTEEL.NS","ONGC.NS","POWERGRID.NS","ULTRACEMCO.NS",
    "NESTLEIND.NS","TATACONSUM.NS","WIPRO.NS","HCLTECH.NS",
    "JSWSTEEL.NS","COALINDIA.NS","ADANIENT.NS","ADANIPORTS.NS",
    "BPCL.NS","BRITANNIA.NS","CIPLA.NS","GRASIM.NS",
    "HEROMOTOCO.NS","HDFCLIFE.NS","DRREDDY.NS","DIVISLAB.NS",
    "BAJAJFINSV.NS","BAJAJ-AUTO.NS","EICHERMOT.NS","SHREECEM.NS",
    "UPL.NS","TATAMOTORS.NS","INDUSINDBK.NS","HAVELLS.NS",
    "TECHM.NS","APOLLOHOSP.NS"
]

RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
PERIOD = "1y"
INTERVAL = "1d"


def send_telegram(msg: str):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ Telegram creds missing")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
        print("Telegram sent")
    except Exception as e:
        print("Telegram error:", e)


def rsi(series: pd.Series, n=14):
    d = series.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    rs = up / dn.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))


def scan_and_alert():
    symbols = [s.strip() for s in WATCH_LIST.split(",")]
    print("Scanning:", symbols)

    for sym in symbols:
        print(f"🔍 Fetching: {sym}")
        df = yf.download(sym, period=PERIOD, interval=INTERVAL, progress=False)

        if df.empty:
            print("No data for", sym)
            continue

        df["RSI"] = rsi(df["Close"])
        valid = df["RSI"].dropna()

        if valid.empty:
            print("No valid RSI for", sym)
            continue

        last_idx = valid.index[-1]
        last_rsi = float(df.loc[last_idx, "RSI"])
        last_close = float(df.loc[last_idx, "Close"])

        print(f"{sym} → RSI: {last_rsi:.1f}  Close: {last_close}")

        msg = None

        if last_rsi <= RSI_OVERSOLD:
            msg = (
                f"🟢 BUY POSSIBLE\n"
                f"{sym}\n"
                f"Price: {last_close:.2f}\n"
                f"RSI: {last_rsi:.1f} (Oversold)"
            )

        elif last_rsi >= RSI_OVERBOUGHT:
            msg = (
                f"🔴 SELL / EXIT POSSIBLE\n"
                f"{sym}\n"
                f"Price: {last_close:.2f}\n"
                f"RSI: {last_rsi:.1f} (Overbought)"
            )

        if msg:
            send_telegram(msg)
        else:
            print("No alert condition")


if __name__ == "__main__":
    print("Scan started", datetime.now(timezone.utc).isoformat())
    scan_and_alert()
    print("Scan finished", datetime.now(timezone.utc).isoformat())
