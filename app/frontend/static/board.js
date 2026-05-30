// OddsFlow Picks Board (v4) — clean, filterable, toggleable view over /picks.
'use strict';

const GROUPS = {
  zone:   ['strong', 'standard', 'low', 'one_sided'],
  bts:    ['over', 'under'],
  tier:   ['1', '2', '3'],
  market: ['goals_nl', 'corners_nl', 'threeway'],
  spread: ['strong', 'slight'],
  h2h:    ['over', 'under', 'none'],
  df:     ['DF0', 'DF1', 'DF2'],
};
const MKT_LABEL = { goals_nl: 'Goals', corners_nl: 'Corners', threeway: '3-Way' };
const state = {
  days: 3, search: '', minhit: 0,
  sel: {}, group: 'fixture', sort: 'composite', signals: true, compact: false,
};
let RAW = [];      // grouped picks fixtures (picks + log views)
let RESULTS = [];  // settled fixtures (results view)
let PERF = null;   // emit_market_breakdown (performance view)
state.view = 'picks';

const $ = (id) => document.getElementById(id);
const compClass = (h) => h == null ? '' : h >= 74 ? 'hi' : h >= 66 ? 'mid' : 'lo';
const kdt = (s) => (s || '').replace('T', ' ').slice(0, 16);
const fmtTime = (s) => {
  if (!s) return '—';
  const d = new Date(s.replace(' ', 'T') + 'Z');           // stored UTC → viewer-local
  if (isNaN(d)) return s;
  return d.toLocaleString(undefined, { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
};

// ---- build chip groups (all on by default = no filtering) ----
function buildChips() {
  for (const [key, vals] of Object.entries(GROUPS)) {
    const box = $('g-' + key);
    state.sel[key] = new Set(vals);
    vals.forEach(v => {
      const b = document.createElement('span');
      b.className = 'chip on'; b.textContent = key === 'market' ? MKT_LABEL[v] : v;
      b.onclick = () => {
        if (state.sel[key].has(v)) { state.sel[key].delete(v); b.classList.remove('on'); }
        else { state.sel[key].add(v); b.classList.add('on'); }
        renderCurrent();
      };
      box.appendChild(b);
    });
  }
}

// ---- fetch + group by fixture ----
async function load() {
  $('bd-status').textContent = 'loading…';
  try {
    const r = await fetch(`/picks?days=${state.days}`);
    const body = await r.json();
    const byFix = new Map();
    for (const p of (body.picks || [])) {
      if (!byFix.has(p.fixture_id)) {
        byFix.set(p.fixture_id, {
          id: p.fixture_id, home: p.home_team, away: p.away_team, league: p.league,
          country: p.country, kickoff: p.kickoff_utc, tier: p.tier,
          zone: p.draw_zone, bts: p.bts, spread: p.spread, df: p.df, h2h: p.h2h_corner,
          odds_updated_at: p.odds_updated_at, markets: {},
        });
      }
      byFix.get(p.fixture_id).markets[p.market] = {
        pick: p.pick, line: p.line, odd: p.pick_odd, hit: p.cell_historical_hit, n: p.cell_historical_n,
      };
    }
    RAW = [...byFix.values()];
    $('bd-status').textContent = `${RAW.length} fixtures · ${body.count || 0} picks`;
  } catch (e) {
    $('bd-status').textContent = 'error'; $('bd-results').innerHTML = `<div class="bd-empty">Error: ${e}</div>`;
    return;
  }
  renderCurrent();
}

// ---- filter + render ----
function passes(fx) {
  const s = state.sel;
  if (fx.zone && !s.zone.has(fx.zone)) return false;
  if (fx.bts && !s.bts.has(fx.bts)) return false;
  if (!s.tier.has(String(fx.tier))) { if (fx.tier != null) return false; }
  if (fx.spread && !s.spread.has(fx.spread)) return false;
  if (fx.df && !s.df.has(fx.df)) return false;
  if (!s.h2h.has(fx.h2h || 'none')) return false;
  if (state.search) {
    const q = state.search.toLowerCase();
    if (!(`${fx.home} ${fx.away} ${fx.league}`.toLowerCase().includes(q))) return false;
  }
  return true;
}
function shownMarkets(fx) {
  return Object.keys(fx.markets).filter(m => state.sel.market.has(m));
}
function composite(fx, mkts) {
  const hits = mkts.map(m => fx.markets[m].hit).filter(h => h != null);
  return hits.length ? Math.round(hits.reduce((a, b) => a + b, 0) / hits.length * 10) / 10 : null;
}

function render() {
  const res = $('bd-results');
  res.classList.toggle('compact', state.compact);
  let fixtures = RAW.filter(passes).map(fx => {
    const mkts = shownMarkets(fx);
    return { fx, mkts, comp: composite(fx, mkts) };
  }).filter(o => o.mkts.length && (o.comp == null || o.comp >= state.minhit));

  fixtures.sort((a, b) =>
    state.sort === 'kickoff' ? (a.fx.kickoff || '').localeCompare(b.fx.kickoff || '')
                             : (b.comp || 0) - (a.comp || 0));

  // summary
  const nf = fixtures.length, np = fixtures.reduce((a, o) => a + o.mkts.length, 0);
  const avg = fixtures.length ? Math.round(fixtures.reduce((a, o) => a + (o.comp || 0), 0) / fixtures.length * 10) / 10 : 0;
  $('bd-summary').innerHTML = `<span><b>${nf}</b> fixtures</span><span><b>${np}</b> picks shown</span><span>avg hit <b>${avg}%</b></span><span>window <b>${state.days}d</b></span>`;

  if (!fixtures.length) { res.innerHTML = '<div class="bd-empty">No picks match these filters.</div>'; return; }

  if (state.group === 'market') return renderByMarket(res, fixtures);

  let html = '';
  if (state.group === 'cell') {
    const cells = {};
    fixtures.forEach(o => { const k = `${o.fx.zone} : ${o.fx.bts}`; (cells[k] ||= []).push(o); });
    for (const k of Object.keys(cells).sort()) {
      html += `<div class="bd-group-h">${k} · ${cells[k].length}</div>` + cells[k].map(card).join('');
    }
  } else {
    html = fixtures.map(card).join('');
  }
  res.innerHTML = html;
}

function card(o) {
  const fx = o.fx;
  // green-light the highest-confidence market in this cell
  let best = null, bestHit = -1;
  o.mkts.forEach(m => { const h = fx.markets[m] && fx.markets[m].hit; if (h != null && h > bestHit) { bestHit = h; best = m; } });
  const pk = (m) => {
    const x = fx.markets[m]; if (!x) return '';
    const label = m === 'goals_nl' ? `Over ${x.line} Goals`
                : m === 'corners_nl' ? `Over ${x.line} Corners`
                : x.pick;
    const odd = x.odd != null ? `<span class="pk-odd">@${x.odd}</span>` : '';
    const isBest = m === best;
    const badge = isBest ? '<span class="gl-badge">★ best</span>' : '';
    return `<div class="pk${isBest ? ' gl' : ''}"><span class="pk-name">${badge}${MKT_LABEL[m]}: ${label}${odd}</span>
            <span class="pk-hit"><b>${x.hit ?? '—'}%</b></span></div>`;
  };
  const sig = state.signals ? `<div class="sig">
      <span class="s ${fx.spread}">spread ${fx.spread || '—'}</span>
      <span class="s">${fx.df || '—'}</span>
      <span class="s ${fx.h2h}">h2h ${fx.h2h || 'none'}</span>
    </div>` : '';
  return `<div class="card">
    <div class="card-h">
      <div class="card-l">
        <div class="teams">${fx.home || ''} <span class="vs">v</span> ${fx.away || ''}</div>
        <div class="kick">🕑 ${fmtTime(fx.kickoff)}</div>
        <div class="lg">${fx.league || ''} · ${fx.country || ''} · T${fx.tier ?? '?'}</div>
      </div>
      <div class="card-r">
        <div class="comp ${compClass(o.comp)}">${o.comp ?? '—'}<span class="comp-pct">%</span></div>
        <span class="pill-bts ${fx.bts}">${fx.zone} ${fx.bts}</span>
      </div>
    </div>
    ${o.mkts.map(pk).join('')}
    ${sig}
    <button class="recent-toggle" data-fid="${fx.id}">recent in this cell ▾</button>
    <div class="recent" data-fid="${fx.id}"></div>
  </div>`;
}

function renderByMarket(res, fixtures) {
  let html = '';
  for (const m of GROUPS.market) {
    if (!state.sel.market.has(m)) continue;
    const rows = fixtures.filter(o => o.fx.markets[m])
      .sort((a, b) => (b.fx.markets[m].hit || 0) - (a.fx.markets[m].hit || 0));
    if (!rows.length) continue;
    html += `<div class="bd-group-h">${MKT_LABEL[m]} · ${rows.length}</div>`;
    html += rows.map(o => {
      const x = o.fx.markets[m];
      const label = m === 'threeway' ? x.pick : `Over ${x.line} ${m === 'goals_nl' ? 'Goals' : 'Corners'}`;
      return `<div class="card"><div class="card-h">
        <div><div class="teams">${o.fx.home} <span class="meta">v</span> ${o.fx.away}</div>
          <div class="meta">${label} · ${o.fx.zone} ${o.fx.bts} · ${kdt(o.fx.kickoff)}</div></div>
        <div class="comp ${compClass(x.hit)}">${x.hit ?? '—'}<span style="font-size:11px;color:var(--muted)">%</span></div>
      </div></div>`;
    }).join('');
  }
  res.innerHTML = html || '<div class="bd-empty">No picks match these filters.</div>';
}

// ===== view dispatch =====
function renderCurrent() {
  const v = state.view;
  if (v === 'results') return renderResults();
  if (v === 'performance') return renderPerformance();
  if (v === 'log') return renderLog();
  return render();   // picks
}
async function loadView() {
  const v = state.view;
  $('bd-filters').classList.toggle('hidden', v === 'performance' || v === 'log');
  if (v === 'results') return loadResults();
  if (v === 'performance') return loadPerformance();
  if (!RAW.length) return load();   // picks + log share RAW; load() ends in renderCurrent()
  return renderCurrent();
}
function refreshCurrent() {
  const v = state.view;
  if (v === 'results') return loadResults();
  if (v === 'performance') return loadPerformance();
  return load();
}

// ===== Results view (authoritative: /api/results — true settled outcomes) =====
async function loadResults() {
  $('bd-status').textContent = 'loading…';
  try {
    const d = await (await fetch(`/api/results?days=${Math.max(state.days, 7)}`)).json();
    RESULTS = (d.fixtures || []).map(f => ({
      ...f, bts: (f.bts_pocket || '').includes('over') ? 'over'
              : (f.bts_pocket || '').includes('under') ? 'under' : null,
    }));
    $('bd-status').textContent = `${RESULTS.length} settled · ${d.window_days}d`;
  } catch (e) { $('bd-status').textContent = 'error'; }
  renderResults();
}
function renderResults() {
  const res = $('bd-results'); res.classList.toggle('compact', state.compact);
  const s = state.sel;
  let fx = RESULTS.filter(f => {
    if (f.draw_zone && !s.zone.has(f.draw_zone)) return false;
    if (f.bts && !s.bts.has(f.bts)) return false;
    if (f.tier != null && !s.tier.has(String(f.tier))) return false;
    if (state.search && !`${f.home_team} ${f.away_team} ${f.league}`.toLowerCase().includes(state.search.toLowerCase())) return false;
    return (f.picks || []).length;
  });
  fx.sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  const np = fx.reduce((a, f) => a + f.picks.length, 0);
  const wins = fx.reduce((a, f) => a + f.picks.filter(p => p.outcome === 'WIN').length, 0);
  const settled = fx.reduce((a, f) => a + f.picks.filter(p => ['WIN', 'LOSS', 'VOID'].includes(p.outcome)).length, 0);
  const hr = settled ? Math.round((wins + fx.reduce((a, f) => a + f.picks.filter(p => p.outcome === 'VOID').length, 0)) / settled * 1000) / 10 : 0;
  $('bd-summary').innerHTML = `<span><b>${fx.length}</b> settled fixtures</span><span><b>${np}</b> picks</span><span>non-loss <b>${hr}%</b></span><span class="lg">true settled outcomes</span>`;
  if (!fx.length) { res.innerHTML = '<div class="bd-empty">No settled results match these filters.</div>'; return; }
  res.innerHTML = fx.map(f => {
    const rows = (f.picks || []).map(p => {
      const oc = p.outcome === 'WIN' ? 'win' : p.outcome === 'LOSS' ? 'loss' : p.outcome === 'VOID' ? 'void' : '';
      const m = p.outcome === 'WIN' ? '✓' : p.outcome === 'LOSS' ? '✗' : p.outcome === 'VOID' ? '∅' : '·';
      return `<div class="pk"><span class="pk-name"><span class="oc ${oc}">${m}</span> ${MKT_LABEL[p.market] || p.market}: ${p.pick}</span>
              <span class="pk-hit">${p.pick_odd ? '@' + p.pick_odd : ''}</span></div>`;
    }).join('');
    return `<div class="card"><div class="card-h">
      <div class="card-l"><div class="teams">${f.home_team} <span class="vs">v</span> ${f.away_team}</div>
        <div class="kick">🕑 ${fmtTime(f.date)}</div><div class="lg">${f.league || ''} · ${f.country || ''} · T${f.tier ?? '?'}</div></div>
      <div class="card-r"><div class="score">${f.home_score}-${f.away_score}</div>
        <span class="pill-bts ${f.bts || ''}">${f.draw_zone || ''} ${f.bts || ''}</span></div>
      </div>${rows}</div>`;
  }).join('');
}

// ===== Performance view (authoritative: /reports/emit_market_breakdown) =====
async function loadPerformance() {
  $('bd-status').textContent = 'loading…';
  try { PERF = await (await fetch('/reports/emit_market_breakdown?days=90')).json(); $('bd-status').textContent = 'performance · 90d'; }
  catch (e) { $('bd-status').textContent = 'error'; }
  renderPerformance();
}
const hc = (h) => h == null ? '' : h >= 66 ? 'hi' : h >= 58 ? 'mid' : 'lo';
function renderPerformance() {
  const res = $('bd-results'); res.classList.remove('compact');
  if (!PERF) { res.innerHTML = '<div class="bd-empty">Loading…</div>'; return; }
  $('bd-summary').innerHTML = `<span>settled-pick performance · window <b>${PERF.window_days || 90}d</b></span><span class="lg">these are the engine's own settled hit-rates — single source of truth</span>`;
  const ms = PERF.markets_summary || [];
  let html = '<div class="psec">Per-market (settled)</div>';
  html += '<table class="ptab"><thead><tr><th>Market</th><th>n</th><th>W</th><th>L</th><th>V</th><th>Hit %</th><th>Baseline</th><th>Δ pp</th></tr></thead><tbody>';
  html += ms.map(m => `<tr><td>${MKT_LABEL[m.market] || m.market}</td><td class="num">${m.n}</td><td class="num">${m.wins}</td><td class="num">${m.losses}</td><td class="num">${m.voids}</td><td class="num ${hc(m.hit_rate)}">${m.hit_rate ?? '—'}</td><td class="num">${m.baseline_hit ?? '—'}</td><td class="num">${m.vs_baseline_pp ?? '—'}</td></tr>`).join('');
  html += '</tbody></table>';
  const cells = (PERF.cells || []).slice().sort((a, b) => (a.partition_key || '').localeCompare(b.partition_key || ''));
  html += '<div class="psec">Per-cell (settled, by market)</div><div class="psub">' + cells.length + ' cells with settled picks in the window</div>';
  html += '<table class="ptab"><thead><tr><th>Cell</th><th>Market</th><th>n</th><th>Hit %</th></tr></thead><tbody>';
  cells.forEach(c => (c.markets || []).forEach((m, i) => {
    html += `<tr><td>${i === 0 ? c.partition_key : ''}</td><td>${MKT_LABEL[m.market] || m.market}</td><td class="num">${m.n}</td><td class="num ${hc(m.hit_rate)}">${m.hit_rate ?? '—'}</td></tr>`;
  }));
  html += '</tbody></table>';
  res.innerHTML = html;
}

// ===== Picks-Log view (3 configs, legs only — no EV) =====
function renderLog() {
  const res = $('bd-results'); res.classList.remove('compact');
  const fixtures = RAW.filter(passes);
  $('bd-summary').innerHTML = `<span><b>${fixtures.length}</b> fixtures · 3 configs each</span><span class="lg">legs only — EV/economics not introduced until validated</span>`;
  if (!fixtures.length) { res.innerHTML = '<div class="bd-empty">No picks in window.</div>'; return; }
  res.innerHTML = fixtures.map(fx => {
    const g = fx.markets.goals_nl, c = fx.markets.corners_nl, t = fx.markets.threeway;
    const gN = g ? g.line : null, cN = c ? c.line : null;
    const alpha = t ? String(t.pick || '').replace(/ or Draw$/, '') : 'Fav';
    const L = (b, a) => b != null ? `O${(b + a).toFixed(1)}` : '—';
    const col = (h, ga, ca, tw, note) => `<div class="cfgcol"><h5>${h}</h5><div>Goals ${L(gN, ga)}</div><div>Corners ${cN != null ? L(cN, ca) : '—'}</div><div>${tw}</div><div class="cfgnote">${note}</div></div>`;
    return `<div class="card"><div class="card-l"><div class="teams">${fx.home} <span class="vs">v</span> ${fx.away}</div>
      <div class="kick">🕑 ${fmtTime(fx.kickoff)}</div><div class="lg">${fx.league || ''} · ${fx.zone} ${fx.bts}</div></div>
      <div class="cfg">${col('Most-likely', 0, 0, `${alpha} or Draw`, 'natural · protected')}${col('Mean', 1, 1, `${alpha} or Draw`, '1-up')}${col('Optimistic', 2, 2, `${alpha} win`, '2-up · straight win')}</div></div>`;
  }).join('');
}

// ---- wire controls ----
function seg(id, key) {
  $(id).querySelectorAll('button').forEach(b => b.onclick = () => {
    $(id).querySelectorAll('button').forEach(x => x.classList.remove('on'));
    b.classList.add('on'); state[key] = b.dataset.v; renderCurrent();
  });
}
function init() {
  buildChips();
  seg('t-group', 'group'); seg('t-sort', 'sort');
  $('bd-nav').querySelectorAll('button').forEach(b => b.onclick = () => {
    $('bd-nav').querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b));
    state.view = b.dataset.view; loadView();
  });
  $('f-days').oninput = (e) => { state.days = +e.target.value || 3; };
  $('f-days').onchange = refreshCurrent;
  $('f-search').oninput = (e) => { state.search = e.target.value; renderCurrent(); };
  $('f-minhit').oninput = (e) => { state.minhit = +e.target.value; $('f-minhit-v').textContent = e.target.value; renderCurrent(); };
  $('t-signals').onchange = (e) => { state.signals = e.target.checked; renderCurrent(); };
  $('t-compact').onchange = (e) => { state.compact = e.target.checked; renderCurrent(); };
  $('f-refresh').onclick = refreshCurrent;
  $('f-reset').onclick = () => { location.reload(); };

  // recent-results-for-similar-odds: expand a card to the cell's recent settled results
  $('bd-results').addEventListener('click', async (e) => {
    const btn = e.target.closest('.recent-toggle');
    if (!btn) return;
    const fid = btn.dataset.fid;
    const box = btn.parentElement.querySelector(`.recent[data-fid="${fid}"]`);
    if (box.dataset.open === '1') { box.style.display = 'none'; box.dataset.open = '0'; btn.textContent = 'recent in this cell ▾'; return; }
    if (!box.dataset.loaded) {
      btn.textContent = 'loading…';
      try {
        const d = await (await fetch(`/inspector/similar?fixture_id=${fid}`)).json();
        const rows = (d.fixtures || []).slice(0, 8).map(f => {
          const cls = f.tw_green ? 'rg' : 'rr';
          return `<div class="recent-row"><span class="rmark ${cls}">${f.tw_green ? '✓' : '✗'}</span>
                  <span class="rdate">${(f.date || '').slice(0, 10)}</span>
                  <span class="rteams">${f.home_team} <b>${f.home_score}-${f.away_score}</b> ${f.away_team}</span></div>`;
        }).join('');
        box.innerHTML = `<div class="recent-head">${d.partition_key} · 3-way hit ${d.threeway_hit ?? '—'}% · n=${d.sample_n ?? 0}</div>${rows || '<div class="lg">no recent settled in this cell</div>'}`;
        box.dataset.loaded = '1';
      } catch (err) { box.innerHTML = '<div class="lg">error loading recent</div>'; }
    }
    box.style.display = 'block'; box.dataset.open = '1'; btn.textContent = 'recent in this cell ▴';
  });

  loadView();
}
init();
