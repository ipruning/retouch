import uuid, os, traceback, json, hashlib
from fasthtml.common import *
from google import genai
from google.genai import types
from starlette.responses import StreamingResponse

API_KEY = "REDACTED_GOOGLE_API_KEY"
MODEL = "gemini-3.1-flash-image-preview"
GEN_DIR = "generated"
os.makedirs(GEN_DIR, exist_ok=True)

gclient = genai.Client(api_key=API_KEY)
sessions: dict = {}


def save_image(data: bytes) -> str:
    """Save image bytes, deduplicate by content hash, return URL path."""
    h = hashlib.md5(data).hexdigest()
    fname = f"{h}.jpg"
    fpath = os.path.join(GEN_DIR, fname)
    if not os.path.exists(fpath):
        with open(fpath, 'wb') as f:
            f.write(data)
    return f"/generated/{fname}"


def build_context(sid: str) -> dict:
    """Build context structure from chat history for UI display."""
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


CSS = """\
* { box-sizing: border-box; margin: 0; padding: 0; }
:root { --fg: #111; --mg: #555; --lg: #aaa; --bg: #fff; --bd: #e0e0e0; }
body { font-family: "PingFang SC", -apple-system, "Helvetica Neue", "Noto Sans SC", sans-serif;
       background: var(--bg); color: var(--fg); height: 100vh; overflow: hidden; }
.w { max-width: 520px; margin: 0 auto; display: flex; flex-direction: column; height: 100vh; }
.head { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px 12px; flex-shrink: 0; }
.head h1 { font-size: 16px; font-weight: 600; }
.nb { font-size: 12px; color: var(--lg); cursor: pointer; border: 1px solid var(--bd); border-radius: 4px; padding: 3px 8px; background: none; }
.nb:hover { color: var(--fg); border-color: var(--fg); }

/* Main scrollable area */
.main { flex: 1; overflow-y: auto; padding: 0 20px 24px; }

/* Envelope */
.envelope { border: 1.5px solid var(--bd); border-radius: 10px; padding: 0; overflow: hidden; }
.env-head { font-size: 11px; color: var(--lg); padding: 10px 14px 0; }
.ctx-list { padding: 6px 14px 0; }
.ctx-empty { font-size: 13px; color: var(--lg); padding: 4px 0; }
.ctx-turn { display: flex; gap: 8px; padding: 3px 0; font-size: 13px; line-height: 1.6; align-items: center; }
.ctx-role { color: var(--mg); font-weight: 500; flex-shrink: 0; min-width: 26px; }
.ctx-parts { color: var(--lg); display: flex; align-items: center; gap: 6px; min-width: 0; }
.ctx-parts .ctx-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ctx-thumb { width: 28px; height: 28px; border-radius: 3px; object-fit: cover; flex-shrink: 0; }
.ctx-img-label { white-space: nowrap; }
.ctx-sep { border-top: 1.5px dashed var(--bd); margin: 8px 14px 0; }

/* Upload preview inside envelope */
.upload-preview { display: flex; align-items: center; gap: 8px; padding: 8px 14px 0; }
.upload-preview img { width: 40px; height: 40px; border-radius: 4px; object-fit: cover; }
.upload-preview .upload-name { font-size: 12px; color: var(--mg); }
.upload-preview .upload-x { background: none; border: none; color: var(--lg); font-size: 16px; cursor: pointer; padding: 0 4px; }
.upload-preview .upload-x:hover { color: var(--fg); }
.hide { display: none; }

/* Input inside envelope */
.env-input { padding: 8px 14px; }
.env-input textarea { width: 100%; min-height: 48px; padding: 8px 10px; border: 1px solid var(--bd); border-radius: 6px;
                       font-size: 14px; font-family: inherit; color: var(--fg); background: var(--bg);
                       resize: vertical; outline: none; }
.env-input textarea:focus { border-color: #999; }
.env-input textarea::placeholder { color: var(--lg); }
.env-actions { display: flex; gap: 8px; padding: 0 14px 10px; align-items: center; }
.env-actions .attach { font-size: 12px; color: var(--lg); cursor: pointer; position: relative; }
.env-actions .attach:hover { color: var(--mg); }
.env-actions .attach input { position: absolute; inset: 0; opacity: 0; width: 100%; cursor: pointer; }
.btn { flex: 1; padding: 9px; background: var(--fg); color: #fff; border: none; border-radius: 6px;
       font-size: 14px; font-weight: 500; cursor: pointer; font-family: inherit; }
.btn:hover { opacity: .85; }
.btn:disabled { opacity: .4; cursor: default; }
.env-footer { font-size: 11px; color: var(--lg); padding: 0 14px 10px; line-height: 1.4; }

/* Result area */
.result-area { margin-top: 16px; }
.result { margin-bottom: 16px; }
.result img { width: 100%; border-radius: 8px; display: block; margin-top: 4px; }
.result-text { font-size: 14px; line-height: 1.6; color: var(--mg); margin-bottom: 4px; }
.meta { font-size: 11px; color: var(--lg); margin-top: 8px; line-height: 1.6; }
.meta span { margin-right: 10px; }
.err { padding: 10px 12px; border-radius: 6px; background: #fef2f2; color: #b91c1c; font-size: 13px; }
.spin { display: inline-block; width: 14px; height: 14px; border: 2px solid rgba(255,255,255,.3);
        border-top-color: #fff; border-radius: 50%; animation: r .5s linear infinite;
        vertical-align: middle; margin-right: 6px; }
@keyframes r { to { transform: rotate(360deg); } }
.streaming-text { display: inline; }
.cursor-blink { display: inline-block; width: 2px; height: 14px; background: var(--fg);
                margin-left: 2px; vertical-align: text-bottom; animation: blink .8s step-end infinite; }
@keyframes blink { 50% { opacity: 0; } }
"""

JS = """\
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
  const btn=document.getElementById('btn'),p=document.getElementById('prompt').value.trim();
  if(!p)return;
  const fd=new FormData();fd.append('prompt',p);fd.append('sid',sid);
  const fi=document.getElementById('file');
  if(pastedFile)fd.append('image',pastedFile,'pasted.png');
  else if(fi&&fi.files[0])fd.append('image',fi.files[0]);
  btn.disabled=true;btn.innerHTML='<span class="spin"></span>\u751f\u6210\u4e2d\u2026';
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

app, rt = fast_app(hdrs=[Style(CSS)], live=False)


@rt("/")
def get():
    return Div(
        Div(
            H1("\u56fe\u7247\u5de5\u4f5c\u53f0"),
            Button("\u65b0\u5bf9\u8bdd", cls="nb", onclick="newChat()"),
            cls="head"
        ),
        Div(
            # The envelope
            Div(
                Div("\u4e0a\u4e0b\u6587", cls="env-head"),
                Div(
                    Div("\u65b0\u5bf9\u8bdd", cls="ctx-empty"),
                    id="ctx-list", cls="ctx-list"
                ),
                Div(cls="ctx-sep"),
                # Upload preview (hidden by default)
                Div(
                    Img(src="", alt=""),
                    Span(cls="upload-name"),
                    Button("\u00d7", cls="upload-x", onclick="clearImage()"),
                    id="upload-preview", cls="upload-preview hide"
                ),
                # Input
                Div(
                    Textarea(id="prompt", placeholder="\u63cf\u8ff0\u4f60\u60f3\u8981\u7684\u56fe\u7247\u2026"),
                    cls="env-input"
                ),
                # Actions row: attach + submit
                Div(
                    Label(
                        "\U0001f4ce \u4e0a\u4f20\u56fe\u7247",
                        Input(type="file", id="file", accept="image/*", onchange="onFile(this)"),
                        cls="attach"
                    ),
                    Button("\u751f\u6210", id="btn", cls="btn", onclick="go()"),
                    cls="env-actions"
                ),
                Div(id="env-footer", cls="env-footer"),
                cls="envelope"
            ),
            # Result area
            Div(id="result-area", cls="result-area"),
            id="main", cls="main"
        ),
        Script(JS),
        cls="w"
    )


def get_or_create_chat(sid: str):
    if sid not in sessions:
        sessions[sid] = gclient.chats.create(
            model=MODEL,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(
                    thinking_level="HIGH",
                ),
                response_modalities=["TEXT", "IMAGE"]
            )
        )
    return sessions[sid]


def sse_event(etype: str, data: str) -> str:
    return f"data: {json.dumps({'type': etype, 'data': data}, ensure_ascii=False)}\n\n"


@rt("/generate", methods=["POST"])
async def post_generate(request):
    form = await request.form()
    prompt = form.get("prompt", "").strip()
    sid = form.get("sid", "")
    if not prompt:
        return StreamingResponse(iter([sse_event("error", "\u8bf7\u8f93\u5165\u63cf\u8ff0")]), media_type="text/event-stream")
    if not sid:
        return StreamingResponse(iter([sse_event("error", "\u7f3a\u5c11\u4f1a\u8bdd")]), media_type="text/event-stream")

    img_bytes = None
    img_ct = None
    upload = form.get("image")
    if upload and hasattr(upload, 'read'):
        img_bytes = await upload.read()
        img_ct = upload.content_type or "image/png"

    def stream_gen():
        try:
            chat = get_or_create_chat(sid)
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

            # Meta
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

            # Context
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


serve(host="0.0.0.0", port=8000)
