import uuid, os, traceback, json, threading
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
# Store pending tasks: task_id -> {contents, sid}
pending: dict = {}

CSS = """\
* { box-sizing: border-box; margin: 0; padding: 0; }
:root { --fg: #111; --mg: #555; --lg: #aaa; --bg: #fff; --bd: #e0e0e0; }
body { font-family: "PingFang SC", -apple-system, "Helvetica Neue", "Noto Sans SC", sans-serif; background: var(--bg); color: var(--fg); height: 100vh; overflow: hidden; }
.w { max-width: 520px; margin: 0 auto; display: flex; flex-direction: column; height: 100vh; }
.head { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px 0; flex-shrink: 0; }
.head h1 { font-size: 16px; font-weight: 600; }
.nb { font-size: 12px; color: var(--lg); cursor: pointer; border: 1px solid var(--bd); border-radius: 4px; padding: 3px 8px; background: none; }
.nb:hover { color: var(--fg); border-color: var(--fg); }
.tabs { display: flex; gap: 20px; border-bottom: 1px solid var(--bd); padding: 0 20px; flex-shrink: 0; }
.tab { padding: 6px 0; font-size: 13px; color: var(--lg); cursor: pointer; border-bottom: 1.5px solid transparent; margin-bottom: -1px; }
.tab:hover { color: var(--mg); }
.tab.on { color: var(--fg); border-bottom-color: var(--fg); }
.field { margin-bottom: 14px; }
textarea { width: 100%; min-height: 56px; padding: 10px 12px; border: 1px solid var(--bd); border-radius: 6px; font-size: 14px; font-family: inherit; color: var(--fg); background: var(--bg); resize: vertical; outline: none; }
textarea:focus { border-color: #999; }
textarea::placeholder { color: var(--lg); }
.drop { border: 1.5px dashed var(--bd); border-radius: 6px; padding: 14px; text-align: center; cursor: pointer; position: relative; color: var(--lg); font-size: 13px; margin-bottom: 14px; }
.drop:hover { border-color: #999; }
.drop input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.drop .name { color: var(--fg); }
.drop.has-img { border-style: solid; border-color: #999; }
.thumb { margin-bottom: 14px; }
.thumb img { max-width: 56px; max-height: 56px; border-radius: 4px; }
.btn { display: block; width: 100%; padding: 10px; background: var(--fg); color: #fff; border: none; border-radius: 6px; font-size: 14px; font-weight: 500; cursor: pointer; font-family: inherit; }
.btn:hover { opacity: .85; }
.btn:disabled { opacity: .4; cursor: default; }
.hide { display: none; }
.history { flex: 1; overflow-y: auto; padding: 20px 20px 10px; }
.turn { margin-bottom: 14px; }
.turn .role { font-size: 11px; color: var(--lg); margin-bottom: 3px; }
.turn .bubble { font-size: 14px; line-height: 1.6; color: var(--mg); }
.turn img { width: 100%; border-radius: 6px; display: block; margin-top: 6px; }
.turn .user-text { color: var(--fg); }
.divider { height: 1px; background: var(--bd); margin: 18px 0; }
.err { margin-top: 14px; padding: 10px 12px; border-radius: 6px; background: #fef2f2; color: #b91c1c; font-size: 13px; }
.input-area { flex-shrink: 0; padding: 10px 20px 20px; border-top: 1px solid var(--bd); background: var(--bg); }
.spin { display: inline-block; width: 14px; height: 14px; border: 2px solid rgba(255,255,255,.3); border-top-color: #fff; border-radius: 50%; animation: r .5s linear infinite; vertical-align: middle; margin-right: 6px; }
@keyframes r { to { transform: rotate(360deg); } }
.meta { font-size: 11px; color: var(--lg); margin-top: 8px; line-height: 1.6; }
.meta span { margin-right: 10px; }
.think { margin-top: 8px; }
.think summary { font-size: 11px; color: var(--lg); cursor: pointer; }
.think summary:hover { color: var(--mg); }
.think pre { font-size: 12px; color: var(--mg); line-height: 1.5; white-space: pre-wrap; margin-top: 4px; font-family: inherit; }
.streaming-text { display: inline; }
.cursor-blink { display: inline-block; width: 2px; height: 14px; background: var(--fg); margin-left: 2px; vertical-align: text-bottom; animation: blink 0.8s step-end infinite; }
@keyframes blink { 50% { opacity: 0; } }
"""

JS = """\
let mode='gen',sid=localStorage.getItem('sid')||'',pastedFile=null;
if(!sid){sid=crypto.randomUUID();localStorage.setItem('sid',sid);}
function sw(m){
  mode=m;
  document.getElementById('t-gen').classList.toggle('on',m==='gen');
  document.getElementById('t-edit').classList.toggle('on',m==='edit');
  document.getElementById('upload').className=m==='edit'?'field':'hide';
  document.getElementById('btn').textContent=m==='gen'?'\u751f\u6210':'\u7f16\u8f91';
}
function showPreview(file,label){
  const t=document.getElementById('thumb');t.innerHTML='';
  const d=document.getElementById('dropzone');
  d.innerHTML='<span class="name">'+label+'</span>';
  const inp=document.createElement('input');
  inp.type='file';inp.id='file';inp.accept='image/*';
  inp.onchange=function(){pastedFile=null;pv(this);};
  d.appendChild(inp);d.classList.add('has-img');
  const img=document.createElement('img');
  const r=new FileReader();r.onload=e=>{img.src=e.target.result;t.appendChild(img);};r.readAsDataURL(file);
}
function pv(el){pastedFile=null;if(el.files[0])showPreview(el.files[0],el.files[0].name);}
function clearImage(){
  pastedFile=null;
  document.getElementById('thumb').innerHTML='';
  const d=document.getElementById('dropzone');d.classList.remove('has-img');
  d.innerHTML='\u70b9\u51fb\u4e0a\u4f20\u6216\u7c98\u8d34\u56fe\u7247';
  const inp=document.createElement('input');
  inp.type='file';inp.id='file';inp.accept='image/*';
  inp.onchange=function(){pastedFile=null;pv(this);};
  d.appendChild(inp);
}
function newChat(){
  sid=crypto.randomUUID();localStorage.setItem('sid',sid);
  document.getElementById('history').innerHTML='';
  document.getElementById('prompt').value='';clearImage();
}
document.addEventListener('paste',function(e){
  const items=e.clipboardData&&e.clipboardData.items;if(!items)return;
  for(let i=0;i<items.length;i++){
    if(items[i].type.indexOf('image')!==-1){
      e.preventDefault();const blob=items[i].getAsFile();if(!blob)return;
      pastedFile=blob;sw('edit');showPreview(blob,'\u5df2\u7c98\u8d34');return;
    }
  }
});
function scrollH(){const h=document.getElementById('history');h.scrollTop=h.scrollHeight;}
async function go(){
  const btn=document.getElementById('btn'),p=document.getElementById('prompt').value.trim();
  if(!p)return;
  const fd=new FormData();fd.append('prompt',p);fd.append('mode',mode);fd.append('sid',sid);
  const f=document.getElementById('file');
  if(mode==='edit'){
    if(pastedFile)fd.append('image',pastedFile,'pasted.png');
    else if(f&&f.files[0])fd.append('image',f.files[0]);
  }
  btn.disabled=true;btn.innerHTML='<span class="spin"></span>\u751f\u6210\u4e2d\u2026';
  // Add user turn
  const h=document.getElementById('history');
  const ut=document.createElement('div');ut.className='turn';
  ut.innerHTML='<div class="role">\u4f60</div><div class="bubble user-text">'+p.replace(/</g,'&lt;')+'</div>';
  h.appendChild(ut);
  // Add model turn (will be filled by stream)
  const mt=document.createElement('div');mt.className='turn';
  mt.innerHTML='<div class="role">\u6a21\u578b</div><div class="bubble" id="stream-bubble"><span class="cursor-blink"></span></div>';
  h.appendChild(mt);
  scrollH();
  try{
    const r=await fetch('/generate',{method:'POST',body:fd});
    const reader=r.body.getReader();
    const decoder=new TextDecoder();
    let buf='';
    const bubble=document.getElementById('stream-bubble');
    while(true){
      const {done,value}=await reader.read();
      if(done)break;
      buf+=decoder.decode(value,{stream:true});
      // Parse SSE lines
      let lines=buf.split(String.fromCharCode(10));
      buf=lines.pop();
      for(const line of lines){
        if(!line.startsWith('data: '))continue;
        const raw=line.slice(6);
        if(raw==='[DONE]')continue;
        let ev;
        try{ev=JSON.parse(raw);}catch(e){continue;}
        if(ev.type==='text'){
          // Remove cursor, append text, re-add cursor
          const cur=bubble.querySelector('.cursor-blink');
          const span=document.createElement('span');
          span.className='streaming-text';
          span.textContent=ev.data;
          if(cur)bubble.insertBefore(span,cur);
          else bubble.appendChild(span);
          scrollH();
        }else if(ev.type==='image'){
          const cur=bubble.querySelector('.cursor-blink');
          const img=document.createElement('img');
          img.src=ev.data;
          img.alt='result';
          if(cur)bubble.insertBefore(img,cur);
          else bubble.appendChild(img);
          scrollH();
        }else if(ev.type==='meta'){
          const cur=bubble.querySelector('.cursor-blink');
          if(cur)cur.remove();
          const d=document.createElement('div');
          d.className='meta';
          d.innerHTML=ev.data;
          bubble.appendChild(d);
        }else if(ev.type==='error'){
          const cur=bubble.querySelector('.cursor-blink');
          if(cur)cur.remove();
          bubble.innerHTML='<div class="err">'+ev.data+'</div>';
        }
      }
    }
    // Remove cursor if still there
    const cur=bubble.querySelector('.cursor-blink');
    if(cur)cur.remove();
    // Remove the temp id
    bubble.removeAttribute('id');
    // Add divider
    const dv=document.createElement('div');dv.className='divider';h.appendChild(dv);
    document.getElementById('prompt').value='';pastedFile=null;
    scrollH();
  }catch(e){
    const bubble=document.getElementById('stream-bubble');
    if(bubble)bubble.innerHTML='<div class="err">'+e.message+'</div>';
  }
  finally{btn.disabled=false;btn.textContent=mode==='gen'?'\u751f\u6210':'\u7f16\u8f91';}
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
            Div("\u751f\u6210", cls="tab on", id="t-gen", onclick="sw('gen')"),
            Div("\u7f16\u8f91", cls="tab", id="t-edit", onclick="sw('edit')"),
            cls="tabs"
        ),
        Div(id="history", cls="history"),
        Div(
            Div(
                Div(
                    "\u70b9\u51fb\u4e0a\u4f20\u6216\u7c98\u8d34\u56fe\u7247",
                    Input(type="file", id="file", accept="image/*", onchange="pv(this)"),
                    id="dropzone", cls="drop"
                ),
                Div(id="thumb", cls="thumb"),
                id="upload", cls="hide"
            ),
            Div(
                Textarea(id="prompt", placeholder="\u63cf\u8ff0\u4f60\u60f3\u8981\u7684\u56fe\u7247\u2026"),
                cls="field"
            ),
            Button("\u751f\u6210", id="btn", cls="btn", onclick="go()"),
            cls="input-area"
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
    """Format a single SSE event."""
    return f"data: {json.dumps({'type': etype, 'data': data}, ensure_ascii=False)}\n\n"


@rt("/generate", methods=["POST"])
async def post_generate(request):
    form = await request.form()
    prompt = form.get("prompt", "").strip()
    mode = form.get("mode", "gen")
    sid = form.get("sid", "")
    if not prompt:
        return StreamingResponse(
            iter([sse_event("error", "\u8bf7\u8f93\u5165\u63cf\u8ff0")]),
            media_type="text/event-stream"
        )
    if not sid:
        return StreamingResponse(
            iter([sse_event("error", "\u7f3a\u5c11\u4f1a\u8bdd")]),
            media_type="text/event-stream"
        )

    # Read upload if present
    img_bytes = None
    img_ct = None
    if mode == "edit":
        upload = form.get("image")
        if upload and hasattr(upload, 'read'):
            img_bytes = await upload.read()
            img_ct = upload.content_type or "image/png"

    def stream_gen():
        try:
            chat = get_or_create_chat(sid)

            if mode == "edit" and img_bytes:
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
                        # Skip thought parts
                        if getattr(part, 'thought', False):
                            continue
                        if hasattr(part, 'inline_data') and part.inline_data and part.inline_data.data:
                            fname = f"{uuid.uuid4().hex}.png"
                            fpath = os.path.join(GEN_DIR, fname)
                            with open(fpath, 'wb') as f:
                                f.write(part.inline_data.data)
                            yield sse_event("image", f"/generated/{fname}")
                        elif hasattr(part, 'text') and part.text:
                            yield sse_event("text", part.text)
                # Track usage from each chunk (last one with data wins)
                um = getattr(chunk, 'usage_metadata', None)
                if um and um.prompt_token_count:
                    last_usage = um

            # Send usage/cost meta
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
