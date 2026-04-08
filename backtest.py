import pandas as pd
import os

# -----------------------
# SETTINGS
# -----------------------
SL_POINTS = 10.0
RR = 2.5
TP_POINTS = SL_POINTS * RR

EMA_PERIOD = 200


# -----------------------
# EMA CALCULATION
# -----------------------
def add_ema(df, period=200):
    df["EMA200"] = df["Close"].ewm(span=period, adjust=False).mean()
    return df


# -----------------------
# PREVIOUS DAY LEVELS
# -----------------------
def add_previous_day_levels(df):
    df["date_only"] = df.index.date

    daily = df.groupby("date_only").agg({
        "High": "max",
        "Low": "min"
    })

    daily["PDH"] = daily["High"].shift(1)
    daily["PDL"] = daily["Low"].shift(1)

    df["PDH"] = df["date_only"].map(daily["PDH"])
    df["PDL"] = df["date_only"].map(daily["PDL"])

    return df


# -----------------------
# BACKTEST FUNCTION
# -----------------------
def backtest(df):
    trades = []
    position = None

    for i in range(2, len(df)):  # start from 2 because confirmation needs previous candle
        row_prev = df.iloc[i - 1]
        row = df.iloc[i]
        time = df.index[i]

        close_price = row["Close"]
        high_price = row["High"]
        low_price = row["Low"]

        pdh = row["PDH"]
        pdl = row["PDL"]
        ema200 = row["EMA200"]

        if pd.isna(pdh) or pd.isna(pdl) or pd.isna(ema200):
            continue

        # -----------------------
        # Confirmation candle logic
        # -----------------------
        buy_confirm = (row_prev["Close"] > pdh) and (close_price > pdh)
        sell_confirm = (row_prev["Close"] < pdl) and (close_price < pdl)

        # -----------------------
        # Trend filter logic
        # -----------------------
        buy_signal = buy_confirm and (close_price > ema200)
        sell_signal = sell_confirm and (close_price < ema200)

        # -----------------------
        # ENTRY
        # -----------------------
        if position is None:
            if buy_signal:
                position = {
                    "type": "BUY",
                    "entry_time": time,
                    "entry_price": close_price,
                    "sl": close_price - SL_POINTS,
                    "tp": close_price + TP_POINTS
                }

            elif sell_signal:
                position = {
                    "type": "SELL",
                    "entry_time": time,
                    "entry_price": close_price,
                    "sl": close_price + SL_POINTS,
                    "tp": close_price - TP_POINTS
                }

        # -----------------------
        # EXIT
        # -----------------------
        else:
            trade_type = position["type"]

            if trade_type == "BUY":
                if low_price <= position["sl"]:
                    trades.append({
                        **position,
                        "exit_time": time,
                        "exit_price": position["sl"],
                        "result": "LOSS",
                        "pnl": -SL_POINTS
                    })
                    position = None

                elif high_price >= position["tp"]:
                    trades.append({
                        **position,
                        "exit_time": time,
                        "exit_price": position["tp"],
                        "result": "WIN",
                        "pnl": TP_POINTS
                    })
                    position = None

            elif trade_type == "SELL":
                if high_price >= position["sl"]:
                    trades.append({
                        **position,
                        "exit_time": time,
                        "exit_price": position["sl"],
                        "result": "LOSS",
                        "pnl": -SL_POINTS
                    })
                    position = None

                elif low_price <= position["tp"]:
                    trades.append({
                        **position,
                        "exit_time": time,
                        "exit_price": position["tp"],
                        "result": "WIN",
                        "pnl": TP_POINTS
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
        <h1>XAUUSD PDH/PDL Breakout + EMA200 + Confirmation (15m)</h1>

        <div class="box">
            <h2>Strategy Settings</h2>
            <p><b>Date Range:</b> {start_date} → {end_date}</p>
            <p><b>Entry:</b> 2 Candle Close Breakout of PDH/PDL</p>
            <p><b>Trend Filter:</b> Buy only above EMA200, Sell only below EMA200</p>
            <p><b>Stoploss:</b> {SL_POINTS} points</p>
            <p><b>RR:</b> 1 : {RR}</p>
            <p><b>Takeprofit:</b> {TP_POINTS} points</p>
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

    df = add_previous_day_levels(df)
    df = add_ema(df, EMA_PERIOD)

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