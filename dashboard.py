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
import streamlit as st
import streamlit.components.v1 as components

import basket
import deriv_feed
import gold_macro_check as g
import livechart
import pricechart

try:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo("Africa/Nairobi")
except Exception:  # if the timezone database is missing, fall back to UTC
    LOCAL_TZ = timezone.utc

st.set_page_config(page_title="Gold Desk", page_icon="🪙", layout="wide")

STYLE = """
<style>
.stApp { background: #EEF0F3; }
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1.1rem; max-width: 1450px; }
h1, h2, h3, h4 { color: #14213D; letter-spacing: -0.01em; }
h3 { font-size: 1.15rem !important; margin-top: 0.6rem; }
[data-testid="stMetric"] { background: #fff; border: 1px solid #E1E4E8; border-radius: 12px;
    padding: 14px 18px; box-shadow: 0 1px 2px rgba(16,24,40,.06); }
[data-testid="stMetricLabel"] p { color: #5B6572; font-weight: 600; }
[data-testid="stMetricValue"] { color: #14213D; }
[data-baseweb="tab-list"] { gap: 6px; border-bottom: 1px solid #D0D5DD; }
button[data-baseweb="tab"] { background: #fff; border: 1px solid #E1E4E8; border-bottom: none;
    border-radius: 10px 10px 0 0; padding: 8px 18px; font-weight: 700; color: #475467; }
button[data-baseweb="tab"][aria-selected="true"] { background: #1F4FD8; color: #fff; }
button[data-baseweb="tab"][aria-selected="true"] p { color: #fff; }
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] { display: none; }
[data-testid="stSidebar"] { background: #fff; border-right: 1px solid #E1E4E8; }
[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
[data-testid="stExpander"] { background: #fff; border: 1px solid #E1E4E8; border-radius: 12px; }
.hero { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;
    background: linear-gradient(120deg, #14213D 0%, #1F4FD8 100%); color: #fff;
    border-radius: 16px; padding: 18px 24px; box-shadow: 0 6px 18px rgba(20,33,61,.25); }
.hero-title { font-size: 1.6rem; font-weight: 800; letter-spacing: -0.02em; }
.hero-sub { opacity: .8; font-size: .9rem; margin-top: 2px; }
.hero-tag { background: rgba(255,255,255,.15); border: 1px solid rgba(255,255,255,.3);
    border-radius: 999px; padding: 6px 16px; font-weight: 700; color: #F5C451; }
.pill { display: inline-block; padding: 5px 14px; border-radius: 999px; font-weight: 700; font-size: .85rem; }
.pill-up { background: #E3F4EA; color: #1B7F45; }
.pill-down { background: #FDE8E8; color: #B42318; }
.pill-mid { background: #E4E7EC; color: #475467; }
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
    st.header("Your key levels")
    support_text = st.text_input(
        "Support", ", ".join(str(x) for x in g.SUPPORT_LEVELS))
    resistance_text = st.text_input(
        "Resistance", ", ".join(str(x) for x in g.RESISTANCE_LEVELS))
    st.caption("Update these weekly. Separate with commas.")
    st.header("Refresh")
    refresh_seconds = st.selectbox(
        "Update every", [1, 5, 15, 60, 300, 900], index=3,
        format_func=lambda s: f"{s} second(s)" if s < 60 else f"{s // 60} minute(s)")
    st.caption("The chart updates at this rate. The other tabs update at most "
               "every 15 seconds. 1 second is the fastest that makes sense, because "
               "Deriv sends about one price per second.")
    st.caption("Gold and currency prices are live from Deriv. The dollar index "
               "(Yahoo) can be delayed about 15 minutes and real yields are daily. "
               "For context, not for trade execution.")

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
        tz=pricechart.TIMEZONES[zone_name], spread_scale=scale, decimals=decimals)
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


TV_SYMBOLS = {"Gold (XAUUSD)": "OANDA:XAUUSD", "Gold in EUR (XAUEUR)": "OANDA:XAUEUR",
              "Gold in GBP (XAUGBP)": "OANDA:XAUGBP", "Gold in JPY (XAUJPY)": "OANDA:XAUJPY",
              "EURUSD": "OANDA:EURUSD",
              "GBPUSD": "OANDA:GBPUSD", "USDJPY": "OANDA:USDJPY",
              "GBPJPY": "OANDA:GBPJPY"}
TV_INTERVALS = {"5m": "5", "15m": "15", "30m": "30", "1h": "60", "4h": "240", "1D": "D"}


def embed_html(html, height):
    """Show an HTML page inside the app (newer Streamlit: st.iframe)."""
    if hasattr(st, "iframe"):
        st.iframe(html, height=height)
    else:  # older Streamlit versions
        components.html(html, height=height)


def show_live_chart():
    """Live chart: your browser connects straight to Deriv (no page refresh)."""
    embed_html(livechart.live_chart_html("XAUUSD", "15m", "New York"), 930)


def show_tradingview():
    """TradingView's free chart widget: full toolbar, drawing tools, indicators."""
    c1, c2, c3 = st.columns(3)
    symbol = c1.selectbox("Symbol", list(TV_SYMBOLS), key="tv_symbol")
    interval = c2.selectbox("Timeframe", list(TV_INTERVALS), index=1, key="tv_interval")
    zone_name = c3.selectbox("Time zone", list(pricechart.TIMEZONES), key="tv_zone")
    embed_html(
        livechart.tradingview_widget_html(
            TV_SYMBOLS[symbol], TV_INTERVALS[interval],
            pricechart.TIMEZONES[zone_name], height=740),
        760)
    st.caption("TradingView's own widget and prices (not Deriv's). Add your "
               "indicators from its Indicators menu: EMA 50, EMA 18 and EMA 9 "
               "(Exponential Moving Average, source close) and SMA 50 (Moving "
               "Average, source close). Drawings are not saved without a TradingView "
               "account.")


st.markdown(
    '<div class="hero"><div><div class="hero-title">🪙 Gold Desk</div>'
    '<div class="hero-sub">Live charts · XAU basket · macro bias · price alerts</div></div>'
    '<div class="hero-tag">XAUUSD</div></div>', unsafe_allow_html=True)
refresh_fast = st.fragment(run_every=refresh_seconds)
refresh_slow = st.fragment(run_every=max(refresh_seconds, 15))
tab_live, tab_tv, tab_macro, tab_chart = st.tabs(
    ["Live chart", "TradingView", "Macro & basket", "Chart (Yahoo)"])
# The two TradingView charts update themselves in the browser, so they sit
# outside the refresh timers (a refresh would reload them and lose your zoom).
with tab_live:
    show_live_chart()
with tab_tv:
    show_tradingview()
with tab_macro:
    refresh_slow(show_macro)()
with tab_chart:
    refresh_fast(show_chart)()
st.caption("Context filter only. Not financial advice and not a trade signal. "
           "Your entry rules decide the trade.")
