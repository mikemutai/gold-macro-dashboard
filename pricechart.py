"""
pricechart.py  -  Interactive candlestick chart (TradingView style)

Indicators come from your Backtesting 2.0 guide (all use the close price,
offset 0): EMA 50, EMA 18, EMA 9 and SMA 50. Sonarlab Sessions is left out.

Chart controls: drag to move around, scroll to zoom, double-click to reset.

Used by dashboard.py. Keep it in the same folder.
"""

import pandas as pd
import plotly.graph_objects as go
import yfinance as yf

# label: (Yahoo Finance ticker, key used for the Deriv live price)
SYMBOLS = {
    "Gold (XAUUSD)": ("GC=F", "XAU"),
    "EURUSD": ("EURUSD=X", "EUR"),
    "GBPUSD": ("GBPUSD=X", "GBP"),
    "USDJPY": ("JPY=X", "JPY"),
    "GBPJPY": ("GBPJPY=X", "GBPJPY"),
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

# name: (type, length, colour as in your TradingView settings)
INDICATORS = {
    "EMA 50": ("ema", 50, "#2962FF"),   # blue
    "EMA 18": ("ema", 18, "#E91E63"),   # pink
    "EMA 9": ("ema", 9, "#4CAF50"),     # green
    "SMA 50": ("sma", 50, "#00BCD4"),   # cyan
}

DISPLAY_TZ = "Africa/Nairobi"


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
    if data.index.tz is not None:
        data.index = data.index.tz_convert(DISPLAY_TZ)
    return data


def indicator_line(close, kind, length):
    """Moving average on the close price."""
    if kind == "ema":
        return close.ewm(span=length, adjust=False).mean()
    return close.rolling(length).mean()


def make_figure(df, shown, candles=120, levels=None, live_price=None,
                uirevision="chart"):
    """
    Build the chart.
      df          candles (Open, High, Low, Close)
      shown       indicator names to draw, e.g. ["EMA 9", "SMA 50"]
      candles     how many of the latest candles to show at first
      levels      list of (price, "support" or "resistance")
      live_price  live price drawn as a dashed line
      uirevision  keeps your zoom/pan when the chart refreshes
    """
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"], low=df["Low"],
        close=df["Close"], name="Price",
        increasing_line_color="#26a69a", increasing_fillcolor="#26a69a",
        decreasing_line_color="#ef5350", decreasing_fillcolor="#ef5350",
    ))
    for name in shown:
        kind, length, colour = INDICATORS[name]
        fig.add_trace(go.Scatter(
            x=df.index, y=indicator_line(df["Close"], kind, length),
            name=name, mode="lines", line=dict(color=colour, width=1.5),
        ))

    visible = df.tail(candles)
    low, high = float(visible["Low"].min()), float(visible["High"].max())
    pad = (high - low) * 0.08 or 1.0

    for price, kind in (levels or []):
        if low - pad <= price <= high + pad:   # only levels near the price
            fig.add_hline(
                y=price, line_dash="dot", opacity=0.6,
                line_color="#26a69a" if kind == "support" else "#ef5350",
                annotation_text=f"{kind} {price:g}", annotation_position="left",
            )
    if live_price is not None:
        low, high = min(low, live_price), max(high, live_price)
        fig.add_hline(
            y=live_price, line_dash="dash", line_color="#FFD54F",
            annotation_text=f"Deriv live {live_price:,.2f}",
            annotation_position="right",
        )

    step = df.index[-1] - df.index[-2] if len(df) > 1 else pd.Timedelta(minutes=1)
    fig.update_layout(
        template="plotly_dark", height=650, uirevision=uirevision,
        dragmode="pan", hovermode="x unified",
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0),
    )
    fig.update_xaxes(
        range=[visible.index[0], df.index[-1] + step * 6],
        rangebreaks=[dict(bounds=["sat", "mon"])],   # hide weekends
        showspikes=True, spikemode="across", spikethickness=1,
    )
    fig.update_yaxes(range=[low - pad, high + pad], side="right",
                     showspikes=True, spikethickness=1)
    return fig
