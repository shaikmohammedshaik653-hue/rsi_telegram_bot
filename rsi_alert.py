 = float(last["RSI"])
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
