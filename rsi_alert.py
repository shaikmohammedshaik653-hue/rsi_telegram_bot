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
    
