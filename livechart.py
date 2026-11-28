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
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; background: #EEF0F3; color: #14213D;
               font-family: Inter, -apple-system, "Segoe UI", Roboto, Arial, sans-serif; }
  #toolbar, #chips, #alertbar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px;
               background: #fff; border: 1px solid #E1E4E8; border-radius: 12px;
               padding: 8px 12px; margin-bottom: 8px; box-shadow: 0 1px 2px rgba(16,24,40,.06); }
  select, input[type=number] { font: inherit; font-size: 13px; padding: 5px 8px; border: 1px solid #D0D5DD;
               border-radius: 8px; background: #fff; color: #14213D; }
  input[type=number] { width: 110px; }
  button { font: inherit; font-size: 13px; font-weight: 600; padding: 5px 12px; border: 1px solid #D0D5DD;
           border-radius: 999px; background: #fff; color: #14213D; cursor: pointer; }
  button:hover { background: #F2F4F7; }
  button.active { background: #1F4FD8; border-color: #1F4FD8; color: #fff; }
  #tfs { display: flex; gap: 4px; }
  #live { margin-left: auto; display: flex; align-items: center; gap: 6px; font-size: 12px; color: #5B6572; }
  #dot { width: 9px; height: 9px; border-radius: 50%; background: #98A2B3; display: inline-block; }
  #dot.on { background: #12B76A; box-shadow: 0 0 0 3px rgba(18,183,106,.2); }
  .chip { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600;
          padding: 4px 10px; border: 1px solid #E1E4E8; border-radius: 999px; background: #F9FAFB; cursor: pointer; }
  .chip i { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
  .chip.off { opacity: .45; }
  .lbl { font-size: 12px; font-weight: 700; color: #5B6572; text-transform: uppercase; letter-spacing: .04em; }
  .alert-chip { background: #FFF4E5; border-color: #F5C98A; color: #9A5B00; }
  #wrap { position: relative; border-radius: 12px; overflow: hidden; border: 1px solid #E1E4E8;
          box-shadow: 0 1px 2px rgba(16,24,40,.06); }
  #chart { width: 100%; height: 620px; }
  #quote { position: absolute; top: 10px; left: 10px; z-index: 5; background: #fff; border: 1px solid #bbb;
           border-radius: 8px; padding: 5px 10px; font-size: 13px; font-weight: 700; display: none; }
  #quote .sell { color: #D32F2F; } #quote .buy { color: #1F4FD8; }
  #quote .spread { color: #555; font-weight: 400; margin: 0 8px; }
  #banner { position: absolute; top: 12px; left: 50%; transform: translateX(-50%); z-index: 9; display: none;
            background: #F57C00; color: #fff; font-weight: 700; padding: 10px 18px; border-radius: 10px;
            box-shadow: 0 6px 18px rgba(0,0,0,.25); cursor: pointer; font-size: 14px; }
  #log { font-size: 12px; color: #5B6572; padding: 6px 4px; min-height: 18px; }
  #foot { font-size: 11px; color: #667085; padding: 2px 4px 8px; }
  #foot a { color: #667085; }
</style>
<div id="toolbar"><select id="sym"></select><div id="tfs"></div><select id="zone"></select>
  <span id="live"><i id="dot"></i><span id="status"></span></span></div>
<div id="chips"><span class="lbl">Indicators</span></div>
<div id="alertbar"><span class="lbl">Alerts</span>
  <input id="alertprice" type="number" step="any" placeholder="price">
  <button id="addalert">+ Add alert</button><button id="pickalert">Click chart to set</button>
  <span id="alertlist"></span></div>
<div id="wrap"><div id="banner"></div><div id="quote"></div><div id="chart"></div></div>
<div id="log"></div>
<div id="foot">Live prices: Deriv public feed. Chart: TradingView Lightweight Charts&trade;
  (<a href="https://www.tradingview.com/" target="_blank" rel="noopener">tradingview.com</a>).
  Alerts work while this page is open in your browser. The SELL / BUY box is a price display,
  not an order button. Not financial advice.</div>
<script src="__LIB__"></script>
<script>
(function () {
  const WS_URL = "wss://api.derivws.com/trading/v1/options/ws/public";
  const SYMBOLS = {
    "XAUUSD": {code: "frxXAUUSD", dec: 2, scale: 100},
    "XAU BASKET": {basket: true, dec: 3},
    "EURUSD": {code: "frxEURUSD", dec: 5, scale: 10000},
    "GBPUSD": {code: "frxGBPUSD", dec: 5, scale: 10000},
    "USDJPY": {code: "frxUSDJPY", dec: 3, scale: 100},
    "GBPJPY": {code: "frxGBPJPY", dec: 3, scale: 100}
  };
  // The basket: gold priced in these currencies (kind = how Deriv quotes the pair)
  const BASKET = [
    {name: "USD", code: null, kind: null},
    {name: "EUR", code: "frxEURUSD", kind: "usd_per"},
    {name: "GBP", code: "frxGBPUSD", kind: "usd_per"},
    {name: "JPY", code: "frxUSDJPY", kind: "per_usd"},
    {name: "CHF", code: "frxUSDCHF", kind: "per_usd"},
    {name: "AUD", code: "frxAUDUSD", kind: "usd_per"},
    {name: "CAD", code: "frxUSDCAD", kind: "per_usd"}
  ];
  const GOLD = "frxXAUUSD";
  const TFS = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1D": 86400};
  const ZONES = {"New York": "America/New_York", "Nairobi": "Africa/Nairobi", "UTC": "UTC"};
  const IND = [
    {id: "ema50", label: "EMA 50", kind: "ema", len: 50, color: "#2962FF"},
    {id: "ema18", label: "EMA 18", kind: "ema", len: 18, color: "#E91E63"},
    {id: "ema9",  label: "EMA 9",  kind: "ema", len: 9,  color: "#2E9E3E"},
    {id: "sma50", label: "SMA 50", kind: "sma", len: 50, color: "#00ACC1"}
  ];
  const $ = id => document.getElementById(id);
  function setStatus(t, on) { $("status").textContent = t; $("dot").className = on ? "on" : ""; }

  // ---------- indicator maths (same as the Python charts) ----------
  function emaArr(values, n) {
    const a = 2 / (n + 1), out = [];
    values.forEach((v, i) => out.push(i === 0 ? v : a * v + (1 - a) * out[i - 1]));
    return out;
  }
  function smaArr(values, n) {
    const out = []; let sum = 0;
    values.forEach((v, i) => { sum += v; if (i >= n) sum -= values[i - n]; out.push(i >= n - 1 ? sum / n : null); });
    return out;
  }

  // ---------- controls ----------
  let curSym = "__SYM__", curTf = "__TF__", curZone = "__ZONE__";
  function fill(sel, options, value) {
    options.forEach(o => { const e = document.createElement("option"); e.value = o; e.textContent = o; sel.appendChild(e); });
    sel.value = value;
  }
  const selSym = $("sym"), selZone = $("zone");
  fill(selSym, Object.keys(SYMBOLS), curSym); fill(selZone, Object.keys(ZONES), curZone);
  const tfButtons = {};
  Object.keys(TFS).forEach(tf => {
    const b = document.createElement("button"); b.textContent = tf; if (tf === curTf) b.className = "active";
    b.onclick = () => { curTf = tf; Object.keys(tfButtons).forEach(k => tfButtons[k].className = k === tf ? "active" : ""); applyFormats(); restart(); };
    $("tfs").appendChild(b); tfButtons[tf] = b;
  });
  const chipState = {};
  IND.concat([{id: "levels", label: "Prev. day levels", color: "#6B6B6B"}]).forEach(i => {
    const c = document.createElement("span"); c.className = "chip";
    c.innerHTML = '<i style="background:' + i.color + '"></i>' + i.label;
    chipState[i.id] = true;
    c.onclick = () => { chipState[i.id] = !chipState[i.id]; c.className = chipState[i.id] ? "chip" : "chip off"; if (i.id === "levels") drawLevels(); else lines[i.id].applyOptions({visible: chipState[i.id]}); };
    $("chips").appendChild(c);
  });

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
  function applyFormats() { chart.applyOptions({localization: {timeFormatter: fullFmt}}); chart.timeScale().applyOptions({tickMarkFormatter: tickFmt}); }

  const el = $("chart");
  const chart = LightweightCharts.createChart(el, {
    width: el.clientWidth, height: 620,
    layout: {background: {type: "solid", color: "#DCDCDC"}, textColor: "#333"},
    grid: {vertLines: {color: "#CFCFCF"}, horzLines: {color: "#CFCFCF"}},
    crosshair: {mode: LightweightCharts.CrosshairMode.Normal,
      vertLine: {color: "#000", labelBackgroundColor: "#000"}, horzLine: {color: "#000", labelBackgroundColor: "#000"}},
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
  let ws = null, candles = [], useTicks = false, priceLines = [], dayRow = null, lastPx = null;
  let bars = {}, baseVals = null, pending = {}, tickLast = {}, tickBase = null;

  function isBasket() { return !!SYMBOLS[curSym].basket; }
  function drawIndicators(full) {
    const closes = candles.map(c => c.close);
    IND.forEach(i => {
      const arr = i.kind === "ema" ? emaArr(closes, i.len) : smaArr(closes, i.len);
      if (full) lines[i.id].setData(candles.map((c, k) => arr[k] === null ? null : {time: c.time, value: arr[k]}).filter(Boolean));
      else if (arr.length && arr[arr.length - 1] !== null) lines[i.id].update({time: candles[candles.length - 1].time, value: arr[arr.length - 1]});
    });
  }
  function setHistory(list) {
    candles = list;
    candleSeries.setData(candles);
    drawIndicators(true);
    const n = candles.length;
    chart.timeScale().setVisibleLogicalRange({from: Math.max(0, n - 120), to: n + 8});
    if (n) lastPx = candles[n - 1].close;
  }
  function pushBar(bar) {
    const last = candles[candles.length - 1];
    if (last && last.time === bar.time) candles[candles.length - 1] = bar;
    else if (!last || bar.time > last.time) candles.push(bar);
    else return;
    candleSeries.update(bar);
    drawIndicators(false);
  }
  function toBar(c) { return {time: +(c.epoch !== undefined ? c.epoch : c.open_time), open: +c.open, high: +c.high, low: +c.low, close: +c.close}; }
  function onTickAggregate(tick) {
    const step = TFS[curTf], t = Math.floor(tick.epoch / step) * step, p = +tick.quote;
    const last = candles[candles.length - 1];
    if (last && last.time === t) pushBar({time: t, open: last.open, high: Math.max(last.high, p), low: Math.min(last.low, p), close: p});
    else pushBar({time: t, open: p, high: p, low: p, close: p});
  }
  function fmtPrice(v) { const d = SYMBOLS[curSym].dec; return Number(v).toLocaleString("en-US", {minimumFractionDigits: d, maximumFractionDigits: d}); }

  // ---------- basket maths ----------
  function conv(gold, fx, kind) { return kind === null ? gold : (kind === "usd_per" ? gold / fx : gold * fx); }
  function fxCloseAt(name, t) {
    const arr = bars[name]; if (!arr || !arr.length) return null;
    let lo = 0, hi = arr.length - 1, ans = 0;
    while (lo <= hi) { const mid = (lo + hi) >> 1; if (arr[mid].time <= t) { ans = mid; lo = mid + 1; } else hi = mid - 1; }
    return arr[ans].close;
  }
  function basketBarFor(g) {
    // average of gold priced in each currency, each set to 100 at the start
    const sums = {open: 0, high: 0, low: 0, close: 0};
    for (const b of BASKET) {
      const fx = b.code === null ? null : fxCloseAt(b.name, g.time);
      if (b.code !== null && fx === null) return null;
      if (!baseVals) return null;
      ["open", "high", "low", "close"].forEach(k => { sums[k] += conv(g[k], fx, b.kind) / baseVals[b.name] * 100; });
    }
    return {time: g.time, open: sums.open / BASKET.length, high: sums.high / BASKET.length, low: sums.low / BASKET.length, close: sums.close / BASKET.length};
  }
  function buildBasketHistory() {
    const gold = bars.XAU; baseVals = {};
    for (const b of BASKET) { const fx = b.code === null ? null : fxCloseAt(b.name, gold[0].time); baseVals[b.name] = conv(gold[0].close, fx, b.kind); }
    return gold.map(basketBarFor).filter(Boolean);
  }
  function basketOnOhlc(sym, o) {
    const name = sym === GOLD ? "XAU" : (BASKET.find(b => b.code === sym) || {}).name;
    if (!name || !bars[name] || !baseVals) return;
    const bar = toBar(o), arr = bars[name], last = arr[arr.length - 1];
    if (last && last.time === bar.time) arr[arr.length - 1] = bar; else if (!last || bar.time > last.time) arr.push(bar);
    const g = bars.XAU[bars.XAU.length - 1], out = basketBarFor(g);
    if (out) { pushBar(out); checkAlerts(out.close); }
  }
  function basketTick(tick) {
    const name = tick.symbol === GOLD ? "XAU" : (BASKET.find(b => b.code === tick.symbol) || {}).name;
    if (!name) return;
    tickLast[name] = +tick.quote;
    if (!BASKET.every(b => b.code === null ? tickLast.XAU !== undefined : tickLast[b.name] !== undefined) || tickLast.XAU === undefined) return;
    const vals = {}; BASKET.forEach(b => { vals[b.name] = conv(tickLast.XAU, b.code === null ? null : tickLast[b.name], b.kind); });
    if (!tickBase) tickBase = vals;
    const idx = BASKET.reduce((a, b) => a + vals[b.name] / tickBase[b.name] * 100, 0) / BASKET.length;
    onTickAggregate({epoch: tick.epoch, quote: idx}); checkAlerts(idx);
  }

  // ---------- alerts ----------
  let alerts = {}, alertLines = [], pick = false, audio = null, logLines = [];
  function loadAlerts() { try { alerts = JSON.parse(localStorage.getItem("gold_desk_alerts_v1") || "{}"); } catch (e) { alerts = {}; } }
  function saveAlerts() { try { localStorage.setItem("gold_desk_alerts_v1", JSON.stringify(alerts)); } catch (e) {} }
  function drawAlerts() {
    alertLines.forEach(l => candleSeries.removePriceLine(l)); alertLines = [];
    const list = alerts[curSym] || [], box = $("alertlist"); box.innerHTML = "";
    list.forEach(a => {
      alertLines.push(candleSeries.createPriceLine({price: a.price, color: "#F57C00", lineWidth: 2, lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true, title: "Alert"}));
      const c = document.createElement("span"); c.className = "chip alert-chip"; c.textContent = fmtPrice(a.price) + "  \u2715";
      c.onclick = () => { alerts[curSym] = (alerts[curSym] || []).filter(x => x.id !== a.id); saveAlerts(); drawAlerts(); };
      box.appendChild(c);
    });
  }
  function unlockSound() {
    try { if (!audio) audio = new (window.AudioContext || window.webkitAudioContext)(); if (audio.state === "suspended") audio.resume(); } catch (e) {}
    try { if (window.Notification && Notification.permission === "default") Notification.requestPermission(); } catch (e) {}
  }
  function beep() {
    try { if (!audio) return; [0, 0.25, 0.5].forEach(d => { const o = audio.createOscillator(), g = audio.createGain();
      o.frequency.value = 880; g.gain.value = 0.15; o.connect(g); g.connect(audio.destination); o.start(audio.currentTime + d); o.stop(audio.currentTime + d + 0.18); }); } catch (e) {}
  }
  function addAlert(price) {
    price = Number(price); if (!isFinite(price) || price <= 0) return;
    price = +price.toFixed(SYMBOLS[curSym].dec);
    (alerts[curSym] = alerts[curSym] || []).push({id: Date.now() + Math.random(), price: price});
    saveAlerts(); drawAlerts(); unlockSound();
  }
  function fire(a, now) {
    alerts[curSym] = (alerts[curSym] || []).filter(x => x.id !== a.id); saveAlerts(); drawAlerts();
    const msg = curSym + " crossed " + fmtPrice(a.price) + " (now " + fmtPrice(now) + ")";
    const b = $("banner"); b.textContent = "\u{1F514} ALERT: " + msg; b.style.display = "block";
    b.onclick = () => { b.style.display = "none"; }; setTimeout(() => { b.style.display = "none"; }, 15000);
    logLines.unshift(new Date().toLocaleTimeString() + "  " + msg); $("log").textContent = "Triggered: " + logLines.slice(0, 4).join("   |   ");
    beep(); try { if (window.Notification && Notification.permission === "granted") new Notification("Gold Desk alert", {body: msg}); } catch (e) {}
  }
  function checkAlerts(price) {
    if (!isFinite(price)) return;
    if (lastPx === null) { lastPx = price; return; }
    (alerts[curSym] || []).filter(a => (lastPx < a.price && price >= a.price) || (lastPx > a.price && price <= a.price)).forEach(a => fire(a, price));
    lastPx = price;
  }
  function setPick(on) { pick = on; $("pickalert").className = on ? "active" : ""; $("pickalert").textContent = on ? "Click the chart..." : "Click chart to set"; }
  $("addalert").onclick = () => { addAlert($("alertprice").value); $("alertprice").value = ""; };
  $("pickalert").onclick = () => { unlockSound(); setPick(!pick); };
  chart.subscribeClick(p => { if (!pick || !p.point) return; const price = candleSeries.coordinateToPrice(p.point.y); if (price !== null) addAlert(price); setPick(false); });

  // ---------- previous day levels (single symbols) ----------
  function clearLevels() { priceLines.forEach(l => candleSeries.removePriceLine(l)); priceLines = []; }
  function drawLevels() {
    clearLevels();
    if (!dayRow || !chipState.levels || isBasket()) return;
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
  function onTick(tick) {
    if (isBasket()) { if (useTicks) basketTick(tick); return; }
    if (tick.bid !== undefined && tick.ask !== undefined) {
      const q = $("quote"), s = SYMBOLS[curSym];
      q.style.display = "block";
      q.innerHTML = '<span class="sell">SELL ' + fmtPrice(tick.bid) + '</span><span class="spread">' +
        ((tick.ask - tick.bid) * s.scale).toFixed(1) + '</span><span class="buy">BUY ' + fmtPrice(tick.ask) + '</span>';
    }
    if (useTicks) onTickAggregate(tick);
    checkAlerts(+tick.quote);
  }
  function handle(m) {
    const rid = m.req_id || (m.echo_req && m.echo_req.req_id);
    if (m.error) {
      if (rid === 1 || (rid >= 10 && rid < 20)) {
        if (!useTicks) { useTicks = true; candles = []; tickLast = {}; tickBase = null; setStatus("Deriv candle history unavailable (" + m.error.code + "). Building candles from live ticks.", true);
          if (isBasket()) { [GOLD].concat(BASKET.filter(b => b.code).map(b => b.code)).forEach(c => send({ticks: c, subscribe: 1})); } }
      } else if (rid !== 3) setStatus("Error: " + (m.error.message || m.error.code), false);
      return;
    }
    if (m.msg_type === "candles") {
      if (rid === 1) { setHistory((m.candles || []).map(toBar)); setStatus("Live from Deriv", true); }
      else if (rid === 3) setLevels(m.candles);
      else if (rid >= 10 && rid < 20) {
        const name = rid === 10 ? "XAU" : BASKET.filter(b => b.code)[rid - 11].name;
        bars[name] = (m.candles || []).map(toBar); delete pending[name];
        if (Object.keys(pending).length === 0 && !useTicks) { setHistory(buildBasketHistory()); setStatus("Live from Deriv (XAU basket)", true); }
      }
    } else if (m.msg_type === "ohlc") {
      if (isBasket()) basketOnOhlc(m.ohlc.symbol, m.ohlc);
      else { pushBar(toBar(m.ohlc)); }
    } else if (m.msg_type === "tick") onTick(m.tick);
  }
  function connect() {
    setStatus("Connecting...", false);
    ws = new WebSocket(WS_URL);
    ws.onopen = () => {
      const g = TFS[curTf];
      if (isBasket()) {
        bars = {}; pending = {XAU: 1}; baseVals = null;
        send({ticks_history: GOLD, adjust_start_time: 1, count: 600, end: "latest", granularity: g, style: "candles", subscribe: 1, req_id: 10});
        BASKET.filter(b => b.code).forEach((b, k) => { pending[b.name] = 1;
          send({ticks_history: b.code, adjust_start_time: 1, count: 600, end: "latest", granularity: g, style: "candles", subscribe: 1, req_id: 11 + k}); });
      } else {
        const code = SYMBOLS[curSym].code;
        send({ticks_history: code, adjust_start_time: 1, count: 600, end: "latest", granularity: g, style: "candles", subscribe: 1, req_id: 1});
        send({ticks: code, subscribe: 1, req_id: 2});
        send({ticks_history: code, count: 3, end: "latest", granularity: 86400, style: "candles", req_id: 3});
      }
    };
    ws.onmessage = ev => { try { handle(JSON.parse(ev.data)); } catch (e) { setStatus("Data error: " + e.message, false); } };
    ws.onerror = () => setStatus("Connection error", false);
    ws.onclose = () => { setStatus("Disconnected. Reconnecting...", false); setTimeout(connect, 2000); };
  }
  function restart() {
    useTicks = false; candles = []; dayRow = null; lastPx = null; bars = {}; baseVals = null; pending = {};
    candleSeries.setData([]); IND.forEach(i => lines[i.id].setData([])); clearLevels(); drawAlerts();
    $("quote").style.display = "none";
    if (ws) { ws.onclose = null; try { ws.close(); } catch (e) {} }
    connect();
  }
  selSym.onchange = () => { curSym = selSym.value; restart(); };
  selZone.onchange = () => { curZone = selZone.value; applyFormats(); };

  loadAlerts(); drawAlerts();
  window.__test = {emaArr, smaArr, handle, getCandles: () => candles, addAlert, getAlerts: () => alerts, setSym: s => { curSym = s; restart(); }};   // used by automated tests only
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
