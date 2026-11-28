"""
dashboard.py  -  Auto-updating Gold macro dashboard (built with Streamlit)

It reuses the functions from gold_macro_check.py, so keep both files in the
same folder.

How to run:
  pip install -r requirements.txt
  streamlit run dashboard.py

Your browser opens the dashboard. It refreshes its data every 15 minutes
by itself, as long as the page is open.
"""

import os
from datetime import date, datetime, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

import basket
import deriv_feed
import gold_macro_check as g
import livechart
import pricechart
import sentiment

try:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo("Africa/Nairobi")
except Exception:  # if the timezone database is missing, fall back to UTC
    LOCAL_TZ = timezone.utc

st.set_page_config(page_title="Gold Desk", page_icon="🪙", layout="wide")

STYLE = """
<style>
:root { --bg:#020306; --panel:#0A0F1A; --panel2:#0E1524; --line:#1C2738; --edge:#263449;
        --text:#E6F1F5; --muted:#9FB3BD; --cyan:#7CE6FC; --mag:#FC36BE; color-scheme: dark; }

/* ---- page ---- */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] { background: var(--bg) !important; color: var(--text) !important; }
[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stHeader"] * { color: var(--muted) !important; }
.block-container { padding-top: 3.6rem !important; max-width: 1450px; }

/* ---- text: everything readable on black ---- */
.stApp p, .stApp li, .stApp label, .stApp td, .stApp th,
.stApp div[data-testid="stMarkdownContainer"] { color: var(--text); }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * { color: var(--muted) !important; font-size: .86rem !important; }
h1, h2, h3, h4, h5 { color: var(--cyan) !important; letter-spacing: -0.01em; }
h3 { font-size: 1.12rem !important; margin-top: .5rem; }
a { color: var(--cyan) !important; }
[data-testid="stWidgetLabel"] p, label p { color: var(--text) !important; font-weight: 600; }

/* ---- inputs ---- */
[data-baseweb="select"] > div, [data-baseweb="input"] > div, [data-baseweb="base-input"],
.stTextInput input, .stNumberInput input { background: var(--panel2) !important; color: var(--text) !important; border-color: var(--edge) !important; }
[data-baseweb="select"] *, [data-baseweb="input"] input { color: var(--text) !important; }
[data-baseweb="select"] svg { fill: var(--cyan) !important; }
[data-baseweb="popover"] ul, [data-baseweb="menu"] { background: var(--panel2) !important; }
[data-baseweb="popover"] li, [data-baseweb="popover"] li * { color: var(--text) !important; }
[data-baseweb="popover"] li:hover, [data-baseweb="popover"] li[aria-selected="true"] { background: #16213A !important; }
[data-baseweb="tag"] { background: #0E2A33 !important; border: 1px solid var(--cyan) !important; }
[data-baseweb="tag"] * { color: var(--cyan) !important; }
[data-testid="stSlider"] [role="slider"] { background: var(--cyan) !important; }
[data-testid="stSlider"] div, [data-testid="stThumbValue"], [data-testid="stTickBarMin"], [data-testid="stTickBarMax"] { color: var(--text) !important; }
[data-testid="stCheckbox"] span, [data-testid="stRadio"] label p { color: var(--text) !important; }
.stButton > button { background: var(--panel2); color: var(--cyan); border: 1px solid var(--cyan); border-radius: 999px; font-weight: 700; }
.stButton > button:hover { background: var(--cyan); color: #020306; border-color: var(--cyan); }

/* ---- tabs ---- */
[data-baseweb="tab-list"] { gap: 8px; border-bottom: 1px solid var(--line); }
button[data-baseweb="tab"] { background: var(--panel); border: 1px solid var(--line); border-bottom: none;
    border-radius: 10px 10px 0 0; padding: 9px 22px; }
button[data-baseweb="tab"] p { color: var(--muted) !important; font-weight: 700; font-size: .95rem; }
button[data-baseweb="tab"]:hover p { color: var(--cyan) !important; }
button[data-baseweb="tab"][aria-selected="true"] { background: var(--cyan); border-color: var(--cyan); }
button[data-baseweb="tab"][aria-selected="true"] p { color: #020306 !important; }
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] { display: none; }

/* ---- cards ---- */
[data-testid="stMetric"] { background: var(--panel); border: 1px solid var(--line); border-left: 3px solid var(--cyan);
    border-radius: 12px; padding: 14px 18px; }
[data-testid="stMetricLabel"] p { color: var(--muted) !important; font-weight: 600; }
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * { color: #FFFFFF !important; }
[data-testid="stExpander"] { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; }
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary * { color: var(--text) !important; }
[data-testid="stAlert"] { background: #1A0E17 !important; border: 1px solid var(--mag); border-radius: 10px; }
[data-testid="stAlert"] * { color: #FFD6F1 !important; }
[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }

/* ---- sidebar ---- */
[data-testid="stSidebar"] { background: #05080F !important; border-right: 1px solid var(--line); }
[data-testid="stSidebar"] h3 { margin-top: 1.1rem; }

/* ---- header banner and badges ---- */
.hero { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 16px;
    background: linear-gradient(120deg, #020306 0%, #0B0A1A 55%, #2A0A24 100%);
    border: 1px solid rgba(124,230,252,.35); border-radius: 16px; padding: 20px 26px;
    box-shadow: 0 0 28px rgba(124,230,252,.10), 0 0 40px rgba(252,54,190,.08); }
.hero .hero-title { font-size: 1.7rem; font-weight: 800; color: #FFFFFF !important; letter-spacing: -0.02em; }
.hero .hero-title b { color: var(--cyan) !important; }
.hero .hero-sub { color: #B8C7CF !important; font-size: .95rem; margin-top: 3px; }
.hero .hero-tag { border: 1px solid var(--mag); color: var(--mag) !important; border-radius: 999px;
    padding: 6px 18px; font-weight: 800; letter-spacing: .06em; }
.pill { display: inline-block; padding: 5px 14px; border-radius: 999px; font-weight: 700; font-size: .88rem; margin: 6px 0; }
.pill-up { background: #0E2A33; color: #7CE6FC !important; border: 1px solid rgba(124,230,252,.4); }
.pill-down { background: #2A0E22; color: #FC36BE !important; border: 1px solid rgba(252,54,190,.4); }
.s-card { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px; margin-bottom: 10px; }
.s-card .s-head { display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; }
.s-card .s-name { color: #FFFFFF !important; font-weight: 700; font-size: 1rem; }
.s-card .s-date { color: var(--muted) !important; font-size: .82rem; }
.s-card .s-body { color: var(--text) !important; margin: 8px 0 6px; line-height: 1.5; font-size: .93rem; }
.s-card .s-watch { color: var(--muted) !important; font-size: .86rem; }
.s-card .s-watch b { color: var(--cyan) !important; }
.s-card a { font-size: .85rem; }
.chip { display: inline-block; padding: 2px 11px; border-radius: 999px; font-weight: 700; font-size: .78rem; margin-left: 6px; }
.chip-Bullish { background: #0E2A33; color: #7CE6FC !important; border: 1px solid rgba(124,230,252,.5); }
.chip-Bearish, .chip-Hawkish { background: #2A0E22; color: #FC36BE !important; border: 1px solid rgba(252,54,190,.5); }
.chip-Cautious { background: #2A1F08; color: #FFB020 !important; border: 1px solid rgba(255,176,32,.5); }
.chip-Neutral, .chip-Dovish { background: #141C2B; color: #B8C7CF !important; border: 1px solid #2A3646; }
.n-row { display: flex; gap: 10px; align-items: baseline; padding: 7px 4px; border-bottom: 1px solid var(--line); }
.n-row .n-mark { font-weight: 800; width: 16px; flex: none; }
.n-row .n-up { color: #7CE6FC !important; } .n-row .n-down { color: #FC36BE !important; } .n-row .n-mid { color: #6B7C86 !important; }
.n-row .n-title { color: var(--text) !important; }
.n-row .n-meta { color: var(--muted) !important; font-size: .8rem; margin-left: auto; white-space: nowrap; }
.pill-mid { background: #141C2B; color: #B8C7CF !important; border: 1px solid #2A3646; }
</style>
"""
st.markdown(STYLE, unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# SIDEBAR: your key levels (edit them here, no need to touch the code)
# ----------------------------------------------------------------------------

def parse_levels(text, fallback):
    """Turn '3500, 3450' into [3450, 3500]. Keep the old levels if typed wrong."""
    try:
        values = sorted(float(x) for x in text.split(",") if x.strip())
        return [int(v) if v == int(v) else v for v in values]
    except ValueError:
        st.sidebar.warning("Levels must be numbers separated by commas.")
        return fallback


with st.sidebar:
    st.markdown("### Chart colours")
    chart_theme = st.radio("Theme", ["Neon", "Classic"], horizontal=True,
                           key="chart_theme", label_visibility="collapsed",
                           help="Neon = black, cyan and magenta. Classic = grey, blue and black.")
    st.markdown("### Key levels")
    support_text = st.text_input(
        "Support", ", ".join(str(x) for x in g.SUPPORT_LEVELS))
    resistance_text = st.text_input(
        "Resistance", ", ".join(str(x) for x in g.RESISTANCE_LEVELS))
    st.caption("Update weekly. Separate numbers with commas.")
    st.markdown("### Refresh")
    refresh_seconds = st.selectbox(
        "Yahoo chart and macro update every", [1, 5, 15, 60, 300, 900], index=3,
        format_func=lambda s: f"{s} second(s)" if s < 60 else f"{s // 60} minute(s)")
    with st.expander("About the data"):
        st.markdown(
            "- **Live chart:** Deriv, updates on every tick.\n"
            "- **Yahoo chart:** Yahoo Finance, can be about 15 minutes delayed.\n"
            "- **Dollar index:** Yahoo. **Real yields:** FRED, daily.\n"
            "- Other tabs update at most every 15 seconds.\n"
            "- For context, not for trade execution.")

g.SUPPORT_LEVELS = parse_levels(support_text, g.SUPPORT_LEVELS)
g.RESISTANCE_LEVELS = parse_levels(resistance_text, g.RESISTANCE_LEVELS)


# ----------------------------------------------------------------------------
# DATA (cached, so it is only downloaded again after 15 minutes)
# ----------------------------------------------------------------------------

@st.cache_data(ttl=55, show_spinner="Updating data...")
def load_history():
    """Download Yahoo and FRED history. If one fails, keep going with the rest."""
    sources = {
        "gold": lambda: g.get_close_prices(g.GOLD_TICKER),
        "dollar": lambda: g.get_close_prices(g.DOLLAR_TICKER),
        "real_yield": g.get_real_yield,
    }
    data, errors = {}, []
    for name, fetch in sources.items():
        try:
            data[name] = fetch()
        except Exception as error:
            errors.append(f"Could not get {name} data: {error}")
    fx = {}
    for code, (ticker, _kind) in basket.CURRENCIES.items():
        try:
            fx[code] = g.get_close_prices(ticker)
        except Exception as error:
            errors.append(f"Could not get {code} rate: {error}")
    data["fx"] = fx
    return data, errors


@st.cache_data(ttl=1)
def load_live():
    """Latest live prices from Deriv (shared by both tabs)."""
    try:
        return deriv_feed.get_live_prices(deriv_feed.SYMBOLS)
    except Exception as error:
        return {}, [str(error)]


def load_data():
    """History (cached) with the live Deriv prices laid over today's bar."""
    history, errors = load_history()
    data = dict(history)
    data["fx"] = dict(history.get("fx", {}))
    live, _live_errors = load_live()
    if "XAU" in live and "gold" in data:
        data["gold"] = deriv_feed.overlay(data["gold"], live["XAU"])
    for code in data["fx"]:
        if code in live:
            data["fx"][code] = deriv_feed.overlay(data["fx"][code], live[code])
    data["live"] = live
    return data, list(errors)


def bias_label(total):
    if total >= 2:
        return "SUPPORTIVE for gold"
    if total <= -2:
        return "AGAINST gold"
    return "MIXED / neutral"


# ----------------------------------------------------------------------------
# THE PAGE (this block re-runs by itself every 15 minutes)
# ----------------------------------------------------------------------------

def show_dashboard():
    data, errors = load_data()
    for message in errors:
        st.warning(message)

    scores, notes = {}, {}
    gold = data.get("gold")
    if gold is not None:
        scores["trend"], notes["trend"] = g.score_trend(gold)
    if "dollar" in data:
        scores["dollar"], notes["dollar"] = g.score_dollar(data["dollar"])
    if "real_yield" in data:
        scores["real_yield"], notes["real_yield"] = g.score_real_yield(
            data["real_yield"])
    total = sum(scores.values())

    # --- Top row: price, bias, last update -----------------------------------
    top1, top2, top3 = st.columns(3)
    if gold is not None:
        price = float(gold.iloc[-1])
        change = price - float(gold.iloc[-2])
        top1.metric("Gold latest price", f"{price:,.1f}", f"{change:+.1f}")
    top2.metric("Macro bias score", f"{total:+d} of {len(scores)}",
                bias_label(total), delta_color="off")
    top3.metric("Last updated",
                datetime.now(LOCAL_TZ).strftime("%H:%M:%S, %d %b"))
    pill = "pill-up" if total >= 2 else "pill-down" if total <= -2 else "pill-mid"
    st.markdown(f'<span class="pill {pill}">Macro bias: {bias_label(total)}</span>',
                unsafe_allow_html=True)
    if "XAU" in data.get("live", {}):
        st.caption("Gold and currency prices: live from Deriv.")
    else:
        st.caption("Deriv live feed unavailable (or market closed). "
                   "Showing Yahoo prices, which can be delayed.")

    # --- The three signals ----------------------------------------------------
    st.subheader("Signals")
    labels = {"trend": "Gold trend", "dollar": "US Dollar",
              "real_yield": "Real yields (10yr)"}
    columns = st.columns(3)
    for column, key in zip(columns, labels):
        if key in scores:
            column.metric(labels[key], f"{scores[key]:+d}")
            column.caption(notes[key])
    st.caption("+1 = supportive for gold, 0 = neutral, -1 = headwind for gold.")

    # --- Gold chart with your trend lines --------------------------------------
    if gold is not None:
        st.subheader("Gold, last 150 days")
        chart = pd.DataFrame({
            "Gold": gold,
            "50 SMA": gold.rolling(50).mean(),
            "9 EMA": gold.ewm(span=9, adjust=False).mean(),
            "18 EMA": gold.ewm(span=18, adjust=False).mean(),
        }).tail(150)
        st.line_chart(chart)

        left, right = st.columns(2)
        with left:
            st.subheader("Key levels")
            for line in g.check_levels(price):
                st.write(line)
        with right:
            st.subheader("Volatility")
            st.write(g.check_volatility(gold))

    # --- Dollar and real yield charts -------------------------------------------
    chart_left, chart_right = st.columns(2)
    if "dollar" in data:
        chart_left.subheader("US Dollar index")
        chart_left.line_chart(data["dollar"].tail(90))
    if "real_yield" in data:
        chart_right.subheader("10yr real yield (%)")
        chart_right.line_chart(data["real_yield"].tail(90))

    # --- Calendar warnings --------------------------------------------------------
    st.subheader("Today's warnings")
    for warning in g.calendar_warnings(date.today()):
        st.write(f"- {warning}")

    # --- Save today's reading to your log ------------------------------------------
    if st.button("Save today's reading to my log") and gold is not None:
        g.save_to_log({
            "date": date.today().isoformat(),
            "gold_close": round(price, 1),
            "trend": scores.get("trend", ""),
            "dollar": scores.get("dollar", ""),
            "real_yield": scores.get("real_yield", ""),
            "total": total,
            "bias": bias_label(total),
        })
        st.success("Saved.")

    if os.path.exists(g.LOG_FILE):
        st.subheader("Your log (last 30 entries)")
        st.dataframe(pd.read_csv(g.LOG_FILE).tail(30))


PLOT_CONFIG = {
    "scrollZoom": True, "displaylogo": False,
    "modeBarButtonsToAdd": ["drawline", "drawopenpath", "drawrect",
                            "drawcircle", "eraseshape"],
}


def show_basket_summary():
    """Daily basket breadth (the chart itself is XAU BASKET on the Live chart tab)."""
    data, _errors = load_data()
    gold, fx = data.get("gold"), data.get("fx", {})
    if gold is None or not fx:
        return
    summary = basket.summarise(basket.build_basket(gold, fx))
    above = int(summary["Above 50 SMA"].sum())
    st.subheader("Gold basket: breadth")
    left, right = st.columns([1, 2])
    left.metric("Gold above its 50 SMA in", f"{above} of {len(summary)} currencies")
    right.write(basket.read_breadth(summary))
    right.caption("See the XAU BASKET chart on the Live chart tab.")
    with st.expander("Table: gold priced in each currency (daily)"):
        st.dataframe(summary.round(2))


def show_macro():
    show_dashboard()
    show_basket_summary()


@st.cache_data(ttl=55, show_spinner="Loading chart data...")
def load_ohlc(symbol, timeframe):
    ticker = pricechart.SYMBOLS[symbol][0]
    interval, period, resample = pricechart.TIMEFRAMES[timeframe]
    return pricechart.get_ohlc(ticker, interval, period, resample)


@st.cache_data(ttl=300)
def load_previous_day(symbol):
    ticker = pricechart.SYMBOLS[symbol][0]
    return pricechart.previous_day_levels(pricechart.get_ohlc(ticker, "1d", "15d"))


def show_chart():
    """Interactive candlestick chart with your Backtesting 2.0 indicators."""
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    symbol = col1.selectbox("Symbol", list(pricechart.SYMBOLS), key="chart_symbol")
    timeframe = col2.selectbox("Timeframe", list(pricechart.TIMEFRAMES),
                               index=1, key="chart_timeframe")
    zone_name = col3.selectbox("Time zone", list(pricechart.TIMEZONES),
                               key="chart_zone")
    candles = col4.slider("Candles shown", 50, 400, 120, key="chart_candles")
    shown = st.multiselect("Indicators", list(pricechart.INDICATORS),
                           default=list(pricechart.INDICATORS), key="chart_indicators")
    opt1, opt2 = st.columns(2)
    show_prev = opt1.checkbox("Previous day high / low / equilibrium",
                              value=True, key="chart_prev_day")
    show_levels = opt2.checkbox("My support / resistance levels (Gold)",
                                value=False, key="chart_levels")

    _ticker, deriv_key, scale, decimals = pricechart.SYMBOLS[symbol]
    try:
        df = load_ohlc(symbol, timeframe)
    except Exception as error:
        st.warning(f"Could not load chart data: {error}")
        return
    live, _live_errors = load_live()
    live_price = live.get(deriv_key)
    bid, ask = live.get(f"{deriv_key}_bid"), live.get(f"{deriv_key}_ask")
    bid_ask = (bid, ask) if bid is not None and ask is not None else None

    prev_day = None
    if show_prev:
        try:
            prev_day = load_previous_day(symbol)
        except Exception:
            st.caption("Previous day levels are not available right now.")
    levels = []
    if show_levels and symbol.startswith("Gold"):
        levels = ([(x, "support") for x in g.SUPPORT_LEVELS]
                  + [(x, "resistance") for x in g.RESISTANCE_LEVELS])

    fig = pricechart.make_figure(
        df, shown, candles, levels, live_price,
        uirevision=f"{symbol}-{timeframe}-{candles}", prev_day=prev_day,
        bid_ask=bid_ask, name=pricechart.short_name(symbol), timeframe=timeframe,
        subtitle=pricechart.SUBTITLES.get(symbol, ""),
        tz=pricechart.TIMEZONES[zone_name], spread_scale=scale, decimals=decimals,
        theme=chart_theme)
    st.plotly_chart(fig, config=PLOT_CONFIG)
    st.caption("Drag to move, scroll to zoom, double-click to reset. Use the "
               "toolbar at the top right of the chart to draw lines and boxes. "
               "Candles come from Yahoo Finance. The SELL / BUY box shows Deriv's "
               "live bid and ask; it is a price display, not an order button.")
    if live_price is not None:
        gap = live_price - float(df["Close"].iloc[-1])
        st.caption(f"Yahoo last price {df['Close'].iloc[-1]:,.{decimals}f} vs Deriv "
                   f"live {live_price:,.{decimals}f} (gap {gap:+.{decimals}f}). The "
                   "orange price tag is Deriv's live price. Small gaps are normal: "
                   "Yahoo's gold is futures, Deriv's is spot.")


def embed_html(html, height):
    """Show an HTML page inside the app (newer Streamlit: st.iframe)."""
    if hasattr(st, "iframe"):
        st.iframe(html, height=height)
    else:  # older Streamlit versions
        components.html(html, height=height)


def show_live_chart():
    """Live chart: your browser connects straight to Deriv (no page refresh)."""
    embed_html(livechart.live_chart_html("XAUUSD", "15m", "New York", chart_theme), 930)


@st.cache_data(ttl=600, show_spinner="Reading the markets...")
def load_gauges():
    return sentiment.market_gauges()


@st.cache_data(ttl=3600)
def load_fear_greed():
    return sentiment.cnn_fear_greed()


@st.cache_data(ttl=1800)
def load_cot():
    return sentiment.cot_gold()


@st.cache_data(ttl=900, show_spinner="Reading headlines...")
def load_news(source):
    if source == "Government & central banks":
        return sentiment.headlines(sentiment.GOVERNMENT_QUERY)
    return sentiment.headlines(sentiment.SOURCES[source])


@st.cache_data(ttl=900)
def load_fed():
    return sentiment.fed_releases()


@st.cache_data(ttl=900, show_spinner="Reading headlines...")
def load_all_news():
    """All sources together, for the overall headline mood."""
    everything, failed = [], []
    for name in sentiment.SOURCES:
        try:
            everything += load_news(name)
        except Exception:
            failed.append(name)
    return everything, failed


def stance_chip(stance):
    return f'<span class="chip chip-{stance}">{stance}</span>' if stance else ""


def news_rows(items):
    """Headline list with a coloured mark for the tone of each headline."""
    if not items:
        st.caption("No headlines found.")
        return
    html = []
    for item in items:
        mark, css = ("▲", "n-up") if item["score"] > 0 else ("▼", "n-down") if item["score"] < 0 else ("●", "n-mid")
        when = item["when"].strftime("%d %b %H:%M") if item["when"] else ""
        meta = f'{item["source"]} · {when}'.strip(" ·")
        title = item["title"].replace("<", "&lt;").replace(">", "&gt;")
        html.append(f'<div class="n-row"><span class="n-mark {css}">{mark}</span>'
                    f'<a class="n-title" href="{item["link"]}" target="_blank">{title}</a>'
                    f'<span class="n-meta">{meta}</span></div>')
    st.markdown("".join(html), unsafe_allow_html=True)


def show_sentiment():
    """What the market, Wall Street and top institutions are feeling."""
    top_left, top_right = st.columns([5, 1])
    top_left.caption("Free public data. Bloomberg, S&P Global and WSJ are paywalled, so only "
                     "their public headlines are used. This shows the mood, not trade signals.")
    if top_right.button("Refresh", key="sent_refresh"):
        st.cache_data.clear()
        st.rerun()

    # ---------- overview ----------
    gauges, gauge_errors = load_gauges()
    score, mood, parts = sentiment.risk_mood(gauges)
    news_all, news_failed = load_all_news()
    tone = sentiment.overall_tone(news_all)
    try:
        cot, cot_group = load_cot()
        percentile = float((cot["net"].tail(52) <= cot["net"].iloc[-1]).mean() * 100)
    except Exception:
        cot, cot_group, percentile = None, "", None

    left, right = st.columns([2, 3])
    with left:
        if score is not None:
            st.plotly_chart(sentiment.risk_gauge(score, mood), config={"displayModeBar": False})
            st.caption("Our risk mood (0 = extreme fear, 100 = extreme greed) from the VIX, "
                       "S&P 500 and Nasdaq trend, and the credit spread: "
                       + ", ".join(f"{n} {v}" for n, v in parts) + ".")
        else:
            st.warning("Could not read the market data for the risk mood.")
    with right:
        r1, r2 = st.columns(2)
        by_key = {g_["key"]: g_ for g_ in gauges}
        if "vix" in by_key:
            r1.metric("VIX", f'{by_key["vix"]["value"]:.1f}', f'{by_key["vix"]["chg1"]:+.2f} today',
                      delta_color="inverse")
        try:
            fg, fg_label = load_fear_greed()
            r2.metric("CNN Fear & Greed", f"{fg:.0f}", fg_label, delta_color="off")
        except Exception:
            r2.metric("CNN Fear & Greed", "n/a", "unofficial feed", delta_color="off")
        r3, r4 = st.columns(2)
        if tone:
            lean = "bullish" if tone["bullish"] > tone["bearish"] else "bearish" if tone["bearish"] > tone["bullish"] else "balanced"
            r3.metric("Headline mood (gold)", lean.title(),
                      f'{tone["bullish"]:.0f}% up · {tone["bearish"]:.0f}% down · {tone["count"]} headlines',
                      delta_color="off")
        else:
            r3.metric("Headline mood (gold)", "n/a", delta_color="off")
        if percentile is not None:
            r4.metric("Hedge-fund gold positioning", f"{percentile:.0f}th percentile",
                      f'{cot["tonnes"].iloc[-1]:,.0f} t net long (52-week range)', delta_color="off")
        else:
            r4.metric("Hedge-fund gold positioning", "n/a", delta_color="off")

    # ---------- what Wall Street watches ----------
    st.subheader("What Wall Street is watching")
    for message in gauge_errors:
        st.caption(f"Could not read {message}")
    cols = st.columns(4)
    for i, g_ in enumerate(gauges):
        d = g_["decimals"]
        unit_pct = g_["kind"] == "index"
        delta = f'{g_["chg1"]:+.2f}%' if unit_pct else f'{g_["chg1"]:+.{max(d, 2)}f}'
        cols[i % 4].metric(g_["label"], f'{g_["value"]:,.{d}f}', delta,
                           delta_color="inverse" if g_["kind"] in ("vix", "spread") else "normal")
        cols[i % 4].caption(g_["read"])

    # ---------- positioning ----------
    st.subheader("What big funds are doing (CFTC positioning)")
    if cot is not None and len(cot):
        fig = go.Figure(go.Scatter(x=cot["date"], y=cot["tonnes"], mode="lines",
                                   line=dict(color="#7CE6FC", width=2.5), fill="tozeroy",
                                   fillcolor="rgba(124,230,252,0.12)", name="Net long (tonnes)"))
        fig.update_layout(template="plotly_dark", height=300, paper_bgcolor="rgba(0,0,0,0)",
                          plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=10, b=10),
                          yaxis_title="tonnes", font=dict(color="#B8C7CF"),
                          xaxis=dict(gridcolor="#111925"), yaxis=dict(gridcolor="#111925"))
        st.plotly_chart(fig, config={"displayModeBar": False})
        change4 = cot["tonnes"].iloc[-1] - cot["tonnes"].iloc[-5] if len(cot) > 4 else 0
        st.caption(f"{cot_group}, COMEX gold futures, weekly. Latest report "
                   f'{cot["date"].iloc[-1]:%d %b %Y}: {cot["tonnes"].iloc[-1]:,.0f} tonnes net long '
                   f"({change4:+,.0f} t over 4 weeks). Falling positions mean funds are selling; "
                   "very low positions can mean selling is exhausted. Source: CFTC.")
    else:
        st.caption("CFTC positioning is not available right now.")

    # ---------- institutions ----------
    st.subheader("What top institutions are saying")
    views = sentiment.load_views("institution_views.csv")
    if len(views):
        f1, f2 = st.columns(2)
        cats = f1.multiselect("Type", sorted(views["category"].unique()), key="views_cat")
        stances = f2.multiselect("Stance", sorted(views["stance"].unique()), key="views_stance")
        shown_views = views
        if cats:
            shown_views = shown_views[shown_views["category"].isin(cats)]
        if stances:
            shown_views = shown_views[shown_views["stance"].isin(stances)]
        for _, v in shown_views.iterrows():
            date = v["date"].strftime("%d %b %Y") if pd.notna(v["date"]) else ""
            link = f'<a href="{v["url"]}" target="_blank">Source</a>' if v["url"] else ""
            st.markdown(
                f'<div class="s-card"><div class="s-head"><span class="s-name">{v["institution"]}'
                f'{stance_chip(v["stance"])}</span><span class="s-date">{v["category"]} · {v["topic"]} · {date}</span></div>'
                f'<div class="s-body">{v["summary"]}</div>'
                f'<div class="s-watch"><b>Watching:</b> {v["watching"]} &nbsp; {link}</div></div>',
                unsafe_allow_html=True)
        st.caption("Summaries are short paraphrases of public reports and of the World Gold Council "
                   "documents you shared, dated as shown. The stance is about the topic named. "
                   "Edit institution_views.csv in your GitHub repo to add or update entries.")
    else:
        st.caption("Add rows to institution_views.csv to list institution views here.")

    # ---------- headlines ----------
    st.subheader("Headlines by source")
    names = list(sentiment.SOURCES) + ["Government & central banks"]
    source = st.radio("Source", names, horizontal=True, key="news_source", label_visibility="collapsed")
    try:
        items = load_news(source)
        mood_here = sentiment.overall_tone(items)
        if mood_here:
            st.caption(f'{source}: {mood_here["bullish"]:.0f}% of headlines lean bullish for gold, '
                       f'{mood_here["bearish"]:.0f}% bearish, {mood_here["neutral"]:.0f}% neutral.')
        news_rows(items)
    except Exception as error:
        st.caption(f"Could not load {source} headlines: {error}")
    if news_failed:
        st.caption("Not loaded for the overall mood: " + ", ".join(news_failed))
    st.caption("▲ leans bullish for gold, ▼ leans bearish, ● neutral. The mark comes from a simple "
               "word list (for example: rally, safe haven vs. plunge, rate hike), so it is rough.")

    # ---------- government ----------
    st.subheader("Government and central bank releases")
    try:
        fed = load_fed()
        html = []
        for item in fed:
            when = item["when"].strftime("%d %b %Y") if item["when"] else ""
            title = item["title"].replace("<", "&lt;").replace(">", "&gt;")
            html.append(f'<div class="n-row"><span class="n-mark n-mid">●</span>'
                        f'<a class="n-title" href="{item["link"]}" target="_blank">{title}</a>'
                        f'<span class="n-meta">Federal Reserve · {when}</span></div>')
        st.markdown("".join(html) or "No releases found.", unsafe_allow_html=True)
    except Exception as error:
        st.caption(f"Could not load Federal Reserve releases: {error}")


st.markdown(
    '<div class="hero"><div><div class="hero-title">🪙 Gold <b>Desk</b></div>'
    '<div class="hero-sub">Live charts · XAU basket · market sentiment · price alerts</div></div>'
    '<div class="hero-tag">XAUUSD</div></div>', unsafe_allow_html=True)
refresh_fast = st.fragment(run_every=refresh_seconds)
refresh_slow = st.fragment(run_every=max(refresh_seconds, 15))
tab_live, tab_sent, tab_macro, tab_chart = st.tabs(
    ["Live chart", "Market sentiment", "Macro & basket", "Chart (Yahoo)"])
# The live chart updates itself in the browser, so it sits outside the refresh
# timers (a refresh would reload it and lose your zoom).
with tab_live:
    show_live_chart()
with tab_sent:
    show_sentiment()
with tab_macro:
    refresh_slow(show_macro)()
with tab_chart:
    refresh_fast(show_chart)()
st.caption("Context filter only. Not financial advice and not a trade signal. "
           "Your entry rules decide the trade.")
