# rsi_alert.py
# Professional swing signal bot
# Indicators: Supertrend + MACD + RSI + Volume + Market filter
# Sends Telegram messages for high-probability swing trades
# Works on Daily timeframe

import os
import requests
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timezone

# --- User config / secrets ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")

# WATCH_LIST should be a comma-separated string in GitHub secrets
# e.g. "RELIANCE.NS,SBIN.NS,TCS.NS,..."
WATCH_LIST = os.getenv(
    "WATCH_LIST",
    "RELIANCE.NS,HDFCBANK.NS,ICICIBANK.NS,INFY.NS,TCS.NS,LT.NS,SBIN.NS,ITC.NS,"
    "HINDUNILVR.NS,AXISBANK.NS,BAJFINANCE.NS,ASIANPAINT.NS,MARUTI.NS,M&M.NS,"
    "SUNPHARMA.NS,TITAN.NS,NTPC.NS,TATASTEEL.NS,ONGC.NS,POWERGRID.NS,ULTRACEMCO.NS,"
    "NESTLEIND.NS,TATACONSUM.NS,WIPRO.NS,HCLTECH.NS,JSWSTEEL.NS,COALINDIA.NS,"
    "ADANIENT.NS,ADANIPORTS.NS,BPCL.NS,BRITANNIA.NS,CIPLA.NS,GRASIM.NS,"
    "HEROMOTOCO.NS,HDFCLIFE.NS,DRREDDY.NS,DIVISLAB.NS,BAJAJFINSV.NS,BAJAJ-AUTO.NS,"
    "EICHERMOT.NS,SHREECEM.NS,UPL.NS,TATAMOTORS.NS,INDUSINDBK.NS,HAVELLS.NS,"
    "TECHM.NS,APOLLOHOSP.NS"
)

# --- Indicator / strategy parameters ---
# Supertrend
ST_PERIOD = 10         # ATR period
ST_MULTIPLIER = 3.0    # factor

# MACD
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# RSI
RSI_PERIOD = 14
RSI_BUY_LOW = 30      # for possible buy zone
RSI_BUY_HIGH = 55     # avoid too overbought for buy
RSI_SELL_HIGH = 65    # threshold for sell (overheated)

# Volume
VOL_LOOKBACK = 20
VOL_MULTIPLIER = 1.5  # require spike

# Market filter (Nifty index)
NIFTY_TICKER = "^NSEI"  # Yahoo Finance ticker for Nifty 50
NIFTY_ST_PERIOD = ST_PERIOD
NIFTY_ST_MULTIPLIER = ST_MULTIPLIER

# Data period
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


def compute_rsi(series: pd.Series, n=RSI_PERIOD):
    d = series.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def compute_macd(df_close: pd.Series):
    ema_fast = df_close.ewm(span=MACD_FAST, adjust=False).mean()
    ema_slow = df_close.ewm(span=MACD_SLOW, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=MACD_SIGNAL, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def compute_supertrend(df, period=ST_PERIOD, multiplier=ST_MULTIPLIER):
    """
    Returns a DataFrame column 'ST' with Supertrend direction:
    +1 for bullish, -1 for bearish
    Also returns 'ST_line' = actual Supertrend value (useful for SL)
    """
    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.rolling(period).mean()  # simple ATR; can use ewm if desired

    # basic upper/lower bands
    upper_band = (high + low) / 2 + multiplier * atr
    lower_band = (high + low) / 2 - multiplier * atr

    st_dir = [1] * len(df)
    st_val = [0.0] * len(df)

    for i in range(len(df)):
        if i == 0:
            st_val[i] = 0.0
            st_dir[i] = 1
            continue

        # Use previous ST to decide
        prev_st_val = st_val[i - 1]
        prev_st_dir = st_dir[i - 1]

        # Current bands
        curr_upper = upper_band.iat[i]
        curr_lower = lower_band.iat[i]

        # Decide ST value
        if close.iat[i] > prev_st_val:
            # bullish
            st_val[i] = curr_lower
            st_dir[i] = 1
        else:
            # bearish
            st_val[i] = curr_upper
            st_dir[i] = -1

        # Correct cross-over cases
        if prev_st_dir == 1 and close.iat[i] < prev_st_val:
            st_dir[i] = -1
            st_val[i] = curr_upper
        elif prev_st_dir == -1 and close.iat[i] > prev_st_val:
            st_dir[i] = 1
            st_val[i] = curr_lower

    df["ST_dir"] = st_dir
    df["ST_line"] = st_val
    return df["ST_dir"], df["ST_line"]


def safe_date_str(idx):
    try:
        return getattr(idx, "date", lambda: idx)()
    except Exception:
        return str(idx)


# --- Market filter for Nifty ---
def get_nifty_trend():
    # download recent data
    df = yf.download(NIFTY_TICKER, period=PERIOD, interval=INTERVAL, progress=False)
    if df is None or df.empty:
        print("No Nifty data")
        return None, None
    # compute ST for Nifty
    df["ST_dir"], df["ST_line"] = compute_supertrend(
        df, period=NIFTY_ST_PERIOD, multiplier=NIFTY_ST_MULTIPLIER
    )
    # last valid
    last_valid = df["ST_dir"].dropna()
    if last_valid.empty:
        return None, None
    last_idx = last_valid.index[-1]
    return df.at[last_idx, "ST_dir"], df.at[last_idx, "ST_line"]


# --- Main scanner ---
def scan_and_alert():
    results = []

    # market trend
    nifty_dir, nifty_line = get_nifty_trend()
    print("Nifty trend:", nifty_dir, "line:", nifty_line)

    # If market trend unknown, skip aggressive alerts
    if nifty_dir is None:
        print("Market trend unknown, skipping signals")
        return

    # parse watchlist
    symbols = [s.strip() for s in WATCH_LIST.split(",") if s.strip()]

    for sym in symbols:
        print("Scanning:", sym)

        # download data
        df = yf.download(sym, period=PERIOD, interval=INTERVAL, progress=False)
        if df is None or df.empty:
            print("No data for", sym)
            continue

        # must have required columns
        if "Close" not in df.columns or "Volume" not in df.columns:
            print("Missing columns:", df.columns)
            continue

        # indicators
        df["RSI"] = compute_rsi(df["Close"])
        df["VOL_AVG"] = df["Volume"].rolling(VOL_LOOKBACK).mean()
        df["MACD"], df["MACD_SIGNAL"], df["MACD_HIST"] = compute_macd(df["Close"])
        df["ST_dir"], df["ST_line"] = compute_supertrend(df)

        # last valid index for RSI
        valid_idx = df["RSI"].dropna().index
        if valid_idx.empty:
            print("RSI empty for", sym)
            continue
        last_idx = valid_idx[-1]

        # last scalars
        try:
            last_rsi = float(df.at[last_idx, "RSI"])
            last_close = float(df.at[last_idx, "Close"))
            last_vol = float(df.at[last_idx, "Volume"))
            vol_avg = float(df.at[last_idx, "VOL_AVG"))
            macd_val = float(df.at[last_idx, "MACD"))
            macd_sig = float(df.at[last_idx, "MACD_SIGNAL"))
            st_dir = int(df.at[last_idx, "ST_dir"))
            st_line = float(df.at[last_idx, "ST_line"))
        except Exception as e:
            print("Data scalar error for", sym, e)
            continue

        # volume spike
        vol_spike = False
        if not np.isnan(last_vol) and not np.isnan(vol_avg) and vol_avg > 0:
            vol_spike = last_vol > (VOL_MULTIPLIER * vol_avg)

        # store result
        results.append((sym, last_idx, last_close, last_rsi, last_vol, vol_avg))

        # --- MARKET FILTER ---
        # If Nifty uptrend: allow only BUY conditions
        # If Nifty downtrend: allow only SELL conditions
        # NOTE: 1 = up, -1 = down
        allow_buy = allow_sell = False
        if nifty_dir == 1:
            allow_buy = True
        elif nifty_dir == -1:
            allow_sell = True
        else:
            # neither clear up nor down
            pass

        # --- SIGNAL LOGIC ---
        signal_msg = None

        # ----- BUY conditions -----
        if allow_buy:
            # Supertrend must be bullish for stock
            if st_dir == 1:
                # MACD bullish
                if macd_val > macd_sig:
                    # RSI healthy zone for buy
                    if RSI_BUY_LOW <= last_rsi <= RSI_BUY_HIGH:
                        # volume spike for confirmation (optional strong)
                        if vol_spike:
                            signal_msg = (
                                "🟢 SWING BUY CONFIRMED\n"
                                f"Symbol: {sym}\n"
                                f"Date: {safe_date_str(last_idx)}\n"
                                f"Price: {last_close:.2f}\n"
                                f"Trend: UP (Supertrend)\n"
                                f"RSI: {last_rsi:.1f}\n"
                                f"MACD: {macd_val:.2f} > {macd_sig:.2f}\n"
                                f"Volume spike: {int(last_vol)} (avg {int(vol_avg)})\n"
                                f"SL: {st_line:.2f}"
                            )

        # ----- SELL / EXIT conditions -----
        if allow_sell and signal_msg is None:
            # Supertrend bearish
            if st_dir == -1:
                # MACD bearish
                if macd_val < macd_sig:
                    # RSI overheated zone
                    if last_rsi >= RSI_SELL_HIGH:
                        signal_msg = (
                            "🔴 SWING SELL/EXIT CONFIRMED\n"
                            f"Symbol: {sym}\n"
                            f"Date: {safe_date_str(last_idx)}\n"
                            f"Price: {last_close:.2f}\n"
                            f"Trend: DOWN (Supertrend)\n"
                            f"RSI: {last_rsi:.1f}\n"
                            f"MACD: {macd_val:.2f} < {macd_sig:.2f}\n"
                            f"SL: {st_line:.2f}"
                        )

        # Send if message built
        if signal_msg:
            print("Signal found:", sym)
            send_telegram(signal_msg)
        else:
            print(f"No signal for {sym} (RSI {last_rsi:.1f}, Trend {st_dir})")

    # summary logs
    print("Scan finished at", datetime.now(timezone.utc).isoformat())
    for r in results:
        print(r)


if __name__ == "__main__":
    try:
        scan_and_alert()
    except Exception as e:
        print("Fatal error in main:", e)
        # optionally send telegram about failure
        # send_telegram(f"Script failed: {e}")
