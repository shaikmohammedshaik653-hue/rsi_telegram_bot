# rsi_alert.py
# Daily RSI + Volume scanner with Telegram alerts

import os
import requests
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timezone

# ------------------- Config from GitHub Secrets -------------------

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID   = os.getenv("CHAT_ID", "")

# Comma separated list in GitHub secret WATCH_LIST
# Example: "RELIANCE.NS,HDFCBANK.NS,TCS.NS"
WATCH_LIST = os.getenv(
    "WATCH_LIST",
    "RELIANCE.NS,HDFCBANK.NS"
).split(",")

# RSI & Volume settings
RSI_OVERSOLD   = 30        # BUY zone
RSI_OVERBOUGHT = 70        # SELL zone
VOL_LOOKBACK   = 20        # days for avg volume
VOL_MULTIPLIER = 1.5       # spike if vol > 1.5 * avg

PERIOD   = "2y"
INTERVAL = "1d"

# ------------------- Helpers -------------------
def send_telegram(msg: str):
    """Send message to Telegram chat."""
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ Telegram creds missing.")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg[:4000]})
    except Exception as e:
        print("Telegram error:", e)


def rsi(series: pd.Series, n: int = 14) -> pd.Series:
    """Standard RSI calculation."""
    d = series.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


# ------------------- Main Scanner -------------------

def scan_and_alert():
    results = []

    for sym in WATCH_LIST:
        sym = sym.strip()
        if not sym:
            continue

        print("\n-----------------------------")
        print("🔎 Scanning:", sym)

        # ---- Download data safely ----
        try:
            df = yf.download(
                sym,
                period=PERIOD,
                interval=INTERVAL,
                auto_adjust=True,
                progress=False,
            )
        except Exception as e:
            print("yfinance download error for", sym, "->", e)
            continue

        if df is None or df.empty:
            print("No data for", sym)
            continue

        if "Close" not in df.columns:
            print("No Close column for", sym)
            continue

        if "Volume" not in df.columns:
            print("No Volume column for", sym)
            continue

        # ---- Indicators ----
        close = df["Close"]
        df["RSI"] = rsi(close)
        df["vol_avg"] = df["Volume"].rolling(VOL_LOOKBACK).mean()

        # Ensure we have at least one valid RSI
        valid_rsi = df["RSI"].dropna()
        if valid_rsi.empty:
            print("RSI all NaN for", sym)
            continue

        last_idx = valid_rsi.index[-1]

        last_rsi   = float(df.loc[last_idx, "RSI"])
        last_close = float(df.loc[last_idx, "Close"])
        last_vol   = df.loc[last_idx, "Volume"]
        vol_avg    = df.loc[last_idx, "vol_avg"]

        if pd.isna(last_vol).any() or pd.isna(vol_avg).any():
            print("Volume/avg NaN for", sym)
            continue

        time_idx = last_idx
        vol_spike = last_vol > VOL_MULTIPLIER * vol_avg

        results.append(
            (
                sym,
                time_idx,
                float(last_close),
                float(last_rsi),
                int(last_vol),
                int(vol_avg),
            )
        )

        print(f"Last RSI: {last_rsi:.1f}, Close: {last_close:.2f}")
        print(f"Volume: {last_vol:.0f}, AvgVol({VOL_LOOKBACK}): {vol_avg:.0f}")
        print("Volume spike?" , vol_spike)

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

        if signal_msg:
            print("✅ Signal generated for", sym)
            send_telegram(signal_msg)
        else:
            print("No trade signal for", sym)

    # ---- Summary ----
    print("\n===== Scan done at", datetime.now(timezone.utc).astimezone().isoformat(), "=====")
    for r in results:
        print(r)


# ------------------- Entry Point -------------------

if __name__ == "__main__":
    scan_and_alert()
