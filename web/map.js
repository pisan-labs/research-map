(() => {
  "use strict";
  const DATA = JSON.parse(document.getElementById("data").textContent);
  const P = DATA.people;
  const META = DATA.meta;

  // ------------------------------------------------------------ helpers
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const SLOTS = 8;

  function rankOf(title) {
    const t = title.toLowerCase();
    if (t.includes("teaching") || t.includes("lecturer")) return "Teaching track";
    if (t.includes("assistant professor")) return "Assistant Professor";
    if (t.includes("associate professor")) return "Associate Professor";
    if (t.includes("professor")) return "Professor";
    return "Other";
  }
  P.forEach((p, i) => { p.i = i; p.rank = rankOf(p.title); });

  // Stable group order per colour mode, computed once from all people, so a
  // filter never repaints the survivors. Largest group gets slot 1.
  function groupsFor(mode) {
    const key = mode === "area" ? (p) => String(p.area) : (p) => p[mode];
    const counts = d3.rollup(P, (v) => v.length, key);
    const order = [...counts.keys()].sort((a, b) => counts.get(b) - counts.get(a) || String(a).localeCompare(String(b)));
    const label = (k) => {
      if (mode !== "area") return k;
      const a = DATA.areas.find((x) => String(x.id) === k);
      return a && a.label ? a.label : "Area " + (Number(k) + 1);
    };
    return { key, order, counts, label, slot: new Map(order.map((k, i) => [k, i < SLOTS ? i + 1 : 0])) };
  }
  const GROUPS = { department: groupsFor("department"), program: groupsFor("program"), area: groupsFor("area") };

  const DEPTS = [...new Set(P.map((p) => p.department))].sort();
  const SHAPES = ["circle", "square", "triangle", "diamond", "circle", "square"];
  const shapeOf = (p) => SHAPES[DEPTS.indexOf(p.department) % SHAPES.length];

  // ------------------------------------------------------------ state
  const state = {
    colorBy: ["department", "program", "area"].includes(META.color_by) ? META.color_by : "department",
    dept: "",
    rank: "",
    q: "",
    focus: null, // legend group key being highlighted
    sel: null, // selected person index
    hover: null,
  };

  let palette = {};
  function readPalette() {
    palette = { other: css("--other"), ink: css("--ink"), ink2: css("--ink-2"), muted: css("--muted"), surface: css("--surface"), grid: css("--grid"), hi: css("--hi") };
    for (let s = 1; s <= SLOTS; s++) palette[s] = css("--s" + s);
  }
  const colorOf = (p) => {
    const g = GROUPS[state.colorBy];
    const s = g.slot.get(g.key(p));
    return s ? palette[s] : palette.other;
  };

  // ------------------------------------------------------------ search
  const norm = (s) => String(s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  P.forEach((p) => {
    p._name = norm(p.name);
    p._kw = norm([p.keywords, p.interests, p.listed.join(" "), p.terms.join(" ")].join(" . "));
    p._bio = norm(p.bio);
  });
  function search(q) {
    const words = norm(q).split(/[\s,]+/).filter((w) => w.length > 1);
    if (!words.length) return null;
    const phrase = norm(q).trim();
    const hits = [];
    for (const p of P) {
      let score = 0;
      if (p._name.includes(phrase)) score += 10;
      if (phrase.includes(" ") && p._kw.includes(phrase)) score += 6;
      let all = true;
      for (const w of words) {
        const inName = p._name.includes(w), inKw = p._kw.includes(w), inBio = p._bio.includes(w);
        if (!(inName || inKw || inBio)) all = false;
        score += (inName ? 3 : 0) + (inKw ? 2 : 0) + (inBio ? 1 : 0);
      }
      if (all && score > 0) hits.push({ p, score });
    }
    hits.sort((a, b) => b.score - a.score || a.p.name.localeCompare(b.p.name));
    return { words, hits };
  }
  let result = null;

  const passesFilters = (p) => (!state.dept || p.department === state.dept) && (!state.rank || p.rank === state.rank);
  function isActive(p) {
    if (!passesFilters(p)) return false;
    if (state.focus !== null && GROUPS[state.colorBy].key(p) !== state.focus) return false;
    if (result && !result.set.has(p.i)) return false;
    return true;
  }

  // ------------------------------------------------------------ canvas & zoom
  const canvas = $("map");
  const ctx = canvas.getContext("2d");
  const wrap = canvas.parentElement;
  let W = 0, H = 0, DPR = 1, base = { s: 1, ox: 0, oy: 0 };
  let T = d3.zoomIdentity;
  const PAD = 48;

  function resize() {
    const r = wrap.getBoundingClientRect();
    W = Math.max(200, r.width); H = Math.max(200, r.height);
    DPR = window.devicePixelRatio || 1;
    canvas.width = Math.round(W * DPR); canvas.height = Math.round(H * DPR);
    const xs = d3.extent(P, (p) => p.x), ys = d3.extent(P, (p) => p.y);
    // Keep the open legend (top-left) clear of points when there is room beside it.
    const lb = $("legendbox");
    const left = lb.open && W > 700 ? lb.offsetWidth + 24 : PAD;
    const s = Math.min((W - left - PAD) / (xs[1] - xs[0] || 1), (H - 2 * PAD) / (ys[1] - ys[0] || 1));
    base = { s, ox: left + (W - left - PAD - s * (xs[1] - xs[0])) / 2 - s * xs[0], oy: (H - s * (ys[1] - ys[0])) / 2 - s * ys[0] };
    zoom.extent([[0, 0], [W, H]]).translateExtent([[-W, -H], [2 * W, 2 * H]]);
    draw();
  }
  const sx = (x) => T.applyX(base.ox + base.s * x);
  const sy = (y) => T.applyY(base.oy + base.s * y);

  const zoom = d3.zoom().scaleExtent([0.6, 14]).on("zoom", (e) => { T = e.transform; hideTip(); draw(); });
  d3.select(canvas).call(zoom).on("dblclick.zoom", null);
  $("zin").onclick = () => d3.select(canvas).transition().duration(250).call(zoom.scaleBy, 1.6);
  $("zout").onclick = () => d3.select(canvas).transition().duration(250).call(zoom.scaleBy, 1 / 1.6);
  $("zreset").onclick = () => d3.select(canvas).transition().duration(350).call(zoom.transform, d3.zoomIdentity);

  function zoomTo(points, maxK = 4) {
    if (!points.length) return;
    const xs = d3.extent(points, (p) => base.ox + base.s * p.x), ys = d3.extent(points, (p) => base.oy + base.s * p.y);
    const w = Math.max(xs[1] - xs[0], 40), h = Math.max(ys[1] - ys[0], 40);
    const panelSafe = W > 500 ? 0.7 : 0.8;
    const k = Math.min(maxK, panelSafe * Math.min(W / w, H / h));
    const cx = (xs[0] + xs[1]) / 2, cy = (ys[0] + ys[1]) / 2;
    d3.select(canvas).transition().duration(450).call(zoom.transform, d3.zoomIdentity.translate(W / 2 - k * cx, H / 2 - k * cy).scale(k));
  }

  // ------------------------------------------------------------ drawing
  const R = 5.5;
  function marker(x, y, r, shape) {
    ctx.beginPath();
    if (shape === "square") { const a = r * 0.9; ctx.rect(x - a, y - a, 2 * a, 2 * a); }
    else if (shape === "triangle") { const a = r * 1.25; ctx.moveTo(x, y - a); ctx.lineTo(x + a * 0.95, y + a * 0.7); ctx.lineTo(x - a * 0.95, y + a * 0.7); ctx.closePath(); }
    else if (shape === "diamond") { const a = r * 1.2; ctx.moveTo(x, y - a); ctx.lineTo(x + a, y); ctx.lineTo(x, y + a); ctx.lineTo(x - a, y); ctx.closePath(); }
    else ctx.arc(x, y, r, 0, Math.PI * 2);
  }

  function draw() {
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    ctx.clearRect(0, 0, W, H);
    const k = T.k;
    const r = R * Math.min(1.6, Math.max(1, Math.sqrt(k) * 0.85));
    const sel = state.sel !== null ? P[state.sel] : null;

    // Links from the selected person to their nearest people.
    if (sel) {
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = palette.muted;
      ctx.globalAlpha = 0.55;
      for (const n of sel.near.slice(0, 10)) {
        const q = P[n.i];
        ctx.beginPath(); ctx.moveTo(sx(sel.x), sy(sel.y)); ctx.lineTo(sx(q.x), sy(q.y)); ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }

    const nearSet = new Set(sel ? sel.near.map((n) => n.i) : []);
    const order = [...P].sort((a, b) => (isActive(a) - isActive(b)) || (nearSet.has(a.i) - nearSet.has(b.i)));
    for (const p of order) {
      const x = sx(p.x), y = sy(p.y);
      if (x < -20 || y < -20 || x > W + 20 || y > H + 20) continue;
      const active = isActive(p);
      ctx.globalAlpha = active ? 1 : 0.16;
      const col = colorOf(p);
      marker(x, y, r, shapeOf(p));
      if (p.sparse) {
        ctx.fillStyle = palette.surface; ctx.fill();
        ctx.lineWidth = 2; ctx.strokeStyle = col; ctx.stroke();
      } else {
        ctx.fillStyle = col; ctx.fill();
        ctx.lineWidth = 1.5; ctx.strokeStyle = palette.surface; ctx.stroke(); // 2px-ish surface ring on overlaps
      }
    }
    ctx.globalAlpha = 1;

    for (const idx of [state.hover, state.sel]) {
      if (idx === null) continue;
      const p = P[idx];
      marker(sx(p.x), sy(p.y), r + 4, "circle");
      ctx.lineWidth = 2; ctx.strokeStyle = palette.hi; ctx.stroke();
    }

    drawLabels(k, r);
  }

  function drawLabels(k, r) {
    const boxes = [];
    const fits = (b) => !boxes.some((o) => b.x < o.x + o.w && b.x + b.w > o.x && b.y < o.y + o.h && b.y + b.h > o.y);
    ctx.textBaseline = "middle";
    ctx.lineJoin = "round";
    const label = (text, x, y, font, color, align = "center") => {
      ctx.font = font;
      const w = ctx.measureText(text).width;
      const bx = align === "center" ? x - w / 2 : x;
      const b = { x: bx - 3, y: y - 9, w: w + 6, h: 18 };
      if (b.x < 0 || b.x + b.w > W || b.y < 0 || b.y + b.h > H || !fits(b)) return false;
      boxes.push(b);
      ctx.textAlign = align;
      ctx.lineWidth = 4; ctx.strokeStyle = palette.surface; ctx.strokeText(text, x, y);
      ctx.fillStyle = color; ctx.fillText(text, x, y);
      return true;
    };

    // Selected and hovered names always win the space.
    for (const idx of [state.sel, state.hover]) {
      if (idx === null) continue;
      const p = P[idx];
      label(p.name, sx(p.x) + r + 7, sy(p.y), "600 13px system-ui, sans-serif", palette.ink, "left");
    }

    if (k < 1.7) {
      for (const a of DATA.areas) if (a.label) label(a.label, sx(a.x), sy(a.y), "650 13px system-ui, sans-serif", palette.ink);
    } else if (k < 3.2) {
      for (const a of DATA.topics) if (a.label && a.n > 1) label(a.label, sx(a.x), sy(a.y), "600 12px system-ui, sans-serif", palette.ink2);
    }
    if (k >= 2.4) {
      const visible = P.filter((p) => isActive(p) && sx(p.x) > 0 && sx(p.x) < W && sy(p.y) > 0 && sy(p.y) < H);
      if (k >= 3.2 || visible.length < 40) {
        for (const p of visible) label(p.name, sx(p.x) + r + 5, sy(p.y), "12px system-ui, sans-serif", palette.ink2, "left");
      }
    }
  }

  // ------------------------------------------------------------ hit testing & tooltip
  function hit(mx, my) {
    let best = null, bd = 14 * 14;
    for (const p of P) {
      const dx = sx(p.x) - mx, dy = sy(p.y) - my, d = dx * dx + dy * dy;
      if (d < bd && (isActive(p) || d < 36)) { bd = d; best = p; }
    }
    return best;
  }
  const tip = $("tip");
  function showTip(p, mx, my) {
    tip.innerHTML = `<b>${esc(p.name)}</b><span class="k">${esc(p.title)} · ${esc(p.program)}</span><div>${esc((p.keywords || p.interests || p.terms.join(", ")).slice(0, 160))}</div>`;
    tip.hidden = false;
    const tw = tip.offsetWidth, th = tip.offsetHeight;
    let x = mx + 14, y = my + 14;
    if (x + tw > W - 8) x = mx - tw - 14;
    if (y + th > H - 8) y = my - th - 14;
    tip.style.left = Math.max(4, x) + "px"; tip.style.top = Math.max(4, y) + "px";
  }
  function hideTip() { tip.hidden = true; }

  canvas.addEventListener("pointermove", (e) => {
    if (e.buttons) return;
    const r = canvas.getBoundingClientRect();
    const p = hit(e.clientX - r.left, e.clientY - r.top);
    const idx = p ? p.i : null;
    canvas.classList.toggle("pointing", !!p);
    if (idx !== state.hover) { state.hover = idx; draw(); }
    if (p) showTip(p, e.clientX - r.left, e.clientY - r.top); else hideTip();
  });
  canvas.addEventListener("pointerleave", () => { state.hover = null; hideTip(); draw(); });
  canvas.addEventListener("click", (e) => {
    const r = canvas.getBoundingClientRect();
    const p = hit(e.clientX - r.left, e.clientY - r.top);
    select(p ? p.i : null);
  });

  // ------------------------------------------------------------ panel
  const panel = $("panel");
  function chips(list) { return list.length ? `<ul class="chips">${list.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>` : ""; }
  function hl(text, words) {
    let out = esc(text);
    for (const w of words || []) {
      if (w.length < 2) continue;
      out = out.replace(new RegExp("(" + w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "gi"), "<mark>$1</mark>");
    }
    return out;
  }

  function renderOverview() {
    const n = P.length;
    const areas = DATA.areas.filter((a) => a.label).map((a) =>
      `<li><button type="button" data-area="${a.id}"><span class="who">${esc(a.label)}</span><span class="score">${a.n}</span></button></li>`).join("");
    panel.innerHTML = `
      <h2>${esc(META.name)}</h2>
      <p class="sub muted">${n} faculty · as of ${esc(META.as_of)}</p>
      <p>Each point is a faculty member. People who describe similar research sit close together. Click a point to see that person's research and the ten people closest to them.</p>
      <p class="muted">Shapes mark departments. Hollow points have little research text to go on, so their position is less certain.</p>
      <h3>Research areas (computed)</h3>
      <ul class="near">${areas}</ul>
      ${META.left_off.length ? `<p class="muted">Not shown, because their directory and profile pages have no research or teaching text: ${META.left_off.map(esc).join(", ")}.</p>` : ""}
      <h3>How this map is made</h3>
      <p class="bio">${esc(META.method)}</p>
      <p class="bio">Sources: ${META.sources.map((u) => `<a href="${esc(u)}">${esc(u.replace(/^https?:\/\//, ""))}</a>`).join(", ")}. Corrections go to the directory page; the map is rebuilt from it.</p>`;
    panel.querySelectorAll("[data-area]").forEach((b) => b.onclick = () => {
      const id = Number(b.dataset.area);
      setColorBy("area");
      state.focus = String(id);
      renderLegend(); draw();
      zoomTo(P.filter((p) => p.area === id), 3);
    });
  }

  function renderPerson(p) {
    const links = [`<a href="${esc(p.url)}" target="_blank" rel="noopener">Directory profile</a>`]
      .concat(p.links.map((l) => `<a href="${esc(l.href)}" target="_blank" rel="noopener">${esc(l.text)}</a>`))
      .concat(p.orcid ? [`<a href="https://orcid.org/${esc(p.orcid)}" target="_blank" rel="noopener">ORCID</a>`] : []);
    const near = p.near.map((n) => {
      const q = P[n.i];
      const why = n.t.length ? "shared: " + n.t.join(", ") : esc(q.keywords || q.interests).slice(0, 90);
      return `<li><button type="button" data-i="${q.i}"><span class="who">${esc(q.name)}</span><span class="score">${q.department === p.department ? "" : esc(q.department)}</span><span class="why">${esc(q.program)} · ${esc(why)}</span></button></li>`;
    }).join("");
    const words = result ? result.words : [];
    panel.innerHTML = `
      <div class="card">
        <button type="button" class="ghost back" id="back">← ${result ? "Back to results" : "Overview"}</button>
        <h2>${esc(p.name)}</h2>
        <p class="sub">${esc(p.title)} · ${esc(p.program)}${p.program !== p.department ? " (" + esc(p.department) + ")" : ""}</p>
        ${p.keywords ? `<h3>Research (directory)</h3><p>${hl(p.keywords, words)}</p>` : ""}
        ${p.interests && p.interests !== p.keywords ? `<h3>Research interests (profile)</h3><p>${hl(p.interests, words)}</p>` : ""}
        ${p.listed.length ? `<h3>Listed research areas</h3>${chips(p.listed)}` : ""}
        <h3>Distinctive terms</h3>${chips(p.terms)}
        <h3>Closest people</h3><ul class="near">${near}</ul>
        ${p.bio ? `<h3>Bio</h3><p class="bio">${hl(p.bio, words)}</p>` : ""}
        <h3>Links</h3><div class="links">${links.join("")}</div>
        ${p.sparse ? `<p class="muted" style="margin-top:12px">Little research text is available for this person, so the position is approximate.</p>` : ""}
      </div>`;
    $("back").onclick = () => select(null);
    panel.querySelectorAll("[data-i]").forEach((b) => b.onclick = () => select(Number(b.dataset.i), true));
    panel.scrollTop = 0;
  }

  function renderHits() {
    const shown = result.hits.filter((h) => passesFilters(h.p));
    panel.innerHTML = `<h2>${shown.length} match${shown.length === 1 ? "" : "es"}</h2>
      <p class="sub muted">for “${esc(state.q)}”${state.dept || state.rank ? " within the filters" : ""}</p>
      <ul class="hits">${shown.map(({ p }) => {
        const why = [p.keywords, p.interests].find((t) => result.words.some((w) => norm(t).includes(w))) || p.keywords || p.interests || "";
        return `<li><button type="button" data-i="${p.i}"><b>${hl(p.name, result.words)}</b> <span class="muted">${esc(p.program)}</span><span class="why">${hl(why.slice(0, 160), result.words)}</span></button></li>`;
      }).join("")}</ul>
      ${shown.length ? "" : `<p class="muted">No one matches. Try a broader word, or clear the filters.</p>`}`;
    panel.querySelectorAll("[data-i]").forEach((b) => b.onclick = () => select(Number(b.dataset.i), true));
  }

  function renderPanel() {
    if (state.sel !== null) renderPerson(P[state.sel]);
    else if (result) renderHits();
    else renderOverview();
  }

  function select(i, pan = false) {
    state.sel = i;
    try { history.replaceState(null, "", i === null ? location.pathname + location.search : "#p=" + encodeURIComponent(P[i].id)); } catch (_) { /* file:// in some browsers */ }
    renderPanel(); draw();
    if (i !== null && pan) {
      const p = P[i];
      zoomTo([p, ...p.near.slice(0, 5).map((n) => P[n.i])], 4);
    }
  }

  // ------------------------------------------------------------ legend
  const legend = $("legend");
  function swatch(color, shape, hollow = false) {
    const s = 14, c = s / 2;
    const fill = hollow ? "none" : color, stroke = color;
    let el;
    if (shape === "square") el = `<rect x="2.5" y="2.5" width="9" height="9"/>`;
    else if (shape === "triangle") el = `<polygon points="${c},1.5 12.5,11.5 1.5,11.5"/>`;
    else if (shape === "diamond") el = `<polygon points="${c},1 13,${c} ${c},13 1,${c}"/>`;
    else el = `<circle cx="${c}" cy="${c}" r="5"/>`;
    return `<svg width="${s}" height="${s}" aria-hidden="true"><g fill="${fill}" stroke="${stroke}" stroke-width="${hollow ? 2 : 0}">${el}</g></svg>`;
  }
  function renderLegend() {
    const g = GROUPS[state.colorBy];
    const shown = g.order.filter((k) => g.slot.get(k));
    const rest = g.order.filter((k) => !g.slot.get(k));
    const rows = shown.map((k) => {
      const shape = state.colorBy === "department" ? shapeOf({ department: k }) : "circle";
      return `<button type="button" data-k="${esc(k)}" aria-pressed="${state.focus === k}">${swatch(palette[g.slot.get(k)], shape)}<span>${esc(g.label(k))}</span><span class="n">${g.counts.get(k)}</span></button>`;
    });
    if (rest.length) rows.push(`<div class="note">${swatch(palette.other, "circle")} Other: ${rest.length} smaller groups</div>`);
    const shapes = state.colorBy === "department" ? "" :
      `<div class="note">${DEPTS.map((d) => swatch(palette.ink2, shapeOf({ department: d })) + " " + esc(d)).join("<br>")}</div>`;
    legend.innerHTML = rows.join("") + shapes + `<div class="note">${swatch(palette.ink2, "circle", true)} little research text</div>`;
    legend.querySelectorAll("[data-k]").forEach((b) => b.onclick = () => {
      state.focus = state.focus === b.dataset.k ? null : b.dataset.k;
      renderLegend(); draw();
    });
  }

  // ------------------------------------------------------------ controls
  function setColorBy(mode) {
    state.colorBy = mode; state.focus = null;
    $("colorby").value = mode;
    renderLegend(); draw();
  }
  $("colorby").value = state.colorBy;
  $("colorby").onchange = (e) => setColorBy(e.target.value);

  for (const d of DEPTS) $("dept").insertAdjacentHTML("beforeend", `<option>${esc(d)}</option>`);
  for (const r of ["Professor", "Associate Professor", "Assistant Professor", "Teaching track", "Other"]) {
    const n = P.filter((p) => p.rank === r).length;
    if (n) $("rank").insertAdjacentHTML("beforeend", `<option value="${r}">${r} (${n})</option>`);
  }
  $("dept").onchange = (e) => { state.dept = e.target.value; renderPanel(); draw(); };
  $("rank").onchange = (e) => { state.rank = e.target.value; renderPanel(); draw(); };

  let qTimer = null;
  $("q").addEventListener("input", (e) => {
    clearTimeout(qTimer);
    qTimer = setTimeout(() => {
      state.q = e.target.value.trim();
      const r = search(state.q);
      result = r ? { ...r, set: new Set(r.hits.map((h) => h.p.i)) } : null;
      state.sel = null;
      renderPanel(); draw();
      if (result && result.hits.length) zoomTo(result.hits.map((h) => h.p).filter(passesFilters), 3);
    }, 160);
  });
  $("q").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && result && result.hits.length) select(result.hits[0].p.i, true);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && document.activeElement !== $("q")) select(null);
  });

  function applyTheme(t) {
    if (t) document.documentElement.dataset.theme = t; else delete document.documentElement.dataset.theme;
    readPalette(); renderLegend(); themeLabel(); draw();
  }
  function themeLabel() {
    const dark = document.documentElement.dataset.theme ? document.documentElement.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    $("theme").textContent = dark ? "Light" : "Dark";
    $("theme").setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
  }
  $("theme").onclick = () => {
    const dark = matchMedia("(prefers-color-scheme: dark)").matches;
    const cur = document.documentElement.dataset.theme || (dark ? "dark" : "light");
    const next = cur === "dark" ? "light" : "dark";
    try { localStorage.setItem("rm-theme", next); } catch (_) { /* storage blocked */ }
    applyTheme(next);
  };
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { readPalette(); renderLegend(); draw(); });

  // ------------------------------------------------------------ start
  $("title").textContent = META.name + " research map";
  $("subtitle").textContent = `${P.length} faculty · built ${META.as_of} from public directory pages`;
  $("foot").innerHTML = `Data: public ${esc(META.university)} directory and profile pages, as of ${esc(META.as_of)}. Not a ranking or evaluation of anyone. Model: ${esc(META.model)}.`;

  let saved = null;
  try { saved = localStorage.getItem("rm-theme"); } catch (_) { /* storage blocked */ }
  if (saved === "dark" || saved === "light") document.documentElement.dataset.theme = saved;
  readPalette();
  themeLabel();
  renderLegend();
  if (window.innerWidth < 820) $("legendbox").open = false;
  $("legendbox").addEventListener("toggle", resize);
  new ResizeObserver(resize).observe(wrap);
  resize();
  const m = location.hash.match(/p=([^&]+)/);
  const start = m ? P.find((p) => p.id === decodeURIComponent(m[1])) : null;
  if (start) select(start.i, true); else renderPanel();
  window.__rm = { state, P, select, search: (q) => { $("q").value = q; $("q").dispatchEvent(new Event("input")); } };
})();
