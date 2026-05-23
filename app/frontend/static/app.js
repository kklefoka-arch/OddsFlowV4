/* OddsFlow V3 operator portal */
(function () {
  'use strict';

  function qs(s,c){return (c||document).querySelector(s);}
  function qsa(s,c){return (c||document).querySelectorAll(s);}

  function showMsg(el,t,err){
    if(!el)return; el.textContent=t;
    el.className='ingest-msg '+(err?'ingest-msg-error':'ingest-msg-ok');
    el.classList.remove('hidden');
  }

  /* Foundation tier tabs */
  qsa('.tab-bar:not(.filter-bar):not(.insp-zone-tab-bar) .tab-btn').forEach(function(btn){
    btn.addEventListener("click",function(){
      var t=btn.dataset.target; if(!t)return;
      btn.closest('.card').querySelectorAll('.tier-table-wrap').forEach(function(p){p.classList.toggle('hidden',p.id!==t);});
      btn.closest('.tab-bar').querySelectorAll('.tab-btn').forEach(function(b){b.classList.toggle('active',b===btn);});
    });
  });

  /* Fixture status filter */
  qsa('.filter-bar .tab-btn').forEach(function(btn){
    btn.addEventListener("click",function(){
      var f=btn.dataset.filter;
      qsa('.fixture-row').forEach(function(row){row.classList.toggle('hidden',f!=='all'&&row.dataset.status!==f);});
      btn.closest('.filter-bar').querySelectorAll('.tab-btn').forEach(function(b){b.classList.toggle('active',b===btn);});
    });
  });

  /* Inspector zone strip tabs */
  qsa('.insp-zone-tab-bar .insp-zone-btn').forEach(function(btn){
    btn.addEventListener("click",function(){
      var k=btn.dataset.zstrip;
      document.querySelectorAll('.zone-strip[id]').forEach(function(s){s.classList.toggle('hidden',s.id!=='zstrip-'+k);});
      btn.closest('.insp-zone-tab-bar').querySelectorAll('.insp-zone-btn').forEach(function(b){b.classList.toggle('active',b===btn);});
    });
  });

  /* Inspector lens switcher (PRE-MATCH / POST-MATCH) */
  qsa('.lens-btn[data-lens]').forEach(function(btn){
    btn.addEventListener('click', function(){
      var k = btn.dataset.lens;
      qsa('.lens-btn').forEach(function(b){ b.classList.toggle('active', b === btn); });
      var pre = qs('#lens-prematch'), post = qs('#lens-postmatch');
      if(pre)  pre.classList.toggle('hidden',  k !== 'prematch');
      if(post) post.classList.toggle('hidden', k !== 'postmatch');
    });
  });

  /* Inspector findings feed tabs */
  qsa('.tab-btn[data-ifeed]').forEach(function(btn){
    btn.addEventListener("click",function(){
      var k=btn.dataset.ifeed;
      qsa('.findings-feed').forEach(function(f){f.classList.toggle('hidden',f.id!=='ifeed-'+k);});
      btn.closest('.tab-bar').querySelectorAll('.tab-btn').forEach(function(b){b.classList.toggle('active',b===btn);});
    });
  });

  /* Hit% colouring */
  qsa('.hit-pct').forEach(function(cell){
    var v=parseFloat(cell.textContent); if(isNaN(v))return;
    if(v>=72)cell.classList.add('hit-high'); else if(v>=67)cell.classList.add('hit-mid');
  });

  /* Zone/BTS classifier */
  function zoneOf(d){if(!d||d<2.70)return null;if(d<3.40)return 'strong';if(d<4.10)return 'standard';if(d<4.80)return 'low';return 'one_sided';}
  function btsOf(y,n){if(!y||!n)return null;var f=y<=n;if(f)return y<1.50?'strong over':'slight over';return n<1.50?'strong under':'slight under';}

  /* Ingest form */
  var igf=qs('#add-fixture-form');
  if(igf){
    function updPrev(){
      var d=parseFloat(igf.querySelector("[name=draw_odd]").value);
      var y=parseFloat(igf.querySelector("[name=btts_yes_odd]").value);
      var n=parseFloat(igf.querySelector("[name=btts_no_odd]").value);
      var zone=zoneOf(d),bts=btsOf(y,n),pv=qs('#odds-preview');
      if(zone||bts){pv&&pv.classList.remove('hidden');var pz=qs('#preview-zone');if(pz)pz.textContent=zone?zone.replace('_',' '):'-';var pb=qs('#preview-bts');if(pb)pb.textContent=bts||'-';}
      else{pv&&pv.classList.add('hidden');}
    }
    ["draw_odd","btts_yes_odd","btts_no_odd"].forEach(function(nm){var el=igf.querySelector("[name="+nm+"]");if(el)el.addEventListener("input",updPrev);});
    igf.addEventListener("submit",function(e){
      e.preventDefault();
      var fd=new FormData(igf),pl={};
      fd.forEach(function(v,k){if(v==='')return;pl[k]=(k==='date')?v:Number(v);});
      fetch("/api/fixtures/add",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(pl)})
      .then(function(r){return r.json();})
      .then(function(d){if(d.detail)throw new Error(d.detail);showMsg(qs('#ingest-msg'),'Added - Zone: '+(d.draw_zone||'-')+' / BTS: '+(d.bts_pocket||'-'),false);igf.reset();var p=qs('#odds-preview');if(p)p.classList.add('hidden');setTimeout(function(){window.location.reload();},1200);})
      .catch(function(err){showMsg(qs('#ingest-msg'),'Error: '+err.message,true);});
    });
  }

  /* Fixture card click → cell signal panel */
  var csp = qs('#cell-signal-panel');
  var activeCard = null;
  function promoteBadge(status) {
    var map = {
      'PROMOTE':           '<span class="badge-fire">&#9650; FIRE</span>',
      'PROMOTE_TOLERANCE': '<span class="badge-tol">&#9650; TOL</span>',
      'HOLD':              '<span class="badge-hold">HOLD</span>',
      'MEASURING':         '<span class="badge-meas">MEAS</span>',
    };
    return map[status] || '<span class="badge-no">—</span>';
  }
  function hitClass(v) {
    if (v >= 72) return 'hit-high';
    if (v >= 67) return 'hit-cyan';
    if (v >= 60) return 'hit-mid';
    return '';
  }
  function renderCSP(cell) {
    if (!csp) return;
    var z = (cell.zone||'').replace(/_/g,' ').toUpperCase();
    var b = (cell.bts_pocket||'').replace(/_/g,' ').toUpperCase();
    var g = cell.gn_hit != null ? cell.gn_hit.toFixed(1) : '—';
    var c = cell.cn_hit != null ? cell.cn_hit.toFixed(1) : '—';
    var t = cell.threeway_hit != null ? cell.threeway_hit.toFixed(1) : '—';
    csp.innerHTML =
      '<div class="csp-header">' +
        '<span class="csp-title">' + z + ' &nbsp;/&nbsp; ' + b + '</span>' +
        '<button class="csp-close" id="csp-close-btn">&#10005;</button>' +
      '</div>' +
      '<div class="csp-metrics">' +
        '<div class="csp-metric"><span class="csp-metric-label">Goals hit%</span>' +
          '<span class="csp-metric-value ' + hitClass(cell.gn_hit) + '">' + g + '%</span></div>' +
        '<div class="csp-metric"><span class="csp-metric-label">Corners hit%</span>' +
          '<span class="csp-metric-value ' + hitClass(cell.cn_hit) + '">' + c + '%</span></div>' +
        '<div class="csp-metric"><span class="csp-metric-label">3-Way hit%</span>' +
          '<span class="csp-metric-value ' + hitClass(cell.threeway_hit) + '">' + t + '%</span></div>' +
      '</div>' +
      '<div class="csp-footer">' +
        promoteBadge(cell.cell_status) +
        '<span class="csp-n">n=' + (cell.n_fixtures||0) + ' fixtures</span>' +
        '<span class="csp-n">' + (cell.n_pct_of_zone||0).toFixed(1) + '% of zone</span>' +
      '</div>';
    csp.classList.remove('hidden');
    var closeBtn = qs('#csp-close-btn');
    if (closeBtn) closeBtn.addEventListener('click', function() {
      csp.classList.add('hidden');
      if (activeCard) { activeCard.classList.remove('fx-card-active'); activeCard = null; }
    });
  }
  qsa('.fx-card[data-zone]').forEach(function(card) {
    card.addEventListener('click', function(e) {
      if (e.target.classList.contains('btn-settle')) return;
      var zone = card.dataset.zone, bts = card.dataset.bts;
      if (!zone || !bts) return;
      if (activeCard) activeCard.classList.remove('fx-card-active');
      if (activeCard === card && !csp.classList.contains('hidden')) {
        csp.classList.add('hidden'); activeCard = null; return;
      }
      activeCard = card; card.classList.add('fx-card-active');
      fetch('/api/inspector/cell?zone=' + encodeURIComponent(zone) + '&bts=' + encodeURIComponent(bts))
        .then(function(r) { return r.json(); })
        .then(function(data) { renderCSP(data); })
        .catch(function() {
          if (csp) { csp.textContent = 'No cell data for this classification yet.'; csp.classList.remove('hidden'); }
        });
    });
  });

  /* Inspector zone bar chart */
  var chartCanvas = qs('#insp-zone-chart');
  if (chartCanvas && typeof Chart !== 'undefined') {
    fetch('/api/inspector')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        var zones = data.zone_summary || [];
        var labels = zones.map(function(z) { return z.zone.replace(/_/g,' ').toUpperCase(); });
        var goals   = zones.map(function(z) { return z.avg_goals; });
        var corners = zones.map(function(z) { return z.avg_corners; });
        var way3    = zones.map(function(z) { return z.avg_3way; });
        new Chart(chartCanvas, {
          type: 'bar',
          data: {
            labels: labels,
            datasets: [
              { label: 'Goals%',   data: goals,   backgroundColor: 'rgba(245,166,35,0.7)',  borderRadius: 3 },
              { label: 'Corners%', data: corners, backgroundColor: 'rgba(0,214,143,0.7)',   borderRadius: 3 },
              { label: '3-Way%',   data: way3,    backgroundColor: 'rgba(0,200,255,0.55)',  borderRadius: 3 },
            ]
          },
          options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { labels: { color: '#6A8CAA', font: { family: 'Nunito', size: 11 } } } },
            scales: {
              x: { ticks: { color: '#6A8CAA', font: { family: 'Nunito', size: 11 } }, grid: { color: '#182030' } },
              y: { min: 40, max: 100, ticks: { color: '#6A8CAA', font: { family: 'JetBrains Mono', size: 10 } }, grid: { color: '#182030' } }
            }
          }
        });
      });
  }

  /* Settle modal */
  var ov=qs('#settle-overlay'),cBtn=qs('#settle-close'),sBtn=qs('#settle-submit'),fid=qs('#settle-fixture-id');
  function openS(id){if(!ov)return;fid.value=id;['#settle-home','#settle-away','#settle-hc','#settle-ac'].forEach(function(s){var e=qs(s);if(e)e.value='';});var m=qs('#settle-msg');if(m)m.classList.add('hidden');ov.classList.remove('hidden');qs('#settle-home').focus();}
  function closeS(){if(ov)ov.classList.add('hidden');}
  if(cBtn)cBtn.addEventListener("click",closeS);
  if(ov)ov.addEventListener("click",function(e){if(e.target===ov)closeS();});
  qsa('.btn-settle').forEach(function(btn){btn.addEventListener('click',function(){openS(btn.dataset.id);});});
  if(sBtn){sBtn.addEventListener('click',function(){
    var id=fid.value,hg=qs('#settle-home').value,ag=qs('#settle-away').value,hc=qs('#settle-hc').value,ac=qs('#settle-ac').value,msg=qs('#settle-msg');
    if(hg===''||ag===''){showMsg(msg,'Goals required.',true);return;}
    var pl={home_score:parseInt(hg,10),away_score:parseInt(ag,10)};
    if(hc!=='')pl.home_corners=parseInt(hc,10);if(ac!=='')pl.away_corners=parseInt(ac,10);
    sBtn.disabled=true;
    fetch("/api/fixtures/settle/"+id,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(pl)})
    .then(function(r){return r.json();})
    .then(function(d){if(d.detail)throw new Error(d.detail);showMsg(msg,'Settled '+d.home_score+' - '+d.away_score,false);setTimeout(function(){window.location.reload();},900);})
    .catch(function(err){showMsg(msg,'Error: '+err.message,true);sBtn.disabled=false;});
  });}

})();
