"""
deriv_feed.py  -  Live prices from Deriv's public feed (no login needed)

Used by dashboard.py. Keep it in the same folder.

It connects, asks for one live price per symbol, then disconnects. The
dashboard lays that live price over the latest daily bar from Yahoo, so the
trend, volatility and currency basket all use the live gold price.
"""

import json
from datetime import datetime

import pandas as pd
import websocket  # from the "websocket-client" package

URL = "wss://api.derivws.com/trading/v1/options/ws/public"

# Name used in the dashboard : Deriv symbol.
# (KES is not offered by Deriv, so it stays on Yahoo's delayed data.)
SYMBOLS = {
    "XAU": "frxXAUUSD",
    "EUR": "frxEURUSD",
    "GBP": "frxGBPUSD",
    "JPY": "frxUSDJPY",
    "CHF": "frxUSDCHF",
    "AUD": "frxAUDUSD",
    "CAD": "frxUSDCAD",
}


def get_live_prices(symbols, timeout=8):
    """
    Return (prices, errors).
      prices: {"XAU": 3633.1, "EUR": 1.16, ...}  only for symbols that answered
      errors: list of messages for symbols that did not
    """
    prices, errors = {}, []
    by_symbol = {symbol: name for name, symbol in symbols.items()}
    ws = websocket.create_connection(URL, timeout=timeout)
    try:
        for number, symbol in enumerate(symbols.values(), start=1):
            ws.send(json.dumps({"ticks": symbol, "subscribe": 1, "req_id": number}))
        while len(prices) + len(errors) < len(symbols):
            try:
                reply = json.loads(ws.recv())
            except websocket.WebSocketTimeoutException:
                break  # stop waiting, use what we have
            if "error" in reply:
                errors.append(str(reply["error"].get("message", reply["error"])))
            elif reply.get("msg_type") == "tick":
                tick = reply["tick"]
                name = by_symbol.get(tick.get("symbol"))
                if name and name not in prices:
                    prices[name] = float(tick["quote"])
        try:
            ws.send(json.dumps({"forget_all": "ticks"}))
        except Exception:
            pass
    finally:
        ws.close()
    return prices, errors


def overlay(series, price):
    """
    Put the live price on today's bar of a daily price series.
    On weekends the market is closed, so the series is returned unchanged.
    """
    if datetime.now().weekday() >= 5:
        return series
    s = series.copy()
    last = s.index[-1]
    if last.tzinfo is not None:
        today = pd.Timestamp.now(tz=last.tzinfo).normalize()
    else:
        today = pd.Timestamp.now().normalize()
    if last.normalize() >= today:
        s.iloc[-1] = price
    else:
        s.loc[today] = price
    return s.sort_index()
