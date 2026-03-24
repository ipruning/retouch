import uuid, os, traceback, json, hashlib, zipfile, io
from concurrent.futures import ThreadPoolExecutor
from fasthtml.common import *
from monsterui.all import *
from google import genai
from google.genai import types
from starlette.responses import StreamingResponse

MODEL = "gemini-3.1-flash-image-preview"
GEN_DIR = "generated"
os.makedirs(GEN_DIR, exist_ok=True)

api_keys: dict = {}
clients: dict = {}
sessions: dict = {}

def get_client(uid: str):
    return clients.get(uid)

def save_image(data: bytes) -> str:
    h = hashlib.md5(data).hexdigest()
    fname = f"{h}.jpg"
    fpath = os.path.join(GEN_DIR, fname)
    if not os.path.exists(fpath):
        with open(fpath, 'wb') as f:
            f.write(data)
    return f"/generated/{fname}"

def build_context(sid: str) -> dict:
    if sid not in sessions:
        return {"turns": [], "total_bytes": 0}
    chat = sessions[sid]
    history = chat.get_history(curated=True)
    turns = []
    total_bytes = 0
    for content in history:
        role = content.role or "?"
        parts_desc = []
        for p in (content.parts or []):
            if hasattr(p, 'inline_data') and p.inline_data and p.inline_data.data:
                size = len(p.inline_data.data)
                total_bytes += size
                url = save_image(p.inline_data.data)
                parts_desc.append({"type": "image", "size": size, "url": url})
            elif hasattr(p, 'text') and p.text and not getattr(p, 'thought', False):
                t = p.text
                preview = (t[:40] + "\u2026") if len(t) > 40 else t
                parts_desc.append({"type": "text", "value": preview})
        if parts_desc:
            turns.append({"role": "\u4f60" if role == "user" else "\u6a21\u578b", "parts": parts_desc})
    return {"turns": turns, "total_bytes": total_bytes}


EXTRA_CSS = """\
.ctx-turn { display:flex; gap:6px; align-items:center; padding:4px 0; font-size:13px; }
.ctx-role { font-weight:600; white-space:nowrap; color:var(--color-muted-foreground); }
.ctx-parts { display:flex; flex-wrap:wrap; gap:4px; align-items:center; }
.ctx-text { color:var(--color-muted-foreground); max-width:300px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.ctx-thumb { width:28px; height:28px; border-radius:4px; object-fit:cover; }
.ctx-img-label { font-size:11px; color:var(--color-muted-foreground); }
.ctx-empty { color:var(--color-muted-foreground); font-size:13px; padding:4px 0; }
.upload-preview { display:flex; align-items:center; gap:8px; padding:8px 0; }
.upload-preview.hide { display:none; }
.upload-preview img { width:48px; height:48px; border-radius:6px; object-fit:cover; }
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
.b-drop { border:2px dashed var(--color-border); border-radius:12px; padding:32px;
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
let hasKey=false;
function toggleKeyModal(){
  UIkit.modal(document.getElementById('key-modal')).toggle();
}
async function checkKey(){
  try{
    const r=await fetch('/api/key');const d=await r.json();
    const st=document.getElementById('key-status');
    if(d.has_key){
      hasKey=true; st.textContent=d.masked; st.className='text-xs text-green-600 mr-1';
    }else{
      hasKey=false; st.textContent='\u672a\u8bbe\u7f6e'; st.className='text-xs text-muted-foreground mr-1';
      toggleKeyModal();
    }
  }catch(e){console.error(e);}
}
async function saveKey(){
  const inp=document.getElementById('key-input'),msg=document.getElementById('key-msg');
  const k=inp.value.trim(); if(!k){msg.textContent='\u8bf7\u8f93\u5165 Key';msg.className='text-xs text-destructive mt-2';return;}
  msg.textContent='\u9a8c\u8bc1\u4e2d\u2026';msg.className='text-xs text-muted-foreground mt-2';
  document.getElementById('key-save-btn').disabled=true;
  try{
    const r=await fetch('/api/key',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:k})});
    const d=await r.json();
    if(d.ok){
      hasKey=true; msg.textContent='\u2705 \u5df2\u4fdd\u5b58';msg.className='text-xs text-green-600 mt-2';
      document.getElementById('key-status').textContent=d.masked;
      document.getElementById('key-status').className='text-xs text-green-600 mr-1';
      inp.value='';
      setTimeout(function(){UIkit.modal(document.getElementById('key-modal')).hide();},800);
    }else{
      msg.textContent=d.error||'\u5931\u8d25';msg.className='text-xs text-destructive mt-2';
    }
  }catch(e){msg.textContent='\u7f51\u7edc\u9519\u8bef';msg.className='text-xs text-destructive mt-2';}
  document.getElementById('key-save-btn').disabled=false;
}
async function clearKey(){
  await fetch('/api/key',{method:'DELETE'});
  hasKey=false;
  document.getElementById('key-status').textContent='\u672a\u8bbe\u7f6e';
  document.getElementById('key-status').className='text-xs text-muted-foreground mr-1';
  document.getElementById('key-msg').textContent='\u5df2\u6e05\u9664';
  document.getElementById('key-msg').className='text-xs text-green-600 mt-2';
  document.getElementById('key-input').value='';
}
checkKey();
"""

MAIN_JS = KEY_JS + """\
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
  btn.disabled=true;btn.innerHTML='<span uk-spinner="ratio:0.6"></span> \u751f\u6210\u4e2d\u2026';
  // Prepare result area
  const ra=document.getElementById('result-area');
  ra.innerHTML='<div class="result" id="cur-result"><span class="cursor-blink"></span></div>';
  scrollM();
  try{
    const r=await fetch('/generate',{method:'POST',body:fd});
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
  finally{btn.disabled=false;btn.textContent='\u751f\u6210';}
}
document.getElementById('prompt').addEventListener('keydown',function(e){
  if((e.metaKey||e.ctrlKey)&&e.key==='Enter'){e.preventDefault();go();}
});
"""


# ── App setup ────────────────────────────────────────────────────────────
app, rt = fast_app(
    hdrs=Theme.blue.headers(mode='light') + [Style(EXTRA_CSS)],
    live=False,
)


def key_modal():
    """Shared API Key settings modal."""
    return Modal(
        P("\u5728 ", A("Google AI Studio", href="https://aistudio.google.com/apikey",
                    target="_blank", cls="text-primary underline"),
          " \u83b7\u53d6 Key", cls="text-sm text-muted-foreground"),
        Input(type="password", id="key-input", placeholder="AIzaSy...",
              cls="uk-input font-mono"),
        Div(id="key-msg"),
        header=H3("\u8bbe\u7f6e Gemini API Key", cls="text-lg font-semibold"),
        footer=DivFullySpaced(
            Button("\u6e05\u9664", cls=ButtonT.ghost, onclick="clearKey()"),
            Button("\u4fdd\u5b58", cls=ButtonT.primary, onclick="saveKey()", id="key-save-btn"),
        ),
        id="key-modal",
    )


def page_header(title, *extra_buttons):
    return DivFullySpaced(
        H3(title, cls="font-bold"),
        DivHStacked(
            Span(id="key-status", cls="text-xs text-muted-foreground mr-1"),
            Button(UkIcon('key', height=16), cls=ButtonT.ghost,
                   onclick="toggleKeyModal()", title="\u8bbe\u7f6e API Key"),
            *extra_buttons,
        ),
        cls="py-3",
    )


@rt("/")
def get():
    return Container(
        page_header(
            "\u56fe\u7247\u5de5\u4f5c\u53f0",
            A("\u6279\u91cf", href="/batch", cls="uk-btn uk-btn-default uk-btn-sm"),
            Button("\u65b0\u5bf9\u8bdd", cls=(ButtonT.default, ButtonT.sm), onclick="newChat()"),
        ),
        Card(
            Div(Div("\u65b0\u5bf9\u8bdd", cls="ctx-empty"), id="ctx-list"),
            DividerLine(),
            Div(
                Img(src="", alt=""),
                Span(cls="upload-name"),
                Button("\u00d7", cls="upload-x", onclick="clearImage()"),
                id="upload-preview", cls="upload-preview hide",
            ),
            Textarea(id="prompt", placeholder="\u63cf\u8ff0\u4f60\u60f3\u8981\u7684\u56fe\u7247\u2026",
                     cls="uk-textarea", rows=3),
            header=P("\u4e0a\u4e0b\u6587", cls=TextPresets.muted_sm),
            footer=Div(
                DivFullySpaced(
                    Label(
                        UkIcon('paperclip', height=16),
                        " \u4e0a\u4f20\u56fe\u7247",
                        Input(type="file", id="file", accept="image/*",
                              onchange="onFile(this)", cls="hidden"),
                        cls="cursor-pointer text-sm text-muted-foreground flex items-center gap-1",
                    ),
                    Button("\u751f\u6210", id="btn", cls=(ButtonT.primary, 'px-12'),
                           onclick="go()"),
                ),
                Div(id="env-footer", cls="text-xs text-muted-foreground mt-2"),
            ),
        ),
        Div(id="result-area", cls="mt-4"),
        key_modal(),
        Script(MAIN_JS),
        cls=ContainerT.sm,
        id="main",
        style="display:flex;flex-direction:column;min-height:100vh;",
    )


def get_or_create_chat(sid: str, uid: str):
    client = get_client(uid)
    if not client:
        return None
    if sid not in sessions:
        sessions[sid] = client.chats.create(
            model=MODEL,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level="HIGH"),
                response_modalities=["TEXT", "IMAGE"]
            )
        )
    return sessions[sid]


@rt("/api/key", methods=["POST"])
async def post_api_key(request):
    body = await request.json()
    key = (body.get("key") or "").strip()
    if not key:
        return JSONResponse({"ok": False, "error": "Key \u4e0d\u80fd\u4e3a\u7a7a"})
    uid = request.cookies.get("uid", "")
    if not uid:
        uid = uuid.uuid4().hex[:16]
    try:
        c = genai.Client(api_key=key)
        c.models.get(model=f"models/{MODEL}")
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"Key \u65e0\u6548: {e}"})
    api_keys[uid] = key
    clients[uid] = c
    to_del = [k for k in sessions if k.startswith(uid + "_")]
    for k in to_del:
        del sessions[k]
    resp = JSONResponse({"ok": True, "masked": key[:6] + "..." + key[-4:]})
    resp.set_cookie("uid", uid, max_age=86400*365, httponly=True, samesite="lax")
    return resp

@rt("/api/key", methods=["GET"])
def get_api_key(request):
    uid = request.cookies.get("uid", "")
    if uid and uid in api_keys:
        k = api_keys[uid]
        return JSONResponse({"has_key": True, "masked": k[:6] + "..." + k[-4:]})
    return JSONResponse({"has_key": False})

@rt("/api/key", methods=["DELETE"])
def delete_api_key(request):
    uid = request.cookies.get("uid", "")
    if uid:
        api_keys.pop(uid, None)
        clients.pop(uid, None)
        to_del = [k for k in sessions if k.startswith(uid + "_")]
        for k in to_del:
            del sessions[k]
    return JSONResponse({"ok": True})


def sse_event(etype: str, data: str) -> str:
    return f"data: {json.dumps({'type': etype, 'data': data}, ensure_ascii=False)}\n\n"


@rt("/generate", methods=["POST"])
async def post_generate(request):
    form = await request.form()
    prompt = form.get("prompt", "").strip()
    sid = form.get("sid", "")
    uid = request.cookies.get("uid", "")
    if not prompt:
        return StreamingResponse(iter([sse_event("error", "\u8bf7\u8f93\u5165\u63cf\u8ff0")]), media_type="text/event-stream")
    if not sid:
        return StreamingResponse(iter([sse_event("error", "\u7f3a\u5c11\u4f1a\u8bdd")]), media_type="text/event-stream")
    if not get_client(uid):
        return StreamingResponse(iter([sse_event("error", "\u8bf7\u5148\u8bbe\u7f6e API Key")]), media_type="text/event-stream")

    img_bytes = None
    img_ct = None
    upload = form.get("image")
    if upload and hasattr(upload, 'read'):
        img_bytes = await upload.read()
        img_ct = upload.content_type or "image/png"

    def stream_gen():
        try:
            chat = get_or_create_chat(sid, uid)
            if not chat:
                yield sse_event("error", "\u8bf7\u5148\u8bbe\u7f6e API Key")
                return
            if img_bytes:
                contents = [types.Part.from_bytes(data=img_bytes, mime_type=img_ct), prompt]
            else:
                contents = prompt
            last_usage = None
            for chunk in chat.send_message_stream(contents):
                if not chunk.candidates:
                    continue
                cand = chunk.candidates[0]
                if cand.content and cand.content.parts:
                    for part in cand.content.parts:
                        if getattr(part, 'thought', False):
                            continue
                        if hasattr(part, 'inline_data') and part.inline_data and part.inline_data.data:
                            url = save_image(part.inline_data.data)
                            yield sse_event("image", url)
                        elif hasattr(part, 'text') and part.text:
                            yield sse_event("text", part.text)
                um = getattr(chunk, 'usage_metadata', None)
                if um and um.prompt_token_count:
                    last_usage = um
            if last_usage:
                um = last_usage
                inp_t = um.prompt_token_count or 0
                out_t = um.candidates_token_count or 0
                think_t = um.thoughts_token_count or 0
                img_t = 0
                for d in (um.candidates_tokens_details or []):
                    if d.modality and d.modality.value == 'IMAGE':
                        img_t = d.token_count or 0
                txt_out_t = out_t - img_t
                cost = (inp_t * 0.50 + (txt_out_t + think_t) * 3.0 + img_t * 60.0) / 1_000_000
                parts = [f'<span>\u8f93\u5165 {inp_t}</span>', f'<span>\u8f93\u51fa {out_t}</span>']
                if think_t:
                    parts.append(f'<span>\u601d\u7ef4 {think_t}</span>')
                parts.append(f'<span>\u5408\u8ba1 {um.total_token_count or 0} tokens</span>')
                parts.append(f'<span>${cost:.4f}</span>')
                yield sse_event("meta", ''.join(parts))
            ctx = build_context(sid)
            yield sse_event("context", json.dumps(ctx, ensure_ascii=False))
            yield "data: [DONE]\n\n"
        except Exception as e:
            traceback.print_exc()
            yield sse_event("error", f"\u9519\u8bef\uff1a{e}")

    return StreamingResponse(stream_gen(), media_type="text/event-stream")


@rt("/generated/{fname}")
def get_generated(fname: str):
    fpath = os.path.join(GEN_DIR, fname)
    if os.path.exists(fpath):
        return FileResponse(fpath, media_type="image/png")
    return Response("Not found", status_code=404)


# ═══════════════════════════════════════════════════════════════════════════
# BATCH MODE
# ═══════════════════════════════════════════════════════════════════════════

batch_pool = ThreadPoolExecutor(max_workers=3)
batches: dict = {}

def _find_item(batch_id: str, item_id: str):
    batch = batches.get(batch_id)
    if not batch:
        return None, None
    for it in batch["items"]:
        if it["id"] == item_id:
            return batch, it
    return batch, None

def process_batch_item(batch_id: str, item_id: str):
    batch, item = _find_item(batch_id, item_id)
    if not item:
        return
    client = get_client(batch.get("uid", ""))
    if not client:
        item["status"] = "failed"
        item["error"] = "API Key \u672a\u8bbe\u7f6e"
        return
    item["status"] = "running"
    try:
        with open(item["src_path"], "rb") as f:
            img_bytes = f.read()
        response = client.models.generate_content(
            model=MODEL,
            contents=[types.Part.from_bytes(data=img_bytes, mime_type=item["src_mime"]),
                      batch["prompt"]],
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level="HIGH"),
                response_modalities=["TEXT", "IMAGE"],
            ),
        )
        result_url = None
        result_text = ""
        if response.candidates and response.candidates[0].content:
            for part in (response.candidates[0].content.parts or []):
                if getattr(part, "thought", False):
                    continue
                if hasattr(part, "inline_data") and part.inline_data and part.inline_data.data:
                    result_url = save_image(part.inline_data.data)
                elif hasattr(part, "text") and part.text:
                    result_text += part.text
        cost = 0.0
        um = getattr(response, "usage_metadata", None)
        if um:
            inp_t = um.prompt_token_count or 0
            out_t = um.candidates_token_count or 0
            think_t = um.thoughts_token_count or 0
            img_t = 0
            for d in (um.candidates_tokens_details or []):
                if d.modality and d.modality.value == "IMAGE":
                    img_t = d.token_count or 0
            txt_out_t = out_t - img_t
            cost = (inp_t * 0.50 + (txt_out_t + think_t) * 3.0 + img_t * 60.0) / 1_000_000
        item["result_url"] = result_url
        item["result_text"] = result_text
        item["cost"] = cost
        if result_url:
            item["status"] = "done"
        else:
            item["status"] = "failed"
            item["error"] = item.get("error") or "\u6a21\u578b\u672a\u8fd4\u56de\u56fe\u7247"
    except Exception as e:
        traceback.print_exc()
        item["status"] = "failed"
        item["error"] = str(e)[:300]


BATCH_JS_BODY = """\
let bFiles=[], bStarted=false, bItems=[], batchId=null, selIdx=-1, pollTimer=null;
const COST_EST=0.05;
/* ── file handling ── */
function addFiles(fileList){
  if(bStarted)return;
  for(let i=0;i<fileList.length;i++){
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
  btn.disabled=true; btn.innerHTML='<span uk-spinner="ratio:0.6"></span> 上传中…';
  const fd=new FormData();
  fd.append('prompt',prompt);
  bFiles.forEach(function(bf){fd.append('images',bf.file);});
  try{
    const r=await fetch('/batch/start',{method:'POST',body:fd});
    const j=await r.json();
    if(j.error){alert(j.error);btn.disabled=false;btn.textContent='开始处理';return;}
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
    alert('上传失败: '+e.message);
    btn.disabled=false; btn.textContent='开始处理';
  }
}

/* ── polling ── */
function startPoll(){ pollTimer=setInterval(pollStatus,2000); pollStatus(); }
function stopPoll(){ if(pollTimer){clearInterval(pollTimer);pollTimer=null;} }

async function pollStatus(){
  if(!batchId)return;
  try{
    const r=await fetch('/batch/status/'+batchId);
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
    await fetch('/batch/retry/'+batchId+'/'+it.id,{method:'POST'});
    if(!pollTimer) startPoll();
  }catch(e){alert('重试失败: '+e.message);}
  finally{ btn.disabled=false; btn.textContent='重试'; }
}

/* ── download ── */
function downloadZip(){
  if(!batchId)return;
  window.location.href='/batch/download/'+batchId;
}
"""

BATCH_JS = KEY_JS + BATCH_JS_BODY


@rt("/batch")
def get_batch():
    return Container(
        page_header(
            "\u6279\u91cf\u5904\u7406",
            A("\u2190 \u5355\u5f20\u6a21\u5f0f", href="/", cls="uk-btn uk-btn-default uk-btn-sm"),
        ),
        Card(
            Textarea(id="b-prompt",
                     placeholder="\u8f93\u5165\u63d0\u793a\u8bcd\uff0c\u5c06\u5e94\u7528\u5230\u6240\u6709\u56fe\u7247\u2026",
                     cls="uk-textarea", rows=3),
        ),
        Div(
            Input(type="file", id="b-files", multiple=True, accept="image/*"),
            DivCentered(
                UkIcon('upload', height=32, cls="text-muted-foreground"),
                P("\u62d6\u62fd\u6216\u70b9\u51fb\u4e0a\u4f20\u56fe\u7247\uff08\u652f\u6301\u591a\u9009\uff09",
                  cls="text-sm text-muted-foreground"),
            ),
            id="b-drop", cls="b-drop",
        ),
        Div(id="b-grid", cls="b-grid"),
        Div(
            DivFullySpaced(
                Span(id="b-estimate", cls="text-sm text-muted-foreground"),
                Button("\u5f00\u59cb\u5904\u7406", id="b-start", cls=ButtonT.primary,
                       onclick="startBatch()"),
            ),
            id="b-controls", style="display:none",
        ),
        Div(
            Div(id="b-progress-text", cls="b-progress-text"),
            Div(Div(id="b-bar-fill", cls="b-bar-fill"), cls="b-bar"),
            id="b-progress", style="display:none",
        ),
        Card(
            Div(id="b-compare-title", cls="b-compare-title"),
            Div(
                Div(Div("\u539f\u56fe", cls="b-compare-label"), Img(id="b-cmp-src", src="")),
                Div(Div("\u7ed3\u679c", cls="b-compare-label"), Img(id="b-cmp-res", src="")),
                cls="b-compare-imgs",
            ),
            Div(id="b-compare-error", cls="b-compare-error", style="display:none"),
            Div(id="b-compare-meta", cls="b-compare-meta"),
            Button("\u91cd\u8bd5", id="b-retry-btn", cls=ButtonT.destructive,
                   style="display:none", onclick="retrySelected()"),
            id="b-compare", style="display:none",
        ),
        Div(
            Button(UkIcon('download', height=16), " \u6253\u5305\u4e0b\u8f7d",
                   cls=ButtonT.primary, onclick="downloadZip()"),
            id="b-done", cls="mt-4", style="display:none",
        ),
        key_modal(),
        Script(BATCH_JS),
        cls=(ContainerT.sm, 'space-y-4'),
    )


@rt("/batch/start", methods=["POST"])
async def post_batch_start(request):
    form = await request.form()
    prompt = form.get("prompt", "").strip()
    uid = request.cookies.get("uid", "")
    if not get_client(uid):
        return JSONResponse({"error": "\u8bf7\u5148\u8bbe\u7f6e API Key"}, status_code=400)
    if not prompt:
        return JSONResponse({"error": "\u8bf7\u8f93\u5165\u63d0\u793a\u8bcd"}, status_code=400)
    raw_images = form.getlist("images")
    if not raw_images:
        return JSONResponse({"error": "\u8bf7\u4e0a\u4f20\u56fe\u7247"}, status_code=400)
    batch_id = uuid.uuid4().hex[:12]
    items = []
    for upload in raw_images:
        if not hasattr(upload, "read"):
            continue
        data = await upload.read()
        if not data or len(data) < 100:
            continue
        item_id = uuid.uuid4().hex[:8]
        src_url = save_image(data)
        src_path = os.path.join(GEN_DIR, os.path.basename(src_url))
        mime = getattr(upload, "content_type", None) or "image/png"
        items.append({
            "id": item_id, "status": "pending",
            "src_url": src_url, "src_path": src_path, "src_mime": mime,
            "result_url": None, "result_text": None, "error": None, "cost": 0.0,
        })
    if not items:
        return JSONResponse({"error": "\u672a\u68c0\u6d4b\u5230\u6709\u6548\u56fe\u7247"}, status_code=400)
    batches[batch_id] = {"prompt": prompt, "items": items, "uid": uid}
    for item in items:
        batch_pool.submit(process_batch_item, batch_id, item["id"])
    return JSONResponse({"batch_id": batch_id})


@rt("/batch/status/{batch_id}")
def get_batch_status(batch_id: str):
    batch = batches.get(batch_id)
    if not batch:
        return JSONResponse({"error": "\u6279\u6b21\u4e0d\u5b58\u5728"}, status_code=404)
    items_out = []
    total = len(batch["items"])
    done = failed = running = 0
    cost = 0.0
    for it in batch["items"]:
        s = it["status"]
        if s == "done": done += 1
        elif s == "failed": failed += 1
        elif s == "running": running += 1
        cost += it.get("cost", 0.0)
        items_out.append({
            "id": it["id"], "status": s, "src_url": it["src_url"],
            "result_url": it.get("result_url"), "result_text": it.get("result_text"),
            "error": it.get("error"), "cost": it.get("cost", 0.0),
        })
    return JSONResponse({
        "total": total, "done": done, "failed": failed, "running": running,
        "cost": cost, "items": items_out,
    })


@rt("/batch/retry/{batch_id}/{item_id}", methods=["POST"])
def post_batch_retry(batch_id: str, item_id: str):
    batch, item = _find_item(batch_id, item_id)
    if not item:
        return JSONResponse({"error": "not found"}, status_code=404)
    if item["status"] not in ("failed", "error"):
        return JSONResponse({"error": "not failed"}, status_code=400)
    item["status"] = "pending"
    item["error"] = None
    item["result_url"] = None
    item["result_text"] = None
    item["cost"] = 0.0
    batch_pool.submit(process_batch_item, batch_id, item_id)
    return JSONResponse({"ok": True})


@rt("/batch/download/{batch_id}")
def get_batch_download(batch_id: str):
    batch = batches.get(batch_id)
    if not batch:
        return Response("Not found", status_code=404)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for i, it in enumerate(batch["items"]):
            if it["status"] == "done" and it.get("result_url"):
                fpath = os.path.join(GEN_DIR, os.path.basename(it["result_url"]))
                if os.path.exists(fpath):
                    zf.write(fpath, f"result_{i+1}.jpg")
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=batch_{batch_id}.zip"},
    )


serve(host="0.0.0.0", port=8000)
