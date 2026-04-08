import pandas as pd
import os

# -----------------------
# SETTINGS
# -----------------------
BB_PERIOD = 20
BB_STD = 2

RSI_PERIOD = 14
RSI_BUY_LEVEL = 30
RSI_SELL_LEVEL = 70

SAFETY_SL_ENABLED = True
SAFETY_SL = 10.0   # max loss in price points


# -----------------------
# INDICATORS
# -----------------------
def calculate_rsi(series, period=14):
    delta = series.diff()

    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_bollinger(df, period=20, std=2):
    df["BB_MID"] = df["Close"].rolling(period).mean()
    df["BB_STD"] = df["Close"].rolling(period).std()

    df["BB_UPPER"] = df["BB_MID"] + (std * df["BB_STD"])
    df["BB_LOWER"] = df["BB_MID"] - (std * df["BB_STD"])

    return df


# -----------------------
# BACKTEST FUNCTION
# -----------------------
def backtest(df):
    trades = []
    position = None

    for i in range(1, len(df)):
        row = df.iloc[i]
        time = df.index[i]

        close_price = row["Close"]
        high_price = row["High"]
        low_price = row["Low"]

        bb_upper = row["BB_UPPER"]
        bb_lower = row["BB_LOWER"]
        bb_mid = row["BB_MID"]

        rsi = row["RSI"]

        # Skip rows until indicators are ready
        if pd.isna(bb_upper) or pd.isna(bb_lower) or pd.isna(bb_mid) or pd.isna(rsi):
            continue

        # -----------------------
        # ENTRY SIGNALS
        # -----------------------
        buy_signal = (close_price <= bb_lower) and (rsi < RSI_BUY_LEVEL)
        sell_signal = (close_price >= bb_upper) and (rsi > RSI_SELL_LEVEL)

        # -----------------------
        # ENTRY
        # -----------------------
        if position is None:
            if buy_signal:
                position = {
                    "type": "BUY",
                    "entry_time": time,
                    "entry_price": close_price
                }

            elif sell_signal:
                position = {
                    "type": "SELL",
                    "entry_time": time,
                    "entry_price": close_price
                }

        # -----------------------
        # EXIT
        # -----------------------
        else:
            trade_type = position["type"]
            entry_price = position["entry_price"]

            # Safety SL check
            if SAFETY_SL_ENABLED:
                if trade_type == "BUY":
                    sl_price = entry_price - SAFETY_SL
                    if low_price <= sl_price:
                        trades.append({
                            **position,
                            "exit_time": time,
                            "exit_price": sl_price,
                            "result": "LOSS",
                            "pnl": sl_price - entry_price
                        })
                        position = None
                        continue

                elif trade_type == "SELL":
                    sl_price = entry_price + SAFETY_SL
                    if high_price >= sl_price:
                        trades.append({
                            **position,
                            "exit_time": time,
                            "exit_price": sl_price,
                            "result": "LOSS",
                            "pnl": entry_price - sl_price
                        })
                        position = None
                        continue

            # Exit at middle band
            if trade_type == "BUY" and close_price >= bb_mid:
                pnl = close_price - entry_price
                trades.append({
                    **position,
                    "exit_time": time,
                    "exit_price": close_price,
                    "result": "WIN" if pnl > 0 else "LOSS",
                    "pnl": pnl
                })
                position = None

            elif trade_type == "SELL" and close_price <= bb_mid:
                pnl = entry_price - close_price
                trades.append({
                    **position,
                    "exit_time": time,
                    "exit_price": close_price,
                    "result": "WIN" if pnl > 0 else "LOSS",
                    "pnl": pnl
                })
                position = None

    return pd.DataFrame(trades)


# -----------------------
# METRICS
# -----------------------
def calculate_max_streak(trades_df, result_type="WIN"):
    max_streak = 0
    current = 0

    for r in trades_df["result"]:
        if r == result_type:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0

    return max_streak


def calculate_drawdown(trades_df):
    if len(trades_df) == 0:
        return 0

    trades_df["equity"] = trades_df["pnl"].cumsum()
    trades_df["peak"] = trades_df["equity"].cummax()
    trades_df["drawdown"] = trades_df["equity"] - trades_df["peak"]

    return trades_df["drawdown"].min()


def calculate_profit_factor(trades_df):
    if len(trades_df) == 0:
        return 0

    gross_profit = trades_df[trades_df["pnl"] > 0]["pnl"].sum()
    gross_loss = abs(trades_df[trades_df["pnl"] < 0]["pnl"].sum())

    if gross_loss == 0:
        return float("inf")

    return gross_profit / gross_loss


def calculate_monthly_returns(trades_df):
    if len(trades_df) == 0:
        return pd.DataFrame(columns=["month", "pnl"])

    trades_df["exit_time"] = pd.to_datetime(trades_df["exit_time"])
    trades_df["month"] = trades_df["exit_time"].dt.to_period("M")

    monthly = trades_df.groupby("month")["pnl"].sum().reset_index()
    monthly["month"] = monthly["month"].astype(str)

    return monthly


# -----------------------
# REPORT
# -----------------------
def generate_report(trades_df, start_date, end_date):
    total = len(trades_df)
    wins = len(trades_df[trades_df["result"] == "WIN"])
    losses = len(trades_df[trades_df["result"] == "LOSS"])

    win_rate = (wins / total * 100) if total > 0 else 0
    net_profit = trades_df["pnl"].sum() if total > 0 else 0

    max_win_streak = calculate_max_streak(trades_df, "WIN") if total > 0 else 0
    max_loss_streak = calculate_max_streak(trades_df, "LOSS") if total > 0 else 0

    max_drawdown = calculate_drawdown(trades_df)
    profit_factor = calculate_profit_factor(trades_df)

    monthly_returns = calculate_monthly_returns(trades_df)

    html = f"""
    <html>
    <head>
        <title>XAUUSD Backtest Report</title>
        <style>
            body {{
                font-family: Arial;
                padding: 20px;
                background: #0b0f19;
                color: white;
            }}
            .box {{
                background: #161b2b;
                padding: 15px;
                border-radius: 10px;
                margin-bottom: 15px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 15px;
            }}
            th, td {{
                padding: 8px;
                border: 1px solid #333;
                font-size: 14px;
                text-align: center;
            }}
            th {{
                background: #222a44;
            }}
            h1, h2 {{
                color: #00ffcc;
            }}
        </style>
    </head>
    <body>
        <h1>XAUUSD Bollinger Bands + RSI Backtest Report (15m)</h1>

        <div class="box">
            <h2>Strategy Settings</h2>
            <p><b>Date Range:</b> {start_date} → {end_date}</p>
            <p><b>Bollinger Period:</b> {BB_PERIOD}</p>
            <p><b>Bollinger Std Dev:</b> {BB_STD}</p>
            <p><b>RSI Period:</b> {RSI_PERIOD}</p>
            <p><b>Buy Condition:</b> Close <= Lower Band AND RSI < {RSI_BUY_LEVEL}</p>
            <p><b>Sell Condition:</b> Close >= Upper Band AND RSI > {RSI_SELL_LEVEL}</p>
            <p><b>Exit Condition:</b> Price reaches Middle Band</p>
            <p><b>Safety SL Enabled:</b> {SAFETY_SL_ENABLED}</p>
            <p><b>Safety SL Value:</b> {SAFETY_SL}</p>
        </div>

        <div class="box">
            <h2>Summary</h2>
            <p><b>Total Trades:</b> {total}</p>
            <p><b>Wins:</b> {wins}</p>
            <p><b>Losses:</b> {losses}</p>
            <p><b>Win Rate:</b> {win_rate:.2f}%</p>
            <p><b>Net Profit (points):</b> {net_profit:.2f}</p>
            <p><b>Profit Factor:</b> {profit_factor:.2f}</p>
            <p><b>Max Drawdown (points):</b> {max_drawdown:.2f}</p>
            <p><b>Max Winning Streak:</b> {max_win_streak}</p>
            <p><b>Max Losing Streak:</b> {max_loss_streak}</p>
        </div>

        <div class="box">
            <h2>Monthly Returns</h2>
            {monthly_returns.to_html(index=False)}
        </div>

        <div class="box">
            <h2>Trades</h2>
            {trades_df.to_html(index=False)}
        </div>

    </body>
    </html>
    """

    return html


# -----------------------
# MAIN
# -----------------------
if __name__ == "__main__":
    os.makedirs("results", exist_ok=True)

    start_date_input = input("Enter start date (dd/mm/yy) e.g. 01/01/20: ")
    start_date = pd.to_datetime(start_date_input, format="%d/%m/%y")

    df = pd.read_csv("data/xauusd_15m.csv")
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date")

    df = df[df.index >= start_date]

    if len(df) == 0:
        print("No data found after this start date.")
        exit()

    # Calculate indicators
    df = calculate_bollinger(df, BB_PERIOD, BB_STD)
    df["RSI"] = calculate_rsi(df["Close"], RSI_PERIOD)

    start_range = df.index.min()
    end_range = df.index.max()

    print("Data filtered from:", start_range, "to", end_range)
    print("Total candles:", len(df))

    trades_df = backtest(df)

    trades_df.to_csv("results/trades.csv", index=False)

    report_html = generate_report(trades_df, start_range, end_range)

    with open("results/report.html", "w") as f:
        f.write(report_html)

    print("Backtest Completed ✅")
    print("Trades saved: results/trades.csv")
    print("Report saved: results/report.html")