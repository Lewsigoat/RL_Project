(() => {
  const $ = (id) => document.getElementById(id);
  const els = {
    form: $("controls"), quote: $("quote"), symbol: $("symbol"), levels: $("levels"), topn: $("topn"),
    symbols: $("symbols"), status: $("status"), asks: $("asks"), bids: $("bids"), midRow: $("mid-row"),
    depth: $("depth"), history: $("history"), bands: $("bands").querySelector("tbody"),
    slip: $("slip").querySelector("tbody"), walls: $("walls"), signalCard: document.querySelector(".card.signal"),
  };

  let ws = null;
  let priceDecimals = 2;
  let qtyDecimals = 4;
  const history = []; // {t, imb}
  const HISTORY_MAX = 1200;

  // ---------- formatting ----------
  const fmt = (x, d = 2) => (x == null || Number.isNaN(x)) ? "-" : Number(x).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  const fmtBig = (x) => {
    if (x == null) return "-";
    const a = Math.abs(x);
    if (a >= 1e9) return (x / 1e9).toFixed(2) + "B";
    if (a >= 1e6) return (x / 1e6).toFixed(2) + "M";
    if (a >= 1e3) return (x / 1e3).toFixed(1) + "K";
    return x.toFixed(0);
  };
  const signed = (x, d = 2) => (x == null ? "-" : (x >= 0 ? "+" : "") + Number(x).toFixed(d));
  const decimalsFor = (tick) => {
    if (!tick) return 2;
    const s = tick.toString();
    if (s.includes("e-")) return parseInt(s.split("e-")[1], 10);
    return Math.max(0, (s.split(".")[1] || "").replace(/0+$/, "").length);
  };
  const inferDecimals = (levels) => {
    let d = 0;
    for (const [p, q] of levels) {
      const ps = String(p).split(".")[1] || ""; const qs = String(q).split(".")[1] || "";
      d = Math.max(d, ps.length);
      qtyDecimals = Math.max(Math.min(qs.length, 6), 2);
    }
    return Math.min(d, 8);
  };

  // ---------- symbols ----------
  let symbolMeta = new Map();
  async function loadSymbols() {
    const quote = els.quote.value;
    const url = quote ? `/api/symbols?quote=${quote}&limit=5000` : "/api/symbols?limit=5000";
    try {
      const r = await fetch(url);
      const data = await r.json();
      symbolMeta = new Map(data.symbols.map((s) => [s.symbol, s]));
      els.symbols.innerHTML = data.symbols.map((s) => `<option value="${s.symbol}">${s.base}/${s.quote}</option>`).join("");
    } catch (e) {
      setStatus("warn", "symbol list unavailable");
    }
  }

  // ---------- status ----------
  function setStatus(cls, text) {
    els.status.className = `status ${cls}`;
    els.status.textContent = text;
  }

  // ---------- websocket ----------
  function connect() {
    if (ws) { ws.onclose = null; ws.close(); ws = null; }
    const symbol = els.symbol.value.trim().toUpperCase();
    if (!symbol) return;
    els.symbol.value = symbol;
    history.length = 0;
    const meta = symbolMeta.get(symbol);
    priceDecimals = meta ? decimalsFor(meta.tick_size) : 2;
    const params = new URLSearchParams({ levels: els.levels.value, top_n: els.topn.value, interval_ms: "250" });
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws/${symbol}?${params}`);
    setStatus("warn", `connecting ${symbol}…`);
    document.title = `${symbol} · Binance DOM`;
    ws.onopen = () => setStatus("warn", `waiting for data…`);
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "depth") { setStatus("on", `${symbol} · ${msg.source}`); render(msg); }
      else if (msg.type === "error") setStatus("off", msg.message);
      else if (msg.type === "info") setStatus("warn", msg.message);
    };
    ws.onclose = () => setStatus("off", "disconnected");
    ws.onerror = () => setStatus("off", "connection error");
    loadTicker(symbol);
  }

  async function loadTicker(symbol) {
    try {
      const r = await fetch(`/api/ticker?symbol=${symbol}`);
      if (!r.ok) return;
      const t = await r.json();
      const chg = parseFloat(t.priceChangePercent);
      $("m-ticker").innerHTML = `24h <span class="${chg >= 0 ? "bid" : "ask"}">${signed(chg)}%</span> · vol ${fmtBig(parseFloat(t.quoteVolume))}`;
    } catch (_) { /* ignore */ }
  }

  // ---------- render ----------
  function render(msg) {
    const a = msg.analysis;
    if (!symbolMeta.has(msg.symbol)) priceDecimals = inferDecimals(msg.bids.concat(msg.asks));
    else inferDecimals(msg.bids.concat(msg.asks));

    $("m-mid").textContent = fmt(a.mid, priceDecimals);
    $("m-spread").textContent = fmt(a.spread, priceDecimals);
    $("m-spread-bps").textContent = `${a.spread_bps.toFixed(3)} bps`;
    $("m-micro").textContent = fmt(a.microprice, priceDecimals);
    $("m-skew").textContent = `${signed(a.microprice_skew_bps)} bps vs mid`;
    $("m-imb").textContent = signed(a.imbalance_top, 3);
    $("m-imb").className = "v " + (a.imbalance_top > 0.05 ? "bid" : a.imbalance_top < -0.05 ? "ask" : "");
    $("m-imb-fill").style.width = `${((a.imbalance_top + 1) / 2) * 100}%`;
    $("m-bidn").textContent = fmtBig(a.bid_depth_notional);
    $("m-askn").textContent = fmtBig(a.ask_depth_notional);
    $("m-levels").textContent = `${a.levels} levels/side · ${a.bid_depth_qty.toFixed(qtyDecimals)} / ${a.ask_depth_qty.toFixed(qtyDecimals)} base`;
    $("m-signal").textContent = a.signal;
    $("m-source").textContent = `${msg.source} · ${new Date(msg.ts).toLocaleTimeString()}`;
    els.signalCard.className = "card signal " + (a.signal.includes("buy") ? "buy" : a.signal.includes("sell") ? "sell" : "");

    renderLadder(msg, a);
    renderBands(a);
    renderSlippage(a);
    renderWalls(a);
    drawDepth(a);
    history.push({ t: msg.ts, imb: a.imbalance_top });
    if (history.length > HISTORY_MAX) history.shift();
    drawHistory();
  }

  function renderLadder(msg, a) {
    const n = Math.min(20, msg.bids.length, msg.asks.length);
    const wallPrices = new Set(a.walls.map((w) => w.price));
    const maxCum = Math.max(a.cumulative_bids[n - 1]?.cum_notional || 0, a.cumulative_asks[n - 1]?.cum_notional || 0) || 1;
    const row = (lvl, cum) => {
      const pct = Math.min(100, (cum.cum_notional / maxCum) * 100);
      const cls = wallPrices.has(lvl[0]) ? "row wall" : "row";
      return `<div class="${cls}"><div class="bar" style="width:${pct}%"></div><span>${fmt(lvl[0], priceDecimals)}</span><span>${fmt(lvl[1], qtyDecimals)}</span><span>${fmtBig(cum.cum_notional)}</span></div>`;
    };
    els.asks.innerHTML = msg.asks.slice(0, n).map((l, i) => row(l, a.cumulative_asks[i])).reverse().join("");
    els.bids.innerHTML = msg.bids.slice(0, n).map((l, i) => row(l, a.cumulative_bids[i])).join("");
    els.midRow.innerHTML = `mid <b>${fmt(a.mid, priceDecimals)}</b> · spread ${a.spread_bps.toFixed(3)} bps`;
  }

  function renderBands(a) {
    els.bands.innerHTML = Object.keys(a.imbalance_bands).map((k) => {
      const imb = a.imbalance_bands[k];
      const cls = imb > 0.05 ? "bid" : imb < -0.05 ? "ask" : "";
      return `<tr><td>${k} bps</td><td class="bid">${fmtBig(a.bid_notional_bands[k])}</td><td class="ask">${fmtBig(a.ask_notional_bands[k])}</td><td class="${cls}">${signed(imb)}</td></tr>`;
    }).join("");
  }

  function renderSlippage(a) {
    els.slip.innerHTML = Object.entries(a.slippage).map(([size, s]) => {
      const cell = (bps, full) => bps == null ? '<span class="muted">n/a</span>' : `${bps.toFixed(2)} bps${full ? "" : ' <span class="muted">(partial)</span>'}`;
      return `<tr><td>${fmtBig(parseFloat(size))}</td><td>${cell(s.buy_slippage_bps, s.buy_fully_filled)}</td><td>${cell(s.sell_slippage_bps, s.sell_fully_filled)}</td></tr>`;
    }).join("");
  }

  function renderWalls(a) {
    if (!a.walls.length) { els.walls.innerHTML = '<li class="muted">none detected in visible depth</li>'; return; }
    els.walls.innerHTML = a.walls.slice(0, 8).map((w) =>
      `<li><span class="${w.side}">${w.side.toUpperCase()}</span> ${fmt(w.price, priceDecimals)} · ${fmt(w.quantity, qtyDecimals)} (${fmtBig(w.notional)}) · ${w.ratio_to_median.toFixed(1)}x median · ${w.distance_bps.toFixed(1)} bps away</li>`
    ).join("");
  }

  // ---------- charts ----------
  function drawDepth(a) {
    const c = els.depth, ctx = c.getContext("2d");
    const W = c.width, H = c.height, pad = { l: 60, r: 16, t: 12, b: 28 };
    ctx.clearRect(0, 0, W, H);
    const bids = a.cumulative_bids, asks = a.cumulative_asks;
    if (!bids.length || !asks.length) return;
    const pMin = bids[bids.length - 1].price, pMax = asks[asks.length - 1].price;
    const yMax = Math.max(bids[bids.length - 1].cum_notional, asks[asks.length - 1].cum_notional) * 1.05;
    const x = (p) => pad.l + ((p - pMin) / (pMax - pMin || 1)) * (W - pad.l - pad.r);
    const y = (v) => H - pad.b - (v / yMax) * (H - pad.t - pad.b);

    // grid + axes
    ctx.strokeStyle = "#232b3b"; ctx.fillStyle = "#7d8aa3"; ctx.font = "11px ui-monospace, monospace"; ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const v = (yMax / 4) * i, yy = y(v);
      ctx.beginPath(); ctx.moveTo(pad.l, yy); ctx.lineTo(W - pad.r, yy); ctx.stroke();
      ctx.textAlign = "right"; ctx.fillText(fmtBig(v), pad.l - 6, yy + 4);
    }
    ctx.textAlign = "center";
    for (let i = 0; i <= 4; i++) {
      const p = pMin + ((pMax - pMin) / 4) * i;
      ctx.fillText(fmt(p, priceDecimals), x(p), H - 8);
    }

    const step = (levels, color, dir) => {
      ctx.beginPath();
      ctx.moveTo(x(dir > 0 ? a.mid : a.mid), y(0));
      let prevY = y(0);
      for (const l of levels) {
        ctx.lineTo(x(l.price), prevY);
        ctx.lineTo(x(l.price), y(l.cum_notional));
        prevY = y(l.cum_notional);
      }
      const last = levels[levels.length - 1];
      ctx.lineTo(x(last.price), y(0));
      ctx.closePath();
      ctx.fillStyle = color + "33"; ctx.fill();
      ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.stroke();
    };
    step(bids, "#22c55e", -1);
    step(asks, "#ef4444", 1);

    // mid line
    ctx.strokeStyle = "#f0b90b"; ctx.setLineDash([4, 4]);
    ctx.beginPath(); ctx.moveTo(x(a.mid), pad.t); ctx.lineTo(x(a.mid), H - pad.b); ctx.stroke();
    ctx.setLineDash([]);
  }

  function drawHistory() {
    const c = els.history, ctx = c.getContext("2d");
    const W = c.width, H = c.height, pad = 8;
    ctx.clearRect(0, 0, W, H);
    const mid = H / 2;
    ctx.strokeStyle = "#232b3b"; ctx.beginPath(); ctx.moveTo(0, mid); ctx.lineTo(W, mid); ctx.stroke();
    if (history.length < 2) return;
    const x = (i) => (i / (HISTORY_MAX - 1)) * (W - pad * 2) + pad;
    const y = (v) => mid - v * (H / 2 - pad);
    const offset = HISTORY_MAX - history.length;
    // fill positive green / negative red
    for (let i = 1; i < history.length; i++) {
      const v = history[i].imb;
      ctx.fillStyle = v >= 0 ? "#22c55e55" : "#ef444455";
      const x0 = x(offset + i - 1), x1 = x(offset + i);
      ctx.fillRect(x0, Math.min(mid, y(v)), Math.max(1, x1 - x0), Math.abs(y(v) - mid));
    }
    ctx.strokeStyle = "#dfe6f2"; ctx.lineWidth = 1; ctx.beginPath();
    history.forEach((h, i) => { const px = x(offset + i), py = y(h.imb); i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); });
    ctx.stroke();
    ctx.fillStyle = "#7d8aa3"; ctx.font = "11px ui-monospace, monospace"; ctx.textAlign = "left";
    ctx.fillText("+1 bids", 4, 12); ctx.fillText("-1 asks", 4, H - 4);
  }

  // ---------- wire up ----------
  els.form.addEventListener("submit", (e) => { e.preventDefault(); connect(); });
  els.quote.addEventListener("change", loadSymbols);
  els.levels.addEventListener("change", () => ws && connect());
  els.topn.addEventListener("change", () => ws && connect());

  const initial = new URLSearchParams(location.search).get("symbol");
  if (initial) els.symbol.value = initial.toUpperCase();
  loadSymbols().then(connect);
})();
