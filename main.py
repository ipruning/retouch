import uuid, os, traceback
from fasthtml.common import *
from google import genai
from google.genai import types

API_KEY = "REDACTED_GOOGLE_API_KEY"
MODEL = "gemini-3.1-flash-image-preview"
GEN_DIR = "generated"
os.makedirs(GEN_DIR, exist_ok=True)

gclient = genai.Client(api_key=API_KEY)
sessions: dict = {}

CSS = """\
* { box-sizing: border-box; margin: 0; padding: 0; }
:root { --fg: #111; --mg: #555; --lg: #aaa; --bg: #fff; --bd: #e0e0e0; }
body { font-family: "PingFang SC", -apple-system, "Helvetica Neue", "Noto Sans SC", sans-serif; background: var(--bg); color: var(--fg); }
.w { max-width: 520px; margin: 0 auto; padding: 56px 20px 40px; }
.head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }
.head h1 { font-size: 16px; font-weight: 600; }
.nb { font-size: 12px; color: var(--lg); cursor: pointer; border: 1px solid var(--bd); border-radius: 4px; padding: 3px 8px; background: none; }
.nb:hover { color: var(--fg); border-color: var(--fg); }
.tabs { display: flex; gap: 20px; margin-bottom: 20px; border-bottom: 1px solid var(--bd); }
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
.history { margin-bottom: 20px; }
.turn { margin-bottom: 14px; }
.turn .role { font-size: 11px; color: var(--lg); margin-bottom: 3px; }
.turn .bubble { font-size: 14px; line-height: 1.6; color: var(--mg); }
.turn img { width: 100%; border-radius: 6px; display: block; margin-top: 6px; }
.turn .user-text { color: var(--fg); }
.divider { height: 1px; background: var(--bd); margin: 18px 0; }
.err { margin-top: 14px; padding: 10px 12px; border-radius: 6px; background: #fef2f2; color: #b91c1c; font-size: 13px; }
.spin { display: inline-block; width: 14px; height: 14px; border: 2px solid rgba(255,255,255,.3); border-top-color: #fff; border-radius: 50%; animation: r .5s linear infinite; vertical-align: middle; margin-right: 6px; }
@keyframes r { to { transform: rotate(360deg); } }
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
  try{
    const r=await fetch('/generate',{method:'POST',body:fd});
    const html=await r.text();
    const h=document.getElementById('history');
    const ut=document.createElement('div');ut.className='turn';
    ut.innerHTML='<div class="role">\u4f60</div><div class="bubble user-text">'+p.replace(/</g,'&lt;')+'</div>';
    h.appendChild(ut);
    const mt=document.createElement('div');mt.className='turn';
    mt.innerHTML='<div class="role">\u6a21\u578b</div><div class="bubble">'+html+'</div>';
    h.appendChild(mt);
    const dv=document.createElement('div');dv.className='divider';h.appendChild(dv);
    document.getElementById('prompt').value='';pastedFile=null;
    window.scrollTo(0,document.body.scrollHeight);
  }catch(e){alert(e.message);}
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


@rt("/generate", methods=["POST"])
async def post_generate(request):
    form = await request.form()
    prompt = form.get("prompt", "").strip()
    mode = form.get("mode", "gen")
    sid = form.get("sid", "")
    if not prompt:
        return Div("\u8bf7\u8f93\u5165\u63cf\u8ff0", cls="err")
    if not sid:
        return Div("\u7f3a\u5c11\u4f1a\u8bdd", cls="err")

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
        return Div("\u672a\u751f\u6210\u5185\u5bb9\uff0c\u8bf7\u6362\u4e2a\u63cf\u8ff0\u8bd5\u8bd5", cls="err")

    except Exception as e:
        traceback.print_exc()
        return Div(f"\u9519\u8bef\uff1a{e}", cls="err")


@rt("/generated/{fname}")
def get_generated(fname: str):
    fpath = os.path.join(GEN_DIR, fname)
    if os.path.exists(fpath):
        return FileResponse(fpath, media_type="image/png")
    return Response("Not found", status_code=404)


serve(host="0.0.0.0", port=8000)
