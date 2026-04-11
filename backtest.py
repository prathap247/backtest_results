import pandas as pd
import os

# -----------------------
# SETTINGS
# -----------------------
RR = 2.5
BUFFER = 0.20   # XAUUSD buffer
EMA_PERIOD = 200

DATA_FILE = "/Users/prathapd/Documents/forex_backtesting/data/xauusd-m15-bid-2025-04-10-2026-04-10.csv"


# -----------------------
# ENTRY LOGIC
# -----------------------
def detect_entries(df):
    trades = []

    ny_high = None
    ny_low = None
    current_day = None
    breakout_ready = False
    traded_today = False

    for i in range(len(df)):
        row = df.iloc[i]
        time_utc = df.index[i]
        time_ny = time_utc.tz_convert("America/New_York")

        date = time_ny.date()
        hour = time_ny.hour
        minute = time_ny.minute

        high = row["High"]
        low = row["Low"]
        close = row["Close"]
        ema = row["EMA200"]

        # reset daily state
        if current_day != date:
            current_day = date
            ny_high = None
            ny_low = None
            breakout_ready = False
            traded_today = False

        # capture NY 9:30 candle
        if hour == 9 and minute == 30:
            ny_high = high
            ny_low = low
            breakout_ready = True
            continue

        if breakout_ready and not traded_today:

            # BUY breakout (EMA filter)
            if (
                high > ny_high and close > ny_high
                and close > ema
            ):
                sl = ny_low - BUFFER

                trades.append({
                    "type": "BUY",
                    "entry_time": time_utc,
                    "entry_price": close,
                    "sl": sl,
                    "hour": hour
                })

                traded_today = True

            # SELL breakout (EMA filter)
            elif (
                low < ny_low and close < ny_low
                and close < ema
            ):
                sl = ny_high + BUFFER

                trades.append({
                    "type": "SELL",
                    "entry_time": time_utc,
                    "entry_price": close,
                    "sl": sl,
                    "hour": hour
                })

                traded_today = True

    return pd.DataFrame(trades)


# -----------------------
# EXIT LOGIC
# -----------------------
def simulate_trades(df, trades):
    results = []

    for _, t in trades.iterrows():

        entry_time = t["entry_time"]
        entry = t["entry_price"]
        sl = t["sl"]
        trade_type = t["type"]

        risk = abs(entry - sl)
        tp = entry + (risk * RR) if trade_type == "BUY" else entry - (risk * RR)

        data = df.loc[entry_time:]

        for i in range(len(data)):
            row = data.iloc[i]
            time = data.index[i]

            high = row["High"]
            low = row["Low"]

            if trade_type == "BUY":

                if low <= sl:
                    results.append({
                        **t,
                        "exit_time": time,
                        "exit_price": sl,
                        "tp": tp,
                        "result": "LOSS",
                        "pnl": -risk
                    })
                    break

                if high >= tp:
                    results.append({
                        **t,
                        "exit_time": time,
                        "exit_price": tp,
                        "tp": tp,
                        "result": "WIN",
                        "pnl": risk * RR
                    })
                    break

            else:

                if high >= sl:
                    results.append({
                        **t,
                        "exit_time": time,
                        "exit_price": sl,
                        "tp": tp,
                        "result": "LOSS",
                        "pnl": -risk
                    })
                    break

                if low <= tp:
                    results.append({
                        **t,
                        "exit_time": time,
                        "exit_price": tp,
                        "tp": tp,
                        "result": "WIN",
                        "pnl": risk * RR
                    })
                    break

    return pd.DataFrame(results)


# -----------------------
# REPORT
# -----------------------
def generate_report(trades_df):

    if len(trades_df) == 0:
        return "<h2>No Trades</h2>"

    trades_df["hour"] = pd.to_datetime(trades_df["entry_time"]).dt.hour

    heatmap = trades_df.groupby(["hour", "result"]).size().unstack(fill_value=0)

    wins_df = trades_df[trades_df["result"] == "WIN"]
    losses_df = trades_df[trades_df["result"] == "LOSS"]

    wins = len(wins_df)
    losses = len(losses_df)
    total = len(trades_df)

    win_rate = (wins / total) * 100 if total > 0 else 0
    net_profit = trades_df["pnl"].sum()

    max_tp = wins_df["pnl"].max() if len(wins_df) > 0 else 0
    max_loss = losses_df["pnl"].min() if len(losses_df) > 0 else 0

    equity = trades_df["pnl"].cumsum()
    drawdown = equity - equity.cummax()
    max_drawdown = drawdown.min()

    gross_profit = wins_df["pnl"].sum()
    gross_loss = abs(losses_df["pnl"].sum())
    profit_factor = gross_profit / gross_loss if gross_loss != 0 else float("inf")

    # -----------------------
    # STREAKS
    # -----------------------
    streak = 0
    max_win_streak = 0
    max_loss_streak = 0

    for r in trades_df["result"]:
        if r == "WIN":
            streak = streak + 1 if streak > 0 else 1
            max_win_streak = max(max_win_streak, streak)
        else:
            streak = streak - 1 if streak < 0 else -1
            max_loss_streak = max(max_loss_streak, abs(streak))

    html = f"""
    <html>
    <head>
    <style>
    body {{
        font-family: Arial;
        background: #0b0f19;
        color: white;
        padding: 20px;
    }}
    .box {{
        background: #161b2b;
        padding: 15px;
        margin: 10px 0;
        border-radius: 10px;
    }}
    table {{
        border-collapse: collapse;
        width: 100%;
    }}
    th, td {{
        border: 1px solid #333;
        padding: 8px;
        text-align: center;
    }}
    th {{
        background: #222a44;
    }}
    </style>
    </head>

    <body>

    <h1>NY 9:30 Breakout + EMA200 Strategy Report</h1>

    <div class="box">
        <h2>Summary</h2>
        <p>Total Trades: {total}</p>
        <p>Wins: {wins}</p>
        <p>Losses: {losses}</p>
        <p>Win Rate: {win_rate:.2f}%</p>
        <p>Net Profit: {net_profit:.2f}</p>
        <p>Profit Factor: {profit_factor:.2f}</p>
    </div>

    <div class="box">
        <h2>Streaks</h2>
        <p>Max Winning Streak: {max_win_streak}</p>
        <p>Max Losing Streak: {max_loss_streak}</p>
    </div>

    <div class="box">
        <h2>Risk Metrics</h2>
        <p>Max Drawdown: {max_drawdown:.2f}</p>
        <p>Max Winning Trade: {max_tp:.2f}</p>
        <p>Max Losing Trade: {max_loss:.2f}</p>
    </div>

    <div class="box">
        <h2>Hourly Heatmap</h2>
        {heatmap.to_html()}
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

    start_date_input = input("Enter start date (dd/mm/yy): ")
    start_date = pd.to_datetime(start_date_input, format="%d/%m/%y").tz_localize("UTC")

    df = pd.read_csv(DATA_FILE)

    df.rename(columns={
        "timestamp": "Date",
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close"
    }, inplace=True)

    df["Date"] = pd.to_datetime(df["Date"], unit="ms")
    df["Date"] = df["Date"].dt.tz_localize("UTC")
    df = df.set_index("Date")

    # -----------------------
    # EMA200 CALCULATION
    # -----------------------
    df["EMA200"] = df["Close"].ewm(span=EMA_PERIOD, adjust=False).mean()

    df = df[df.index >= start_date]

    print("Data loaded:", len(df))

    trades = detect_entries(df)
    trades_df = simulate_trades(df, trades)

    trades_df.to_csv("results/trades.csv", index=False)

    report = generate_report(trades_df)

    with open("results/report.html", "w") as f:
        f.write(report)

    print("Backtest Completed ✅")
    print("Report saved → results/report.html")