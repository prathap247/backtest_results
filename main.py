import pandas as pd

# Load dataset (auto detect separator: comma / tab / spaces)
df = pd.read_csv("data/xauusd_1min.csv", sep=None, engine="python")

# Clean column names (removes hidden spaces)
df.columns = df.columns.str.strip()

# Convert Date column to datetime
df["Date"] = pd.to_datetime(df["Date"])

# Sort by date
df = df.sort_values("Date")

# Set Date as index
df = df.set_index("Date")

# Convert price columns to numeric (important)
df["Open"] = pd.to_numeric(df["Open"], errors="coerce")
df["High"] = pd.to_numeric(df["High"], errors="coerce")
df["Low"] = pd.to_numeric(df["Low"], errors="coerce")
df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce")

# Drop bad rows
df = df.dropna()

# Resample to 15-minute candles
df_15m = df.resample("15min").agg({
    "Open": "first",
    "High": "max",
    "Low": "min",
    "Close": "last",
    "Volume": "sum"
})

# Drop empty candles
df_15m = df_15m.dropna()

# Calculate EMA50 and EMA200
df_15m["EMA50"] = df_15m["Close"].ewm(span=50, adjust=False).mean()
df_15m["EMA200"] = df_15m["Close"].ewm(span=200, adjust=False).mean()

# Save cleaned 15m data
df_15m.to_csv("data/xauusd_15m.csv")

print("Done! 15-min data saved as data/xauusd_15m.csv")
print(df_15m.tail(5))