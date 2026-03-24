import uuid, base64, io, os, traceback
from fasthtml.common import *
from google import genai
from google.genai import types

# --- Config ---
API_KEY = "REDACTED_GOOGLE_API_KEY"
MODEL = "gemini-2.5-flash-image"
GEN_DIR = "generated"
os.makedirs(GEN_DIR, exist_ok=True)

client = genai.Client(api_key=API_KEY)

# --- FastHTML App ---
app, rt = fast_app(
    hdrs=[
        Style("""
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0f0f11; color: #e0e0e0; min-height: 100vh; }
            .container { max-width: 720px; margin: 0 auto; padding: 24px 16px; }
            h1 { text-align: center; font-size: 1.8rem; margin-bottom: 8px; background: linear-gradient(135deg, #6366f1, #a855f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
            .subtitle { text-align: center; color: #888; margin-bottom: 32px; font-size: 0.95rem; }
            .card { background: #1a1a2e; border: 1px solid #2a2a3e; border-radius: 16px; padding: 28px; margin-bottom: 24px; }
            label { display: block; font-weight: 600; margin-bottom: 8px; font-size: 0.9rem; color: #aaa; text-transform: uppercase; letter-spacing: 0.05em; }
            textarea { width: 100%; min-height: 100px; padding: 14px; border-radius: 10px; border: 1px solid #333; background: #12121a; color: #e0e0e0; font-size: 1rem; resize: vertical; outline: none; transition: border 0.2s; }
            textarea:focus { border-color: #6366f1; }
            .file-upload { position: relative; }
            .file-label { display: flex; align-items: center; gap: 10px; padding: 14px; border: 2px dashed #333; border-radius: 10px; cursor: pointer; transition: all 0.2s; color: #888; }
            .file-label:hover { border-color: #6366f1; color: #bbb; }
            .file-label svg { flex-shrink: 0; }
            input[type=file] { position: absolute; opacity: 0; width: 100%; height: 100%; top: 0; left: 0; cursor: pointer; }
            .btn { display: block; width: 100%; padding: 16px; border: none; border-radius: 12px; font-size: 1.05rem; font-weight: 600; cursor: pointer; transition: all 0.2s; }
            .btn-primary { background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; }
            .btn-primary:hover { transform: translateY(-1px); box-shadow: 0 8px 24px rgba(99,102,241,0.3); }
            .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; transform: none; box-shadow: none; }
            .preview-row { display: flex; gap: 12px; margin-top: 12px; }
            .preview-img { max-width: 120px; max-height: 120px; border-radius: 8px; border: 1px solid #333; }
            #result { margin-top: 24px; }
            .result-card { background: #1a1a2e; border: 1px solid #2a2a3e; border-radius: 16px; overflow: hidden; }
            .result-card img { width: 100%; display: block; }
            .result-text { padding: 16px; color: #ccc; line-height: 1.6; font-size: 0.95rem; }
            .spinner { display: inline-block; width: 20px; height: 20px; border: 3px solid rgba(255,255,255,0.3); border-top-color: white; border-radius: 50%; animation: spin 0.6s linear infinite; vertical-align: middle; margin-right: 8px; }
            @keyframes spin { to { transform: rotate(360deg); } }
            .error { background: #2d1b1b; border: 1px solid #5c2626; border-radius: 12px; padding: 16px; color: #f87171; margin-top: 24px; }
            .mode-tabs { display: flex; gap: 8px; margin-bottom: 20px; }
            .mode-tab { flex: 1; padding: 10px; text-align: center; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 0.9rem; border: 1px solid #333; background: #12121a; color: #888; transition: all 0.2s; }
            .mode-tab.active { background: #6366f1; color: white; border-color: #6366f1; }
            .upload-section { display: none; }
            .upload-section.show { display: block; }
            .gap { height: 20px; }
        """)
    ],
    live=False
)


def layout(*children):
    return Div(
        Div(
            H1("✨ AI Image Studio"),
            P("Generate images from text, or edit images with prompts", cls="subtitle"),
            *children,
            cls="container"
        )
    )


@rt("/")
def get():
    return layout(
        Div(
            # Mode tabs
            Div(
                Div("🎨 Generate", cls="mode-tab active", id="tab-gen",
                    onclick="switchMode('gen')"),
                Div("✏️ Edit Image", cls="mode-tab", id="tab-edit",
                    onclick="switchMode('edit')"),
                cls="mode-tabs"
            ),
            # Upload section (hidden by default)
            Div(
                Label("Upload Image"),
                Div(
                    Label(
                        NotStr('<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>'),
                        Span("Click or drag an image here", id="file-text"),
                        cls="file-label", **{"for": "image-input"}
                    ),
                    Input(type="file", name="image", id="image-input", accept="image/*",
                          onchange="previewFile(this)"),
                    cls="file-upload"
                ),
                Div(id="preview-area", cls="preview-row"),
                id="upload-section", cls="upload-section"
            ),
            Div(cls="gap"),
            # Prompt
            Label("Prompt"),
            Textarea(
                name="prompt", id="prompt-input",
                placeholder="Describe the image you want to create..."
            ),
            Div(cls="gap"),
            # Submit
            Button("Generate ✨", cls="btn btn-primary", id="submit-btn",
                   onclick="submitForm()"),
            cls="card"
        ),
        Div(id="result"),
        Script("""
            let currentMode = 'gen';

            function switchMode(mode) {
                currentMode = mode;
                document.getElementById('tab-gen').classList.toggle('active', mode==='gen');
                document.getElementById('tab-edit').classList.toggle('active', mode==='edit');
                document.getElementById('upload-section').classList.toggle('show', mode==='edit');
                document.getElementById('submit-btn').textContent = mode==='gen' ? 'Generate ✨' : 'Edit Image ✏️';
            }

            function previewFile(input) {
                const area = document.getElementById('preview-area');
                const fileText = document.getElementById('file-text');
                area.innerHTML = '';
                if (input.files && input.files[0]) {
                    fileText.textContent = input.files[0].name;
                    const reader = new FileReader();
                    reader.onload = e => {
                        const img = document.createElement('img');
                        img.src = e.target.result;
                        img.className = 'preview-img';
                        area.appendChild(img);
                    };
                    reader.readAsDataURL(input.files[0]);
                } else {
                    fileText.textContent = 'Click or drag an image here';
                }
            }

            async function submitForm() {
                const btn = document.getElementById('submit-btn');
                const result = document.getElementById('result');
                const prompt = document.getElementById('prompt-input').value.trim();
                if (!prompt) { alert('Please enter a prompt'); return; }

                const formData = new FormData();
                formData.append('prompt', prompt);
                formData.append('mode', currentMode);

                const fileInput = document.getElementById('image-input');
                if (currentMode === 'edit' && fileInput.files[0]) {
                    formData.append('image', fileInput.files[0]);
                }

                btn.disabled = true;
                btn.innerHTML = '<span class="spinner"></span> Working...';
                result.innerHTML = '';

                try {
                    const resp = await fetch('/generate', { method: 'POST', body: formData });
                    result.innerHTML = await resp.text();
                } catch(e) {
                    result.innerHTML = '<div class="error">Network error: ' + e.message + '</div>';
                } finally {
                    btn.disabled = false;
                    btn.innerHTML = currentMode==='gen' ? 'Generate ✨' : 'Edit Image ✏️';
                }
            }
        """)
    )


@rt("/generate", methods=["POST"])
async def post_generate(request):
    form = await request.form()
    prompt = form.get("prompt", "").strip()
    mode = form.get("mode", "gen")

    if not prompt:
        return Div("Please provide a prompt.", cls="error")

    try:
        if mode == "edit":
            # Image + Prompt editing
            upload = form.get("image")
            if upload and hasattr(upload, 'read'):
                img_bytes = await upload.read()
                content_type = upload.content_type or "image/png"
                contents = [
                    types.Part.from_bytes(data=img_bytes, mime_type=content_type),
                    prompt
                ]
            else:
                # No image provided, fall back to text generation
                contents = prompt

            response = client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"]
                )
            )

            parts_html = []
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    fname = f"{uuid.uuid4().hex}.png"
                    fpath = os.path.join(GEN_DIR, fname)
                    with open(fpath, 'wb') as f:
                        f.write(part.inline_data.data)
                    parts_html.append(
                        Img(src=f"/generated/{fname}", alt="Generated image")
                    )
                if hasattr(part, 'text') and part.text:
                    parts_html.append(Div(part.text, cls="result-text"))

            return Div(*parts_html, cls="result-card") if parts_html else Div("No output generated.", cls="error")

        else:
            # Text-only → use Imagen 4 for best quality
            response = client.models.generate_images(
                model="imagen-4.0-generate-001",
                prompt=prompt,
                config=types.GenerateImagesConfig(number_of_images=1)
            )

            if response.generated_images:
                fname = f"{uuid.uuid4().hex}.png"
                fpath = os.path.join(GEN_DIR, fname)
                with open(fpath, 'wb') as f:
                    f.write(response.generated_images[0].image.image_bytes)
                return Div(
                    Img(src=f"/generated/{fname}", alt="Generated image"),
                    cls="result-card"
                )
            else:
                return Div("No image was generated. Try a different prompt.", cls="error")

    except Exception as e:
        traceback.print_exc()
        return Div(f"Error: {str(e)}", cls="error")


# Serve generated images
@rt("/generated/{fname}")
def get_generated(fname: str):
    fpath = os.path.join(GEN_DIR, fname)
    if os.path.exists(fpath):
        return FileResponse(fpath, media_type="image/png")
    return Response("Not found", status_code=404)


serve(host="0.0.0.0", port=8000)
