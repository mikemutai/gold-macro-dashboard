"""
basket.py  -  Gold priced in other currencies (an "XAU basket")

Why this matters: gold is quoted in US dollars. If gold rises in USD but not in
EUR, GBP or JPY, the move is mostly the dollar weakening. If gold rises in
ALL of them, the strength is in gold itself.

Used by dashboard.py. Keep it in the same folder.
"""

import pandas as pd

# code: (Yahoo Finance ticker, how the ticker is quoted)
#   "usd_per" = US dollars per 1 unit of the currency (e.g. EURUSD)
#   "per_usd" = units of the currency per 1 US dollar (e.g. USDJPY)
CURRENCIES = {
    "EUR": ("EURUSD=X", "usd_per"),
    "GBP": ("GBPUSD=X", "usd_per"),
    "JPY": ("USDJPY=X", "per_usd"),
    "CHF": ("USDCHF=X", "per_usd"),
    "AUD": ("AUDUSD=X", "usd_per"),
    "CAD": ("USDCAD=X", "per_usd"),
    "KES": ("KES=X", "per_usd"),
}


def _clean(series):
    """Make dates comparable: remove time zones and times, drop duplicates."""
    s = series.copy()
    s.index = pd.to_datetime(s.index)
    if s.index.tz is not None:
        s.index = s.index.tz_localize(None)
    s.index = s.index.normalize()
    return s[~s.index.duplicated(keep="last")]


def to_currency(gold_usd, rate, kind):
    """Convert the gold price from USD into another currency."""
    return gold_usd / rate if kind == "usd_per" else gold_usd * rate


def build_basket(gold, fx, intraday=False):
    """
    Return a table with the gold price in USD and in each currency.
    intraday=True keeps the time of day (for 5m, 15m, 1h charts).
    """
    gold = gold if intraday else _clean(gold)
    columns = {"USD": gold}
    for code, rate in fx.items():
        if intraday:
            # line the currency up with gold's timestamps, using the latest rate
            rate = rate.reindex(rate.index.union(gold.index)).ffill().reindex(gold.index)
        else:
            rate = _clean(rate).reindex(gold.index).ffill()
        columns[code] = to_currency(gold, rate, CURRENCIES[code][1])
    return pd.DataFrame(columns).dropna()


def summarise(table):
    """One row per currency: last price, recent changes, and trend."""
    rows = []
    for code in table.columns:
        s = table[code]
        rows.append({
            "Currency": code,
            "Last": s.iloc[-1],
            "1d %": (s.iloc[-1] / s.iloc[-2] - 1) * 100,
            "5d %": (s.iloc[-1] / s.iloc[-6] - 1) * 100,
            "20d %": (s.iloc[-1] / s.iloc[-21] - 1) * 100,
            "Above 50 SMA": bool(s.iloc[-1] > s.rolling(50).mean().iloc[-1]),
        })
    return pd.DataFrame(rows).set_index("Currency")


def read_breadth(summary):
    """Plain-English reading of how many currencies show gold in an uptrend."""
    flags = summary["Above 50 SMA"].astype(bool)
    usd_up = bool(flags["USD"])
    share = flags.drop("USD").mean()
    if share >= 0.75 and usd_up:
        return ("Broad strength: gold is above its 50 SMA in USD and most other "
                "currencies. The strength is in gold itself.")
    if share <= 0.25 and not usd_up:
        return ("Broad weakness: gold is below its 50 SMA in USD and most other "
                "currencies. The weakness is in gold itself, not just the dollar.")
    if share >= 0.75 and not usd_up:
        return ("Gold is weak in USD but above trend in most other currencies. "
                "This looks more like a strong-dollar move than a gold move.")
    if share <= 0.25 and usd_up:
        return ("Gold is strong in USD but below trend in most other currencies. "
                "This looks more like a weak-dollar move than a gold move.")
    return "Mixed: gold's trend depends on the currency. No clear broad signal."
