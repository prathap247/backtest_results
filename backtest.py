import pandas as pd
import os

# -----------------------
# SETTINGS
# -----------------------
EMA_PERIOD = 200
RR = 3

SL_POINTS = 12.0
TP_POINTS = SL_POINTS * RR

ADX_PERIOD = 14
ADX_THRESHOLD = 40

# Ignore minor EMA_FLIP losses up to -3 points
MINOR_LOSS_LIMIT = -3.0

DATA_FILE = "/Users/prathapd/Documents/forex_backtesting/data/xauusd-m15-bid-2025-04-10-2026-04-10.csv"


# -----------------------
# EMA CALCULATION
# -----------------------
def add_ema(df, period=200):
    df["EMA200"] = df["Close"].ewm(span=period, adjust=False).mean()
    return df


# -----------------------
# ADX CALCULATION
# -----------------------
def add_adx(df, period=14):
    df = df.copy()

    df["prev_close"] = df["Close"].shift(1)
    df["prev_high"] = df["High"].shift(1)
    df["prev_low"] = df["Low"].shift(1)

    # True Range (TR)
    df["tr"] = df[["High", "prev_close"]].max(axis=1) - df[["Low", "prev_close"]].min(axis=1)

    # Directional Movement
    df["plus_dm"] = df["High"] - df["prev_high"]
    df["minus_dm"] = df["prev_low"] - df["Low"]

    df["plus_dm"] = df["plus_dm"].where((df["plus_dm"] > df["minus_dm"]) & (df["plus_dm"] > 0), 0.0)
    df["minus_dm"] = df["minus_dm"].where((df["minus_dm"] > df["plus_dm"]) & (df["minus_dm"] > 0), 0.0)

    # Smooth TR, +DM, -DM using Wilder's method
    df["tr_smooth"] = df["tr"].ewm(alpha=1/period, adjust=False).mean()
    df["plus_dm_smooth"] = df["plus_dm"].ewm(alpha=1/period, adjust=False).mean()
    df["minus_dm_smooth"] = df["minus_dm"].ewm(alpha=1/period, adjust=False).mean()

    # +DI and -DI
    df["plus_di"] = 100 * (df["plus_dm_smooth"] / df["tr_smooth"])
    df["minus_di"] = 100 * (df["minus_dm_smooth"] / df["tr_smooth"])

    # DX
    df["dx"] = 100 * (abs(df["plus_di"] - df["minus_di"]) / (df["plus_di"] + df["minus_di"]))

    # ADX
    df["ADX"] = df["dx"].ewm(alpha=1/period, adjust=False).mean()

    # cleanup
    df.drop(columns=[
        "prev_close", "prev_high", "prev_low",
        "tr", "plus_dm", "minus_dm",
        "tr_smooth", "plus_dm_smooth", "minus_dm_smooth",
        "plus_di", "minus_di", "dx"
    ], inplace=True)

    return df


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

        close_price = row["Close"]
        high_price = row["High"]
        low_price = row["Low"]

        ema_prev = row_prev["EMA200"]
        ema_now = row["EMA200"]

        close_prev = row_prev["Close"]

        adx_now = row["ADX"]

        if pd.isna(ema_prev) or pd.isna(ema_now) or pd.isna(adx_now):
            continue

        # -----------------------
        # CROSS CONDITIONS (CLOSE BASED)
        # -----------------------
        cross_up = (close_prev < ema_prev) and (close_price > ema_now)
        cross_down = (close_prev > ema_prev) and (close_price < ema_now)

        # -----------------------
        # ADX FILTER (Avoid choppy market)
        # -----------------------
        adx_ok = adx_now > ADX_THRESHOLD

        # -----------------------
        # ENTRY
        # -----------------------
        if position is None:

            if cross_up and adx_ok:
                position = {
                    "type": "BUY",
                    "entry_time": time,
                    "entry_price": close_price,
                    "sl": close_price - SL_POINTS,
                    "tp": close_price + TP_POINTS,
                    "adx": adx_now
                }

            elif cross_down and adx_ok:
                position = {
                    "type": "SELL",
                    "entry_time": time,
                    "entry_price": close_price,
                    "sl": close_price + SL_POINTS,
                    "tp": close_price - TP_POINTS,
                    "adx": adx_now
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
                        "pnl": -SL_POINTS,
                        "exit_reason": "SL"
                    })
                    position = None

                elif high_price >= position["tp"]:
                    trades.append({
                        **position,
                        "exit_time": time,
                        "exit_price": position["tp"],
                        "result": "WIN",
                        "pnl": TP_POINTS,
                        "exit_reason": "TP"
                    })
                    position = None

                elif cross_down:
                    pnl = close_price - position["entry_price"]
                    trades.append({
                        **position,
                        "exit_time": time,
                        "exit_price": close_price,
                        "result": "WIN" if pnl > 0 else "LOSS",
                        "pnl": pnl,
                        "exit_reason": "EMA_FLIP"
                    })
                    position = None

            elif trade_type == "SELL":

                if high_price >= position["sl"]:
                    trades.append({
                        **position,
                        "exit_time": time,
                        "exit_price": position["sl"],
                        "result": "LOSS",
                        "pnl": -SL_POINTS,
                        "exit_reason": "SL"
                    })
                    position = None

                elif low_price <= position["tp"]:
                    trades.append({
                        **position,
                        "exit_time": time,
                        "exit_price": position["tp"],
                        "result": "WIN",
                        "pnl": TP_POINTS,
                        "exit_reason": "TP"
                    })
                    position = None

                elif cross_up:
                    pnl = position["entry_price"] - close_price
                    trades.append({
                        **position,
                        "exit_time": time,
                        "exit_price": close_price,
                        "result": "WIN" if pnl > 0 else "LOSS",
                        "pnl": pnl,
                        "exit_reason": "EMA_FLIP"
                    })
                    position = None

    return pd.DataFrame(trades)


# -----------------------
# FILTER MEANINGFUL TRADES
# -----------------------
def filter_meaningful_trades(trades_df):
    """
    Removes minor EMA_FLIP losses (example pnl between 0 and -3).
    Keeps SL losses and all wins.
    """
    if len(trades_df) == 0:
        return trades_df

    trades_df = trades_df.copy()

    mask_minor_flip_loss = (
        (trades_df["exit_reason"] == "EMA_FLIP") &
        (trades_df["pnl"] < 0) &
        (trades_df["pnl"] >= MINOR_LOSS_LIMIT)
    )

    return trades_df[~mask_minor_flip_loss]


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

    trades_df = trades_df.copy()
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

    trades_df = trades_df.copy()
    trades_df["exit_time"] = pd.to_datetime(trades_df["exit_time"])
    trades_df["month"] = trades_df["exit_time"].dt.to_period("M")

    monthly = trades_df.groupby("month")["pnl"].sum().reset_index()
    monthly["month"] = monthly["month"].astype(str)

    return monthly


# -----------------------
# REPORT
# -----------------------
def generate_report(trades_df, start_date, end_date):

    # full history for table
    full_trades_df = trades_df.copy()

    # filtered for summary calculations
    filtered_trades_df = filter_meaningful_trades(trades_df)

    total = len(filtered_trades_df)
    wins = len(filtered_trades_df[filtered_trades_df["result"] == "WIN"])
    losses = len(filtered_trades_df[filtered_trades_df["result"] == "LOSS"])

    win_rate = (wins / total * 100) if total > 0 else 0
    net_profit = filtered_trades_df["pnl"].sum() if total > 0 else 0

    max_win_streak = calculate_max_streak(filtered_trades_df, "WIN") if total > 0 else 0
    max_loss_streak = calculate_max_streak(filtered_trades_df, "LOSS") if total > 0 else 0

    max_drawdown = calculate_drawdown(filtered_trades_df)
    profit_factor = calculate_profit_factor(filtered_trades_df)

    monthly_returns = calculate_monthly_returns(filtered_trades_df)

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
        <h1>XAUUSD EMA200 Cross Strategy (15m)</h1>

        <div class="box">
            <h2>Strategy Settings</h2>
            <p><b>Date Range:</b> {start_date} → {end_date}</p>
            <p><b>Entry:</b> Close crosses EMA200 + ADX Filter</p>
            <p><b>ADX Filter:</b> ADX({ADX_PERIOD}) > {ADX_THRESHOLD}</p>
            <p><b>Exit:</b> TP / SL / EMA Flip</p>
            <p><b>Stoploss:</b> {SL_POINTS} points (120 pips)</p>
            <p><b>RR:</b> 1 : {RR}</p>
            <p><b>Takeprofit:</b> {TP_POINTS} points</p>
            <p><b>Minor EMA Flip Loss Ignored:</b> EMA_FLIP losses between 0 and {MINOR_LOSS_LIMIT}</p>
        </div>

        <div class="box">
            <h2>Summary (Meaningful Trades Only)</h2>
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
            <h2>Monthly Returns (Meaningful Trades Only)</h2>
            {monthly_returns.to_html(index=False)}
        </div>

        <div class="box">
            <h2>Trades History (Full Data - Includes SL + Minor EMA Flip)</h2>
            {full_trades_df.to_html(index=False)}
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

    df = pd.read_csv(DATA_FILE)

    # Rename dataset columns
    df.rename(columns={
        "timestamp": "Date",
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close"
    }, inplace=True)

    # timestamp is in milliseconds
    df["Date"] = pd.to_datetime(df["Date"], unit="ms")
    df = df.set_index("Date")
    df = df.sort_index()

    df = df[df.index >= start_date]

    if len(df) == 0:
        print("No data found after this start date.")
        exit()

    # Add indicators
    df = add_ema(df, EMA_PERIOD)
    df = add_adx(df, ADX_PERIOD)

    start_range = df.index.min()
    end_range = df.index.max()

    print("Data filtered from:", start_range, "to", end_range)
    print("Total candles:", len(df))

    trades_df = backtest(df)

    # Save full trades history
    trades_df.to_csv("results/trades.csv", index=False)

    # Save filtered trades (meaningful only)
    filtered_trades_df = filter_meaningful_trades(trades_df)
    filtered_trades_df.to_csv("results/filtered_trades.csv", index=False)

    report_html = generate_report(trades_df, start_range, end_range)

    with open("results/report.html", "w") as f:
        f.write(report_html)

    print("Backtest Completed ✅")
    print("Full Trades saved: results/trades.csv")
    print("Filtered Trades saved: results/filtered_trades.csv")
    print("Report saved: results/report.html")