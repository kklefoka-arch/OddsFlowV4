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
let RAW = [];  // grouped fixtures

const $ = (id) => document.getElementById(id);
const compClass = (h) => h == null ? '' : h >= 74 ? 'hi' : h >= 66 ? 'mid' : 'lo';
const kdt = (s) => (s || '').replace('T', ' ').slice(0, 16);

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
        render();
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
  render();
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
  const pk = (m) => {
    const x = fx.markets[m]; if (!x) return '';
    const label = m === 'goals_nl' ? `Over ${x.line} Goals`
                : m === 'corners_nl' ? `Over ${x.line} Corners`
                : x.pick;
    const odd = x.odd != null ? `<span class="pk-odd">@${x.odd}</span>` : '';
    return `<div class="pk"><span class="pk-name">${MKT_LABEL[m]}: ${label}${odd}</span>
            <span class="pk-hit"><b>${x.hit ?? '—'}%</b></span></div>`;
  };
  const sig = state.signals ? `<div class="sig">
      <span class="s ${fx.spread}">spread ${fx.spread || '—'}</span>
      <span class="s">${fx.df || '—'}</span>
      <span class="s ${fx.h2h}">h2h ${fx.h2h || 'none'}</span>
      ${fx.odds_updated_at ? '' : '<span class="s">odds: base</span>'}
    </div>` : '';
  return `<div class="card">
    <div class="card-h">
      <div><div class="teams">${fx.home || ''} <span class="meta">v</span> ${fx.away || ''}</div>
        <div class="meta">${fx.league || ''} · T${fx.tier ?? '?'} · ${kdt(fx.kickoff)}
          <span class="pill-bts ${fx.bts}">${fx.zone} ${fx.bts}</span></div></div>
      <div class="comp ${compClass(o.comp)}">${o.comp ?? '—'}<span style="font-size:11px;color:var(--muted)">%</span></div>
    </div>
    ${o.mkts.map(pk).join('')}
    ${sig}
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

// ---- wire controls ----
function seg(id, key) {
  $(id).querySelectorAll('button').forEach(b => b.onclick = () => {
    $(id).querySelectorAll('button').forEach(x => x.classList.remove('on'));
    b.classList.add('on'); state[key] = b.dataset.v; render();
  });
}
function init() {
  buildChips();
  seg('t-group', 'group'); seg('t-sort', 'sort');
  $('f-days').oninput = (e) => { state.days = +e.target.value || 3; };
  $('f-days').onchange = load;
  $('f-search').oninput = (e) => { state.search = e.target.value; render(); };
  $('f-minhit').oninput = (e) => { state.minhit = +e.target.value; $('f-minhit-v').textContent = e.target.value; render(); };
  $('t-signals').onchange = (e) => { state.signals = e.target.checked; render(); };
  $('t-compact').onchange = (e) => { state.compact = e.target.checked; render(); };
  $('f-refresh').onclick = load;
  $('f-reset').onclick = () => { location.reload(); };
  load();
}
init();
