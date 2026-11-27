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

import gold_macro_check as g

try:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo("Africa/Nairobi")
except Exception:  # if the timezone database is missing, fall back to UTC
    LOCAL_TZ = timezone.utc

REFRESH_SECONDS = 900  # 15 minutes

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

g.SUPPORT_LEVELS = parse_levels(support_text, g.SUPPORT_LEVELS)
g.RESISTANCE_LEVELS = parse_levels(resistance_text, g.RESISTANCE_LEVELS)


# ----------------------------------------------------------------------------
# DATA (cached, so it is only downloaded again after 15 minutes)
# ----------------------------------------------------------------------------

@st.cache_data(ttl=REFRESH_SECONDS, show_spinner="Updating data...")
def load_data():
    """Download all three data sets. If one fails, keep going with the rest."""
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
    return data, errors


def bias_label(total):
    if total >= 2:
        return "SUPPORTIVE for gold"
    if total <= -2:
        return "AGAINST gold"
    return "MIXED / neutral"


# ----------------------------------------------------------------------------
# THE PAGE (this block re-runs by itself every 15 minutes)
# ----------------------------------------------------------------------------

@st.fragment(run_every=REFRESH_SECONDS)
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
        top1.metric("Gold last close", f"{price:,.1f}", f"{change:+.1f}")
    top2.metric("Macro bias score", f"{total:+d} of {len(scores)}",
                bias_label(total), delta_color="off")
    top3.metric("Last updated",
                datetime.now(LOCAL_TZ).strftime("%H:%M, %d %b"))

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
        st.dataframe(pd.read_csv(g.LOG_FILE).tail(30), use_container_width=True)


st.title("Gold macro dashboard")
show_dashboard()
st.caption("Context filter only. Not financial advice and not a trade signal. "
           "Your entry rules decide the trade.")
