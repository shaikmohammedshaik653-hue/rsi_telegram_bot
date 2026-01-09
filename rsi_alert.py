import os
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timezone

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")

WATCH_LIST = os.getenv(
    "WATCH_LIST",
    "ADANIENT.NS,ADANIPORTS.NS,APOLLOHOSP.NS,ASIANPAINT.NS,AXISBANK.NS,"
    "BAJAJ-AUTO.NS,BAJFINANCE.NS,BAJAJFINSV.NS,BPCL.NS,BHARTIARTL.NS,"
    "BRITANNIA.NS,CIPLA.NS,COALINDIA.NS,DIVISLAB.NS,DRREDDY.NS,"
    "EICHERMOT.NS,GRASIM.NS,HCLTECH.NS,HDFCBANK.NS,HDFCLIFE.NS,"
    "HEROMOTOCO.NS,HINDALCO.NS,HINDUNILVR.NS,ICICIBANK.NS,ITC.NS,"
    "INDUSINDBK.NS,INFY.NS,JSWSTEEL.NS,KOTAKBANK.NS,LT.NS,"
    "M&M.NS,MARUTI.NS,NESTLEIND.NS,NTPC.NS,ONGC.NS,"
    "POWERGRID.NS,RELIANCE.NS,SBIN.NS,SBILIFE.NS,"
    "SUNPHARMA.NS,TATAMOTORS.NS,TATASTEEL.NS,TCS.NS,"
    "TECHM.NS,TITAN.NS,ULTRACEMCO.NS,WIPRO.NS"
).split(",")

RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
VOL_LOOKBACK = 20

# ================== TELEGRAM ==================
def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram creds missing")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg})

# ================== INDICATORS ==================
def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def macd(close):
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9).mean()
    return macd_line, signal

def supertrend(df, period=10, multiplier=3):
    hl2 = (df["High"] + df["Low"]) / 2
    atr = df["High"].rolling(period).max() - df["Low"].rolling(period).min()
    upper = hl2 + multiplier * atr
    lower = hl2 - multiplier * atr

    st = [True]
    for i in range(1, len(df)):
        if df["Close"].iloc[i] > upper.iloc[i-1]:
            st.append(True)
        elif df["Close"].iloc[i] < lower.iloc[i-1]:
            st.append(False)
        else:
            st.append(st[i-1])
    return pd.Series(st, index=df.index)

# ================== MAIN LOGIC ==================
def scan():
    print("Scan started", datetime.now(timezone.utc))

    for sym in WATCH_LIST:
        try:
            df = yf.download(sym, period="6mo", interval="1d", progress=False)
            if len(df) < 50:
                continue

            df["RSI"] = rsi(df["Close"])
            df["MACD"], df["MACD_SIGNAL"] = macd(df["Close"])
            df["ST"] = supertrend(df)
            df["VOL_AVG"] = df["Volume"].rolling(VOL_LOOKBACK).mean()

            last = df.iloc[-1]

            price = float(last["Close"])
            rsi_v = float(last["RSI"])
            macd_v = float(last["MACD"])
            macd_s = float(last["MACD_SIGNAL"])
            st_up = bool(last["ST"])
            vol_ok = last["Volume"] > last["VOL_AVG"]

            # ================== SIGNALS ==================
            signal = None

            if st_up and rsi_v < 40 and macd_v > macd_s and vol_ok:
                signal = f"""🟢 STRONG BUY
{sym}
Price: {price:.2f}
RSI: {rsi_v:.1f}
Trend: Supertrend Bullish
MACD: Bullish
Volume: High"""

            elif st_up and rsi_v < 40:
                signal = f"""🟡 WEAK BUY (Watch)
{sym}
Price: {price:.2f}
RSI: {rsi_v:.1f}
Trend: Bullish
Waiting confirmation"""

            elif (not st_up) and macd_v < macd_s:
                signal = f"""🔴 SELL / EXIT
{sym}
Price: {price:.2f}
RSI: {rsi_v:.1f}
Trend: Bearish"""

            if signal:
                print(signal)
                send_telegram(signal)

        except Exception as e:
            print(f"Error in {sym}:", e)

    print("Scan finished")

# ================== RUN ==================
if __name__ == "__main__":
    scan()
