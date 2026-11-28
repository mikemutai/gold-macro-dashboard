"""
livechart.py  -  Two TradingView-powered charts for the dashboard

1) live_chart_html():  a LIVE chart built with TradingView Lightweight Charts
   (free, open source). Your browser connects straight to Deriv's public price
   feed, so candles update on every tick with no page refresh.
   Symbols: XAUUSD, XAU BASKET (gold vs 7 currencies), EURUSD, GBPUSD, USDJPY,
   GBPJPY. Indicators: EMA 50, EMA 18, EMA 9, SMA 50. Price alerts built in.

2) tradingview_widget_html():  TradingView's free embeddable chart widget with
   the full TradingView toolbar (drawing tools, indicators). It uses
   TradingView's own prices, not Deriv's.

Used by dashboard.py. Keep it in the same folder.
"""

import json

LIGHTWEIGHT_URL = ("https://cdn.jsdelivr.net/npm/lightweight-charts@4.2.0/dist/"
                   "lightweight-charts.standalone.production.js")

# Chart colours. The page around the chart always uses Black / Cyan / Magenta.
CHART_THEMES = {
    "Neon": {   # black, cyan, magenta
        "bg": "#020306", "grid": "#111925", "text": "#B8C7CF", "cross": "#7CE6FC",
        "up": "#7CE6FC", "down": "#FC36BE", "pd": "#8FA3AD", "eq": "#FC36BE",
        "alert": "#FFB020", "scale": "#243247",
        "ind": {"ema50": "#4C8DFF", "ema18": "#FFB020", "ema9": "#39E58C", "sma50": "#E6F1F5"},
    },
    "Classic": {   # whitish grey, blue and black (TradingView look)
        "bg": "#DCDCDC", "grid": "#CFCFCF", "text": "#333333", "cross": "#000000",
        "up": "#1F4FD8", "down": "#000000", "pd": "#6B6B6B", "eq": "#E53935",
        "alert": "#F57C00", "scale": "#B0B0B0",
        "ind": {"ema50": "#2962FF", "ema18": "#E91E63", "ema9": "#2E9E3E", "sma50": "#00ACC1"},
    },
}

_LIVE_TEMPLATE = r"""
<style>
  :root { --bg:#020306; --panel:#0A0F1A; --line:#17212F; --edge:#243247; --text:#E6F1F5;
          --muted:#9FB3BD; --cyan:#7CE6FC; --mag:#FC36BE; }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; background: var(--bg); color: var(--text);
               font-family: Inter, -apple-system, "Segoe UI", Roboto, Arial, sans-serif; font-size: 14px; }
  #toolbar, #chips, #alertbar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px;
               background: var(--panel); border: 1px solid var(--line); border-radius: 12px;
               padding: 9px 14px; margin-bottom: 8px; }
  select, input[type=number] { font: inherit; font-size: 14px; padding: 6px 10px; border: 1px solid var(--edge);
               border-radius: 8px; background: #050912; color: var(--text); outline: none; }
  select:focus, input:focus { border-color: var(--cyan); }
  input[type=number] { width: 120px; }
  input::placeholder { color: #6B7C86; }
  button { font: inherit; font-size: 14px; font-weight: 600; padding: 6px 14px; border: 1px solid var(--edge);
           border-radius: 999px; background: #050912; color: var(--text); cursor: pointer; }
  button:hover { border-color: var(--cyan); color: var(--cyan); }
  button.active { background: var(--cyan); border-color: var(--cyan); color: #020306; }
  #tfs { display: flex; gap: 5px; flex-wrap: wrap; }
  #live { margin-left: auto; display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--muted); }
  #dot { width: 10px; height: 10px; border-radius: 50%; background: #4B5A66; display: inline-block; flex: none; }
  #dot.on { background: var(--cyan); box-shadow: 0 0 0 3px rgba(124,230,252,.25); }
  #dot.err { background: var(--mag); box-shadow: 0 0 0 3px rgba(252,54,190,.25); }
  .chip { display: inline-flex; align-items: center; gap: 7px; font-size: 13px; font-weight: 600; color: var(--text);
          padding: 5px 12px; border: 1px solid var(--edge); border-radius: 999px; background: #050912; cursor: pointer; user-select: none; }
  .chip i { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
  .chip.off { opacity: .4; }
  .lbl { font-size: 12px; font-weight: 700; color: var(--cyan); text-transform: uppercase; letter-spacing: .08em; }
  .alert-chip { background: #2A1F08; border-color: #FFB020; color: #FFB020; }
  #wrap { position: relative; border-radius: 12px; overflow: hidden; border: 1px solid var(--line); }
  #chart { width: 100%; height: 620px; }
  #quote { position: absolute; top: 10px; left: 10px; z-index: 5; background: var(--panel); border: 1px solid var(--edge);
           border-radius: 8px; padding: 6px 12px; font-size: 14px; font-weight: 700; display: none; }
  #quote .sell { color: var(--mag); } #quote .buy { color: var(--cyan); }
  #quote .spread { color: var(--muted); font-weight: 400; margin: 0 10px; }
  #banner { position: absolute; top: 12px; left: 50%; transform: translateX(-50%); z-index: 9; display: none;
            background: var(--mag); color: #020306; font-weight: 800; padding: 11px 20px; border-radius: 10px;
            box-shadow: 0 6px 24px rgba(252,54,190,.45); cursor: pointer; font-size: 15px; }
  #log { font-size: 13px; color: var(--muted); padding: 7px 4px; min-height: 20px; }
  #foot { font-size: 12px; color: #7B8C96; padding: 2px 4px 8px; line-height: 1.5; }
  #foot a { color: var(--cyan); }
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
  const THEME = __THEME__;
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
    {id: "ema50", label: "EMA 50", kind: "ema", len: 50, color: THEME.ind.ema50},
    {id: "ema18", label: "EMA 18", kind: "ema", len: 18, color: THEME.ind.ema18},
    {id: "ema9",  label: "EMA 9",  kind: "ema", len: 9,  color: THEME.ind.ema9},
    {id: "sma50", label: "SMA 50", kind: "sma", len: 50, color: THEME.ind.sma50}
  ];
  const $ = id => document.getElementById(id);
  function setStatus(t, state) { $("status").textContent = t; $("dot").className = state === true ? "on" : (state === "err" ? "err" : ""); }

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
  IND.concat([{id: "levels", label: "Prev. day levels", color: THEME.pd}]).forEach(i => {
    const c = document.createElement("span"); c.className = "chip";
    c.innerHTML = '<i style="background:' + i.color + '"></i>' + i.label;
    chipState[i.id] = true;
    c.onclick = () => { chipState[i.id] = !chipState[i.id]; c.className = chipState[i.id] ? "chip" : "chip off"; if (i.id === "levels") drawLevels(); else lines[i.id].applyOptions({visible: chipState[i.id]}); };
    $("chips").appendChild(c);
  });

  if (typeof LightweightCharts === "undefined") { setStatus("Could not load the chart library (network blocked?).", "err"); return; }

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
    layout: {background: {type: "solid", color: THEME.bg}, textColor: THEME.text},
    grid: {vertLines: {color: THEME.grid}, horzLines: {color: THEME.grid}},
    crosshair: {mode: LightweightCharts.CrosshairMode.Normal,
      vertLine: {color: THEME.cross, labelBackgroundColor: THEME.cross}, horzLine: {color: THEME.cross, labelBackgroundColor: THEME.cross}},
    rightPriceScale: {borderColor: THEME.scale},
    timeScale: {borderColor: THEME.scale, timeVisible: true, secondsVisible: false, tickMarkFormatter: tickFmt, rightOffset: 8},
    localization: {timeFormatter: fullFmt}
  });
  const candleSeries = chart.addCandlestickSeries({
    upColor: THEME.up, downColor: THEME.down, borderUpColor: THEME.up, borderDownColor: THEME.down,
    wickUpColor: THEME.up, wickDownColor: THEME.down});
  const lines = {};
  IND.forEach(i => { lines[i.id] = chart.addLineSeries({color: i.color, lineWidth: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false}); });
  new ResizeObserver(() => chart.applyOptions({width: el.clientWidth})).observe(el);

  // ---------- data ----------
  let ws = null, candles = [], useTicks = false, priceLines = [], dayRow = null, lastPx = null;
  let bars = {}, baseVals = null, tickLast = {}, tickBase = null, queue = [], awaiting = null, gotData = false, lastReply = "";

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
    if (n) { lastPx = candles[n - 1].close; gotData = true; }
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
    const gold = bars.XAU || []; if (!gold.length) return [];
    baseVals = {};
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
    if (tickLast.XAU === undefined || !BASKET.every(b => b.code === null || tickLast[b.name] !== undefined)) return;
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
      alertLines.push(candleSeries.createPriceLine({price: a.price, color: THEME.alert, lineWidth: 2, lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true, title: "Alert"}));
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
    [[hi, "PDH", THEME.pd, LS.Dotted], [lo, "PDL", THEME.pd, LS.Dotted], [eq, "EQUILIBRIUM", THEME.eq, LS.Dashed]].forEach(x => {
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
  // Requests go out one at a time and each reply is matched to the request that
  // is waiting, so it does not matter whether Deriv echoes a request id.
  function send(o) { if (ws && ws.readyState === 1) ws.send(JSON.stringify(o)); }
  function candlesReq(code, granularity, count, subscribe) {
    const r = {ticks_history: code, adjust_start_time: 1, count: count, end: "latest", granularity: granularity, style: "candles"};
    if (subscribe) r.subscribe = 1; return r;
  }
  function runQueue() { awaiting = queue.shift() || null; if (awaiting) send(awaiting.req); else historyDone(); }
  function historyDone() {
    if (useTicks) return;
    if (isBasket()) {
      const list = buildBasketHistory(); setHistory(list);
      setStatus(list.length ? "Live from Deriv (XAU basket)" : "No basket candles returned", list.length > 0);
    } else send({ticks: SYMBOLS[curSym].code, subscribe: 1});
  }
  function startTickFallback(why) {
    queue = []; awaiting = null; useTicks = true; candles = []; tickLast = {}; tickBase = null;
    setStatus("Candle history unavailable (" + why + "). Building candles from live ticks.", true);
    (isBasket() ? [GOLD].concat(BASKET.filter(b => b.code).map(b => b.code)) : [SYMBOLS[curSym].code]).forEach(c => send({ticks: c, subscribe: 1}));
  }
  function onCandles(m) {
    const item = awaiting; if (!item) return;
    const list = (m.candles || []).map(toBar);
    if (item.kind === "main") { setHistory(list); setStatus(list.length ? "Live from Deriv" : "Deriv returned no candles", list.length > 0); }
    else if (item.kind === "daily") setLevels(m.candles);
    else if (item.kind === "basket") bars[item.name] = list;
    runQueue();
  }
  function onError(m) {
    const msg = (m.error && (m.error.message || m.error.code)) || "unknown error";
    const closed = /closed/i.test(msg);
    if (awaiting) {
      const item = awaiting;
      if (closed && item.req.subscribe && !item.retried) { item.retried = true; delete item.req.subscribe; send(item.req); return; }   // closed market: ask for history only
      if (item.kind === "daily") { runQueue(); return; }
      if (closed) { queue = []; awaiting = null; setStatus("Market closed. " + msg, "err"); return; }
      startTickFallback(m.error.code || msg); return;
    }
    if (closed) setStatus("Market closed. " + (candles.length ? "Showing the last available candles. " : "") + msg, false);
    else setStatus("Error: " + msg, "err");
  }
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
    lastReply = (m.msg_type || (m.error ? "error" : "?"));
    if (m.error) return onError(m);
    if (Array.isArray(m.candles)) return onCandles(m);
    if (m.msg_type === "ohlc" && m.ohlc) { if (isBasket()) basketOnOhlc(m.ohlc.symbol, m.ohlc); else pushBar(toBar(m.ohlc)); }
    else if (m.msg_type === "tick" && m.tick) onTick(m.tick);
  }
  function connect() {
    setStatus("Connecting...", false);
    ws = new WebSocket(WS_URL);
    ws.onopen = () => {
      const g = TFS[curTf]; queue = []; awaiting = null; gotData = false;
      if (isBasket()) {
        bars = {}; baseVals = null;
        queue.push({kind: "basket", name: "XAU", req: candlesReq(GOLD, g, 600, true)});
        BASKET.filter(b => b.code).forEach(b => queue.push({kind: "basket", name: b.name, req: candlesReq(b.code, g, 600, true)}));
      } else {
        const code = SYMBOLS[curSym].code;
        queue.push({kind: "main", req: candlesReq(code, g, 600, true)});
        queue.push({kind: "daily", req: candlesReq(code, 86400, 3, false)});
      }
      runQueue();
      setTimeout(() => { if (!gotData && !useTicks && queue.length + (awaiting ? 1 : 0) > 0) setStatus("Waiting for Deriv... (last reply: " + (lastReply || "none") + ")", false); }, 8000);
    };
    ws.onmessage = ev => { try { handle(JSON.parse(ev.data)); } catch (e) { setStatus("Data error: " + e.message, "err"); } };
    ws.onerror = () => setStatus("Connection error", "err");
    ws.onclose = () => { setStatus("Disconnected. Reconnecting...", false); setTimeout(connect, 2000); };
  }
  function restart() {
    useTicks = false; candles = []; dayRow = null; lastPx = null; bars = {}; baseVals = null; queue = []; awaiting = null;
    candleSeries.setData([]); IND.forEach(i => lines[i.id].setData([])); clearLevels(); drawAlerts();
    $("quote").style.display = "none";
    if (ws) { ws.onclose = null; try { ws.close(); } catch (e) {} }
    connect();
  }
  selSym.onchange = () => { curSym = selSym.value; restart(); };
  selZone.onchange = () => { curZone = selZone.value; applyFormats(); };

  loadAlerts(); drawAlerts();
  window.__test = {emaArr, smaArr, handle, getCandles: () => candles, addAlert, getAlerts: () => alerts, setSym: s => { curSym = s; restart(); }, getQueueState: () => ({queue: queue.length, awaiting: awaiting && awaiting.kind})};   // used by automated tests only
  connect();
})();
</script>
"""


def live_chart_html(symbol="XAUUSD", timeframe="15m", zone="New York", theme="Neon"):
    """HTML for the live Deriv chart (use with st.iframe or components.html)."""
    colours = CHART_THEMES.get(theme, CHART_THEMES["Neon"])
    return (_LIVE_TEMPLATE.replace("__LIB__", LIGHTWEIGHT_URL)
            .replace("__THEME__", json.dumps(colours))
            .replace("__SYM__", symbol).replace("__TF__", timeframe)
            .replace("__ZONE__", zone))


def tradingview_widget_html(symbol="OANDA:XAUUSD", interval="15",
                            timezone="America/New_York", height=720, theme="Neon"):
    """HTML for TradingView's free Advanced Chart widget."""
    dark = theme == "Neon"
    config = {
        "autosize": True, "symbol": symbol, "interval": interval,
        "timezone": timezone, "theme": "dark" if dark else "light",
        "style": "1", "locale": "en",
        "backgroundColor": "#020306" if dark else "#DCDCDC",
        "gridColor": "#111925" if dark else "#CFCFCF",
        "allow_symbol_change": True, "hide_side_toolbar": False,
        "withdateranges": True, "details": False, "calendar": False,
        "support_host": "https://www.tradingview.com",
    }
    link = "#7CE6FC" if dark else "#1F4FD8"
    return f"""
<style>html, body {{ margin: 0; background: {"#020306" if dark else "#DCDCDC"}; }}</style>
<div class="tradingview-widget-container" style="height:{height}px;width:100%">
  <div class="tradingview-widget-container__widget" style="height:{height - 28}px;width:100%"></div>
  <div class="tradingview-widget-copyright" style="font-size:12px;font-family:Arial,sans-serif;padding:4px">
    <a href="https://www.tradingview.com/" rel="noopener nofollow" target="_blank" style="color:{link}">Track all markets on TradingView</a>
  </div>
  <script type="text/javascript"
    src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
  {json.dumps(config)}
  </script>
</div>
"""
