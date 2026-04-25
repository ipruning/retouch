import os

DEFAULT_MODEL = "gemini-3.1-flash-image-preview"
GEN_DIR = "generated"
os.makedirs(GEN_DIR, exist_ok=True)

PROVIDERS = {
    "google": {
        "name": "Google 官方",
        "models": [
            ("gemini-3.1-flash-image-preview", "Gemini 3.1 Flash Image"),
            ("gemini-3-pro-image-preview", "Gemini 3 Pro Image"),
        ],
    },
    "apiyi": {
        "name": "Apiyi 代理",
        "models": [
            ("gemini-2.5-flash-image", "Gemini 2.5 Flash Image"),
            ("gemini-3-pro-image-preview", "Gemini 3 Pro Image"),
            ("nano-banana-pro", "Nano Banana Pro"),
        ],
    },
}

# Batch concurrency / lifecycle
USER_SEM_LIMIT = 3
GLOBAL_SEM_LIMIT = 10
BATCH_MAX_IMAGES = 50
USER_MAX_BATCHES = 3
BATCH_TTL = 3600

EXTRA_CSS = """\
/* ── Mobile responsive ── */
@media(max-width:480px){
  #key-status { display:none; }
  .uk-container { padding-left:12px !important; padding-right:12px !important; }
}
/* ── Global border-radius override (8px for all UIkit components) ── */
.uk-card, .uk-modal-dialog, .uk-textarea, .uk-input, .uk-select { border-radius:8px !important; }
.uk-btn { border-radius:8px !important; }
.uk-card-header:first-child { border-radius:8px 8px 0 0; }
.uk-card-footer:last-child { border-radius:0 0 8px 8px; }
/* ── Button loading state alignment ── */
.btn-loading { display:inline-flex !important; align-items:center; gap:6px; }

.ctx-turn { display:flex; gap:6px; align-items:center; padding:4px 0; font-size:13px; }
.ctx-role { font-weight:600; white-space:nowrap; color:var(--color-muted-foreground); }
.ctx-parts { display:flex; flex-wrap:wrap; gap:4px; align-items:center; }
.ctx-text { color:var(--color-muted-foreground); max-width:300px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.ctx-thumb { width:28px; height:28px; border-radius:8px; object-fit:cover; }
.ctx-img-label { font-size:11px; color:var(--color-muted-foreground); }
.ctx-empty { color:var(--color-muted-foreground); font-size:13px; padding:4px 0; }
.upload-preview { display:flex; align-items:center; gap:8px; padding:8px 0; }
.upload-preview.hide { display:none; }
.upload-preview img { width:48px; height:48px; border-radius:8px; object-fit:cover; }
.upload-name { font-size:12px; color:var(--color-muted-foreground); }
.upload-x { background:none; border:none; cursor:pointer; font-size:16px; color:var(--color-muted-foreground); }
.result { margin-top:16px; line-height:1.6; }
.result img { width:100%; border-radius:8px; margin:8px 0; }
.meta { display:flex; flex-wrap:wrap; gap:8px; font-size:12px; color:var(--color-muted-foreground); margin-top:8px; }
.err { padding:12px; border-radius:8px; background:hsl(var(--destructive)/.1); color:hsl(var(--destructive)); font-size:13px; margin-top:8px; }
.cursor-blink { display:inline-block; width:2px; height:16px; background:currentColor;
  margin-left:2px; vertical-align:text-bottom; animation:blink .8s step-end infinite; }
@keyframes blink { 50% { opacity:0; } }
.b-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(90px,1fr)); gap:8px; margin-top:12px; }
.b-thumb { position:relative; border-radius:8px; overflow:hidden; cursor:pointer; aspect-ratio:1; border:2px solid transparent; }
.b-thumb.selected { border-color:hsl(var(--primary)); }
.b-thumb img { width:100%; height:100%; object-fit:cover; }
.b-overlay { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; font-size:22px; pointer-events:none; }
.b-ov-pending { background:rgba(0,0,0,.25); }
.b-ov-running { background:rgba(0,0,0,.35); }
.b-ov-done { background:rgba(0,180,0,.18); }
.b-ov-failed { background:rgba(220,0,0,.22); }
.b-remove { position:absolute; top:2px; right:2px; width:20px; height:20px; border-radius:50%;
  background:rgba(0,0,0,.55); color:#fff; display:flex; align-items:center;
  justify-content:center; font-size:13px; cursor:pointer; }
.b-spin { width:22px; height:22px; border:3px solid rgba(255,255,255,.4);
  border-top-color:#fff; border-radius:50%; animation:spin .7s linear infinite; }
@keyframes spin { to { transform:rotate(360deg); } }
.b-drop { border:2px dashed var(--color-border); border-radius:8px; padding:32px;
  text-align:center; cursor:pointer; transition:border-color .2s; }
.b-drop.over { border-color:hsl(var(--primary)); background:hsl(var(--primary)/.05); }
.b-drop input[type=file] { display:none; }
.b-bar { height:6px; background:var(--color-border); border-radius:3px; overflow:hidden; margin-top:6px; }
.b-bar-fill { height:100%; background:hsl(var(--primary)); transition:width .3s; border-radius:3px; }
.b-bar-fill.has-fail { background:linear-gradient(90deg,hsl(var(--primary)) var(--ok-pct,0%),hsl(var(--destructive)) var(--ok-pct,0%)); }
.b-progress-text { display:flex; justify-content:space-between; font-size:13px; color:var(--color-muted-foreground); }
.b-compare-imgs { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:8px; }
.b-compare-imgs img { width:100%; border-radius:8px; }
.b-compare-label { font-size:12px; color:var(--color-muted-foreground); margin-bottom:4px; }
.b-compare-title { font-weight:600; font-size:14px; }
.b-compare-error { color:hsl(var(--destructive)); font-size:13px; margin-top:8px; }
.b-compare-meta { font-size:12px; color:var(--color-muted-foreground); margin-top:6px; }
"""


KEY_JS = """\
function isDark(){ return document.documentElement.classList.contains('dark'); }
function toggleDark(){
  const html=document.documentElement;
  const dark=!isDark();
  html.classList.toggle('dark',dark);
  const f=JSON.parse(localStorage.getItem('__FRANKEN__')||'{}');
  f.mode=dark?'dark':'light';
  localStorage.setItem('__FRANKEN__',JSON.stringify(f));
  updateDarkBtn();
}
function updateDarkBtn(){
  const btn=document.getElementById('dark-toggle');
  if(btn) btn.innerHTML=isDark()?'☀️':'🌙';
}
document.addEventListener('DOMContentLoaded',updateDarkBtn);
let hasKey=false, curProvider='google', curModel='';
const providerModels={
  google:[
    ['gemini-3.1-flash-image-preview','Gemini 3.1 Flash Image'],
    ['gemini-3-pro-image-preview','Gemini 3 Pro Image'],
  ],
  apiyi:[
    ['gemini-2.5-flash-image','Gemini 2.5 Flash Image'],
    ['gemini-3-pro-image-preview','Gemini 3 Pro Image'],
    ['nano-banana-pro','Nano Banana Pro'],
  ]
};
function toggleKeyModal(){
  UIkit.modal(document.getElementById('key-modal')).toggle();
}
function onProviderChange(sel){
  const p=sel.value;
  const mSel=document.getElementById('model-select');
  mSel.innerHTML='';
  (providerModels[p]||[]).forEach(function(m,i){
    const o=document.createElement('option');
    o.value=m[0]; o.textContent=m[1];
    if(i===0) o.selected=true;
    mSel.appendChild(o);
  });
  const inp=document.getElementById('key-input');
  if(p==='google') inp.placeholder='AIzaSy...';
  else inp.placeholder='sk-...';
}
async function checkKey(){
  try{
    const r=await fetch('/api/user/config');const d=await r.json();
    const st=document.getElementById('key-status');
    if(d.has_key){
      hasKey=true;
      curProvider=d.provider||'google';
      curModel=d.model||'';
      const label=(d.provider==='apiyi'?'Apiyi':'Google')+' '+(d.masked_key||d.masked);
      st.textContent=label; st.className='text-xs text-green-600 mr-1';
      // Update model indicator
      const mi=document.getElementById('model-indicator');
      if(mi) mi.textContent=d.model_label||curModel;
    }else{
      hasKey=false; st.textContent='\u672a\u8bbe\u7f6e'; st.className='text-xs text-muted-foreground mr-1';
      const mi=document.getElementById('model-indicator');
      if(mi) mi.textContent='';
      toggleKeyModal();
    }
  }catch(e){console.error(e);}
}
async function saveKey(){
  const inp=document.getElementById('key-input'),msg=document.getElementById('key-msg');
  const k=inp.value.trim(); if(!k){msg.textContent='\u8bf7\u8f93\u5165 Key';msg.className='text-xs text-destructive mt-2';return;}
  const provider=document.getElementById('provider-select').value;
  const model=document.getElementById('model-select').value;
  msg.textContent='\u9a8c\u8bc1\u4e2d\u2026';msg.className='text-xs text-muted-foreground mt-2';
  document.getElementById('key-save-btn').disabled=true;
  try{
    const r=await fetch('/api/user/config',{method:'PUT',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({api_key:k,provider:provider,model:model})});
    const d=await r.json();
    if(d.ok){
      hasKey=true; curProvider=provider; curModel=model;
      msg.textContent='\u2705 \u5df2\u4fdd\u5b58';msg.className='text-xs text-green-600 mt-2';
      const label=(provider==='apiyi'?'Apiyi':'Google')+' '+(d.masked_key||d.masked);
      document.getElementById('key-status').textContent=label;
      document.getElementById('key-status').className='text-xs text-green-600 mr-1';
      const mi=document.getElementById('model-indicator');
      if(mi) mi.textContent=d.model_label||model;
      inp.value='';
      setTimeout(function(){UIkit.modal(document.getElementById('key-modal')).hide();},800);
    }else{
      msg.textContent=d.error||'\u5931\u8d25';msg.className='text-xs text-destructive mt-2';
    }
  }catch(e){msg.textContent='\u7f51\u7edc\u9519\u8bef';msg.className='text-xs text-destructive mt-2';}
  document.getElementById('key-save-btn').disabled=false;
}
async function clearKey(){
  await fetch('/api/user/config',{method:'DELETE'});
  hasKey=false; curProvider='google'; curModel='';
  document.getElementById('key-status').textContent='\u672a\u8bbe\u7f6e';
  document.getElementById('key-status').className='text-xs text-muted-foreground mr-1';
  document.getElementById('key-msg').textContent='\u5df2\u6e05\u9664';
  document.getElementById('key-msg').className='text-xs text-green-600 mt-2';
  document.getElementById('key-input').value='';
  const mi=document.getElementById('model-indicator');
  if(mi) mi.textContent='';
}
checkKey();
"""

MAIN_JS = (
    KEY_JS
    + """\
let sid=localStorage.getItem('sid')||'',pastedFile=null;
if(!sid){sid=crypto.randomUUID();localStorage.setItem('sid',sid);}

function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function scrollM(){const m=document.getElementById('main');m.scrollTop=m.scrollHeight;}

function renderCtx(ctx){
  const el=document.getElementById('ctx-list');
  const ft=document.getElementById('env-footer');
  if(!ctx||!ctx.turns||ctx.turns.length===0){
    el.innerHTML='<div class="ctx-empty">\u65b0\u5bf9\u8bdd</div>';
    ft.textContent='';return;
  }
  let h='';
  ctx.turns.forEach(function(t){
    h+='<div class="ctx-turn"><span class="ctx-role">'+t.role+'</span><span class="ctx-parts">';
    t.parts.forEach(function(p){
      if(p.type==='text')h+='<span class="ctx-text">'+esc(p.value)+'</span>';
      else if(p.type==='image'){
        if(p.url)h+='<img class="ctx-thumb" src="'+p.url+'">';
        h+='<span class="ctx-img-label">'+Math.round(p.size/1024)+'KB</span>';
      }
    });
    h+='</span></div>';
  });
  el.innerHTML=h;
  if(ctx.total_bytes>0){
    ft.textContent='\u2191 \u4ee5\u4e0a '+ctx.turns.length+' \u8f6e\u5c06\u968f\u65b0\u6d88\u606f\u53d1\u9001\u7ed9\u6a21\u578b \u00b7 '+(ctx.total_bytes/1024/1024).toFixed(1)+'MB';
  }else{ft.textContent='';}
}

function showUpload(file,label){
  const box=document.getElementById('upload-preview');
  box.classList.remove('hide');
  const img=box.querySelector('img');
  const nm=box.querySelector('.upload-name');
  nm.textContent=label;
  const r=new FileReader();r.onload=function(e){img.src=e.target.result;};r.readAsDataURL(file);
}
function clearImage(){
  pastedFile=null;
  const box=document.getElementById('upload-preview');
  box.classList.add('hide');
  const fi=document.getElementById('file');if(fi)fi.value='';
}
function onFile(el){pastedFile=null;if(el.files[0])showUpload(el.files[0],el.files[0].name);}

function newChat(){
  sid=crypto.randomUUID();localStorage.setItem('sid',sid);
  renderCtx(null);
  document.getElementById('result-area').innerHTML='';
  document.getElementById('prompt').value='';clearImage();
}

document.addEventListener('paste',function(e){
  const items=e.clipboardData&&e.clipboardData.items;if(!items)return;
  for(let i=0;i<items.length;i++){
    if(items[i].type.indexOf('image')!==-1){
      e.preventDefault();const blob=items[i].getAsFile();if(!blob)return;
      pastedFile=blob;showUpload(blob,'\u5df2\u7c98\u8d34');return;
    }
  }
});

async function go(){
  if(!hasKey){toggleKeyModal();return;}
  const btn=document.getElementById('btn'),p=document.getElementById('prompt').value.trim();
  if(!p)return;
  const fd=new FormData();fd.append('prompt',p);fd.append('sid',sid);
  const fi=document.getElementById('file');
  if(pastedFile)fd.append('image',pastedFile,'pasted.png');
  else if(fi&&fi.files[0])fd.append('image',fi.files[0]);
  btn.disabled=true;btn.classList.add('btn-loading');btn.innerHTML='<span uk-spinner="ratio:0.6"></span> \u751f\u6210\u4e2d\u2026';
  // Prepare result area
  const ra=document.getElementById('result-area');
  ra.innerHTML='<div class="result" id="cur-result"><span class="cursor-blink"></span></div>';
  scrollM();
  try{
    const r=await fetch('/api/generate/stream',{method:'POST',body:fd});
    const reader=r.body.getReader();
    const decoder=new TextDecoder();
    let buf='';
    const res=document.getElementById('cur-result');
    while(true){
      const {done,value}=await reader.read();
      if(done)break;
      buf+=decoder.decode(value,{stream:true});
      let lines=buf.split(String.fromCharCode(10));
      buf=lines.pop();
      for(const line of lines){
        if(!line.startsWith('data: '))continue;
        const raw=line.slice(6);
        if(raw==='[DONE]')continue;
        let ev;
        try{ev=JSON.parse(raw);}catch(e){continue;}
        if(ev.type==='text'){
          const cur=res.querySelector('.cursor-blink');
          const span=document.createElement('span');
          span.className='streaming-text';
          span.textContent=ev.data;
          if(cur)res.insertBefore(span,cur);else res.appendChild(span);
          scrollM();
        }else if(ev.type==='image'){
          const cur=res.querySelector('.cursor-blink');
          const img=document.createElement('img');
          img.src=ev.data;img.alt='result';
          if(cur)res.insertBefore(img,cur);else res.appendChild(img);
          scrollM();
        }else if(ev.type==='meta'){
          const cur=res.querySelector('.cursor-blink');if(cur)cur.remove();
          const d=document.createElement('div');d.className='meta';d.innerHTML=ev.data;
          res.appendChild(d);
        }else if(ev.type==='context'){
          try{renderCtx(JSON.parse(ev.data));}catch(e){}
        }else if(ev.type==='error'){
          const cur=res.querySelector('.cursor-blink');if(cur)cur.remove();
          res.innerHTML='<div class="err">'+ev.data+'</div>';
        }
      }
    }
    const cur=res.querySelector('.cursor-blink');if(cur)cur.remove();
    res.removeAttribute('id');
    document.getElementById('prompt').value='';clearImage();
    scrollM();
  }catch(e){
    const res=document.getElementById('cur-result');
    if(res)res.innerHTML='<div class="err">'+e.message+'</div>';
  }
  finally{btn.disabled=false;btn.classList.remove('btn-loading');btn.textContent='\u751f\u6210';}
}
document.getElementById('prompt').addEventListener('keydown',function(e){
  if((e.metaKey||e.ctrlKey)&&e.key==='Enter'){e.preventDefault();go();}
});
"""
)

BATCH_JS_BODY = """\
let bFiles=[], bStarted=false, bItems=[], batchId=null, selIdx=-1, pollTimer=null;
const COST_EST=0.05;
const MAX_IMAGES=50;
/* ── file handling ── */
function addFiles(fileList){
  if(bStarted)return;
  for(let i=0;i<fileList.length;i++){
    if(bFiles.length>=MAX_IMAGES){alert('单次最多 '+MAX_IMAGES+' 张图片');break;}
    const f=fileList[i];
    if(!f.type.startsWith('image/'))continue;
    bFiles.push({file:f, url:URL.createObjectURL(f)});
  }
  renderGrid(); updateControls();
}
function removeFile(idx){
  if(bStarted)return;
  URL.revokeObjectURL(bFiles[idx].url);
  bFiles.splice(idx,1);
  if(selIdx===idx){selIdx=-1; hideCompare();}
  else if(selIdx>idx) selIdx--;
  renderGrid(); updateControls();
}
function renderGrid(){
  const g=document.getElementById('b-grid'); let h='';
  bFiles.forEach(function(bf,i){
    const cls = i===selIdx ? 'b-thumb selected' : 'b-thumb';
    const ovCls = bf.ov||'';
    const ovContent = bf.ovIcon||'';
    h+='<div class="'+cls+'" data-i="'+i+'" onclick="thumbClick('+i+')">'+
       '<img src="'+bf.url+'">'+
       '<div class="b-overlay '+ovCls+'">'+ovContent+'</div>';
    if(!bStarted) h+='<div class="b-remove" onclick="event.stopPropagation();removeFile('+i+')">×</div>';
    h+='</div>';
  });
  g.innerHTML=h;
}
function updateControls(){
  const c=document.getElementById('b-controls');
  const n=bFiles.length;
  if(n===0){c.style.display='none';return;}
  c.style.display='block';
  document.getElementById('b-estimate').textContent=
    '约 '+n+' 张 × $'+COST_EST.toFixed(2)+' ≈ $'+(n*COST_EST).toFixed(2);
}

/* ── drop zone ── */
(function(){
  const dz=document.getElementById('b-drop'), fi=document.getElementById('b-files');
  dz.addEventListener('dragover',function(e){e.preventDefault();dz.classList.add('over');});
  dz.addEventListener('dragleave',function(){dz.classList.remove('over');});
  dz.addEventListener('drop',function(e){e.preventDefault();dz.classList.remove('over');addFiles(e.dataTransfer.files);});
  fi.addEventListener('change',function(){addFiles(fi.files);fi.value='';});
})();

/* ── start batch ── */
async function startBatch(){
  const prompt=document.getElementById('b-prompt').value.trim();
  if(!hasKey){toggleKeyModal();return;}
  if(!prompt){alert('请输入提示词');return;}
  if(bFiles.length===0){alert('请上传图片');return;}
  const btn=document.getElementById('b-start');
  btn.disabled=true; btn.classList.add('btn-loading'); btn.innerHTML='<span uk-spinner="ratio:0.6"></span> 上传中…';
  const fd=new FormData();
  fd.append('prompt',prompt);
  bFiles.forEach(function(bf){fd.append('images',bf.file);});
  try{
    const r=await fetch('/api/batches',{method:'POST',body:fd});
    const j=await r.json();
    if(j.error){alert(j.error);btn.disabled=false;btn.classList.remove('btn-loading');btn.textContent='开始处理';return;}
    batchId=j.batch_id;
    bStarted=true;
    document.getElementById('b-drop').style.display='none';
    document.getElementById('b-prompt').disabled=true;
    btn.style.display='none';
    document.getElementById('b-progress').style.display='block';
    bFiles.forEach(function(bf){bf.ov='b-ov-pending';bf.ovIcon='⏳';});
    renderGrid();
    startPoll();
  }catch(e){
    alert('上传失败：'+e.message);
    btn.disabled=false; btn.classList.remove('btn-loading'); btn.textContent='开始处理';
  }
}

/* ── polling ── */
function startPoll(){ pollTimer=setInterval(pollStatus,2000); pollStatus(); }
function stopPoll(){ if(pollTimer){clearInterval(pollTimer);pollTimer=null;} }

async function pollStatus(){
  if(!batchId)return;
  try{
    const r=await fetch('/api/batches/'+batchId);
    const j=await r.json();
    bItems=j.items;
    let done=0,failed=0,running=0,cost=0;
    j.items.forEach(function(it,i){
      cost+=it.cost||0;
      if(it.status==='done'){done++;bFiles[i].ov='b-ov-done';bFiles[i].ovIcon='✅';}
      else if(it.status==='failed'){failed++;bFiles[i].ov='b-ov-failed';bFiles[i].ovIcon='❌';}
      else if(it.status==='running'){running++;bFiles[i].ov='b-ov-running';bFiles[i].ovIcon='<div class="b-spin"></div>';}
      else{bFiles[i].ov='b-ov-pending';bFiles[i].ovIcon='⏳';}
    });
    renderGrid();
    const total=j.total, finished=done+failed;
    const pct=total?Math.round(finished/total*100):0;
    document.getElementById('b-progress-text').innerHTML=
      '<span>进度 '+finished+'/'+total+'</span><span>$'+cost.toFixed(4)+'</span>';
    const fill=document.getElementById('b-bar-fill');
    fill.style.width=pct+'%';
    if(failed>0){
      fill.classList.add('has-fail');
      const okPct=total?Math.round(done/total*100):0;
      fill.style.setProperty('--ok-pct',okPct+'%');
    }else{ fill.classList.remove('has-fail'); }
    if(selIdx>=0) showCompare(selIdx);
    if(finished>=total){
      stopPoll();
      if(done>0) document.getElementById('b-done').style.display='block';
    }
  }catch(e){console.error('poll error',e);}
}

/* ── thumbnail click / compare ── */
function thumbClick(i){
  selIdx = (selIdx===i) ? -1 : i;
  renderGrid();
  if(selIdx>=0) showCompare(selIdx);
  else hideCompare();
}
function showCompare(i){
  const c=document.getElementById('b-compare'); c.style.display='block';
  document.getElementById('b-cmp-src').src=bFiles[i].url;
  const it=bItems[i];
  const title=document.getElementById('b-compare-title');
  const resImg=document.getElementById('b-cmp-res');
  const meta=document.getElementById('b-compare-meta');
  const errEl=document.getElementById('b-compare-error');
  const retryBtn=document.getElementById('b-retry-btn');
  if(!it){
    title.textContent='图片 '+(i+1)+' · 等待上传';
    resImg.src=''; resImg.style.display='none';
    meta.textContent=''; errEl.style.display='none'; retryBtn.style.display='none';
    return;
  }
  title.textContent='图片 '+(i+1)+' · '+({pending:'等待中',running:'处理中',done:'完成',failed:'失败'}[it.status]||it.status);
  if(it.result_url){
    resImg.src=it.result_url; resImg.style.display='block';
  }else{
    resImg.src=''; resImg.style.display='none';
  }
  if(it.status==='done'){
    meta.textContent='$'+(it.cost||0).toFixed(4)+(it.result_text?' · '+it.result_text.slice(0,80):'');
  }else{ meta.textContent=''; }
  if(it.status==='failed' && it.error){
    errEl.textContent=it.error; errEl.style.display='block';
  }else{ errEl.style.display='none'; }
  retryBtn.style.display = it.status==='failed' ? 'block' : 'none';
  c.scrollIntoView({behavior:'smooth',block:'nearest'});
}
function hideCompare(){
  document.getElementById('b-compare').style.display='none';
}

/* ── retry ── */
async function retrySelected(){
  if(selIdx<0||!batchId)return;
  const it=bItems[selIdx];
  if(!it)return;
  const btn=document.getElementById('b-retry-btn');
  btn.disabled=true; btn.textContent='重试中…';
  try{
    await fetch('/api/batches/'+batchId+'/items/'+it.id+'/retry',{method:'POST'});
    if(!pollTimer) startPoll();
  }catch(e){alert('重试失败：'+e.message);}
  finally{ btn.disabled=false; btn.textContent='重试'; }
}

/* ── download ── */
function downloadZip(){
  if(!batchId)return;
  window.location.href='/api/batches/'+batchId+'/archive';
}
"""

BATCH_JS = KEY_JS + BATCH_JS_BODY
