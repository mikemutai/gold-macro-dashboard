"""
livechart.py  -  Two TradingView-powered charts for the dashboard

1) live_chart_html():  a LIVE chart built with TradingView Lightweight Charts
   (free, open source). Your browser connects straight to Deriv's public price
   feed, so candles update on every tick with no page refresh, and the candles
   come from Deriv itself (spot gold), not Yahoo futures.
   Includes your Backtesting 2.0 indicators: EMA 50, EMA 18, EMA 9, SMA 50.

2) tradingview_widget_html():  TradingView's free embeddable chart widget, with
   the full TradingView toolbar (drawing tools, indicators). It uses
   TradingView's own prices, not Deriv's.

Used by dashboard.py. Keep it in the same folder.
"""

import json

LIGHTWEIGHT_URL = ("https://cdn.jsdelivr.net/npm/lightweight-charts@4.2.0/dist/"
                   "lightweight-charts.standalone.production.js")

_LIVE_TEMPLATE = r"""
<style>
  html, body { margin: 0; padding: 0; background: #DCDCDC;
               font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; }
  #bar { display: flex; flex-wrap: wrap; gap: 8px 14px; align-items: center;
         padding: 8px 6px; font-size: 13px; color: #222; }
  #bar select { font-size: 13px; padding: 2px 4px; }
  #bar label { display: inline-flex; align-items: center; gap: 4px; cursor: pointer; }
  #status { margin-left: auto; color: #555; font-size: 12px; }
  #wrap { position: relative; }
  #chart { width: 100%; height: 640px; }
  #quote { position: absolute; top: 8px; left: 8px; z-index: 5; background: #fff;
           border: 1px solid #bbb; padding: 5px 10px; font-size: 13px;
           font-weight: 600; display: none; }
  #quote .sell { color: #D32F2F; } #quote .buy { color: #1F4FD8; }
  #quote .spread { color: #555; font-weight: 400; margin: 0 8px; }
  #foot { font-size: 11px; color: #555; padding: 6px; }
  #foot a { color: #555; }
</style>
<div id="bar"></div>
<div id="wrap"><div id="quote"></div><div id="chart"></div></div>
<div id="foot">Live prices: Deriv public feed. Chart: TradingView Lightweight Charts&trade;
  (<a href="https://www.tradingview.com/" target="_blank" rel="noopener">tradingview.com</a>).
  The SELL / BUY box is a price display, not an order button. Not financial advice.</div>
<script src="__LIB__"></script>
<script>
(function () {
  const WS_URL = "wss://api.derivws.com/trading/v1/options/ws/public";
  const SYMBOLS = {
    "XAUUSD": {code: "frxXAUUSD", dec: 2, scale: 100},
    "EURUSD": {code: "frxEURUSD", dec: 5, scale: 10000},
    "GBPUSD": {code: "frxGBPUSD", dec: 5, scale: 10000},
    "USDJPY": {code: "frxUSDJPY", dec: 3, scale: 100},
    "GBPJPY": {code: "frxGBPJPY", dec: 3, scale: 100}
  };
  const TFS = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1D": 86400};
  const ZONES = {"New York": "America/New_York", "Nairobi": "Africa/Nairobi", "UTC": "UTC"};
  const IND = [
    {id: "ema50", label: "EMA 50", kind: "ema", len: 50, color: "#2962FF"},
    {id: "ema18", label: "EMA 18", kind: "ema", len: 18, color: "#E91E63"},
    {id: "ema9",  label: "EMA 9",  kind: "ema", len: 9,  color: "#2E9E3E"},
    {id: "sma50", label: "SMA 50", kind: "sma", len: 50, color: "#00ACC1"}
  ];
  const $ = id => document.getElementById(id);
  function setStatus(t) { $("status").textContent = t; }

  // ---------- indicator maths (same as the Python charts) ----------
  function emaArr(values, n) {
    const a = 2 / (n + 1), out = [];
    values.forEach((v, i) => out.push(i === 0 ? v : a * v + (1 - a) * out[i - 1]));
    return out;
  }
  function smaArr(values, n) {
    const out = []; let sum = 0;
    values.forEach((v, i) => {
      sum += v;
      if (i >= n) sum -= values[i - n];
      out.push(i >= n - 1 ? sum / n : null);
    });
    return out;
  }

  // ---------- controls ----------
  let curSym = "__SYM__", curTf = "__TF__", curZone = "__ZONE__";
  const bar = $("bar");
  function makeSelect(id, options, value) {
    const s = document.createElement("select"); s.id = id;
    options.forEach(o => { const e = document.createElement("option"); e.value = o; e.textContent = o; s.appendChild(e); });
    s.value = value; bar.appendChild(s); return s;
  }
  const selSym = makeSelect("sym", Object.keys(SYMBOLS), curSym);
  const selTf = makeSelect("tf", Object.keys(TFS), curTf);
  const selZone = makeSelect("zone", Object.keys(ZONES), curZone);
  const boxes = {};
  IND.concat([{id: "levels", label: "Prev. day levels", color: "#444"}]).forEach(i => {
    const l = document.createElement("label");
    const c = document.createElement("input"); c.type = "checkbox"; c.checked = true;
    const t = document.createElement("span"); t.textContent = i.label; t.style.color = i.color; t.style.fontWeight = "600";
    l.appendChild(c); l.appendChild(t); bar.appendChild(l); boxes[i.id] = c;
  });
  const status = document.createElement("span"); status.id = "status"; bar.appendChild(status);

  if (typeof LightweightCharts === "undefined") { setStatus("Could not load the chart library (network blocked?)."); return; }

  // ---------- chart ----------
  function zone() { return curTf === "1D" ? "UTC" : ZONES[curZone]; }
  function tzFormat(t, o) { return new Intl.DateTimeFormat("en-GB", Object.assign({timeZone: zone()}, o)).format(new Date(t * 1000)); }
  function tickFmt(t, type) {
    if (type === 0) return tzFormat(t, {year: "numeric"});
    if (type === 1) return tzFormat(t, {month: "short"});
    if (type === 2) return tzFormat(t, {weekday: "short", day: "numeric"});
    return tzFormat(t, {hour: "2-digit", minute: "2-digit", hour12: false});
  }
  function fullFmt(t) { return tzFormat(t, {weekday: "short", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false}); }

  const el = $("chart");
  const chart = LightweightCharts.createChart(el, {
    width: el.clientWidth, height: 640,
    layout: {background: {type: "solid", color: "#DCDCDC"}, textColor: "#333"},
    grid: {vertLines: {color: "#CFCFCF"}, horzLines: {color: "#CFCFCF"}},
    crosshair: {mode: LightweightCharts.CrosshairMode.Normal,
      vertLine: {color: "#000", labelBackgroundColor: "#000"},
      horzLine: {color: "#000", labelBackgroundColor: "#000"}},
    rightPriceScale: {borderColor: "#B0B0B0"},
    timeScale: {borderColor: "#B0B0B0", timeVisible: true, secondsVisible: false, tickMarkFormatter: tickFmt, rightOffset: 8},
    localization: {timeFormatter: fullFmt}
  });
  const candleSeries = chart.addCandlestickSeries({
    upColor: "#1F4FD8", downColor: "#000000", borderUpColor: "#1F4FD8", borderDownColor: "#000000",
    wickUpColor: "#1F4FD8", wickDownColor: "#000000"});
  const lines = {};
  IND.forEach(i => { lines[i.id] = chart.addLineSeries({color: i.color, lineWidth: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false}); });
  new ResizeObserver(() => chart.applyOptions({width: el.clientWidth})).observe(el);

  // ---------- data ----------
  let ws = null, candles = [], useTicks = false, priceLines = [], dayRow = null;

  function drawIndicators(full) {
    const closes = candles.map(c => c.close);
    IND.forEach(i => {
      const arr = i.kind === "ema" ? emaArr(closes, i.len) : smaArr(closes, i.len);
      if (full) {
        lines[i.id].setData(candles.map((c, k) => arr[k] === null ? null : {time: c.time, value: arr[k]}).filter(Boolean));
      } else if (arr.length && arr[arr.length - 1] !== null) {
        lines[i.id].update({time: candles[candles.length - 1].time, value: arr[arr.length - 1]});
      }
    });
  }
  function setHistory(arr) {
    candles = arr.map(c => ({time: +c.epoch, open: +c.open, high: +c.high, low: +c.low, close: +c.close}));
    candleSeries.setData(candles);
    drawIndicators(true);
    const n = candles.length;
    chart.timeScale().setVisibleLogicalRange({from: Math.max(0, n - 120), to: n + 8});
  }
  function pushBar(bar) {
    const last = candles[candles.length - 1];
    if (last && last.time === bar.time) candles[candles.length - 1] = bar;
    else if (!last || bar.time > last.time) candles.push(bar);
    else return;
    candleSeries.update(bar);
    drawIndicators(false);
  }
  function onOhlc(o) { pushBar({time: +o.open_time, open: +o.open, high: +o.high, low: +o.low, close: +o.close}); }
  function onTickAggregate(tick) {
    const step = TFS[curTf], t = Math.floor(tick.epoch / step) * step, p = +tick.quote;
    const last = candles[candles.length - 1];
    if (last && last.time === t) pushBar({time: t, open: last.open, high: Math.max(last.high, p), low: Math.min(last.low, p), close: p});
    else pushBar({time: t, open: p, high: p, low: p, close: p});
  }
  function fmtPrice(v) { const d = SYMBOLS[curSym].dec; return Number(v).toLocaleString("en-US", {minimumFractionDigits: d, maximumFractionDigits: d}); }
  function onTick(tick) {
    if (tick.bid !== undefined && tick.ask !== undefined) {
      const q = $("quote"), s = SYMBOLS[curSym];
      q.style.display = "block";
      q.innerHTML = '<span class="sell">SELL ' + fmtPrice(tick.bid) + '</span><span class="spread">' +
        ((tick.ask - tick.bid) * s.scale).toFixed(1) + '</span><span class="buy">BUY ' + fmtPrice(tick.ask) + '</span>';
    }
    if (useTicks) onTickAggregate(tick);
  }

  // ---------- previous day levels ----------
  function clearLevels() { priceLines.forEach(l => candleSeries.removePriceLine(l)); priceLines = []; }
  function drawLevels() {
    clearLevels();
    if (!dayRow || !boxes.levels.checked) return;
    const hi = +dayRow.high, lo = +dayRow.low, eq = (hi + lo) / 2, LS = LightweightCharts.LineStyle;
    [[hi, "PDH", "#6B6B6B", LS.Dotted], [lo, "PDL", "#6B6B6B", LS.Dotted], [eq, "EQUILIBRIUM", "#E53935", LS.Dashed]].forEach(x => {
      priceLines.push(candleSeries.createPriceLine({price: x[0], color: x[2], lineWidth: 1, lineStyle: x[3], axisLabelVisible: true, title: x[1]}));
    });
  }
  function setLevels(arr) {
    dayRow = null;
    if (arr && arr.length) {
      const todayStart = Math.floor(Date.now() / 86400000) * 86400;
      dayRow = (+arr[arr.length - 1].epoch >= todayStart && arr.length > 1) ? arr[arr.length - 2] : arr[arr.length - 1];
    }
    drawLevels();
  }

  // ---------- Deriv connection ----------
  function send(o) { if (ws && ws.readyState === 1) ws.send(JSON.stringify(o)); }
  function handle(m) {
    const rid = m.req_id || (m.echo_req && m.echo_req.req_id);
    if (m.error) {
      if (rid === 1) { useTicks = true; candles = []; setStatus("Deriv candle history unavailable (" + m.error.code + "). Building candles from live ticks."); }
      else if (rid !== 3) setStatus("Error: " + (m.error.message || m.error.code));
      return;
    }
    if (m.msg_type === "candles") {
      if (rid === 1) { setHistory(m.candles || []); setStatus("Live from Deriv"); }
      else if (rid === 3) setLevels(m.candles);
    } else if (m.msg_type === "ohlc") onOhlc(m.ohlc);
    else if (m.msg_type === "tick") onTick(m.tick);
  }
  function connect() {
    const code = SYMBOLS[curSym].code;
    setStatus("Connecting...");
    ws = new WebSocket(WS_URL);
    ws.onopen = () => {
      send({ticks_history: code, adjust_start_time: 1, count: 600, end: "latest", granularity: TFS[curTf], style: "candles", subscribe: 1, req_id: 1});
      send({ticks: code, subscribe: 1, req_id: 2});
      send({ticks_history: code, count: 3, end: "latest", granularity: 86400, style: "candles", req_id: 3});
    };
    ws.onmessage = ev => { try { handle(JSON.parse(ev.data)); } catch (e) { setStatus("Data error: " + e.message); } };
    ws.onerror = () => setStatus("Connection error");
    ws.onclose = () => { setStatus("Disconnected. Reconnecting..."); setTimeout(connect, 2000); };
  }
  function restart() {
    useTicks = false; candles = []; dayRow = null;
    candleSeries.setData([]); IND.forEach(i => lines[i.id].setData([])); clearLevels();
    $("quote").style.display = "none";
    if (ws) { ws.onclose = null; try { ws.close(); } catch (e) {} }
    connect();
  }

  selSym.onchange = () => { curSym = selSym.value; restart(); };
  selTf.onchange = () => { curTf = selTf.value; chart.applyOptions({localization: {timeFormatter: fullFmt}}); chart.timeScale().applyOptions({tickMarkFormatter: tickFmt}); restart(); };
  selZone.onchange = () => { curZone = selZone.value; chart.applyOptions({localization: {timeFormatter: fullFmt}}); chart.timeScale().applyOptions({tickMarkFormatter: tickFmt}); };
  IND.forEach(i => { boxes[i.id].onchange = () => lines[i.id].applyOptions({visible: boxes[i.id].checked}); });
  boxes.levels.onchange = drawLevels;

  window.__test = {emaArr, smaArr, handle, getCandles: () => candles};   // used by automated tests only
  connect();
})();
</script>
"""


def live_chart_html(symbol="XAUUSD", timeframe="15m", zone="New York"):
    """HTML for the live Deriv chart (use with streamlit components.html)."""
    return (_LIVE_TEMPLATE.replace("__LIB__", LIGHTWEIGHT_URL)
            .replace("__SYM__", symbol).replace("__TF__", timeframe)
            .replace("__ZONE__", zone))


def tradingview_widget_html(symbol="OANDA:XAUUSD", interval="15",
                            timezone="America/New_York", height=720):
    """HTML for TradingView's free Advanced Chart widget."""
    config = {
        "autosize": True, "symbol": symbol, "interval": interval,
        "timezone": timezone, "theme": "light", "style": "1", "locale": "en",
        "backgroundColor": "#DCDCDC", "gridColor": "#CFCFCF",
        "allow_symbol_change": True, "hide_side_toolbar": False,
        "withdateranges": True, "details": False, "calendar": False,
        "support_host": "https://www.tradingview.com",
    }
    return f"""
<div class="tradingview-widget-container" style="height:{height}px;width:100%">
  <div class="tradingview-widget-container__widget" style="height:{height - 28}px;width:100%"></div>
  <div class="tradingview-widget-copyright" style="font-size:12px;font-family:Arial,sans-serif;padding:4px">
    <a href="https://www.tradingview.com/" rel="noopener nofollow" target="_blank">Track all markets on TradingView</a>
  </div>
  <script type="text/javascript"
    src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
  {json.dumps(config)}
  </script>
</div>
"""
