import uuid, os, traceback
from fasthtml.common import *
from google import genai
from google.genai import types

API_KEY = "REDACTED_GOOGLE_API_KEY"
MODEL = "gemini-3.1-flash-image-preview"
GEN_DIR = "generated"
os.makedirs(GEN_DIR, exist_ok=True)

gclient = genai.Client(api_key=API_KEY)

# In-memory session store: session_id -> chat object
sessions: dict = {}

CSS = """\
:root { --fg: #111; --mg: #666; --lg: #aaa; --bg: #fff; --border: #ddd; }
body { font-family: -apple-system, 'Helvetica Neue', sans-serif; background: var(--bg); color: var(--fg); margin: 0; }
.w { max-width: 560px; margin: 0 auto; padding: 48px 20px 40px; }
h1 { font-size: 18px; font-weight: 500; letter-spacing: -0.01em; }
h1 span { color: var(--lg); font-weight: 400; }
.head { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 32px; }
.new-btn { font-size: 12px; color: var(--lg); cursor: pointer; border: 1px solid var(--border); border-radius: 4px; padding: 4px 10px; background: none; transition: all .15s; }
.new-btn:hover { color: var(--fg); border-color: var(--fg); }

.tabs { display: flex; gap: 0; margin-bottom: 28px; border-bottom: 1px solid var(--border); }
.tab { padding: 8px 0; margin-right: 24px; font-size: 13px; color: var(--lg); cursor: pointer; border-bottom: 1.5px solid transparent; margin-bottom: -1px; transition: all .15s; }
.tab:hover { color: var(--mg); }
.tab.on { color: var(--fg); border-bottom-color: var(--fg); }

.field { margin-bottom: 20px; }
.field label { display: block; font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: var(--lg); margin-bottom: 6px; }
textarea { width: 100%; min-height: 72px; padding: 10px 12px; border: 1px solid var(--border); border-radius: 6px; font-size: 14px; font-family: inherit; color: var(--fg); background: var(--bg); resize: vertical; outline: none; transition: border .15s; }
textarea:focus { border-color: #999; }
textarea::placeholder { color: var(--lg); }

.drop { border: 1.5px dashed var(--border); border-radius: 6px; padding: 16px; text-align: center; cursor: pointer; position: relative; transition: border .15s; color: var(--lg); font-size: 13px; }
.drop:hover { border-color: #999; }
.drop input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.drop .name { color: var(--fg); }
.thumb { margin-top: 10px; max-width: 72px; max-height: 72px; border-radius: 4px; }

.btn { display: block; width: 100%; padding: 10px; background: var(--fg); color: #fff; border: none; border-radius: 6px; font-size: 14px; font-weight: 500; cursor: pointer; transition: opacity .15s; }
.btn:hover { opacity: .85; }
.btn:disabled { opacity: .4; cursor: default; }

.hide { display: none; }
.show { display: block; }

.history { margin-bottom: 28px; }
.turn { margin-bottom: 20px; }
.turn .role { font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: var(--lg); margin-bottom: 6px; }
.turn .bubble { font-size: 14px; line-height: 1.6; color: var(--mg); }
.turn img { width: 100%; border-radius: 6px; display: block; margin-top: 8px; }
.turn .user-text { color: var(--fg); }
.divider { height: 1px; background: var(--border); margin: 24px 0; }

.err { margin-top: 20px; padding: 12px; border-radius: 6px; background: #fef2f2; color: #b91c1c; font-size: 13px; }
.spin { display: inline-block; width: 14px; height: 14px; border: 2px solid rgba(255,255,255,.3); border-top-color: #fff; border-radius: 50%; animation: r .5s linear infinite; vertical-align: middle; margin-right: 6px; }
@keyframes r { to { transform: rotate(360deg); } }
"""

JS = """\
let mode='gen', sid=localStorage.getItem('sid')||'';
if(!sid){ sid=crypto.randomUUID(); localStorage.setItem('sid',sid); }

function sw(m){
  mode=m;
  document.getElementById('t-gen').classList.toggle('on',m==='gen');
  document.getElementById('t-edit').classList.toggle('on',m==='edit');
  document.getElementById('upload').className=m==='edit'?'field':'hide';
  document.getElementById('btn').textContent=m==='gen'?'Generate':'Edit';
}
function pv(el){
  const t=document.getElementById('thumb'); t.innerHTML='';
  const d=document.getElementById('dropzone');
  if(el.files[0]){
    d.innerHTML='<span class="name">'+el.files[0].name+'</span>';
    d.appendChild(el);
    const img=document.createElement('img'); img.className='thumb';
    const r=new FileReader(); r.onload=e=>{img.src=e.target.result;t.appendChild(img);}; r.readAsDataURL(el.files[0]);
  }
}
function newChat(){
  sid=crypto.randomUUID(); localStorage.setItem('sid',sid);
  document.getElementById('history').innerHTML='';
  document.getElementById('prompt').value='';
  const t=document.getElementById('thumb'); t.innerHTML='';
}
async function go(){
  const btn=document.getElementById('btn'), p=document.getElementById('prompt').value.trim();
  if(!p){alert('Enter a prompt');return;}
  const fd=new FormData(); fd.append('prompt',p); fd.append('mode',mode); fd.append('sid',sid);
  const f=document.getElementById('file');
  if(mode==='edit'&&f&&f.files[0]) fd.append('image',f.files[0]);
  btn.disabled=true; btn.innerHTML='<span class="spin"></span>Working...';
  try{
    const r=await fetch('/generate',{method:'POST',body:fd});
    const html=await r.text();
    const hist=document.getElementById('history');
    // Add user turn
    const ut=document.createElement('div'); ut.className='turn';
    ut.innerHTML='<div class="role">You</div><div class="bubble user-text">'+p.replace(/</g,'&lt;')+'</div>';
    hist.appendChild(ut);
    // Add model turn
    const mt=document.createElement('div'); mt.className='turn';
    mt.innerHTML='<div class="role">Model</div><div class="bubble">'+html+'</div>';
    hist.appendChild(mt);
    // Add divider
    const dv=document.createElement('div'); dv.className='divider'; hist.appendChild(dv);
    document.getElementById('prompt').value='';
    window.scrollTo(0,document.body.scrollHeight);
  } catch(e){ alert('Error: '+e.message); }
  finally{ btn.disabled=false; btn.textContent=mode==='gen'?'Generate':'Edit'; }
}
"""

app, rt = fast_app(hdrs=[Style(CSS)], live=False)


@rt("/")
def get():
    return Div(
        Div(
            H1("Image Studio ", Span("\u2014 generate & edit")),
            Button("New chat", cls="new-btn", onclick="newChat()"),
            cls="head"
        ),
        Div(
            Div("Generate", cls="tab on", id="t-gen", onclick="sw('gen')"),
            Div("Edit", cls="tab", id="t-edit", onclick="sw('edit')"),
            cls="tabs"
        ),
        Div(id="history", cls="history"),
        Div(
            Label("Reference image"),
            Div(
                "Drop an image or click to upload",
                Input(type="file", id="file", accept="image/*", onchange="pv(this)"),
                id="dropzone", cls="drop"
            ),
            Div(id="thumb"),
            id="upload", cls="hide"
        ),
        Div(
            Label("Prompt"),
            Textarea(id="prompt", placeholder="Describe what you want..."),
            cls="field"
        ),
        Button("Generate", id="btn", cls="btn", onclick="go()"),
        Script(JS),
        cls="w"
    )


def get_or_create_chat(sid: str):
    if sid not in sessions:
        sessions[sid] = gclient.chats.create(
            model=MODEL,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"]
            )
        )
    return sessions[sid]


@rt("/generate", methods=["POST"])
async def post_generate(request):
    form = await request.form()
    prompt = form.get("prompt", "").strip()
    mode = form.get("mode", "gen")
    sid = form.get("sid", "")
    if not prompt:
        return Div("Please provide a prompt.", cls="err")
    if not sid:
        return Div("Missing session.", cls="err")

    try:
        chat = get_or_create_chat(sid)

        if mode == "edit":
            upload = form.get("image")
            if upload and hasattr(upload, 'read'):
                img_bytes = await upload.read()
                ct = upload.content_type or "image/png"
                contents = [types.Part.from_bytes(data=img_bytes, mime_type=ct), prompt]
            else:
                contents = prompt
        else:
            contents = prompt

        response = chat.send_message(contents)

        parts = []
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'inline_data') and part.inline_data:
                fname = f"{uuid.uuid4().hex}.png"
                with open(os.path.join(GEN_DIR, fname), 'wb') as f:
                    f.write(part.inline_data.data)
                parts.append(Img(src=f"/generated/{fname}", alt="result"))
            if hasattr(part, 'text') and part.text:
                parts.append(P(part.text))

        if parts:
            return Div(*parts)
        return Div("No output. Try a different prompt.", cls="err")

    except Exception as e:
        traceback.print_exc()
        return Div(f"Error: {e}", cls="err")


@rt("/generated/{fname}")
def get_generated(fname: str):
    fpath = os.path.join(GEN_DIR, fname)
    if os.path.exists(fpath):
        return FileResponse(fpath, media_type="image/png")
    return Response("Not found", status_code=404)


serve(host="0.0.0.0", port=8000)
