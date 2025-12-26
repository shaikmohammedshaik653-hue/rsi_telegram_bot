# rsi_alert.py
# Simple RSI + Volume scanner -> Telegram notifier
# Put this file in your repo, set BOT_TOKEN, CHAT_ID, WATCH_LIST as GitHub secrets.

import os
import requests
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timezone

# --- Config (tweak) ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")
WATCH_LIST = os.getenv("WATCH_LIST", "RELIANCE.NS,ICICIBANK.NS").split(",")
RSI_PERIOD = 14
VOL_LOOKBACK = 20
VOL_MULTIPLIER = 2.0
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
NEAR_RSI_LOW = 32
NEAR_RSI_HIGH = 40
PERIOD = "2y"
INTERVAL = "1d"

# --- Helpers ---
def send_telegram(msg: str):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ Telegram creds missing.")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg[:4000]})
    except Exception as e:
        print("Telegram error:", e)

def rsi(series: pd.Series, n=RSI_PERIOD):
    d = series.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def safe_date_str(index_label):
    # index_label often is Timestamp; else return str
    try:
        return getattr(index_label, "date", lambda: index_label)()
    except Exception:
        return str(index_label)

# --- Main scan ---
def scan_and_alert():
    results = []
    for sym in WATCH_LIST:
        sym = sym.strip()
        if not sym:
            continue
        print("🔎 Scanning:", sym)
        try:
            df = yf.download(sym, period=PERIOD, interval=INTERVAL, auto_adjust=True, progress=False)
        except Exception as e:
            print("yfinance download error for", sym, e)
            continue

        if df is None or df.empty:
            print("No data for", sym)
            continue

        # Ensure required columns exist
        if "Close" not in df.columns or "Volume" not in df.columns:
            print("Missing required columns for", sym, "cols:", df.columns.tolist())
            continue

        # Compute RSI and volume average
        df["RSI"] = rsi(df["Close"])
        df["vol_avg"] = df["Volume"].rolling(VOL_LOOKBACK).mean()

        # Ensure at least one valid RSI
        valid_rsi = df["RSI"].dropna()
        if valid_rsi.empty:
            print("RSI all NaN for", sym)
            continue

        last_label = valid_rsi.index[-1]

        # Convert label -> integer position safely using get_indexer
        pos_arr = df.index.get_indexer_for([last_label])
        if pos_arr.size == 0 or pos_arr[0] < 0:
            print("Could not get integer position for", sym, "label:", last_label)
            continue
        pos = int(pos_arr[0])

        # Use iloc to get single row
        row = df.iloc[pos]

        # Safe scalar conversions:
        try:
            last_rsi = float(row["RSI"])
        except Exception:
            print("Invalid RSI scalar for", sym, "value:", row.get("RSI"))
            continue
        try:
            last_close = float(row["Close"])
        except Exception:
            print("Invalid Close scalar for", sym, "value:", row.get("Close"))
            continue

        # Volume values (may be NaN)
        last_vol = row.get("Volume", np.nan)
        vol_avg = row.get("vol_avg", np.nan)
        try:
            last_vol_f = float(last_vol) if not pd.isna(last_vol) else np.nan
        except Exception:
            last_vol_f = np.nan
        try:
            vol_avg_f = float(vol_avg) if not pd.isna(vol_avg) else np.nan
        except Exception:
            vol_avg_f = np.nan

        if pd.isna(last_vol_f) or pd.isna(vol_avg_f):
            print("Volume/avg NaN for", sym, "vol:", last_vol, "vol_avg:", vol_avg)
            continue

        vol_spike = last_vol_f > (VOL_MULTIPLIER * vol_avg_f)

        results.append((sym, last_label, last_close, last_rsi, int(last_vol_f), int(vol_avg_f)))

        print(f"Last RSI: {last_rsi:.1f}, Close: {last_close:.2f}")
        print(f"Volume: {last_vol_f:.0f}, AvgVol({VOL_LOOKBACK}): {vol_avg_f:.0f}")
        print("Volume spike?", vol_spike)

        # ---- Signal logic ----
        signal_msg = None

        # BUY: oversold + volume spike
        if last_rsi <= RSI_OVERSOLD and vol_spike:
            signal_msg =(
                "🟢 BUY SIGNAL\n"
                f"Symbol: {sym}\n"
                f"Date: {safe_date_str(last_label)}\n"
                f"Close: {last_close:.2f}\n"
                f"RSI: {last_rsi:.1f} (Oversold)\n"
                f"Volume: {int(last_vol_f)} (>{VOL_MULTIPLIER}x avg)\n\n"
                f"Buy Above: {last_close:.2f}\n"
                f"Stoploss: {last_close * 0.98:.2f}\n"
                f"Target1: {last_close * 1.02:.2f}\n"
                f"Target2: {last_close * 1.03:.2f}"
            )
                # ---- Signal Logic ----
signal_msg = None

# BUY: Oversold + Volume spike
if last_rsi <= RSI_OVERSOLD and vol_spike:
    signal_msg = (
        "🟢 BUY SIGNAL\n"
        f"Symbol: {sym}\n"
        f"Date: {getattr(time_idx, 'date', lambda: time_idx)()}\n"
        f"Close: {last_close:.2f}\n"
        f"RSI: {last_rsi:.1f} (Oversold)\n"
        f"Volume: {last_vol:.0f} (>{VOL_MULTIPLIER}x avg)\n\n"
        f"Buy Above: {last_close:.2f}\n"
        f"Stoploss: {last_close * 0.98:.2f}\n"
        f"Target 1: {last_close * 1.02:.2f}\n"
        f"Target 2: {last_close * 1.03:.2f}"
    )

# SELL: Overbought + Volume spike
elif last_rsi >= RSI_OVERBOUGHT and vol_spike:
    signal_msg = (
        "🔴 SELL SIGNAL\n"
        f"Symbol: {sym}\n"
        f"Date: {getattr(time_idx, 'date', lambda: time_idx)()}\n"
        f"Close: {last_close:.2f}\n"
        f"RSI: {last_rsi:.1f} (Overbought)\n"
        f"Volume: {last_vol:.0f} (>{VOL_MULTIPLIER}x avg)\n\n"
        f"Sell Below: {last_close:.2f}\n"
        f"Stoploss: {last_close * 1.02:.2f}\n"
        f"Target 1: {last_close * 0.98:.2f}\n"
        f"Target 2: {last_close * 0.97:.2f}"
    )
    # SEND TELEGRAM
    if signal_msg:
        print("Prepared message:", signal_msg.replace("\n", " | "))
        send_telegram(signal_msg)
        print("Alert sent for", sym)
    else:
        print(f"No alert for {sym} (RSI={last_rsi:.1f}, spike={vol_spike})")

# -------- SUMMARY PRINT --------
print("Scan finished at", datetime.now(timezone.utc).isoformat())

for r in results:
    print(r)


if __name__ == "__main__":
    try:
        scan_and_alert()
    except Exception as e:
        print("Fatal error in main:", e)
        # send_telegram(f"Script failed: {e}")  # optional
