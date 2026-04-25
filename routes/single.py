import base64
import json
import traceback

import httpx
from starlette.responses import StreamingResponse

from files import save_image, file_response
from providers import apiyi as apiyi_provider
from providers import google as google_provider
from state import (
    sessions,
    get_client,
    get_oai_client,
    get_provider,
    get_user_model,
    has_any_client,
    google_session_key,
    apiyi_history_key,
)
from ui.single import single_page


def build_context(uid: str, sid: str) -> dict:
    session_key = google_session_key(uid, sid)
    if session_key not in sessions:
        return {"turns": [], "total_bytes": 0}
    chat = sessions[session_key]
    history = chat.get_history(curated=True)
    turns = []
    total_bytes = 0
    for content in history:
        role = content.role or "?"
        parts_desc = []
        for p in content.parts or []:
            if hasattr(p, "inline_data") and p.inline_data and p.inline_data.data:
                size = len(p.inline_data.data)
                total_bytes += size
                url = save_image(p.inline_data.data)
                parts_desc.append({"type": "image", "size": size, "url": url})
            elif hasattr(p, "text") and p.text and not getattr(p, "thought", False):
                t = p.text
                preview = (t[:40] + "\u2026") if len(t) > 40 else t
                parts_desc.append({"type": "text", "value": preview})
        if parts_desc:
            turns.append({"role": "你" if role == "user" else "模型", "parts": parts_desc})
    return {"turns": turns, "total_bytes": total_bytes}


def get_or_create_chat(sid: str, uid: str):
    """Create/get a Google genai chat session. Only for google provider."""
    client = get_client(uid)
    if not client:
        return None
    model = get_user_model(uid)
    session_key = google_session_key(uid, sid)
    if session_key not in sessions:
        sessions[session_key] = google_provider.create_chat(client, model)
    return sessions[session_key]


def sse_event(etype: str, data: str) -> str:
    return f"data: {json.dumps({'type': etype, 'data': data}, ensure_ascii=False)}\n\n"


async def post_generate(request):
    form = await request.form()
    prompt = form.get("prompt", "").strip()
    sid = form.get("sid", "")
    uid = request.cookies.get("uid", "")
    if not prompt:
        return StreamingResponse(
            iter([sse_event("error", "\u8bf7\u8f93\u5165\u63cf\u8ff0")]),
            media_type="text/event-stream",
        )
    if not sid:
        return StreamingResponse(
            iter([sse_event("error", "\u7f3a\u5c11\u4f1a\u8bdd")]),
            media_type="text/event-stream",
        )
    if not has_any_client(uid):
        return StreamingResponse(
            iter([sse_event("error", "\u8bf7\u5148\u8bbe\u7f6e API Key")]),
            media_type="text/event-stream",
        )

    img_bytes = None
    img_ct = None
    upload = form.get("image")
    if upload and hasattr(upload, "read"):
        img_bytes = await upload.read()
        img_ct = upload.content_type or "image/png"

    prov = get_provider(uid)

    if prov == "apiyi":
        # OpenAI-compatible path (non-streaming, parse markdown images)
        def stream_oai():
            try:
                oai = get_oai_client(uid)
                if not oai:
                    yield sse_event("error", "\u8bf7\u5148\u8bbe\u7f6e API Key")
                    return
                model = get_user_model(uid)
                # Build message content
                content_parts = []
                if img_bytes:
                    b64 = base64.b64encode(img_bytes).decode()
                    mime = img_ct or "image/png"
                    content_parts.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}"},
                        }
                    )
                content_parts.append({"type": "text", "text": prompt})

                # Build conversation history for apiyi (no native chat session)
                history_key = apiyi_history_key(uid, sid)
                if history_key not in sessions:
                    sessions[history_key] = []  # list of messages
                messages = list(sessions[history_key])  # copy
                messages.append(
                    {"role": "user", "content": content_parts if img_bytes else prompt}
                )

                yield sse_event(
                    "text", "\u2728 \u751f\u6210\u4e2d\u2026\u8bf7\u7a0d\u5019\n\n"
                )

                r = oai.chat.completions.create(
                    model=model,
                    messages=messages,
                    timeout=httpx.Timeout(300.0, connect=30.0),
                )
                content = r.choices[0].message.content or ""
                # Parse images and text from response
                parsed = apiyi_provider.parse_image_response(content)
                for ptype, pdata in parsed:
                    if ptype == "image":
                        url = save_image(pdata)
                        yield sse_event("image", url)
                    elif ptype == "image_url":
                        yield sse_event("image", pdata)
                    elif ptype == "text":
                        yield sse_event("text", pdata)

                # Save to conversation history
                # For history, store text-only summary (don't store huge base64)
                sessions[history_key] = messages  # includes user msg
                sessions[history_key].append({"role": "assistant", "content": content})
                # Keep last 10 turns to avoid memory bloat
                if len(sessions[history_key]) > 20:
                    sessions[history_key] = sessions[history_key][-20:]

                # Usage / cost meta
                usage = r.usage
                if usage:
                    inp_t = usage.prompt_tokens or 0
                    out_t = usage.completion_tokens or 0
                    total_t = usage.total_tokens or 0
                    parts = [
                        f"<span>\u8f93\u5165 {inp_t}</span>",
                        f"<span>\u8f93\u51fa {out_t}</span>",
                        f"<span>\u5408\u8ba1 {total_t} tokens</span>",
                    ]
                    yield sse_event("meta", "".join(parts))

                yield "data: [DONE]\n\n"
            except Exception as e:
                traceback.print_exc()
                yield sse_event("error", f"\u9519\u8bef\uff1a{e}")

        return StreamingResponse(stream_oai(), media_type="text/event-stream")

    else:
        # Google official path (streaming)
        def stream_gen():
            try:
                chat = get_or_create_chat(sid, uid)
                if not chat:
                    yield sse_event("error", "\u8bf7\u5148\u8bbe\u7f6e API Key")
                    return
                if img_bytes:
                    contents = [
                        google_provider.image_part(img_bytes, img_ct or "image/png"),
                        prompt,
                    ]
                else:
                    contents = prompt
                last_usage = None
                for chunk in chat.send_message_stream(contents):
                    if not chunk.candidates:
                        continue
                    cand = chunk.candidates[0]
                    if cand.content and cand.content.parts:
                        for part in cand.content.parts:
                            if getattr(part, "thought", False):
                                continue
                            if (
                                hasattr(part, "inline_data")
                                and part.inline_data
                                and part.inline_data.data
                            ):
                                url = save_image(part.inline_data.data)
                                yield sse_event("image", url)
                            elif hasattr(part, "text") and part.text:
                                yield sse_event("text", part.text)
                    um = getattr(chunk, "usage_metadata", None)
                    if um and um.prompt_token_count:
                        last_usage = um
                if last_usage:
                    um = last_usage
                    inp_t = um.prompt_token_count or 0
                    out_t = um.candidates_token_count or 0
                    think_t = um.thoughts_token_count or 0
                    cost = google_provider.usage_cost(um)
                    parts = [
                        f"<span>\u8f93\u5165 {inp_t}</span>",
                        f"<span>\u8f93\u51fa {out_t}</span>",
                    ]
                    if think_t:
                        parts.append(f"<span>\u601d\u7ef4 {think_t}</span>")
                    parts.append(
                        f"<span>\u5408\u8ba1 {um.total_token_count or 0} tokens</span>"
                    )
                    parts.append(f"<span>${cost:.4f}</span>")
                    yield sse_event("meta", "".join(parts))
                ctx = build_context(uid, sid)
                yield sse_event("context", json.dumps(ctx, ensure_ascii=False))
                yield "data: [DONE]\n\n"
            except Exception as e:
                traceback.print_exc()
                yield sse_event("error", f"\u9519\u8bef\uff1a{e}")

        return StreamingResponse(stream_gen(), media_type="text/event-stream")


def register_routes(rt):
    @rt("/")
    def get():
        return single_page()

    @rt("/api/generate/stream", methods=["POST"])
    async def generate(request):
        return await post_generate(request)

    @rt("/files/{fname}")
    def get_generated(fname: str):
        return file_response(fname)
