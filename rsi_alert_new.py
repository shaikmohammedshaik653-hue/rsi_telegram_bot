import os
import yfinance as yf
import pandas as pd
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

WATCH_LIST = ["IRCON.NS","NBCC.NS","SJVN.NS"]

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg})

def rsi(data, period=14):
    delta = data.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def run():
    for stock in WATCH_LIST:
        df = yf.download(stock, period="1mo", interval="1d", progress=False)
        df["RSI"] = rsi(df["Close"])

        price = float(df["Close"].iloc[-1])
        rsi_val = float(df["RSI"].iloc[-1])

        if rsi_val < 60:
            msg = f"{stock} BUY | Price: {price:.2f} | RSI: {rsi_val:.1f}"
            print(msg)
            send_telegram(msg)

if __name__ == "__main__":
    run()
