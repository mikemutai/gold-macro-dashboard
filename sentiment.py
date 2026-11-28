"""
sentiment.py  -  Market sentiment for the Gold Desk dashboard

What it reads (all free and public):
  * Markets that Wall Street watches: VIX, S&P 500, Nasdaq 100, US yields,
    real yields, breakeven inflation, the 10y-2y curve, the high-yield credit
    spread, the US dollar and gold (Yahoo Finance and FRED).
  * CNN Fear & Greed (unofficial feed, optional).
  * Institutional positioning: CFTC Commitments of Traders for COMEX gold.
  * Headlines from Bloomberg, Reuters, WSJ, S&P Global, World Gold Council,
    CNBC and Kitco (through Google News, headlines and links only), plus
    Federal Reserve releases.
  * institution_views.csv: what the World Gold Council, banks and central banks
    are saying. You can edit that file.

Bloomberg, S&P Global, WSJ and most bank research are paywalled, so only public
headlines and links are used. The scores here are simple and transparent. They
describe the mood. They are not trade signals.
"""

import io
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import pandas as pd
import plotly.graph_objects as go
import requests
import yfinance as yf

UA = {"User-Agent": "Mozilla/5.0 (Gold Desk dashboard)"}
TIMEOUT = 20


def _get(url, **kwargs):
    response = requests.get(url, headers=UA, timeout=TIMEOUT, **kwargs)
    response.raise_for_status()
    return response


# ----------------------------------------------------------------------------
# MARKET GAUGES
# ----------------------------------------------------------------------------

def fred(series_id):
    """A FRED data series (free, no account needed)."""
    text = _get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}").text
    table = pd.read_csv(io.StringIO(text))
    values = pd.to_numeric(table.iloc[:, 1], errors="coerce")
    values.index = pd.to_datetime(table.iloc[:, 0])
    return values.dropna()


def yahoo(ticker, period="1y"):
    data = yf.download(ticker, period=period, interval="1d", progress=False,
                       auto_adjust=True)
    if data.empty:
        raise RuntimeError(f"No data for {ticker}")
    close = data["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    return close.dropna()


# key, label, source, id, kind, decimals
GAUGES = [
    ("vix", "VIX (fear index)", "yahoo", "^VIX", "vix", 2),
    ("spx", "S&P 500", "yahoo", "^GSPC", "index", 0),
    ("ndx", "Nasdaq 100", "yahoo", "^NDX", "index", 0),
    ("dxy", "US dollar index", "yahoo", "DX-Y.NYB", "index", 2),
    ("gold", "Gold (futures)", "yahoo", "GC=F", "index", 1),
    ("us10", "US 10-year yield (%)", "fred", "DGS10", "yield", 2),
    ("us2", "US 2-year yield (%)", "fred", "DGS2", "yield", 2),
    ("curve", "10y minus 2y (pts)", "fred", "T10Y2Y", "curve", 2),
    ("real10", "10-year real yield (%)", "fred", "DFII10", "yield", 2),
    ("be10", "10-year breakeven inflation (%)", "fred", "T10YIE", "yield", 2),
    ("hy", "High-yield credit spread (pts)", "fred", "BAMLH0A0HYM2", "spread", 2),
]


def _read(kind, series, value, change5):
    """A short plain-English reading of a gauge."""
    if kind == "vix":
        if value < 15:
            return "Calm"
        if value < 20:
            return "Normal"
        if value < 30:
            return "Elevated fear"
        return "Stress"
    if kind == "index":
        if len(series) >= 200:
            pct = (value / series.rolling(200).mean().iloc[-1] - 1) * 100
            return f"{pct:+.1f}% vs 200-day average ({'above' if pct >= 0 else 'below'} trend)"
        return "Not enough history"
    if kind == "yield":
        if change5 > 0.05:
            return "Rising over 5 days"
        if change5 < -0.05:
            return "Falling over 5 days"
        return "Flat over 5 days"
    if kind == "curve":
        if value < 0:
            return "Inverted (recession warning)"
        return "Flat" if value < 0.5 else "Normal slope"
    if kind == "spread":
        if value < 3.5:
            return "Tight (calm credit)"
        if value < 5:
            return "Normal"
        return "Wide (credit stress)"
    return ""


def market_gauges():
    """Returns (list of gauge dicts, list of error messages)."""
    rows, errors = [], []
    for key, label, source, ident, kind, decimals in GAUGES:
        try:
            series = yahoo(ident) if source == "yahoo" else fred(ident)
            value = float(series.iloc[-1])
            chg1 = value - float(series.iloc[-2])
            chg5 = value - float(series.iloc[-6]) if len(series) > 5 else 0.0
            pct200 = None
            if kind == "index" and len(series) >= 200:
                pct200 = (value / series.rolling(200).mean().iloc[-1] - 1) * 100
            if kind == "index":   # show index moves in percent
                chg1 = chg1 / (value - chg1) * 100
                chg5 = chg5 / (value - chg5) * 100
            rows.append(dict(key=key, label=label, value=value, decimals=decimals,
                             chg1=chg1, chg5=chg5, pct200=pct200, kind=kind,
                             read=_read(kind, series, value, chg5)))
        except Exception as error:
            errors.append(f"{label}: {error}")
    return rows, errors


def _clamp(x, low=0.0, high=100.0):
    return max(low, min(high, x))


def risk_mood(rows):
    """
    Our own 0-100 risk mood (0 = extreme fear, 100 = extreme greed) built from
    four ingredients. It is NOT the CNN Fear & Greed index.
    """
    by_key = {r["key"]: r for r in rows}
    parts = []
    if "vix" in by_key:      # VIX 12 -> 100, VIX 30 -> 0
        parts.append(("VIX", _clamp((30 - by_key["vix"]["value"]) / 18 * 100), 0.35))
    if "spx" in by_key and by_key["spx"]["pct200"] is not None:   # -10% -> 0, +10% -> 100
        parts.append(("S&P 500 vs 200-day", _clamp((by_key["spx"]["pct200"] + 10) / 20 * 100), 0.25))
    if "ndx" in by_key and by_key["ndx"]["pct200"] is not None:
        parts.append(("Nasdaq vs 200-day", _clamp((by_key["ndx"]["pct200"] + 10) / 20 * 100), 0.15))
    if "hy" in by_key:       # spread 3 -> 100, 7 -> 0
        parts.append(("Credit spread", _clamp((7 - by_key["hy"]["value"]) / 4 * 100), 0.25))
    if not parts:
        return None, "Not available", []
    total_weight = sum(w for _, _, w in parts)
    score = sum(s * w for _, s, w in parts) / total_weight
    return score, mood_label(score), [(n, round(s)) for n, s, _ in parts]


def mood_label(score):
    if score < 25:
        return "Extreme fear"
    if score < 45:
        return "Fear"
    if score < 55:
        return "Neutral"
    if score < 75:
        return "Greed"
    return "Extreme greed"


def cnn_fear_greed():
    """CNN Fear & Greed (an unofficial feed that may change or stop working)."""
    data = _get("https://production.dataviz.cnn.io/index/fearandgreed/graphdata").json()
    item = data["fear_and_greed"]
    return float(item["score"]), str(item["rating"]).title()


def risk_gauge(score, label):
    """Half-circle dial in the dashboard colours."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score, number=dict(font=dict(size=44, color="#FFFFFF")),
        title=dict(text=f"<b>{label}</b>", font=dict(size=20, color="#7CE6FC")),
        gauge=dict(
            axis=dict(range=[0, 100], tickcolor="#9FB3BD", tickfont=dict(color="#9FB3BD")),
            bar=dict(color="#7CE6FC", thickness=0.28), bgcolor="#0A0F1A", borderwidth=0,
            steps=[dict(range=[0, 25], color="#FC36BE"), dict(range=[25, 45], color="#7A2563"),
                   dict(range=[45, 55], color="#2A3646"), dict(range=[55, 75], color="#1E6F80"),
                   dict(range=[75, 100], color="#3FA9C2")])))
    fig.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#E6F1F5"))
    return fig


# ----------------------------------------------------------------------------
# INSTITUTIONAL POSITIONING (CFTC Commitments of Traders, COMEX gold)
# ----------------------------------------------------------------------------

CFTC_DISAGGREGATED = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"
CFTC_LEGACY = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
TONNES_PER_CONTRACT = 0.00311035   # 100 troy ounces


def _cot_rows(url, long_col, short_col, weeks):
    params = {"$where": "market_and_exchange_names like 'GOLD - COMMODITY EXCHANGE INC.%'",
              "$order": "report_date_as_yyyy_mm_dd DESC", "$limit": str(weeks)}
    rows = _get(url, params=params).json()
    if not rows:
        raise RuntimeError("no rows")
    table = pd.DataFrame(rows)
    table["date"] = pd.to_datetime(table["report_date_as_yyyy_mm_dd"])
    table["net"] = (pd.to_numeric(table[long_col], errors="coerce")
                    - pd.to_numeric(table[short_col], errors="coerce"))
    table["tonnes"] = table["net"] * TONNES_PER_CONTRACT
    return table.sort_values("date")[["date", "net", "tonnes"]].dropna().reset_index(drop=True)


def cot_gold(weeks=60):
    """
    Weekly net long of 'managed money' (hedge funds) in COMEX gold futures.
    Falls back to the older 'non-commercial' report if needed.
    Returns (table, group name).
    """
    try:
        return (_cot_rows(CFTC_DISAGGREGATED, "m_money_positions_long_all",
                          "m_money_positions_short_all", weeks), "Managed money (hedge funds)")
    except Exception:
        return (_cot_rows(CFTC_LEGACY, "noncomm_positions_long_all",
                          "noncomm_positions_short_all", weeks), "Large speculators (non-commercial)")


# ----------------------------------------------------------------------------
# HEADLINES AND TONE
# ----------------------------------------------------------------------------

SOURCES = {
    "Bloomberg": "site:bloomberg.com (gold OR markets OR Fed OR yields)",
    "Reuters": "site:reuters.com (gold OR Fed OR markets)",
    "Wall Street Journal": "site:wsj.com (gold OR Fed OR stocks)",
    "S&P Global": "site:spglobal.com (gold OR markets OR PMI)",
    "World Gold Council": '(site:gold.org OR "World Gold Council")',
    "CNBC": "site:cnbc.com (gold OR Fed OR stocks)",
    "Kitco": "site:kitco.com gold",
}
GOVERNMENT_QUERY = '(Fed OR "Federal Reserve" OR Treasury OR "central bank") gold'
FED_FEED = "https://www.federalreserve.gov/feeds/press_monetary.xml"

# Simple word lists: what usually helps or hurts gold prices in a headline.
BULLISH = ["safe haven", "safe-haven", "rally", "rallies", "surge", "surges", "soar", "jump",
           "jumps", "record high", "gains", "rebound", "rebounds", "bounce", "rate cut",
           "rate cuts", "dovish", "weaker dollar", "dollar falls", "dollar slips",
           "central bank buying", "central banks buy", "inflation fears", "uncertainty",
           "tensions", "geopolitical", "inflows", "upgrade", "raises forecast", "bullish",
           "rises", "climbs", "recovers"]
BEARISH = ["plunge", "plunges", "slump", "slumps", "tumble", "tumbles", "sell-off", "selloff",
           "drop", "drops", "falls", "fall", "slide", "slides", "decline", "declines",
           "loses", "rate hike", "rate hikes", "hawkish", "stronger dollar", "dollar rises",
           "dollar climbs", "outflows", "profit-taking", "yields rise", "yields climb",
           "downgrade", "cuts forecast", "bearish", "pressure", "worst", "lowest", "weakens"]


def tone_score(title):
    """+1 for each bullish-for-gold phrase, -1 for each bearish one."""
    text = title.lower()
    return sum(text.count(w) for w in BULLISH) - sum(text.count(w) for w in BEARISH)


def tone_label(score):
    return "Bullish" if score > 0 else "Bearish" if score < 0 else "Neutral"


def _parse_items(xml_bytes, limit):
    root = ET.fromstring(xml_bytes)
    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        published = item.findtext("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date")
        source_node = item.find("source")
        source = source_node.text.strip() if source_node is not None and source_node.text else ""
        if source and title.endswith(f" - {source}"):
            title = title[: -len(f" - {source}")]
        try:
            when = parsedate_to_datetime(published) if published else None
        except Exception:
            try:
                when = pd.Timestamp(published).to_pydatetime()
            except Exception:
                when = None
        items.append(dict(title=title, link=link, source=source, when=when,
                          score=tone_score(title)))
    items.sort(key=lambda x: (x["when"] is not None, x["when"].timestamp() if x["when"] else 0),
               reverse=True)
    return items[:limit]


def headlines(query, days=7, limit=15):
    """Headlines from Google News for a search query (titles and links only)."""
    url = ("https://news.google.com/rss/search?q=" + quote(f"{query} when:{days}d")
           + "&hl=en-US&gl=US&ceid=US:en")
    return _parse_items(_get(url).content, limit)


def fed_releases(limit=10):
    """Latest monetary-policy releases from the Federal Reserve."""
    return _parse_items(_get(FED_FEED).content, limit)


def overall_tone(items):
    """Share of headlines that lean bullish / bearish / neutral for gold."""
    if not items:
        return None
    n = len(items)
    bull = sum(1 for i in items if i["score"] > 0)
    bear = sum(1 for i in items if i["score"] < 0)
    return dict(bullish=bull / n * 100, bearish=bear / n * 100,
                neutral=(n - bull - bear) / n * 100, count=n,
                net=sum(i["score"] for i in items))


# ----------------------------------------------------------------------------
# WHAT INSTITUTIONS ARE SAYING (edit institution_views.csv)
# ----------------------------------------------------------------------------

def load_views(path="institution_views.csv"):
    """Reads institution_views.csv. Returns an empty table if it is missing."""
    columns = ["date", "institution", "category", "topic", "stance", "summary",
               "watching", "url"]
    try:
        table = pd.read_csv(path)
    except Exception:
        return pd.DataFrame(columns=columns)
    for column in columns:
        if column not in table.columns:
            table[column] = ""
    table["date"] = pd.to_datetime(table["date"], errors="coerce")
    return table.fillna("").sort_values("date", ascending=False).reset_index(drop=True)
