import pandas as pd
import os

# -----------------------
# SETTINGS
# -----------------------
SAFETY_SL_ENABLED = True   # Change to False if you don't want safety SL
SAFETY_SL = 10.0           # Max loss allowed (price points)


# -----------------------
# BACKTEST FUNCTION
# -----------------------
def backtest(df):
    trades = []
    position = None

    for i in range(1, len(df)):
        row_prev = df.iloc[i - 1]
        row = df.iloc[i]
        time = df.index[i]

        ema50_prev = row_prev["EMA50"]
        ema200_prev = row_prev["EMA200"]
        ema50 = row["EMA50"]
        ema200 = row["EMA200"]

        close_price = row["Close"]
        high_price = row["High"]
        low_price = row["Low"]

        # Detect crossover signals
        buy_signal = (ema50_prev <= ema200_prev) and (ema50 > ema200)
        sell_signal = (ema50_prev >= ema200_prev) and (ema50 < ema200)

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

            # Safety SL logic
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

            # Exit on opposite crossover
            if trade_type == "BUY" and sell_signal:
                pnl = close_price - entry_price
                trades.append({
                    **position,
                    "exit_time": time,
                    "exit_price": close_price,
                    "result": "WIN" if pnl > 0 else "LOSS",
                    "pnl": pnl
                })
                position = None

            elif trade_type == "SELL" and buy_signal:
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
        <h1>XAUUSD EMA50/EMA200 Backtest Report (15m)</h1>

        <div class="box">
            <h2>Settings</h2>
            <p><b>Date Range:</b> {start_date} → {end_date}</p>
            <p><b>Entry:</b> EMA50/EMA200 Crossover</p>
            <p><b>Exit:</b> Opposite Crossover</p>
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