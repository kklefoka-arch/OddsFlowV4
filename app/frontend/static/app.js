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
