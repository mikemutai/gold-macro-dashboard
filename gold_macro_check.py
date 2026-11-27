"""
gold_macro_check.py  -  Daily macro check for Gold (XAUUSD)

What it does (every time you run it):
  1. Downloads recent prices for Gold, the US Dollar index, and 10-year US real yields.
  2. Scores each one: +1 = supportive for gold, 0 = neutral, -1 = headwind for gold.
  3. Checks gold's trend (50 SMA, 9 and 18 EMA), volatility, and your key levels.
  4. Warns you about weekends, US holidays, and the day after Thanksgiving.
  5. Saves the result to macro_log.csv so you build a record over time.

IMPORTANT: this is a CONTEXT FILTER, not a buy/sell signal. It tells you what
the bigger picture looks like. Your entry rules still decide the trade.

How to run:
  pip install -r requirements.txt
  python gold_macro_check.py
"""

import csv
import io
import os
from datetime import date, timedelta

import pandas as pd
import requests
import yfinance as yf
from pandas.tseries.holiday import USFederalHolidayCalendar

# ----------------------------------------------------------------------------
# SETTINGS  -  edit these whenever you like
# ----------------------------------------------------------------------------

# Yahoo Finance symbols. GC=F is gold futures. It trades a little above spot
# XAUUSD, so your levels may be off by a few dollars. That is fine for context.
GOLD_TICKER = "GC=F"
DOLLAR_TICKER = "DX-Y.NYB"

# FRED publishes 10-year real yields for free (no account needed).
REAL_YIELD_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFII10"

# Your key levels. Update these each week.
# (Starting values come from the World Gold Council Weekly Markets Monitor,
#  23 Nov 2026. They are analysts' levels, not guarantees.)
SUPPORT_LEVELS = [3500, 3450, 3320, 3268, 3249]
RESISTANCE_LEVELS = [3595, 3693, 3835, 3901, 4000]

LOG_FILE = "macro_log.csv"


# ----------------------------------------------------------------------------
# STEP 1: GET THE DATA
# ----------------------------------------------------------------------------

def get_close_prices(ticker):
    """Download about 1 year of daily closing prices from Yahoo Finance."""
    data = yf.download(ticker, period="1y", interval="1d",
                       progress=False, auto_adjust=True)
    if data.empty:
        raise RuntimeError(f"No data returned for {ticker}")
    close = data["Close"]
    if isinstance(close, pd.DataFrame):  # newer yfinance returns a table
        close = close.iloc[:, 0]
    return close.dropna()


def get_real_yield():
    """Download the 10-year US real yield history from FRED."""
    response = requests.get(REAL_YIELD_URL, timeout=20)
    response.raise_for_status()
    table = pd.read_csv(io.StringIO(response.text))
    values = pd.to_numeric(table.iloc[:, 1], errors="coerce")
    values.index = pd.to_datetime(table.iloc[:, 0])
    return values.dropna()


# ----------------------------------------------------------------------------
# STEP 2: SCORE EACH SIGNAL  (+1 good for gold, 0 neutral, -1 bad for gold)
# ----------------------------------------------------------------------------

def score_dollar(dollar):
    """A rising dollar is usually a headwind for gold."""
    last = dollar.iloc[-1]
    average_20 = dollar.rolling(20).mean().iloc[-1]
    change_5d = last - dollar.iloc[-6]
    if last > average_20 and change_5d > 0:
        return -1, f"Dollar rising ({last:.2f}, above its 20-day average)"
    if last < average_20 and change_5d < 0:
        return 1, f"Dollar falling ({last:.2f}, below its 20-day average)"
    return 0, f"Dollar mixed ({last:.2f})"


def score_real_yield(real_yield):
    """Rising real yields are usually a headwind for gold."""
    last = real_yield.iloc[-1]
    change_5d = last - real_yield.iloc[-6]
    if change_5d > 0.05:
        return -1, f"Real yields rising ({last:.2f}%, {change_5d:+.2f} over 5 days)"
    if change_5d < -0.05:
        return 1, f"Real yields falling ({last:.2f}%, {change_5d:+.2f} over 5 days)"
    return 0, f"Real yields flat ({last:.2f}%, {change_5d:+.2f} over 5 days)"


def score_trend(gold):
    """Is gold in an uptrend or downtrend on the daily chart?"""
    last = gold.iloc[-1]
    sma_50 = gold.rolling(50).mean().iloc[-1]
    ema_9 = gold.ewm(span=9, adjust=False).mean().iloc[-1]
    ema_18 = gold.ewm(span=18, adjust=False).mean().iloc[-1]
    if last > sma_50 and ema_9 > ema_18:
        return 1, f"Uptrend (price above 50 SMA {sma_50:.0f}, 9 EMA above 18 EMA)"
    if last < sma_50 and ema_9 < ema_18:
        return -1, f"Downtrend (price below 50 SMA {sma_50:.0f}, 9 EMA below 18 EMA)"
    return 0, f"Trend mixed (50 SMA {sma_50:.0f})"


# ----------------------------------------------------------------------------
# STEP 3: EXTRA CHECKS (volatility, levels, calendar)
# ----------------------------------------------------------------------------

def check_volatility(gold):
    """Compare recent swings (10 days) with normal swings (60 days)."""
    returns = gold.pct_change().dropna()
    recent = returns.tail(10).std() * (252 ** 0.5) * 100
    normal = returns.tail(60).std() * (252 ** 0.5) * 100
    if recent > normal * 1.25:
        return (f"HIGH volatility ({recent:.0f}% vs {normal:.0f}% normal). "
                "Consider smaller position sizes and wider stops.")
    return f"Volatility normal ({recent:.0f}% vs {normal:.0f}% normal)."


def check_levels(price):
    """Find the nearest support below and resistance above the current price."""
    supports_below = [s for s in SUPPORT_LEVELS if s < price]
    resistances_above = [r for r in RESISTANCE_LEVELS if r > price]
    lines = []
    if supports_below:
        s = max(supports_below)
        lines.append(f"Nearest support:    {s}  ({(price - s) / price * 100:.1f}% below)")
    else:
        lines.append("Price is BELOW all your support levels. Update them.")
    if resistances_above:
        r = min(resistances_above)
        lines.append(f"Nearest resistance: {r}  ({(r - price) / price * 100:.1f}% above)")
    else:
        lines.append("Price is ABOVE all your resistance levels. Update them.")
    return lines


def thanksgiving(year):
    """Thanksgiving is the 4th Thursday of November."""
    first_day = date(year, 11, 1)
    first_thursday = first_day + timedelta(days=(3 - first_day.weekday()) % 7)
    return first_thursday + timedelta(weeks=3)


def calendar_warnings(today):
    """Warn about days when trading is usually messy."""
    warnings = []
    if today.weekday() >= 5:
        warnings.append("It is the weekend. The gold market is closed.")
    holidays = USFederalHolidayCalendar().holidays(
        start=today, end=today)
    if len(holidays) > 0:
        warnings.append("US federal holiday. Liquidity is thin, so avoid trading.")
    if today == thanksgiving(today.year) + timedelta(days=1):
        warnings.append("Day after US Thanksgiving. Thin liquidity, early close.")
    warnings.append("Manual check: any high-impact news today (CPI, NFP, FOMC, PCE)? "
                    "No new trades 30 minutes before or after.")
    return warnings


# ----------------------------------------------------------------------------
# STEP 4: PUT IT ALL TOGETHER
# ----------------------------------------------------------------------------

def save_to_log(row):
    """Add today's reading to macro_log.csv (creates the file if needed)."""
    file_exists = os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def run_check():
    today = date.today()
    print(f"\nGOLD MACRO CHECK  -  {today:%A %d %B %Y}")
    print("=" * 60)

    scores = {}
    gold_price = None

    # Each signal is wrapped in try/except, so one failed download
    # does not stop the rest of the report.
    try:
        gold = get_close_prices(GOLD_TICKER)
        gold_price = float(gold.iloc[-1])
        print(f"\nGold ({GOLD_TICKER}) last close: {gold_price:,.1f}")
        scores["trend"], text = score_trend(gold)
        print(f"  Trend:      {scores['trend']:+d}  {text}")
        print(f"  {check_volatility(gold)}")
    except Exception as error:
        print(f"\nCould not get gold data: {error}")

    try:
        dollar = get_close_prices(DOLLAR_TICKER)
        scores["dollar"], text = score_dollar(dollar)
        print(f"  Dollar:     {scores['dollar']:+d}  {text}")
    except Exception as error:
        print(f"  Could not get dollar data: {error}")

    try:
        real_yield = get_real_yield()
        scores["real_yield"], text = score_real_yield(real_yield)
        print(f"  Real yield: {scores['real_yield']:+d}  {text}")
    except Exception as error:
        print(f"  Could not get real yield data: {error}")

    if gold_price is not None:
        print("\nKey levels (update SUPPORT_LEVELS / RESISTANCE_LEVELS weekly):")
        for line in check_levels(gold_price):
            print(f"  {line}")

    print("\nCalendar:")
    for warning in calendar_warnings(today):
        print(f"  - {warning}")

    total = sum(scores.values())
    if total >= 2:
        bias = "SUPPORTIVE for gold"
    elif total <= -2:
        bias = "AGAINST gold"
    else:
        bias = "MIXED / neutral"
    print("\n" + "=" * 60)
    print(f"Macro bias score: {total:+d} of {len(scores)}  ->  {bias}")
    print("Remember: this is context, not a trade signal. Follow your entry rules.")
    print("=" * 60 + "\n")

    save_to_log({
        "date": today.isoformat(),
        "gold_close": round(gold_price, 1) if gold_price else "",
        "trend": scores.get("trend", ""),
        "dollar": scores.get("dollar", ""),
        "real_yield": scores.get("real_yield", ""),
        "total": total,
        "bias": bias,
    })


if __name__ == "__main__":
    run_check()
