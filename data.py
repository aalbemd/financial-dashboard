import yfinance as yf
import pandas as pd
from datetime import date

BENCHMARKS = {
    "S&P 500": "^GSPC",
    "NASDAQ": "^IXIC",
    "Dow Jones": "^DJI",
    "FTSE 100": "^FTSE",
    "DAX": "^GDAXI",
    "Nikkei 225": "^N225",
    "Ibovespa": "^BVSP",
    "Euro Stoxx 50": "^STOXX50E",
}

DEFAULT_START = "2000-01-01"


def get_stock_data(ticker: str, start: str, end: str, interval: str = "1d") -> pd.DataFrame:
    try:
        df = yf.download(ticker, start=start, end=end, interval=interval, progress=False, auto_adjust=True)
        if df.empty:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.index = pd.to_datetime(df.index)
        df.index.name = "Date"
        return df
    except Exception:
        return pd.DataFrame()


def get_benchmarks() -> dict:
    results = {}
    for name, ticker in BENCHMARKS.items():
        try:
            info = yf.Ticker(ticker).fast_info
            results[name] = {
                "ticker": ticker,
                "price": round(info.last_price, 2) if info.last_price else None,
                "change_pct": round((info.last_price / info.previous_close - 1) * 100, 2)
                if info.last_price and info.previous_close
                else None,
            }
        except Exception:
            results[name] = {"ticker": ticker, "price": None, "change_pct": None}
    return results


def compute_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "Close" not in df.columns:
        return df
    df = df.copy()
    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA50"] = df["Close"].rolling(50).mean()
    df["MA200"] = df["Close"].rolling(200).mean()
    return df


def compute_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    if df.empty or "Close" not in df.columns:
        return pd.Series(dtype=float)
    delta = df["Close"].diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, float("nan"))
    return 100 - 100 / (1 + rs)


def compute_cumulative_performance(df: pd.DataFrame) -> pd.Series:
    """Cumulative % return from first row of series."""
    if df.empty or "Close" not in df.columns:
        return pd.Series(dtype=float)
    close = df["Close"].dropna()
    if len(close) < 2:
        return pd.Series(dtype=float)
    return (close / close.iloc[0] - 1) * 100


def compute_monthly_volume(df: pd.DataFrame) -> pd.DataFrame:
    """Resample volume to monthly totals."""
    if df.empty or "Volume" not in df.columns:
        return pd.DataFrame()
    vol = df["Volume"].resample("ME").sum()
    result = vol.reset_index()
    result.columns = ["Date", "Volume"]
    return result


def period_to_dates(period: str) -> tuple:
    today = date.today()
    end = today.strftime("%Y-%m-%d")
    mapping = {
        "1S": pd.DateOffset(weeks=1),
        "1M": pd.DateOffset(months=1),
        "3M": pd.DateOffset(months=3),
        "6M": pd.DateOffset(months=6),
        "1A": pd.DateOffset(years=1),
        "2A": pd.DateOffset(years=2),
    }
    if period == "YTD":
        start = date(today.year, 1, 1).strftime("%Y-%m-%d")
    elif period == "Máx":
        start = DEFAULT_START
    elif period in mapping:
        start = (pd.Timestamp(today) - mapping[period]).strftime("%Y-%m-%d")
    else:
        start = DEFAULT_START
    return start, end
