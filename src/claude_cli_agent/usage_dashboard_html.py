"""Self-contained usage dashboard HTML; CSS aligned with ecommerce-sales-dashboard when present."""

from __future__ import annotations

import json
from pathlib import Path


def _ecommerce_style_root() -> Path:
    """Sibling folder `ecommerce-sales-dashboard` next to `claude_cli_agent` repo."""
    repo = Path(__file__).resolve().parents[2]
    return repo.parent / "ecommerce-sales-dashboard"


def load_dashboard_css() -> str:
    """Merge ecommerce dashboard CSS (main + components) when files exist; else minimal fallback."""
    ec = _ecommerce_style_root()
    parts: list[str] = []
    for rel in ("assets/css/main.css", "assets/css/components.css", "assets/css/responsive.css"):
        p = ec / rel
        if p.is_file():
            parts.append(f"/* ---- {rel} ---- */\n{p.read_text(encoding='utf-8')}")
    cagent_extra = """
/* ---- cagent observability layout (maps to ecommerce patterns) ---- */
.cagent-wrap { min-height: 100vh; display: flex; flex-direction: column; }
.cagent-main { flex: 1; }
.obs-filter-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: var(--space-lg); align-items: end; }
.obs-kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: var(--space-lg); }
.obs-charts-grid { display: grid; grid-template-columns: 2fr 1.2fr 1fr; gap: var(--space-lg); margin-bottom: var(--space-xl); }
@media (max-width: 1100px) { .obs-charts-grid { grid-template-columns: 1fr; } }
.obs-chart-body { min-height: 240px; }
.obs-chart-body canvas { width: 100%; height: 240px; display: block; }
.mini-bars { display: grid; gap: var(--space-sm); margin-top: var(--space-sm); }
.mini-row { display: grid; grid-template-columns: 100px 1fr auto; gap: var(--space-sm); align-items: center; font-size: 12px; color: var(--text-secondary); }
.track { height: 9px; border-radius: var(--radius-full); background: rgba(17,24,39,0.06); overflow: hidden; }
.fill { height: 100%; border-radius: var(--radius-full); background: linear-gradient(90deg, var(--brand-secondary), var(--brand-primary)); }
.table-scroll { max-height: 480px; overflow: auto; }
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table thead th { position: sticky; top: 0; z-index: 2; text-align: left; padding: 12px; background: var(--glass-strong); color: var(--text-secondary); border-bottom: 1px solid var(--border-light); font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; }
.data-table tbody td { padding: 10px 12px; border-bottom: 1px solid var(--border-light); color: var(--text-primary); vertical-align: top; }
.status-ok { color: var(--success); font-weight: 600; }
.status-err { color: var(--error); font-weight: 600; }
.status-warn { color: var(--warning); font-weight: 600; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
.error-cell { max-width: 360px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--error); }
"""
    if parts:
        return "\n".join(parts) + cagent_extra
    return _FALLBACK_CSS + cagent_extra


_FALLBACK_CSS = """
:root {
  --bg-primary: linear-gradient(135deg, #f6f8fc 0%, #eef2f9 100%);
  --glass: rgba(255, 255, 255, 0.72);
  --glass-strong: rgba(255, 255, 255, 0.88);
  --border-light: rgba(17, 24, 39, 0.08);
  --text-primary: #101828;
  --text-secondary: #475467;
  --text-tertiary: #667085;
  --text-inverse: #ffffff;
  --brand-primary: #5b6cff;
  --brand-secondary: #8098ff;
  --success: #067647;
  --error: #b42318;
  --warning: #b54708;
  --space-lg: 24px;
  --space-xl: 32px;
  --radius-lg: 16px;
  --shadow-md: 0 4px 12px rgba(16, 24, 40, 0.08);
}
* { box-sizing: border-box; }
body { margin: 0; font-family: Inter, system-ui, sans-serif; font-size: 14px; color: var(--text-primary); background: var(--bg-primary); min-height: 100vh; }
.glass-card { background: var(--glass); backdrop-filter: blur(14px); border: 1px solid var(--border-light); border-radius: var(--radius-lg); box-shadow: var(--shadow-md); }
.dashboard-header { background: var(--glass-strong); border-bottom: 1px solid var(--border-light); padding: var(--space-lg) 0; position: sticky; top: 0; z-index: 50; }
.header-content { max-width: 1920px; margin: 0 auto; padding: 0 var(--space-lg); display: flex; justify-content: space-between; align-items: center; gap: var(--space-lg); }
.dashboard-title { font-size: 24px; font-weight: 700; }
.dashboard-subtitle { font-size: 13px; color: var(--text-secondary); }
.container { max-width: 1920px; margin: 0 auto; padding: 0 var(--space-lg); }
.dashboard-main { padding: var(--space-xl) 0; }
.dashboard-footer { background: var(--glass-strong); border-top: 1px solid var(--border-light); padding: var(--space-lg) 0; margin-top: auto; }
.footer-content { max-width: 1920px; margin: 0 auto; padding: 0 var(--space-lg); display: flex; justify-content: space-between; color: var(--text-tertiary); font-size: 12px; }
"""


def build_usage_dashboard_html(events: list[dict], total_cost: float) -> str:
    css = load_dashboard_css()
    events_json = json.dumps(events, ensure_ascii=True)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>cagent · Usage observability</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet" />
  <style>
{css}
  </style>
</head>
<body class="cagent-wrap">
  <header class="dashboard-header">
    <div class="header-content">
      <div class="header-left">
        <h1 class="dashboard-title">cagent observability</h1>
        <p class="dashboard-subtitle">Tokens, sessions, and cost — independent + claude_code</p>
      </div>
      <div class="header-right">
        <div class="last-updated">Last export: <span id="lastUpdatedPill">--</span></div>
        <button type="button" class="btn btn-secondary" id="resetBtn"><span class="btn-icon">↺</span> Reset filters</button>
      </div>
    </div>
  </header>

  <main class="dashboard-main cagent-main">
    <div class="container">
      <section class="filter-section glass-card">
        <div class="filter-header">
          <h2 class="section-title">Filters</h2>
        </div>
        <div class="obs-filter-grid" id="filter-container">
          <div class="filter-group">
            <label class="filter-label" for="backendFilter">Backend</label>
            <select class="filter-select" id="backendFilter">
              <option value="all">all</option>
              <option value="independent">independent</option>
              <option value="claude_code">claude_code</option>
            </select>
          </div>
          <div class="filter-group">
            <label class="filter-label" for="statusFilter">Status</label>
            <select class="filter-select" id="statusFilter">
              <option value="all">all</option>
              <option value="ok">ok</option>
              <option value="error">error</option>
              <option value="approx">approx tokens</option>
            </select>
          </div>
          <div class="filter-group">
            <label class="filter-label" for="sessionFilter">Session</label>
            <select class="filter-select" id="sessionFilter"><option value="all">all</option></select>
          </div>
          <div class="filter-group">
            <label class="filter-label" for="modelFilter">Model</label>
            <select class="filter-select" id="modelFilter"><option value="all">all</option></select>
          </div>
          <div class="filter-group">
            <label class="filter-label" for="searchInput">Search</label>
            <input type="text" class="filter-input" id="searchInput" placeholder="session, model, backend, error…" />
          </div>
        </div>
      </section>

      <section class="kpi-section">
        <div class="obs-kpi-grid" id="kpi-container">
          <article class="kpi-card glass-card">
            <div class="kpi-header"><span class="kpi-title">Total requests</span></div>
            <div class="kpi-value" id="kpiRequests">0</div>
            <p class="kpi-footer"><span class="kpi-change" id="kpiReqRate">--</span></p>
          </article>
          <article class="kpi-card glass-card">
            <div class="kpi-header"><span class="kpi-title">Total cost (USD)</span></div>
            <div class="kpi-value" id="kpiCost">0.000000</div>
            <p class="kpi-footer"><span class="kpi-change" id="kpiCostPerReq">--</span></p>
          </article>
          <article class="kpi-card glass-card">
            <div class="kpi-header"><span class="kpi-title">Input tokens</span></div>
            <div class="kpi-value" id="kpiInTok">0</div>
            <p class="kpi-footer"><span class="kpi-change" id="kpiInPct">--</span></p>
          </article>
          <article class="kpi-card glass-card">
            <div class="kpi-header"><span class="kpi-title">Output tokens</span></div>
            <div class="kpi-value" id="kpiOutTok">0</div>
            <p class="kpi-footer"><span class="kpi-change" id="kpiOutPct">--</span></p>
          </article>
          <article class="kpi-card glass-card">
            <div class="kpi-header"><span class="kpi-title">Success rate</span></div>
            <div class="kpi-value" id="kpiSuccess">0%</div>
            <p class="kpi-footer"><span class="kpi-change" id="kpiErrorCount">--</span></p>
          </article>
          <article class="kpi-card glass-card">
            <div class="kpi-header"><span class="kpi-title">Active sessions</span></div>
            <div class="kpi-value" id="kpiSessions">0</div>
            <p class="kpi-footer"><span class="kpi-change" id="kpiModels">--</span></p>
          </article>
        </div>
      </section>

      <section class="charts-section">
        <div class="obs-charts-grid">
          <div class="chart-card glass-card chart-large">
            <div class="chart-header"><h3 class="chart-title">Cost & tokens over time</h3></div>
            <div class="chart-body obs-chart-body"><canvas id="trendChart" width="900" height="240"></canvas></div>
          </div>
          <div class="chart-card glass-card">
            <div class="chart-header"><h3 class="chart-title">Backend share</h3></div>
            <div class="chart-body obs-chart-body"><canvas id="shareChart" width="420" height="240"></canvas></div>
          </div>
          <div class="chart-card glass-card">
            <div class="chart-header"><h3 class="chart-title">Top cost sessions</h3></div>
            <div class="chart-body"><div id="sessionBars" class="mini-bars"></div></div>
          </div>
        </div>
      </section>

      <section class="tables-section">
        <div class="table-card glass-card">
          <div class="table-header" style="padding:16px 20px;border-bottom:1px solid var(--border-light);">
            <h3 class="table-title">Event log</h3>
          </div>
          <div class="table-scroll">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Timestamp</th><th>Backend</th><th>Session</th><th>Model</th>
                  <th>In</th><th>Out</th><th>Cost</th><th>Status</th><th>Approx</th><th>Error</th>
                </tr>
              </thead>
              <tbody id="rows"></tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  </main>

  <footer class="dashboard-footer">
    <div class="footer-content">
      <p class="footer-text" id="footerMeta">—</p>
    </div>
  </footer>

  <script>
    const events = {events_json};
    const totalCost = {total_cost:.6f};
    const rowsEl = document.getElementById("rows");
    const backendEl = document.getElementById("backendFilter");
    const statusEl = document.getElementById("statusFilter");
    const sessionEl = document.getElementById("sessionFilter");
    const modelEl = document.getElementById("modelFilter");
    const searchEl = document.getElementById("searchInput");
    const resetBtn = document.getElementById("resetBtn");
    const trendCanvas = document.getElementById("trendChart");
    const shareCanvas = document.getElementById("shareChart");
    const sessionBarsEl = document.getElementById("sessionBars");
    const fmtMoney = (v) => Number(v || 0).toFixed(6);
    const fmtNum = (v) => Number(v || 0).toLocaleString();
    const tsLabel = (ts) => String(ts || "").replace("T", " ").slice(0, 19);
    const safe = (v) => String(v == null ? "" : v);
    function uniqueValues(key) {{
      const set = new Set();
      events.forEach((e) => {{ const v = safe(e[key]).trim(); if (v) set.add(v); }});
      return [...set].sort();
    }}
    function fillSelect(selectEl, values) {{
      const prev = selectEl.value;
      selectEl.innerHTML = '<option value="all">all</option>' + values.map((v) => `<option value="${{v}}">${{v}}</option>`).join("");
      if (values.includes(prev)) selectEl.value = prev;
    }}
    fillSelect(sessionEl, uniqueValues("session_id"));
    fillSelect(modelEl, uniqueValues("model"));
    function matchesFilter(e) {{
      if (backendEl.value !== "all" && e.backend_mode !== backendEl.value) return false;
      if (sessionEl.value !== "all" && safe(e.session_id) !== sessionEl.value) return false;
      if (modelEl.value !== "all" && safe(e.model) !== modelEl.value) return false;
      if (statusEl.value === "ok" && !e.success) return false;
      if (statusEl.value === "error" && e.success) return false;
      if (statusEl.value === "approx" && !e.approx_tokens) return false;
      const search = searchEl.value.trim().toLowerCase();
      if (!search) return true;
      const text = [e.backend_mode, e.session_id, e.model, e.error, e.timestamp].map(safe).join(" ").toLowerCase();
      return text.includes(search);
    }}
    function getFiltered() {{ return events.filter(matchesFilter); }}
    function updateKpis(filtered) {{
      const count = filtered.length;
      const inTok = filtered.reduce((a, e) => a + Number(e.input_tokens || 0), 0);
      const outTok = filtered.reduce((a, e) => a + Number(e.output_tokens || 0), 0);
      const ok = filtered.filter((e) => e.success).length;
      const err = count - ok;
      const cost = filtered.reduce((a, e) => a + Number(e.cost_usd || 0), 0);
      const sessions = new Set(filtered.map((e) => safe(e.session_id)).filter(Boolean)).size;
      const models = new Set(filtered.map((e) => safe(e.model)).filter(Boolean)).size;
      const tokenTotal = inTok + outTok;
      document.getElementById("kpiRequests").textContent = fmtNum(count);
      document.getElementById("kpiCost").textContent = fmtMoney(cost);
      document.getElementById("kpiInTok").textContent = fmtNum(inTok);
      document.getElementById("kpiOutTok").textContent = fmtNum(outTok);
      document.getElementById("kpiSuccess").textContent = count ? ((ok / count) * 100).toFixed(1) + "%" : "0%";
      document.getElementById("kpiSessions").textContent = fmtNum(sessions);
      document.getElementById("kpiReqRate").textContent = count ? "Filtered view" : "No rows";
      document.getElementById("kpiCostPerReq").textContent = count ? ("avg $" + (cost / count).toFixed(6) + " / req") : "—";
      document.getElementById("kpiInPct").textContent = tokenTotal ? ((inTok / tokenTotal) * 100).toFixed(1) + "% of tokens" : "—";
      document.getElementById("kpiOutPct").textContent = tokenTotal ? ((outTok / tokenTotal) * 100).toFixed(1) + "% of tokens" : "—";
      document.getElementById("kpiErrorCount").textContent = fmtNum(err) + " errors";
      document.getElementById("kpiModels").textContent = fmtNum(models) + " models";
    }}
    function drawTrendChart(filtered) {{
      const ctx = trendCanvas.getContext("2d");
      const w = trendCanvas.width, h = trendCanvas.height;
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, w, h);
      if (!filtered.length) {{ ctx.fillStyle = "#667085"; ctx.font = "13px Inter,sans-serif"; ctx.fillText("No data for filters", 16, 28); return; }}
      const sorted = [...filtered].sort((a, b) => safe(a.timestamp).localeCompare(safe(b.timestamp)));
      const costs = sorted.map((e) => Number(e.cost_usd || 0));
      const toks = sorted.map((e) => Number(e.input_tokens || 0) + Number(e.output_tokens || 0));
      const maxCost = Math.max(...costs, 1e-9);
      const maxTok = Math.max(...toks, 1);
      const pad = 32, cw = w - pad * 2, ch = h - pad * 2;
      ctx.strokeStyle = "#e4e7ec"; ctx.lineWidth = 1;
      for (let i = 0; i <= 4; i += 1) {{ const y = pad + (ch * i) / 4; ctx.beginPath(); ctx.moveTo(pad, y); ctx.lineTo(w - pad, y); ctx.stroke(); }}
      function line(values, max, color) {{
        ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.beginPath();
        values.forEach((val, idx) => {{ const x = pad + (idx / Math.max(1, values.length - 1)) * cw; const y = h - pad - (val / max) * ch; if (idx === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); }});
        ctx.stroke();
      }}
      line(costs, maxCost, "#5b6cff");
      line(toks, maxTok, "#12b76a");
    }}
    function drawShareChart(filtered) {{
      const ctx = shareCanvas.getContext("2d");
      const w = shareCanvas.width, h = shareCanvas.height;
      ctx.clearRect(0, 0, w, h); ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, w, h);
      const ind = filtered.filter((e) => e.backend_mode === "independent").length;
      const cc = filtered.filter((e) => e.backend_mode === "claude_code").length;
      const total = Math.max(1, ind + cc);
      const values = [{{ name: "claude_code", count: cc, color: "#5b6cff" }}, {{ name: "independent", count: ind, color: "#12b76a" }}];
      const cx = 110, cy = h / 2, r = 74, inner = 45;
      let start = -Math.PI / 2;
      values.forEach((v) => {{ const sweep = (v.count / total) * Math.PI * 2; ctx.beginPath(); ctx.moveTo(cx, cy); ctx.arc(cx, cy, r, start, start + sweep); ctx.closePath(); ctx.fillStyle = v.color; ctx.fill(); start += sweep; }});
      ctx.beginPath(); ctx.arc(cx, cy, inner, 0, Math.PI * 2); ctx.fillStyle = "#ffffff"; ctx.fill();
      ctx.fillStyle = "#1d2939"; ctx.font = "bold 18px Inter,sans-serif"; ctx.fillText(String(ind + cc), cx - 12, cy + 5);
      ctx.font = "12px Inter,sans-serif"; ctx.fillStyle = "#667085"; ctx.fillText("events", cx - 17, cy + 22);
      let y = 72;
      values.forEach((v) => {{ ctx.fillStyle = v.color; ctx.fillRect(215, y - 9, 11, 11); ctx.fillStyle = "#344054"; ctx.font = "12px Inter,sans-serif"; ctx.fillText(v.name + " (" + v.count + ")", 232, y); y += 24; }});
    }}
    function renderSessionBars(filtered) {{
      const bySession = new Map();
      filtered.forEach((e) => {{ const key = safe(e.session_id) || "unknown"; bySession.set(key, (bySession.get(key) || 0) + Number(e.cost_usd || 0)); }});
      const top = [...bySession.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);
      const max = top.length ? top[0][1] : 1;
      sessionBarsEl.innerHTML = top.map(([name, cost]) => `<div class="mini-row"><div class="mono">${{name.slice(0, 14)}}</div><div class="track"><div class="fill" style="width:${{(cost / max) * 100}}%"></div></div><div>${{fmtMoney(cost)}}</div></div>`).join("") || '<p class="dashboard-subtitle">No session cost for this filter.</p>';
    }}
    function renderRows(filtered) {{
      const rows = [...filtered].sort((a, b) => safe(b.timestamp).localeCompare(safe(a.timestamp)));
      rowsEl.innerHTML = rows.map((e) => `
        <tr>
          <td class="mono">${{tsLabel(e.timestamp)}}</td><td>${{safe(e.backend_mode)}}</td><td class="mono">${{safe(e.session_id) || "-"}}</td>
          <td>${{safe(e.model)}}</td><td>${{fmtNum(e.input_tokens)}}</td><td>${{fmtNum(e.output_tokens)}}</td>
          <td class="mono">${{fmtMoney(e.cost_usd)}}</td><td class="${{e.success ? "status-ok" : "status-err"}}">${{e.success ? "ok" : "error"}}</td>
          <td>${{e.approx_tokens ? '<span class="status-warn">yes</span>' : "no"}}</td><td class="error-cell" title="${{safe(e.error)}}">${{safe(e.error) || "-"}}</td>
        </tr>`).join("");
    }}
    function renderAll() {{
      const filtered = getFiltered();
      updateKpis(filtered);
      drawTrendChart(filtered);
      drawShareChart(filtered);
      renderSessionBars(filtered);
      renderRows(filtered);
      const latest = filtered.length ? [...filtered].sort((a, b) => safe(b.timestamp).localeCompare(safe(a.timestamp)))[0].timestamp : null;
      document.getElementById("lastUpdatedPill").textContent = latest ? tsLabel(latest) + " UTC" : "--";
      document.getElementById("footerMeta").textContent = "Stored events: " + fmtNum(events.length) + " · Global cost $" + fmtMoney(totalCost) + " · Shown: " + fmtNum(filtered.length);
    }}
    [backendEl, statusEl, sessionEl, modelEl].forEach((el) => el.addEventListener("change", renderAll));
    searchEl.addEventListener("input", renderAll);
    resetBtn.addEventListener("click", () => {{ backendEl.value = "all"; statusEl.value = "all"; sessionEl.value = "all"; modelEl.value = "all"; searchEl.value = ""; renderAll(); }});
    renderAll();
  </script>
</body>
</html>
"""
