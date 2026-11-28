"""
pricechart.py  -  TradingView-style interactive charts

Look: whitish-grey background, blue bullish candles, black bearish candles,
price tags on the right axis, day separators with day names, previous-day
high / low / equilibrium, and a bid / ask box.

Indicators come from your Backtesting 2.0 guide (all on the close price,
offset 0): EMA 50, EMA 18, EMA 9 and SMA 50. Sonarlab Sessions is left out.

Chart controls: drag to move, scroll to zoom, double-click to reset. Use the
toolbar icons at the top right of the chart to draw lines and boxes.

Used by dashboard.py. Keep it in the same folder.
"""

import pandas as pd
import plotly.graph_objects as go
import yfinance as yf

# label: (Yahoo ticker, Deriv key, spread scale, price decimals)
# spread scale: multiplies the bid/ask gap into "points" (gold 0.41 -> 41.0)
SYMBOLS = {
    "Gold (XAUUSD)": ("GC=F", "XAU", 100, 2),
    "EURUSD": ("EURUSD=X", "EUR", 10000, 5),
    "GBPUSD": ("GBPUSD=X", "GBP", 10000, 5),
    "USDJPY": ("JPY=X", "JPY", 100, 3),
    "GBPJPY": ("GBPJPY=X", "GBPJPY", 100, 3),
}
SUBTITLES = {
    "Gold (XAUUSD)": "Gold Spot / U.S. Dollar",
    "EURUSD": "Euro / U.S. Dollar",
    "GBPUSD": "British Pound / U.S. Dollar",
    "USDJPY": "U.S. Dollar / Japanese Yen",
    "GBPJPY": "British Pound / Japanese Yen",
}

# timeframe: (Yahoo interval, how far back to load, resample rule)
TIMEFRAMES = {
    "5m": ("5m", "5d", None),
    "15m": ("15m", "20d", None),
    "30m": ("30m", "40d", None),
    "1h": ("1h", "90d", None),
    "4h": ("1h", "180d", "4h"),
    "1D": ("1d", "2y", None),
}

TIMEZONES = {"New York": "America/New_York", "Nairobi": "Africa/Nairobi",
             "UTC": "UTC"}

# name: (type, length). Settings from your guide: source = close, offset 0.
INDICATORS = {
    "EMA 50": ("ema", 50),
    "EMA 18": ("ema", 18),
    "EMA 9": ("ema", 9),
    "SMA 50": ("sma", 50),
}

# Chart looks: "Neon" = black / cyan / magenta, "Classic" = whitish grey / blue / black
THEMES = {
    "Neon": dict(
        template="plotly_dark", bg="#020306", grid="#111925", text="#B8C7CF",
        bull="#7CE6FC", bear="#FC36BE", live="#FFB020", spike="#7CE6FC",
        faint="rgba(124,230,252,0.07)", dayline="#2A3646", daylabel="#8FA3AD",
        pd_line="#8FA3AD", pd_tag="#2A3646", eq="#FC36BE", support="#7CE6FC",
        resistance="#FC36BE", box_bg="#0A0F1A", box_border="#243247",
        sell="#FC36BE", buy="#7CE6FC", hover_bg="#0A0F1A", hover_font="#E6F1F5",
        tag_text="#020306",
        ind={"EMA 50": "#4C8DFF", "EMA 18": "#FFB020", "EMA 9": "#39E58C", "SMA 50": "#E6F1F5"}),
    "Classic": dict(
        template="plotly_white", bg="#DCDCDC", grid="#CFCFCF", text="#333333",
        bull="#1F4FD8", bear="#000000", live="#F57C00", spike="#000000",
        faint="rgba(0,0,0,0.07)", dayline="#9A9A9A", daylabel="#555555",
        pd_line="#6B6B6B", pd_tag="#4A4A4A", eq="#E53935", support="#00897B",
        resistance="#D32F2F", box_bg="#FFFFFF", box_border="#BBBBBB",
        sell="#D32F2F", buy="#1F4FD8", hover_bg="#FFFFFF", hover_font="#222222",
        tag_text="#FFFFFF",
        ind={"EMA 50": "#2962FF", "EMA 18": "#E91E63", "EMA 9": "#2E9E3E", "SMA 50": "#00ACC1"}),
}


def short_name(label):
    return "XAUUSD" if label.startswith("Gold") else label


# ----------------------------------------------------------------------------
# DATA
# ----------------------------------------------------------------------------

def get_ohlc(ticker, interval, period, resample=None):
    """Download open/high/low/close candles from Yahoo Finance."""
    data = yf.download(ticker, interval=interval, period=period,
                       progress=False, auto_adjust=True)
    if data.empty:
        raise RuntimeError(f"No data returned for {ticker}")
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    data = data[["Open", "High", "Low", "Close"]].dropna()
    if resample:
        data = data.resample(resample).agg(
            {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
        ).dropna()
    return data


def indicator_line(close, kind, length):
    """Moving average on the close price."""
    if kind == "ema":
        return close.ewm(span=length, adjust=False).mean()
    return close.rolling(length).mean()


def previous_day_levels(daily):
    """High, low and equilibrium (the midpoint) of the last finished day."""
    last = daily.index[-1]
    if getattr(last, "tzinfo", None) is not None:
        last = last.tz_localize(None)
    in_progress = last.date() >= pd.Timestamp.now().date()
    row = daily.iloc[-2] if in_progress and len(daily) > 1 else daily.iloc[-1]
    high, low = float(row["High"]), float(row["Low"])
    return {"high": high, "low": low, "equilibrium": (high + low) / 2}


# ----------------------------------------------------------------------------
# DRAWING HELPERS
# ----------------------------------------------------------------------------

def _to_zone(df, tz):
    if tz and df.index.tz is not None:
        df = df.copy()
        df.index = df.index.tz_convert(tz)
    return df


def _step(index):
    """Typical time between candles."""
    if len(index) < 2:
        return pd.Timedelta(minutes=1)
    return index.to_series().diff().median()


def _range_breaks(index, step):
    """Hide weekends and holidays so there are no empty gaps (like TradingView)."""
    if step >= pd.Timedelta(days=1):
        return [dict(bounds=["sat", "mon"])]
    limit = max(step * 3, pd.Timedelta(hours=3))
    breaks = []
    for before, after in zip(index[:-1], index[1:]):
        if after - before > limit:
            breaks.append(dict(bounds=[before + step, after]))
    return breaks


def _tag(fig, y, text, background, colour="white"):
    """A coloured price label sitting on the right-hand price axis."""
    fig.add_annotation(
        xref="paper", x=1.0, xanchor="left", yref="y", y=y, text=f"<b>{text}</b>",
        showarrow=False, bgcolor=background, font=dict(color=colour, size=12),
        borderpad=3)


def _contrast(hex_colour):
    """Black or white text, whichever is easier to read on this colour."""
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#020306" if (0.299 * r + 0.587 * g + 0.114 * b) > 140 else "#FFFFFF"


def _day_marks(fig, visible, t):
    """Dotted vertical line and day name at the start of each day."""
    first = visible.index[0]
    for day in visible.index.normalize().unique():
        if day > first:
            fig.add_shape(type="line", xref="x", yref="paper", x0=day, x1=day,
                          y0=0, y1=1, layer="below",
                          line=dict(color=t["dayline"], width=1, dash="dot"))
        fig.add_annotation(
            xref="x", yref="paper", x=max(day, first) + pd.Timedelta(hours=2),
            y=1.0, yanchor="bottom", text=day.strftime("%a"), showarrow=False,
            font=dict(size=12, color=t["daylabel"]))


def _watermark(fig, title, subtitle, t):
    faint = t["faint"]
    fig.add_annotation(xref="paper", yref="paper", x=0.5, y=0.58, text=title,
                       showarrow=False, font=dict(size=84, color=faint))
    if subtitle:
        fig.add_annotation(xref="paper", yref="paper", x=0.5, y=0.42,
                           text=subtitle, showarrow=False,
                           font=dict(size=40, color=faint))


def _layout(fig, index, visible, step, low, high, pad, uirevision, t):
    fig.update_layout(
        template=t["template"], height=680, uirevision=uirevision,
        dragmode="pan", hovermode="x unified",
        paper_bgcolor=t["bg"], plot_bgcolor=t["bg"],
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=95, t=60, b=10), font=dict(color=t["text"]),
        legend=dict(orientation="h", yanchor="bottom", y=1.06, x=0),
        hoverlabel=dict(bgcolor=t["hover_bg"], font_color=t["hover_font"]),
        newshape=dict(line_color=t["bull"]),
    )
    fig.update_xaxes(
        range=[visible.index[0], index[-1] + step * 6],
        rangebreaks=_range_breaks(index, step), gridcolor=t["grid"],
        showspikes=True, spikemode="across", spikecolor=t["spike"],
        spikethickness=1)
    fig.update_yaxes(
        range=[low - pad, high + pad], side="right", gridcolor=t["grid"],
        showspikes=True, spikecolor=t["spike"], spikethickness=1)


# ----------------------------------------------------------------------------
# THE PRICE CHART
# ----------------------------------------------------------------------------

def make_figure(df, shown, candles=120, levels=None, live_price=None,
                uirevision="chart", prev_day=None, bid_ask=None,
                name="XAUUSD", timeframe="15m", subtitle="", tz=None,
                spread_scale=100, decimals=2, theme="Neon"):
    """
    Candlestick chart.
      shown      indicator names to draw, e.g. ["EMA 9", "SMA 50"]
      candles    how many of the latest candles to show at first
      levels     your own levels: list of (price, "support" or "resistance")
      live_price live price from Deriv (price tag turns orange)
      prev_day   dict from previous_day_levels()
      bid_ask    (bid, ask) from Deriv, shown in the SELL / BUY box
      tz         time zone name for the time axis
      theme      "Neon" (black / cyan / magenta) or "Classic" (grey / blue / black)
    """
    t = THEMES.get(theme, THEMES["Neon"])
    df = _to_zone(df, tz)
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"], low=df["Low"],
        close=df["Close"], name="Price",
        increasing_line_color=t["bull"], increasing_fillcolor=t["bull"],
        decreasing_line_color=t["bear"], decreasing_fillcolor=t["bear"],
    ))
    for indicator in shown:
        kind, length = INDICATORS[indicator]
        fig.add_trace(go.Scatter(
            x=df.index, y=indicator_line(df["Close"], kind, length),
            name=indicator, mode="lines", line=dict(color=t["ind"][indicator], width=1.5)))

    step = _step(df.index)
    visible = df.tail(candles)
    last_price = live_price if live_price is not None else float(df["Close"].iloc[-1])
    low = min(float(visible["Low"].min()), last_price)
    high = max(float(visible["High"].max()), last_price)
    pad = (high - low) * 0.08 or 1.0

    def inside(y):
        return low - pad <= y <= high + pad

    # Your own support / resistance levels (optional)
    for price, kind in (levels or []):
        if inside(price):
            fig.add_hline(y=price, line_dash="dot", line_width=1, opacity=0.7,
                          line_color=t["support"] if kind == "support" else t["resistance"],
                          annotation_text=f"{kind} {price:g}",
                          annotation_position="left")

    # Previous day high / low / equilibrium
    if prev_day:
        for label, y, dash, colour, tag in (
                ("PDH", prev_day["high"], "dot", t["pd_line"], t["pd_tag"]),
                ("PDL", prev_day["low"], "dot", t["pd_line"], t["pd_tag"]),
                ("EQUILIBRIUM", prev_day["equilibrium"], "dash", t["eq"], t["eq"])):
            if inside(y):
                fig.add_hline(y=y, line_dash=dash, line_width=1, line_color=colour)
                _tag(fig, y, f"{y:,.{decimals}f}", tag, _contrast(tag))
                if label == "EQUILIBRIUM":
                    fig.add_annotation(xref="paper", x=0.62, yref="y", y=y,
                                       yshift=-12, text=label, showarrow=False,
                                       font=dict(size=12, color=t["eq"]))
                else:
                    fig.add_annotation(xref="paper", x=0.005, xanchor="left",
                                       yref="y", y=y, yshift=9, text=label,
                                       showarrow=False,
                                       font=dict(size=11, color=t["pd_line"]))

    # Last price tag and dotted line
    if live_price is not None:
        tag_colour = t["live"]
    else:
        up = float(df["Close"].iloc[-1]) >= float(df["Open"].iloc[-1])
        tag_colour = t["bull"] if up else t["bear"]
    fig.add_hline(y=last_price, line_dash="dot", line_width=1, line_color=tag_colour)
    _tag(fig, last_price, f"{last_price:,.{decimals}f}", tag_colour, _contrast(tag_colour))

    if step < pd.Timedelta(days=1):
        _day_marks(fig, visible, t)
    _watermark(fig, f"{name}, {timeframe}", subtitle, t)

    # SELL / BUY quote box (display only, not order buttons)
    if bid_ask:
        bid, ask = bid_ask
        spread = (ask - bid) * spread_scale
        fig.add_annotation(
            xref="paper", yref="paper", x=0.005, y=0.995, xanchor="left",
            yanchor="top", showarrow=False, bgcolor=t["box_bg"],
            bordercolor=t["box_border"], borderwidth=1, borderpad=6, font=dict(size=13),
            text=(f'<span style="color:{t["sell"]}"><b>SELL {bid:,.{decimals}f}</b></span>'
                  f'   <span style="color:{t["text"]}">{spread:.1f}</span>   '
                  f'<span style="color:{t["buy"]}"><b>BUY {ask:,.{decimals}f}</b></span>'))

    _layout(fig, df.index, visible, step, low, high, pad, uirevision, t)
    return fig
