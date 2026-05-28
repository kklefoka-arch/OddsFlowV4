// OddsFlow V4 — engine view client. Vanilla JS, no framework.
// Talks to: /picks, /api/foundation, /diagnostics/*

const fmt = {
  pct: (v) => v == null ? '—' : (v * 100).toFixed(1) + '%',
  num: (v) => v == null ? '—' : v.toLocaleString(),
  odd: (v) => v == null ? '—' : v.toFixed(2),
  edge: (v) => v == null ? '—' : (v >= 0 ? '+' : '') + (v * 100).toFixed(1) + '%',
};

// Parse a "YYYY-MM-DD HH:MM:SS" kickoff_utc string as actual UTC.
function parseKickoffUtc(s) {
  if (!s) return null;
  if (/T.*(Z|[+-]\d{2}:?\d{2})$/.test(s)) return new Date(s);
  const iso = s.replace(' ', 'T') + (s.includes('T') ? '' : '') + 'Z';
  return new Date(iso);
}

// ---- Tab switching ----
const tabs = document.querySelectorAll('.tab');
const panels = document.querySelectorAll('.panel');
tabs.forEach(t => t.addEventListener('click', () => {
  const target = t.dataset.tab;
  tabs.forEach(x => x.classList.toggle('active', x === t));
  panels.forEach(p => p.classList.toggle('active', p.id === target));
  loadTab(target);
}));

// ---- Health badge ----
async function refreshHealth() {
  const badge = document.getElementById('health-badge');
  const envTag = document.getElementById('env-tag');
  try {
    const r = await fetch('/healthz/deep');
    const body = await r.json();
    envTag.textContent = `env: ${body.env}`;
    if (body.status === 'ok') {
      badge.textContent = 'healthy';
      badge.className = 'badge badge-ok';
    } else {
      badge.textContent = 'degraded';
      badge.className = 'badge badge-degraded';
    }
  } catch (e) {
    badge.textContent = 'down';
    badge.className = 'badge badge-down';
  }
}

// ---- Today ----
async function loadToday() {
  const cronWrap   = document.getElementById('today-cron-chip-wrap');
  const summary    = document.getElementById('today-summary');
  const byMarket   = document.getElementById('today-by-market');
  // V4: today-recent-failure element may not exist — guard before use
  const recentFail = document.getElementById('today-recent-failure');
  cronWrap.innerHTML = '<span class="muted">Loading…</span>';
  summary.innerHTML  = '';
  byMarket.innerHTML = '';
  if (recentFail) recentFail.textContent = '—';
  try {
    const r = await fetch('/diagnostics/today_summary');
    const body = await r.json();

    const cronStatus = (body.cron && body.cron.status) || 'unknown';
    const cronAge    = body.cron && body.cron.age_hours;
    const cronCls = cronStatus === 'fresh'    ? 'chip chip-positive'
                  : cronStatus === 'warning'  ? 'chip chip-emerging'
                  : cronStatus === 'stale'    ? 'chip chip-negative'
                  : 'chip';
    const cronTxt = cronStatus === 'never_fired'
      ? 'Cron: never fired'
      : `Cron: ${cronStatus}${cronAge != null ? ` (${cronAge}h ago)` : ''}`;
    const chainCls = (body.chain && body.chain.verified === true) ? 'chip chip-positive'
                   : (body.chain && body.chain.verified === false) ? 'chip chip-negative'
                   : 'chip';
    const chainTxt = body.chain
      ? `Chain: ${body.chain.verified === true ? 'verified'
                : body.chain.verified === false ? 'BROKEN'
                : 'unknown'}`
      : 'Chain: —';

    const lastClean = body.cron && body.cron.last_clean_run;
    let cleanChip = '';
    if (lastClean) {
      const cleanCls = lastClean.age_hours <= 26  ? 'chip chip-positive'
                     : lastClean.age_hours <= 48  ? 'chip chip-emerging'
                     :                                'chip chip-negative';
      cleanChip = `<span class="${cleanCls}">Last clean run: ${lastClean.age_hours}h ago</span>`;
    } else {
      cleanChip = '<span class="chip muted">Last clean run: never</span>';
    }

    const drift = body.drift || {};
    let driftChip = '';
    if (drift.error) {
      driftChip = '<span class="chip muted">Drift: unavailable</span>';
    } else if ((drift.drifting || 0) > 0) {
      driftChip = `<span class="chip chip-negative">${drift.drifting} drifting</span>`;
    } else if ((drift.watch || 0) > 0) {
      driftChip = `<span class="chip chip-emerging">${drift.watch} on watch</span>`;
    } else if ((drift.stable || 0) > 0) {
      driftChip = `<span class="chip chip-positive">${drift.stable} stable</span>`;
    } else {
      driftChip = '<span class="chip muted">Drift: no data</span>';
    }

    cronWrap.innerHTML = `
      <span class="${cronCls}">${cronTxt}</span>
      ${cleanChip}
      <span class="${chainCls}">${chainTxt}</span>
      ${driftChip}
      <span class="chip muted">as of ${(body.as_of || '').slice(11, 19)} UTC</span>
    `;

    const fx  = body.fixtures || {};
    const pk  = body.picks    || {};
    const lk  = body.locks    || {};
    const eng = body.engine   || {};
    const db  = body.db       || {};
    const w7  = eng.window_7d || null;
    const w30 = eng.window_30d || null;
    const lbs = db.locked_by_state || {};

    const engBlock = w7 ? `
      <div class="summary-item">
        <span class="summary-label">Engine hit rate (7d events)</span>
        <span class="summary-value ${(w7.events && w7.events.hit_rate >= 55) ? 'positive' : ((w7.events && w7.events.hit_rate < 45 && w7.events.hit_rate != null) ? 'negative' : '')}">
          ${w7.events && w7.events.hit_rate != null ? w7.events.hit_rate + '%' : '—'}
        </span>
      </div>
      <div class="summary-item">
        <span class="summary-label">Events settled (7d)</span>
        <span class="summary-value">${fmt.num((w7.events && w7.events.settled) || 0)}</span>
      </div>
      <div class="summary-item">
        <span class="summary-label">Legs settled / total (7d)</span>
        <span class="summary-value">${fmt.num((w7.legs && w7.legs.settled) || 0)} / ${fmt.num((w7.legs && w7.legs.total) || 0)}</span>
      </div>
      <div class="summary-item">
        <span class="summary-label">Engine hit rate (30d events)</span>
        <span class="summary-value ${(w30 && w30.events && w30.events.hit_rate >= 55) ? 'positive' : ''}">
          ${w30 && w30.events && w30.events.hit_rate != null ? w30.events.hit_rate + '%' : '—'}
        </span>
      </div>
    ` : '';

    summary.innerHTML = `
      <div class="summary-item">
        <span class="summary-label">Fixtures kicking off today</span>
        <span class="summary-value">${fmt.num(fx.kickoff_today)}</span>
      </div>
      <div class="summary-item">
        <span class="summary-label">Fixtures fetched (24h)</span>
        <span class="summary-value">${fmt.num(fx.fetched_last_24h)}</span>
      </div>
      <div class="summary-item">
        <span class="summary-label">Picks emitted today</span>
        <span class="summary-value">${fmt.num(pk.emitted_today)}</span>
      </div>
      <div class="summary-item">
        <span class="summary-label">Locks pending</span>
        <span class="summary-value">${fmt.num(lk.pending)}</span>
      </div>
      <div class="summary-item">
        <span class="summary-label">Settled today</span>
        <span class="summary-value">${fmt.num(lk.settled_today)}</span>
      </div>
      ${engBlock}
      <div class="summary-item">
        <span class="summary-label">Fixtures settled / total</span>
        <span class="summary-value">${fmt.num(db.fixtures_settled || 0)} / ${fmt.num(db.fixtures_total || 0)}</span>
      </div>
      <div class="summary-item">
        <span class="summary-label">Emits settled / total</span>
        <span class="summary-value">${fmt.num(db.emit_settled || 0)} / ${fmt.num(db.emit_total || 0)}</span>
      </div>
    `;

    const bm = pk.by_market_today || {};
    const marketKeys = Object.keys(bm);
    if (marketKeys.length === 0) {
      byMarket.innerHTML = '<div class="muted">No picks emitted today yet.</div>';
    } else {
      byMarket.innerHTML = marketKeys.map(k => `
        <div class="summary-item">
          <span class="summary-label">${marketLabel(k)}</span>
          <span class="summary-value">${bm[k]}</span>
        </div>
      `).join('');
    }

    const rf = body.cron && body.cron.recent_failure;
    if (recentFail) {
      if (rf) {
        recentFail.textContent = `${rf.recorded_at}  →  ${rf.value}`;
        recentFail.className = 'negative';
      } else {
        recentFail.textContent = 'No failure recorded in the last 24h.';
        recentFail.className = 'muted';
      }
    }
  } catch (e) {
    cronWrap.innerHTML = `<span class="chip chip-negative">Error: ${e}</span>`;
  }
}

// ---- Picks ----
async function loadPicks() {
  const days = document.getElementById('picks-days').value;
  const summary = document.getElementById('picks-summary');
  const list = document.getElementById('picks-list');
  const prx9Panel = document.getElementById('picks-prx9');
  summary.innerHTML = '<div class="muted">Loading…</div>';
  list.innerHTML = '';
  if (prx9Panel) prx9Panel.innerHTML = '';
  try {
    const [r, rp] = await Promise.all([
      fetch(`/picks?days=${days}`),
      fetch(`/picks/prx9?days=${days}`),
    ]);
    const body = await r.json();
    const prx9Body = rp.ok ? await rp.json() : null;
    renderPicksSummary(summary, body);
    renderPicksList(list, body.picks);
    if (prx9Panel) renderPrx9Panel(prx9Panel, prx9Body, days);
  } catch (e) {
    summary.innerHTML = `<div class="empty">Error: ${e}</div>`;
  }
}

function renderPicksSummary(el, body) {
  const sk = body.skip_reasons || {};
  const cm = body.counts_by_market || {};
  el.innerHTML = `
    <div class="summary-item">
      <span class="summary-label">Fixtures emitted</span>
      <span class="summary-value">${fmt.num(body.fixtures_count)}</span>
    </div>
    <div class="summary-item">
      <span class="summary-label">Picks emitted</span>
      <span class="summary-value">${fmt.num(body.count)}</span>
    </div>
    <div class="summary-item">
      <span class="summary-label">Window</span>
      <span class="summary-value">${body.window_days}d</span>
    </div>
    <div class="summary-item">
      <span class="summary-label">DNB</span>
      <span class="summary-value">${cm.dnb || 0}</span>
    </div>
    <div class="summary-item">
      <span class="summary-label">Alpha Win</span>
      <span class="summary-value">${cm.alpha_win || 0}</span>
    </div>
    <div class="summary-item">
      <span class="summary-label">Goals NL</span>
      <span class="summary-value">${cm.goals_nl || 0}</span>
    </div>
    <div class="summary-item">
      <span class="summary-label">Unclassifiable</span>
      <span class="summary-value">${sk.unclassifiable || 0}</span>
    </div>
    <div class="summary-item">
      <span class="summary-label">Not promoted</span>
      <span class="summary-value">${sk.partition_not_promoted || 0}</span>
    </div>
  `;
}

function renderPrx9Panel(el, body, days) {
  if (!body || !body.picks || body.picks.length === 0) {
    el.innerHTML = '';
    return;
  }
  const rows = body.picks.map(p => {
    const dt = parseKickoffUtc(p.kickoff_utc);
    const time = dt ? dt.toLocaleString([], {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'}) : p.kickoff_utc || '—';
    const rankColor = p.rank_score >= 7 ? 'positive' : p.rank_score >= 5 ? '' : 'muted';
    return `<tr>
      <td><span class="summary-value ${rankColor}">${p.rank_score}</span></td>
      <td>${p.home_team} vs ${p.away_team}</td>
      <td class="muted">${p.league || '—'}</td>
      <td>${time}</td>
      <td>${marketLabel(p.market)}</td>
      <td><strong>${p.pick}</strong> @ ${p.odd}</td>
    </tr>`;
  }).join('');
  el.innerHTML = `
    <div class="prx9-header">
      <span class="chip">PR-X9 signals &mdash; ${body.count} ranked picks (${days}d window)</span>
      <span class="muted" style="font-size:0.8em;margin-left:8px">Additional layer &bull; foundation picks above</span>
    </div>
    <table class="prx9-table">
      <thead><tr><th>Rank</th><th>Fixture</th><th>League</th><th>Kickoff</th><th>Market</th><th>Pick</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function renderPicksList(el, picks) {
  if (!picks || picks.length === 0) {
    el.innerHTML = '<div class="empty">No picks in this window.</div>';
    return;
  }
  const byFixture = new Map();
  for (const p of picks) {
    if (!byFixture.has(p.fixture_id)) byFixture.set(p.fixture_id, []);
    byFixture.get(p.fixture_id).push(p);
  }
  const fixtureCards = Array.from(byFixture.values())
    .sort((a, b) => (a[0].kickoff_utc || '').localeCompare(b[0].kickoff_utc || ''))
    .map(picks => renderFixtureCard(picks))
    .join('');
  el.innerHTML = fixtureCards;
  el.querySelectorAll('.card').forEach(c => {
    c.addEventListener('click', () => openInspector(JSON.parse(c.dataset.picks)));
  });
}

function renderFixtureCard(picks) {
  // Prefer threeway pick as primary source for drift/hit chip; fall back to first pick
  const p0 = picks.find(p => p.market === 'dnb' || p.market === 'alpha_win') || picks[0];
  const dt = parseKickoffUtc(p0.kickoff_utc);
  const date = dt ? dt.toLocaleDateString() : '—';
  const time = dt ? dt.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}) : '';
  const tierBadge = p0.tier
    ? `<span class="chip chip-tier chip-tier-${p0.tier}">T${p0.tier}</span>`
    : '<span class="chip chip-tier chip-tier-na">untiered</span>';

  const driftChip = renderDriftChipForCard(
    p0.cell_drift_flag,
    p0.cell_drift_gap_pp,
    p0.cell_drift_recent_n,
  );

  const byMarket = new Map();
  for (const p of picks) {
    if (!byMarket.has(p.market)) byMarket.set(p.market, []);
    byMarket.get(p.market).push(p);
  }
  const order = ['total_goals', 'total_corners', 'dnb', 'alpha_win', 'goals_nl'];
  const marketRows = order
    .filter(m => byMarket.has(m))
    .map(m => renderMarketRow(m, byMarket.get(m)))
    .join('');


  return `
    <div class="card fixture-card" data-picks='${JSON.stringify(picks).replace(/'/g, "&#39;")}'>
      <div class="card-header">
        <span>${p0.league || '—'} ${p0.country ? `· ${p0.country}` : ''} ${tierBadge}</span>
        <span>${date} ${time}</span>
      </div>
      <div class="card-fixture">${p0.home_team || '?'} vs ${p0.away_team || '?'}</div>
      <div class="card-chips card-classification">
        ${renderPromoteChip(p0.cell_historical_hit, p0.cell_historical_n)}
        <span class="chip">${p0.partition_key}</span>
        <span class="chip">${p0.draw_zone}</span>
        ${driftChip}
      </div>
      <div class="market-rows">${marketRows}</div>
    </div>
  `;
}

function renderPromoteChip(hist_hit, hist_n) {
  const tooltip = `Locked PROMOTE cell · historical hit-rate ${hist_hit != null ? hist_hit + '%' : '—'} `
                + `over ${hist_n != null ? hist_n.toLocaleString() : '—'} settled fixtures. `
                + `The drift chip (if present) shows how the cell is performing recently vs this baseline.`;
  const hit = hist_hit != null ? `${hist_hit}%` : '—';
  const n   = hist_n   != null ? hist_n.toLocaleString() : '—';
  return `<span class="chip chip-premium" title="${tooltip}">★ PROMOTE · ${hit} · n=${n}</span>`;
}

function renderDriftChipForCard(flag, gap_pp, recent_n) {
  if (!flag || flag === 'stable' || flag === 'no_data') return '';
  const gap = gap_pp != null
    ? ` ${gap_pp >= 0 ? '+' : ''}${gap_pp}pp`
    : '';
  const n = recent_n != null ? ` · n=${recent_n}` : '';
  const cls = flag === 'drifting' ? 'chip chip-negative'
            : flag === 'watch'    ? 'chip chip-emerging'
            :                        'chip';
  const tooltip = `Cell drift: recent vs historical hit-rate gap ${gap}, ` +
                  `based on ${recent_n} recent picks. Display only — engine ` +
                  `does NOT auto-suppress drifting cells.`;
  return `<span class="${cls}" title="${tooltip}">${flag}${gap}${n}</span>`;
}

function marketLabel(m) {
  return {
    total_goals:   'Goals',
    total_corners: 'Corners',
    dnb:           'DNB (Alpha Win or Draw)',
    alpha_win:     'Alpha Win',
    goals_nl:      'Goals — Natural Line',
  }[m] || m;
}

function renderMarketRow(market, picks) {
  const legOrder = { 'natural': 0, 'system': 1 };
  picks.sort((a, b) => (legOrder[a.pick_leg] ?? 2) - (legOrder[b.pick_leg] ?? 2));
  const legCells = picks.map(p => {
    const dotChar = p.pick_leg === 'natural' ? '●'
                  : p.pick_leg === 'system'  ? '○'
                  : '◆';
    const legText = p.pick_leg === 'natural' ? 'natural'
                  : p.pick_leg === 'system'  ? '1-up'
                  : '';
    const odd = p.pick_odd != null ? fmt.odd(p.pick_odd) : '—';
    const derivedFlag = p.pick_odd_derived
      ? '<span class="leg-derived" title="DNB derived from 1X2 — not a quoted bookmaker price">derived</span>'
      : '';
    const hitTag = p.cell_historical_hit != null
      ? `<span class="leg-tag leg-hit">${p.cell_historical_hit}% hit · n=${(p.cell_historical_n||0).toLocaleString()}</span>`
      : '';
    return `
      <div class="leg leg-${p.pick_leg || 'single'}">
        <span class="leg-dot">${dotChar}</span>
        <span class="leg-pick">${p.pick}</span>
        <span class="leg-odd">@ ${odd}</span>
        ${legText ? `<span class="leg-tag">${legText}</span>` : ''}
        ${derivedFlag}
        ${hitTag}
      </div>
    `;
  }).join('');
  return `
    <div class="market-row">
      <div class="market-label">${marketLabel(market)}</div>
      <div class="market-legs">${legCells}</div>
    </div>
  `;
}

// ---- Analysis — Foundation Matrix ----
let _foundationData = null;

async function loadAnalysis() {
  const summary = document.getElementById('analysis-summary');
  const wrap = document.getElementById('analysis-table-wrap');
  summary.innerHTML = '<div class="muted">Loading…</div>';
  wrap.innerHTML = '';
  document.querySelectorAll('.btn-subtab').forEach(b => b.classList.toggle('active', b.dataset.tier === 'all'));
  try {
    const r = await fetch('/api/foundation');
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    _foundationData = await r.json();
    renderAnalysisSummary(summary, _foundationData.summary);
    renderFoundationTable(wrap, _foundationData.all);
  } catch (e) {
    summary.innerHTML = `<div class="empty">Error loading foundation: ${e}</div>`;
  }
}

function renderAnalysisSummary(el, s) {
  el.innerHTML = `
    <div class="summary-item">
      <span class="summary-label">Total fixtures</span>
      <span class="summary-value">${fmt.num(s.total_fixtures)}</span>
    </div>
    <div class="summary-item">
      <span class="summary-label">Promoted cells</span>
      <span class="summary-value">${s.promoted_cells}</span>
    </div>
    <div class="summary-item">
      <span class="summary-label">Last updated</span>
      <span class="summary-value muted" style="font-size:12px">${(s.last_updated || '').slice(0, 19)} UTC</span>
    </div>
  `;
}

function promoteBadge(status) {
  if (status === 'PROMOTE')
    return '<span class="pbadge pbadge-yes">PROMOTE</span>';
  if (status === 'PROMOTE_TOLERANCE')
    return '<span class="pbadge pbadge-tol">TOLERANCE</span>';
  if (status === 'MEASURING')
    return '<span class="pbadge pbadge-meas">MEASURING</span>';
  if (status === 'HOLD')
    return '<span class="pbadge pbadge-hold">HOLD</span>';
  return '<span class="pbadge pbadge-no">NO</span>';
}

function renderFoundationTable(wrap, cells) {
  if (!cells || cells.length === 0) {
    wrap.innerHTML = '<div class="empty">No foundation data for this tier.</div>';
    return;
  }
  const ZONE_ORDER = ['strong', 'standard', 'low', 'one_sided'];
  const BTS_ORDER  = ['strong_over', 'slight_over', 'slight_under', 'strong_under'];
  const sorted = [...cells].sort((a, b) => {
    const zi = ZONE_ORDER.indexOf(a.zone) - ZONE_ORDER.indexOf(b.zone);
    if (zi !== 0) return zi;
    return BTS_ORDER.indexOf(a.bts_pocket) - BTS_ORDER.indexOf(b.bts_pocket);
  });

  let currentZone = null;
  const rows = sorted.map(cell => {
    let zoneHdr = '';
    if (cell.zone !== currentZone) {
      currentZone = cell.zone;
      zoneHdr = `<tr class="fnd-zone-hdr"><td colspan="13">&#9632; ${cell.zone.toUpperCase().replace(/_/g, ' ')}</td></tr>`;
    }
    const drG = cell.goals_drop_rank
      ? `<span class="fnd-drop rank-${cell.goals_drop_rank}">▼${(cell.goals_1up_drop || 0).toFixed(1)}</span>`
      : '<span class="muted">—</span>';
    const drC = cell.corners_drop_rank
      ? `<span class="fnd-drop rank-${cell.corners_drop_rank}">▼${(cell.corners_1up_drop || 0).toFixed(1)}</span>`
      : '<span class="muted">—</span>';
    const promotedCls = cell.cell_promoted ? 'fnd-promoted' : '';
    const lowCls      = (cell.zone === 'low' || cell.zone === 'one_sided') ? 'fnd-low' : '';
    const cpBadge     = cell.cell_promoted
      ? '<span class="pbadge pbadge-yes">✓ YES</span>'
      : '<span class="muted">—</span>';
    return `${zoneHdr}
    <tr class="${promotedCls} ${lowCls}">
      <td class="fnd-zone">${cell.zone.replace(/_/g, ' ')}</td>
      <td class="fnd-bts">${cell.bts_pocket}</td>
      <td class="fnd-num">${cell.n_fixtures}</td>
      <td class="fnd-num muted">${cell.n_pct_of_zone.toFixed(1)}%</td>
      <td class="fnd-num fnd-pct">${cell.gn_hit.toFixed(1)}%</td>
      <td class="fnd-num">${drG}</td>
      <td class="fnd-num">${promoteBadge(cell.goals_promote)}</td>
      <td class="fnd-num fnd-pct">${cell.cn_hit.toFixed(1)}%</td>
      <td class="fnd-num">${drC}</td>
      <td class="fnd-num">${promoteBadge(cell.corners_promote)}</td>
      <td class="fnd-num fnd-pct">${cell.threeway_hit.toFixed(1)}%</td>
      <td>${cell.threeway_pick || '—'}</td>
      <td class="fnd-num">${promoteBadge(cell.threeway_promote)} ${cpBadge}</td>
    </tr>`;
  }).join('');

  wrap.innerHTML = `
    <div class="fnd-scroll">
    <table class="fnd-table">
      <thead>
        <tr>
          <th>Zone</th>
          <th>BTS Pocket</th>
          <th class="fnd-num">n</th>
          <th class="fnd-num">n% Zone</th>
          <th class="fnd-num">Goals Nat%</th>
          <th class="fnd-num">Goals Drop</th>
          <th class="fnd-num">Goals ▲</th>
          <th class="fnd-num">Corners Nat%</th>
          <th class="fnd-num">Corners Drop</th>
          <th class="fnd-num">Corners ▲</th>
          <th class="fnd-num">3-Way%</th>
          <th>3-Way Pick</th>
          <th class="fnd-num">PROMOTE?</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
    </div>
  `;
}

// ---- Stats ----
async function loadStats() {
  const el = document.getElementById('stats-content');
  el.innerHTML = '<div class="muted">Loading…</div>';
  try {
    const [dbR, oddsR, hbR, driftR, tierActR] = await Promise.all([
      fetch('/diagnostics/db_state').then(r => r.json()),
      fetch('/diagnostics/odds_coverage').then(r => r.json()),
      fetch('/diagnostics/cron/heartbeat').then(r => r.json()),
      fetch('/diagnostics/drift_report').then(r => r.json()).catch(() => null),
      fetch('/diagnostics/activity_by_tier?days=7').then(r => r.json()).catch(() => null),
    ]);
    el.innerHTML = `
      <div class="summary">
        ${Object.entries(dbR.counts).map(([k,v]) => `
          <div class="summary-item">
            <span class="summary-label">${k}</span>
            <span class="summary-value">${fmt.num(v)}</span>
          </div>
        `).join('')}
      </div>
      <h3 class="section-h">Cron heartbeat</h3>
      <div class="summary">
        <div class="summary-item">
          <span class="summary-label">Last recorded</span>
          <span class="summary-value">${hbR.recorded_at || 'never'}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">Stale</span>
          <span class="summary-value">${hbR.stale ? 'YES' : 'no'}</span>
        </div>
      </div>
      ${renderActivityByTier(tierActR)}
      <h3 class="section-h">Odds coverage per league</h3>
      <table>
        <thead><tr><th>League</th><th>Tier</th><th class="numeric">Total</th><th class="numeric">Goal %</th><th class="numeric">BTS %</th><th class="numeric">Corner %</th></tr></thead>
        <tbody>
          ${(oddsR.leagues || []).map(l => `
            <tr>
              <td>${l.name}</td>
              <td>T${l.tier || '?'}</td>
              <td class="numeric">${fmt.num(l.total)}</td>
              <td class="numeric">${l.goal_odds_pct ?? '—'}</td>
              <td class="numeric">${l.bts_odds_pct ?? '—'}</td>
              <td class="numeric">${l.corner_odds_pct ?? '—'}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
      ${renderDriftReport(driftR)}
    `;
  } catch (e) {
    el.innerHTML = `<div class="empty">Error: ${e}</div>`;
  }
}

function renderActivityByTier(d) {
  if (!d || !d.tiers) {
    return '<h3 class="section-h">Activity by tier</h3><div class="muted">Unavailable.</div>';
  }
  const totals = {
    emit:    d.tiers.reduce((s, t) => s + t.emit,    0),
    lock:    d.tiers.reduce((s, t) => s + t.lock,    0),
    pass:    d.tiers.reduce((s, t) => s + t.pass,    0),
    settled: d.tiers.reduce((s, t) => s + t.settled, 0),
    pnl:     d.tiers.reduce((s, t) => s + t.pnl_zar, 0),
    stake:   d.tiers.reduce((s, t) => s + t.stake_zar, 0),
  };
  return `
    <h3 class="section-h">Activity by tier (last ${d.window_days}d)</h3>
    <table>
      <thead><tr>
        <th>Tier</th>
        <th class="numeric">Emit</th>
        <th class="numeric">Settled</th>
      </tr></thead>
      <tbody>
        ${d.tiers.map(t => `
          <tr>
            <td><strong>${t.tier_key}</strong></td>
            <td class="numeric">${fmt.num(t.emit)}</td>
            <td class="numeric">${fmt.num(t.settled)}</td>
          </tr>
        `).join('')}
        <tr style="border-top: 2px solid var(--line); font-weight: 700;">
          <td>TOTAL</td>
          <td class="numeric">${fmt.num(totals.emit)}</td>
          <td class="numeric">${fmt.num(totals.settled)}</td>
        </tr>
      </tbody>
    </table>
  `;
}

function renderDriftReport(d) {
  if (!d || !d.partitions) {
    return '<div class="muted" style="margin-top:20px;">Drift report unavailable.</div>';
  }
  const flagPill = (f) => {
    const cls = f === 'critical' ? 'chip-negative'
              : f === 'warning' ? 'chip-emerging'
              : 'chip-positive';
    return `<span class="chip ${cls}">${f}</span>`;
  };
  return `
    <h3 style="margin-top:24px; margin-bottom:10px; font-size:14px; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.04em;">
      Drift report — partition signal stability
    </h3>
    <div class="summary">
      <div class="summary-item"><span class="summary-label">OK</span><span class="summary-value">${d.summary.ok}</span></div>
      <div class="summary-item"><span class="summary-label">Warning</span><span class="summary-value">${d.summary.warning}</span></div>
      <div class="summary-item"><span class="summary-label">Critical</span><span class="summary-value">${d.summary.critical}</span></div>
    </div>
    <table style="margin-top:10px;">
      <thead><tr>
        <th>Partition</th><th>Class</th>
        <th class="numeric">n</th>
        <th>Flag</th>
      </tr></thead>
      <tbody>
        ${d.partitions.map(r => `
          <tr>
            <td>${r.partition_key}</td>
            <td><span class="chip chip-premium">promote</span></td>
            <td class="numeric">${fmt.num(r.n_current)}</td>
            <td>${flagPill(r.flag)}</td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

// ---- Inspector ----
async function loadInspector() {
  const days = document.getElementById('inspector-days').value || 30;
  await loadInspectorDrift(days);
}

async function loadReports() {
  const days = document.getElementById('reports-days').value || 7;
  const tierSel = document.getElementById('reports-tier');
  const tier = tierSel ? tierSel.value : '';
  await Promise.all([
    loadReportsSettleActivity(days),
    loadReportsEmitPerformance(tier),
    loadReportsEmitMarketBreakdown(days, tier),
    loadReportsEmitRecent(days, tier),
  ]);
}

async function loadReportsSettleActivity(days) {
  const el = document.getElementById('reports-settle-activity');
  el.innerHTML = '<div class="muted">Loading…</div>';
  try {
    const r = await fetch(`/reports/settle_activity?days=${days}`);
    const body = await r.json();
    const lc = body.last_clean_run;
    let cleanChip = '<span class="chip muted">Last clean run: never</span>';
    if (lc && lc.recorded_at) {
      try {
        const t = new Date(lc.recorded_at.replace(' ', 'T') + 'Z');
        const ageHours = (Date.now() - t.getTime()) / 3_600_000;
        const cls = ageHours <= 26 ? 'chip chip-positive'
                  : ageHours <= 48 ? 'chip chip-emerging'
                  :                   'chip chip-negative';
        cleanChip = `<span class="${cls}">Last clean run: ${ageHours.toFixed(1)}h ago</span>`;
      } catch (e) {
        cleanChip = `<span class="chip muted">Last clean run: ${lc.recorded_at}</span>`;
      }
    }
    const summary = `
      <div class="summary" style="margin-bottom: 12px;">
        ${cleanChip}
        <span class="chip chip-positive">Settled (pick_results driven)</span>
      </div>
    `;
    const days_html = (body.by_day || []).length === 0
      ? '<div class="empty">No settlements in this window.</div>'
      : `
        <table>
          <thead><tr>
            <th>Date</th>
            <th class="numeric">Settled</th>
          </tr></thead>
          <tbody>
          ${body.by_day.map(d => `
            <tr>
              <td>${d.date}</td>
              <td class="numeric">${fmt.num(d.settled_count)}</td>
            </tr>
          `).join('')}
          </tbody>
        </table>
      `;
    el.innerHTML = summary + days_html;
  } catch (e) {
    el.innerHTML = `<div class="empty">Error: ${e}</div>`;
  }
}

async function loadReportsEmitPerformance(tier) {
  const el = document.getElementById('reports-emit-performance');
  el.innerHTML = '<div class="muted">Loading…</div>';
  try {
    const url = '/reports/emit_performance' + (tier ? `?tier=${tier}` : '');
    const r = await fetch(url);
    const body = await r.json();
    if (!body.windows || body.windows.length === 0) {
      el.innerHTML = '<div class="empty">No engine emits in window.</div>';
      return;
    }
    el.innerHTML = `
      <table>
        <thead><tr>
          <th>Window</th>
          <th class="numeric">Fixtures</th>
          <th class="numeric">Legs total</th>
          <th class="numeric">Legs settled</th>
          <th class="numeric">Legs hit %</th>
          <th class="numeric">Events settled</th>
          <th class="numeric">Events hit %</th>
          <th class="numeric">Wins</th>
          <th class="numeric">Voids</th>
          <th class="numeric">Losses</th>
        </tr></thead>
        <tbody>
        ${body.windows.map(w => `
          <tr>
            <td><strong>${w.name}</strong></td>
            <td class="numeric">${fmt.num(w.fixtures)}</td>
            <td class="numeric muted">${fmt.num(w.legs.total)}</td>
            <td class="numeric">${fmt.num(w.legs.settled)}</td>
            <td class="numeric ${(w.legs.hit_rate || 0) >= 55 ? 'positive' : (w.legs.hit_rate || 0) < 45 && w.legs.hit_rate != null ? 'negative' : ''}">
              ${w.legs.hit_rate != null ? w.legs.hit_rate + '%' : '—'}
            </td>
            <td class="numeric"><strong>${fmt.num(w.events.settled)}</strong></td>
            <td class="numeric ${(w.events.hit_rate || 0) >= 55 ? 'positive' : (w.events.hit_rate || 0) < 45 && w.events.hit_rate != null ? 'negative' : ''}">
              <strong>${w.events.hit_rate != null ? w.events.hit_rate + '%' : '—'}</strong>
            </td>
            <td class="numeric positive">${w.events.wins}</td>
            <td class="numeric">${w.events.voids}</td>
            <td class="numeric negative">${w.events.losses}</td>
          </tr>
        `).join('')}
        </tbody>
      </table>
    `;
  } catch (e) {
    el.innerHTML = `<div class="empty">Error: ${e}</div>`;
  }
}

async function loadReportsEmitMarketBreakdown(days, tier) {
  const el = document.getElementById('reports-emit-market-breakdown');
  el.innerHTML = '<div class="muted">Loading…</div>';
  try {
    const url = `/reports/emit_market_breakdown?days=${days}` + (tier ? `&tier=${tier}` : '');
    const r = await fetch(url);
    const body = await r.json();
    if (!body.cells || body.cells.length === 0) {
      el.innerHTML = '<div class="empty">No engine emits in window.</div>';
      return;
    }
    el.innerHTML = body.cells.map(cell => {
      const promoteChip = cell.is_promoted
        ? '<span class="chip chip-premium">PROMOTE</span>'
        : '<span class="chip muted">non-promote</span>';
      const marketRows = cell.markets.map(m => `
        <div class="market-bd-row">
          <span class="market-bd-label">${marketLabel(m.market)}</span>
          <span class="market-bd-pick">${m.pick}</span>
          <span class="market-bd-n">n=${m.n}</span>
          <span class="market-bd-hit ${(m.hit_rate || 0) >= 60 ? 'positive' : (m.hit_rate || 0) < 45 && m.hit_rate != null ? 'negative' : ''}">
            ${m.hit_rate != null ? m.hit_rate + '%' : '—'}
          </span>
        </div>
      `).join('');
      return `
        <div class="market-bd-cell">
          <div class="market-bd-header">
            <strong>${cell.zone}</strong> · ${cell.bts_v2}
            ${promoteChip}
          </div>
          <div class="market-bd-rows">${marketRows}</div>
        </div>
      `;
    }).join('');
  } catch (e) {
    el.innerHTML = `<div class="empty">Error: ${e}</div>`;
  }
}

async function loadReportsEmitRecent(days, tier) {
  const summary = document.getElementById('reports-emit-recent-summary');
  const list    = document.getElementById('reports-emit-recent-list');
  summary.innerHTML = '<div class="muted">Loading…</div>';
  list.innerHTML    = '';
  try {
    const url = `/reports/emit_recent?days=${days}` + (tier ? `&tier=${tier}` : '');
    const r = await fetch(url);
    const body = await r.json();
    const t = body.totals || {};
    summary.innerHTML = `
      <div class="summary-item">
        <span class="summary-label">Fixtures touched</span>
        <span class="summary-value">${fmt.num(body.fixtures_count)}</span>
      </div>
      <div class="summary-item">
        <span class="summary-label">Legs emitted</span>
        <span class="summary-value">${fmt.num(body.legs_count)}</span>
      </div>
      <div class="summary-item">
        <span class="summary-label">Wins</span>
        <span class="summary-value positive">${t.wins || 0}</span>
      </div>
      <div class="summary-item">
        <span class="summary-label">Voids</span>
        <span class="summary-value">${t.voids || 0}</span>
      </div>
      <div class="summary-item">
        <span class="summary-label">Losses</span>
        <span class="summary-value negative">${t.losses || 0}</span>
      </div>
      <div class="summary-item">
        <span class="summary-label">Pending</span>
        <span class="summary-value muted">${t.pending || 0}</span>
      </div>
    `;
    if (!body.fixtures || body.fixtures.length === 0) {
      list.innerHTML = '<div class="empty">No emit fixtures in window.</div>';
      return;
    }
    list.innerHTML = body.fixtures.map(fx => renderEmitRecentFixtureCard(fx)).join('');
  } catch (e) {
    summary.innerHTML = `<div class="empty">Error: ${e}</div>`;
  }
}

function renderEmitRecentFixtureCard(fx) {
  const dt = fx.kickoff_utc ? parseKickoffUtc(fx.kickoff_utc) : null;
  const date = dt ? dt.toLocaleDateString() : '—';
  const time = dt ? dt.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}) : '';
  const tierBadge = fx.tier
    ? `<span class="chip chip-tier chip-tier-${fx.tier}">T${fx.tier}</span>`
    : '<span class="chip chip-tier chip-tier-na">untiered</span>';
  const score = (fx.home_score != null && fx.away_score != null)
    ? `${fx.home_score} - ${fx.away_score}`
    : '—';
  const corners = (fx.home_corners != null && fx.away_corners != null)
    ? `${fx.home_corners + fx.away_corners} corners`
    : 'corners n/a';
  const totals = fx.totals || {};
  const legRows = (fx.legs || []).map(leg => {
    const outCls = leg.outcome_label === 'WIN' ? 'outcome-win'
                : leg.outcome_label === 'LOSS' ? 'outcome-loss'
                : leg.outcome_label === 'VOID' ? 'outcome-void'
                : 'outcome-pending';
    return `
      <div class="settled-pick-row">
        <span class="settled-market">${marketLabel(leg.market)}</span>
        <span class="settled-pick">${leg.pick}</span>
        <span class="settled-price">@ ${fmt.odd(leg.pick_odd)}</span>
        <span class="settled-outcome ${outCls}">${leg.outcome_label}</span>
      </div>
    `;
  }).join('');
  return `
    <div class="card settled-card">
      <div class="card-header">
        <span>${fx.league || '—'} ${fx.country ? `· ${fx.country}` : ''} ${tierBadge}</span>
        <span>${date} ${time}</span>
      </div>
      <div class="card-fixture">${fx.home_team || '?'} vs ${fx.away_team || '?'}</div>
      <div class="settled-result-line">
        <span class="settled-score">${score}</span>
        <span class="muted">·</span>
        <span class="muted">${corners}</span>
        <span class="muted">·</span>
        <span class="chip">${fx.partition_key || '—'}</span>
      </div>
      <div class="settled-picks">${legRows}</div>
      <div class="settled-fixture-totals">
        <span>${totals.wins || 0}W · ${totals.voids || 0}V · ${totals.losses || 0}L · ${totals.pending || 0}P</span>
      </div>
    </div>
  `;
}

// ---- Inspector single-fixture ----
function openInspector(picks) {
  const list = Array.isArray(picks) ? picks : [picks];
  if (list.length === 0) return;
  const p0 = list[0];
  document.querySelector('[data-tab="inspector"]').click();
  const c = document.getElementById('inspector-selected');
  if (!c) return;

  const dt = parseKickoffUtc(p0.kickoff_utc);
  const tierBadge = p0.tier
    ? `<span class="chip chip-tier chip-tier-${p0.tier}">T${p0.tier}</span>`
    : '<span class="chip chip-tier chip-tier-na">untiered</span>';

  const byMarket = new Map();
  for (const p of list) {
    if (!byMarket.has(p.market)) byMarket.set(p.market, []);
    byMarket.get(p.market).push(p);
  }
  const order = ['total_goals', 'total_corners', 'dnb', 'alpha_win', 'goals_nl'];
  const marketBlocks = order
    .filter(m => byMarket.has(m))
    .map(m => {
      const ps = byMarket.get(m);
      ps.sort((a, b) => ((a.pick_leg === 'natural') ? -1 : 1));
      const rows = ps.map(p => `
        <div class="inspector-pick-row">
          <span class="leg-dot">${p.pick_leg === 'natural' ? '●' : p.pick_leg === 'system' ? '○' : '◆'}</span>
          <span>${p.pick}</span>
          <span class="muted">${p.pick_leg ? `(${p.pick_leg})` : ''}</span>
          <span>@ ${fmt.odd(p.pick_odd)}</span>
          ${p.pick_odd_derived ? '<span class="leg-derived">derived</span>' : ''}
        </div>
      `).join('');
      return `
        <div class="inspector-market">
          <h4>${marketLabel(m)}</h4>
          ${rows}
        </div>
      `;
    }).join('');

  c.innerHTML = `
    <h3 class="section-h">Selected fixture (clicked from Picks)</h3>
    <div class="card" style="cursor: default;">
      <div class="card-header">
        <span>${p0.league || '—'} ${p0.country ? `· ${p0.country}` : ''} ${tierBadge}</span>
        <span>${dt ? dt.toLocaleString() : ''}</span>
      </div>
      <div class="card-fixture">${p0.home_team} vs ${p0.away_team}</div>
      <div class="card-chips">
        <span class="chip chip-premium">Promoted</span>
        <span class="chip">${p0.partition_key}</span>
        <span class="chip">${p0.draw_zone}</span>
      </div>
      <div class="inspector-markets">${marketBlocks}</div>
    </div>
    <h3 class="section-h">Similar historical fixtures <span class="muted" id="inspector-similar-cell"></span></h3>
    <div id="inspector-similar-list"><div class="muted">Loading similar-odds history…</div></div>
  `;
  if (p0.partition_key) {
    // V3 partition_key is 2-part "zone:bts" (DF removed in Session 19 restore).
    const parts = p0.partition_key.split(':');
    const [zone, bts] = parts.length >= 3 ? [parts[0], parts[2]] : parts;
    if (zone && bts) loadInspectorSimilar(zone, bts);
  }
}

// ---- Upcoming fixtures ----
async function loadUpcoming() {
  const summary = document.getElementById('upcoming-summary');
  const list = document.getElementById('upcoming-list');
  const days = document.getElementById('upcoming-days').value || 7;
  const tier = document.getElementById('upcoming-tier').value;
  summary.textContent = 'Loading…';
  list.innerHTML = '';
  try {
    const url = `/upcoming?days=${days}` + (tier ? `&tier=${tier}` : '');
    const r = await fetch(url);
    const body = await r.json();
    renderUpcomingSummary(summary, body);
    renderUpcomingList(list, body.data || []);
  } catch (e) {
    summary.textContent = `Error: ${e.message}`;
  }
}

function renderUpcomingSummary(el, body) {
  const s = body.summary || {};
  const tiers = s.by_tier || {};
  el.innerHTML = `
    <div class="summary-grid">
      <div><label>Total fixtures</label><span>${body.count}</span></div>
      <div><label>Tier 1</label><span>${tiers['1'] || 0}</span></div>
      <div><label>Tier 2</label><span>${tiers['2'] || 0}</span></div>
      <div><label>Tier 3</label><span>${tiers['3'] || 0}</span></div>
      <div><label>★ Promoted</label><span class="positive">${s.partition_promoted || 0}</span></div>
    </div>
  `;
}

function renderUpcomingList(el, rows) {
  if (!rows || rows.length === 0) {
    el.innerHTML = '<div class="empty">No fixtures in this window.</div>';
    return;
  }
  el.innerHTML = rows.map(r => renderUpcomingCard(r)).join('');
}

function renderUpcomingCard(r) {
  const dt = r.kickoff_utc ? parseKickoffUtc(r.kickoff_utc) : null;
  const date = dt ? dt.toLocaleDateString() : '—';
  const time = dt ? dt.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}) : '';
  const promoted = r.partition_promoted
    ? '<span class="chip chip-premium">PROMOTE</span>'
    : '';
  const tierLabel = r.tier ? `T${r.tier}` : '—';
  const zg = r.zone_group || '—';
  const bts = r.bts_v2 || '—';
  return `
    <div class="card">
      <div class="card-header">
        <span>${r.league_name || '—'} · ${tierLabel}</span>
        <span>${date} ${time}</span>
      </div>
      <div class="card-fixture">${r.home_team_name || '?'} vs ${r.away_team_name || '?'}</div>
      <div class="card-pick">
        Home ${fmt.odd(r.home_odd)} · Draw ${fmt.odd(r.draw_odd)} · Away ${fmt.odd(r.away_odd)}
      </div>
      <div class="card-chips">
        ${promoted}
        <span class="chip">${zg}</span>
        <span class="chip">${bts}</span>
        <span class="chip">BTS Yes ${fmt.odd(r.btts_yes_odd)} / No ${fmt.odd(r.btts_no_odd)}</span>
      </div>
    </div>
  `;
}

// ---- Results + Livescores ----
let _liveInterval = null;

async function loadResults() {
  const days    = document.getElementById('results-days').value || 7;
  const summary = document.getElementById('results-summary');
  const list    = document.getElementById('results-list');
  summary.innerHTML = '<div class="muted">Loading…</div>';
  list.innerHTML    = '';
  try {
    const r    = await fetch(`/api/results?days=${days}`);
    const body = await r.json();
    summary.innerHTML = `
      <div class="summary-item">
        <span class="summary-label">Settled fixtures</span>
        <span class="summary-value">${fmt.num(body.count)}</span>
      </div>
      <div class="summary-item">
        <span class="summary-label">Window</span>
        <span class="summary-value">${body.window_days}d</span>
      </div>
    `;
    if (!body.fixtures || body.fixtures.length === 0) {
      list.innerHTML = '<div class="empty">No settled fixtures in this window. Run fetch_results.py after match days.</div>';
      return;
    }
    list.innerHTML = body.fixtures.map(fx => renderResultCard(fx)).join('');
  } catch (e) {
    summary.innerHTML = `<div class="empty">Error: ${e}</div>`;
  }
}

function renderResultCard(fx) {
  const dateStr  = (fx.date || '').slice(0, 10);
  const tierBadge = fx.tier
    ? `<span class="chip chip-tier chip-tier-${fx.tier}">T${fx.tier}</span>` : '';
  const score   = `${fx.home_score} — ${fx.away_score}`;
  const goals   = fx.total_goals != null ? `${fx.total_goals}g` : '';
  const corners = (fx.home_corners != null && fx.away_corners != null)
    ? `${fx.home_corners}/${fx.away_corners}c` : '';
  const cell = (fx.draw_zone && fx.bts_pocket)
    ? `<span class="chip">${fx.draw_zone}</span><span class="chip">${fx.bts_pocket}</span>` : '';

  const pickRows = (fx.picks || []).map(p => {
    const outCls = p.outcome === 'WIN'  ? 'outcome-win'
                : p.outcome === 'LOSS' ? 'outcome-loss'
                : p.outcome === 'VOID' ? 'outcome-void'
                : 'outcome-pending';
    return `
      <div class="settled-pick-row">
        <span class="settled-market">${marketLabel(p.market)}</span>
        <span class="settled-pick">${p.pick}</span>
        <span class="settled-price">@ ${fmt.odd(p.pick_odd)}</span>
        <span class="settled-outcome ${outCls}">${p.outcome || 'PENDING'}</span>
      </div>`;
  }).join('');

  return `
    <div class="card settled-card">
      <div class="card-header">
        <span>${fx.league || '—'}${fx.country ? ` · ${fx.country}` : ''} ${tierBadge}</span>
        <span class="muted">${dateStr}</span>
      </div>
      <div class="card-fixture">${fx.home_team || '?'} vs ${fx.away_team || '?'}</div>
      <div class="settled-result-line">
        <span class="settled-score">${score}</span>
        ${goals   ? `<span class="muted">· ${goals}</span>` : ''}
        ${corners ? `<span class="muted">· ${corners}</span>` : ''}
        ${cell}
      </div>
      ${pickRows ? `<div class="settled-picks">${pickRows}</div>` : ''}
    </div>`;
}

async function loadLivescores() {
  const wrap  = document.getElementById('results-livescores-wrap');
  const list  = document.getElementById('results-livescores-list');
  const badge = document.getElementById('results-live-badge');
  const count = document.getElementById('results-live-count');
  try {
    const r    = await fetch('/api/livescores');
    const body = await r.json();
    if (body.error || !body.fixtures || body.fixtures.length === 0) {
      wrap.style.display  = 'none';
      badge.style.display = 'none';
      return;
    }
    wrap.style.display  = '';
    badge.style.display = '';
    count.textContent   = `(${body.fixtures.length} in play)`;
    list.innerHTML = body.fixtures.map(fx => `
      <div class="card live-card">
        <div class="card-header">
          <span>${fx.home_team || '?'} vs ${fx.away_team || '?'}</span>
          <span class="chip ${fx.status === 'FT' ? 'chip-positive' : 'chip-emerging'}">
            ${fx.status || '—'}${fx.minute ? ` ${fx.minute}'` : ''}
          </span>
        </div>
        <div class="settled-score">${fx.home_score ?? '—'} — ${fx.away_score ?? '—'}</div>
      </div>`).join('');
    if (body.auto_written > 0) loadResults();
  } catch (_) { /* best-effort */ }
}

function startLivePolling() {
  if (_liveInterval) return;
  loadLivescores();
  _liveInterval = setInterval(loadLivescores, 60000);
}

function stopLivePolling() {
  if (_liveInterval) { clearInterval(_liveInterval); _liveInterval = null; }
}

// ---- Inspector similar-odds ----
async function loadInspectorSimilar(zone, bts) {
  const el = document.getElementById('inspector-similar-list');
  const cellEl = document.getElementById('inspector-similar-cell');
  if (!el) return;
  if (cellEl) cellEl.textContent = `${zone} · ${bts}`;
  try {
    const r    = await fetch(`/inspector/similar?zone=${encodeURIComponent(zone)}&bts=${encodeURIComponent(bts)}&limit=30`);
    const body = await r.json();
    if (body.error || !body.fixtures || body.fixtures.length === 0) {
      el.innerHTML = '<div class="muted">No historical data for this cell yet (draw_zone migration may not have run).</div>';
      return;
    }
    const hitLine = body.threeway_hit != null
      ? `<span class="chip chip-premium">${body.threeway_hit}% threeway hit · n=${body.sample_n}</span>` : '';
    const pick   = body.threeway_pick || '—';
    el.innerHTML = `
      <div style="margin-bottom:8px">${hitLine} <span class="chip muted">${pick}</span></div>
      <table>
        <thead><tr>
          <th>Date</th><th>Fixture</th><th>Score</th><th>Result</th><th>Pick</th>
        </tr></thead>
        <tbody>
        ${body.fixtures.map(fx => {
          const green = fx.tw_green;
          const resCls = green ? 'positive' : 'negative';
          const resLabel = green ? 'GREEN' : 'red';
          const pOut = (fx.picks || []).map(p =>
            `<span class="settled-outcome ${p.outcome === 'WIN' ? 'outcome-win' : p.outcome === 'LOSS' ? 'outcome-loss' : p.outcome === 'VOID' ? 'outcome-void' : 'outcome-pending'}">${p.outcome || 'no pick'}</span>`
          ).join(' ');
          return `<tr>
            <td class="muted">${(fx.date || '').slice(0, 10)}</td>
            <td>${fx.home_team} vs ${fx.away_team}</td>
            <td><strong>${fx.home_score} — ${fx.away_score}</strong></td>
            <td class="${resCls}">${resLabel}</td>
            <td>${pOut || '<span class="muted">—</span>'}</td>
          </tr>`;
        }).join('')}
        </tbody>
      </table>`;
  } catch (e) {
    el.innerHTML = `<div class="empty">Error: ${e}</div>`;
  }
}

async function loadInspectorDrift(days) {
  const summary = document.getElementById('inspector-drift-summary');
  const tbl     = document.getElementById('inspector-drift-table');
  summary.innerHTML = '<div class="muted">Loading…</div>';
  tbl.innerHTML     = '';
  try {
    const r = await fetch(`/inspector/partition_drift?recent_days=${days}`);
    const body = await r.json();
    const s = body.summary || {};
    summary.innerHTML = `
      <div class="summary-item">
        <span class="summary-label">Stable</span>
        <span class="summary-value positive">${s.stable || 0}</span>
      </div>
      <div class="summary-item">
        <span class="summary-label">Watch</span>
        <span class="summary-value">${s.watch || 0}</span>
      </div>
      <div class="summary-item">
        <span class="summary-label">Drifting</span>
        <span class="summary-value negative">${s.drifting || 0}</span>
      </div>
      <div class="summary-item">
        <span class="summary-label">No data</span>
        <span class="summary-value muted">${s.no_data || 0}</span>
      </div>
    `;
    if (!body.rows || body.rows.length === 0) {
      tbl.innerHTML = '<div class="empty">No PROMOTE cells found.</div>';
      return;
    }
    tbl.innerHTML = `
      <table>
        <thead><tr>
          <th>Zone</th><th>BTS</th>
          <th class="numeric">Historical n</th>
          <th class="numeric">Hist hit %</th>
          <th class="numeric">Recent n</th>
          <th class="numeric">Recent hit %</th>
          <th class="numeric">Gap pp</th>
          <th>Flag</th>
        </tr></thead>
        <tbody>
        ${body.rows.map(r => {
          const flagCls = r.flag === 'drifting' ? 'row-drift-critical'
                       : r.flag === 'watch'    ? 'row-drift-warning'
                       : '';
          const flagChip = r.flag === 'drifting' ? '<span class="chip chip-negative">drifting</span>'
                       : r.flag === 'watch'      ? '<span class="chip chip-emerging">watch</span>'
                       : r.flag === 'no_data'    ? '<span class="chip muted">no data</span>'
                       :                            '<span class="chip chip-positive">stable</span>';
          return `
          <tr class="${flagCls}">
            <td>${r.zone}</td>
            <td>${r.bts_v2}</td>
            <td class="numeric">${fmt.num(r.historical_n)}</td>
            <td class="numeric">${r.historical_hit != null ? r.historical_hit + '%' : '—'}</td>
            <td class="numeric">${fmt.num(r.recent_n)}</td>
            <td class="numeric">${r.recent_hit != null ? r.recent_hit + '%' : '—'}</td>
            <td class="numeric ${(r.gap_pp || 0) < 0 ? 'negative' : 'positive'}">${r.gap_pp != null ? (r.gap_pp >= 0 ? '+' : '') + r.gap_pp : '—'}</td>
            <td>${flagChip}</td>
          </tr>`;
        }).join('')}
        </tbody>
      </table>
    `;
  } catch (e) {
    summary.innerHTML = `<div class="empty">Error: ${e}</div>`;
  }
}

// ---- Tab loader dispatch ----
function loadTab(name) {
  if (name !== 'results') stopLivePolling();
  if (name === 'today')      loadToday();
  else if (name === 'picks')     loadPicks();
  else if (name === 'upcoming')  loadUpcoming();
  else if (name === 'analysis')  loadAnalysis();
  else if (name === 'inspector') loadInspector();
  else if (name === 'reports')   loadReports();
  else if (name === 'stats')     loadStats();
  else if (name === 'results') { loadResults(); startLivePolling(); }
}

// ---- Wire up buttons ----
document.getElementById('today-refresh').addEventListener('click', loadToday);
document.getElementById('picks-refresh').addEventListener('click', loadPicks);
const picksDaysInput = document.getElementById('picks-days');
const picksCsv = document.getElementById('picks-csv');
function syncPicksCsv() {
  const d = picksDaysInput.value || 3;
  picksCsv.href = `/reports/paper_trading.csv?days=${d}`;
}
picksDaysInput.addEventListener('input', syncPicksCsv);
syncPicksCsv();
document.getElementById('analysis-refresh').addEventListener('click', loadAnalysis);
document.querySelectorAll('.btn-subtab').forEach(btn => {
  btn.addEventListener('click', () => {
    if (!_foundationData) return;
    document.querySelectorAll('.btn-subtab').forEach(b => b.classList.toggle('active', b === btn));
    renderFoundationTable(document.getElementById('analysis-table-wrap'), _foundationData[btn.dataset.tier]);
  });
});
document.getElementById('upcoming-refresh').addEventListener('click', loadUpcoming);
document.getElementById('inspector-refresh').addEventListener('click', loadInspector);
document.getElementById('inspector-days').addEventListener('change', loadInspector);
document.getElementById('reports-refresh').addEventListener('click', loadReports);
document.getElementById('reports-days').addEventListener('change', loadReports);
document.getElementById('reports-tier').addEventListener('change', loadReports);
document.getElementById('results-refresh').addEventListener('click', loadResults);
document.getElementById('results-days').addEventListener('change', loadResults);
document.getElementById('results-livescores-btn').addEventListener('click', loadLivescores);

// ---- Boot: V4 default tab is Picks ----
refreshHealth();
setInterval(refreshHealth, 30000);
loadPicks();
