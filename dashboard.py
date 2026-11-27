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

import basket
import deriv_feed
import gold_macro_check as g
import pricechart

try:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo("Africa/Nairobi")
except Exception:  # if the timezone database is missing, fall back to UTC
    LOCAL_TZ = timezone.utc

st.set_page_config(page_title="Gold Macro Dashboard", page_icon="🪙", layout="wide")


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


def show_basket():
    """Gold priced in USD and other currencies."""
    data, _errors = load_data()
    gold, fx = data.get("gold"), data.get("fx", {})
    if gold is None or not fx:
        st.warning("The basket needs gold and currency data. "
                   "See the warnings on the Macro check tab.")
        return
    table = basket.build_basket(gold, fx)
    summary = basket.summarise(table)
    above = int(summary["Above 50 SMA"].sum())
    st.metric("Gold above its 50 SMA in", f"{above} of {len(summary)} currencies")
    st.write(basket.read_breadth(summary))
    st.subheader("Gold priced in each currency")
    st.dataframe(summary.round(2))
    st.subheader("Last 120 days, all set to 100 at the start")
    st.line_chart(table.tail(120) / table.tail(120).iloc[0] * 100)
    st.caption("Lines that move together mean the move is in gold itself. "
               "If USD moves differently from the rest, the dollar is driving it.")


@st.cache_data(ttl=55, show_spinner="Loading chart data...")
def load_ohlc(symbol, timeframe):
    ticker = pricechart.SYMBOLS[symbol][0]
    interval, period, resample = pricechart.TIMEFRAMES[timeframe]
    return pricechart.get_ohlc(ticker, interval, period, resample)


def show_chart():
    """Interactive candlestick chart with your Backtesting 2.0 indicators."""
    col1, col2, col3 = st.columns([2, 1, 1])
    symbol = col1.selectbox("Symbol", list(pricechart.SYMBOLS), key="chart_symbol")
    timeframe = col2.selectbox("Timeframe", list(pricechart.TIMEFRAMES),
                               index=1, key="chart_timeframe")
    candles = col3.slider("Candles shown", 50, 400, 120, key="chart_candles")
    shown = st.multiselect("Indicators", list(pricechart.INDICATORS),
                           default=list(pricechart.INDICATORS), key="chart_indicators")
    is_gold = symbol.startswith("Gold")
    show_levels = is_gold and st.checkbox("Show my support/resistance levels",
                                          value=True, key="chart_levels")
    try:
        df = load_ohlc(symbol, timeframe)
    except Exception as error:
        st.warning(f"Could not load chart data: {error}")
        return
    live, _live_errors = load_live()
    live_price = live.get(pricechart.SYMBOLS[symbol][1])
    levels = []
    if show_levels:
        levels = ([(x, "support") for x in g.SUPPORT_LEVELS]
                  + [(x, "resistance") for x in g.RESISTANCE_LEVELS])
    fig = pricechart.make_figure(
        df, shown, candles, levels, live_price,
        uirevision=f"{symbol}-{timeframe}-{candles}")
    st.plotly_chart(fig, config={"scrollZoom": True, "displaylogo": False})
    st.caption("Drag to move, scroll to zoom, double-click to reset. Times are "
               "Nairobi time. Candles come from Yahoo Finance.")
    if live_price is not None:
        gap = live_price - float(df["Close"].iloc[-1])
        st.caption(f"Yahoo last price {df['Close'].iloc[-1]:,.2f} vs Deriv live "
                   f"{live_price:,.2f} (gap {gap:+.2f}). Small gaps are normal: "
                   "Yahoo's gold is futures, Deriv's is spot.")


st.title("Gold macro dashboard")
refresh_fast = st.fragment(run_every=refresh_seconds)
refresh_slow = st.fragment(run_every=max(refresh_seconds, 15))
tab_chart, tab_macro, tab_basket = st.tabs(["Chart", "Macro check", "Gold basket"])
with tab_chart:
    refresh_fast(show_chart)()
with tab_macro:
    refresh_slow(show_dashboard)()
with tab_basket:
    refresh_slow(show_basket)()
st.caption("Context filter only. Not financial advice and not a trade signal. "
           "Your entry rules decide the trade.")
