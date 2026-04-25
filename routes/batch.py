import base64
import io
import logging
import os
import threading
import time
import traceback
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor

import httpx
from fasthtml.common import JSONResponse, Response
from starlette.responses import StreamingResponse

from config import GEN_DIR, USER_SEM_LIMIT, GLOBAL_SEM_LIMIT, BATCH_MAX_IMAGES, USER_MAX_BATCHES, BATCH_TTL
from files import save_image
from providers import apiyi as apiyi_provider
from providers import google as google_provider
from state import user_api_keys, get_client, get_provider, get_user_model, has_any_client
from ui.batch import batch_page

log = logging.getLogger("retouch")

# ═══════════════════════════════════════════════════════════════════════════
# BATCH MODE
# ═══════════════════════════════════════════════════════════════════════════

# ── Batch concurrency infrastructure ──
batch_pool = ThreadPoolExecutor(max_workers=GLOBAL_SEM_LIMIT)
_global_sem = threading.Semaphore(GLOBAL_SEM_LIMIT)
_user_sems: dict[str, threading.Semaphore] = {}
_user_sems_lock = threading.Lock()
batches: dict = {}
_batches_lock = threading.Lock()


def _get_user_sem(uid: str) -> threading.Semaphore:
    with _user_sems_lock:
        if uid not in _user_sems:
            _user_sems[uid] = threading.Semaphore(USER_SEM_LIMIT)
        return _user_sems[uid]


def _user_active_batches(uid: str) -> int:
    with _batches_lock:
        return sum(
            1 for b in batches.values() if b.get("uid") == uid and not b.get("finished")
        )


def _cleanup_old_batches():
    """Remove batches older than BATCH_TTL."""
    now = time.time()
    with _batches_lock:
        to_del = [
            bid
            for bid, b in batches.items()
            if b.get("finished") and now - b["finished"] > BATCH_TTL
        ]
        for bid in to_del:
            del batches[bid]


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
    uid = batch.get("uid", "")
    prov = get_provider(uid)
    if not has_any_client(uid):
        item["status"] = "failed"
        item["error"] = "API Key \u672a\u8bbe\u7f6e"
        _maybe_finish_batch(batch_id)
        return
    user_sem = _get_user_sem(uid)
    # Acquire both semaphores: user-level then global
    user_sem.acquire()
    _global_sem.acquire()
    item["status"] = "running"
    try:
        with open(item["src_path"], "rb") as f:
            img_bytes = f.read()

        if prov == "apiyi":
            # OpenAI-compatible path — create fresh client per thread for thread safety
            key = user_api_keys.get(uid, "")
            model = get_user_model(uid)
            oai = apiyi_provider.create_client(key)
            b64 = base64.b64encode(img_bytes).decode()
            mime = item["src_mime"] or "image/png"
            log.info(
                f"Batch {batch_id}/{item_id}: calling Apiyi model={model} img_size={len(img_bytes) / 1024:.0f}KB b64_size={len(b64) / 1024:.0f}KB"
            )
            t0 = time.time()
            r = oai.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime};base64,{b64}"},
                            },
                            {"type": "text", "text": batch["prompt"]},
                        ],
                    }
                ],
            )
            elapsed = time.time() - t0
            content = r.choices[0].message.content or ""
            log.info(
                f"Batch {batch_id}/{item_id}: got response in {elapsed:.1f}s, content_len={len(content)}"
            )
            result_url = None
            result_text = ""
            parsed = apiyi_provider.parse_image_response(content)
            for ptype, pdata in parsed:
                if ptype == "image" and not result_url:
                    result_url = save_image(pdata)
                elif ptype == "image_url" and not result_url:
                    # Try once more to download
                    try:
                        dl = httpx.get(pdata, timeout=30, follow_redirects=True)
                        if dl.status_code == 200 and len(dl.content) > 100:
                            result_url = save_image(dl.content)
                        else:
                            result_url = pdata
                    except Exception:
                        result_url = pdata
                elif ptype == "text":
                    result_text += pdata
            # Proxy usage pricing is opaque, so cost remains unavailable here.
            cost = 0.0
        else:
            # Google official path
            client = get_client(uid)
            model = get_user_model(uid)
            response = client.models.generate_content(
                model=model,
                contents=[
                    google_provider.image_part(img_bytes, item["src_mime"]),
                    batch["prompt"],
                ],
                config=google_provider.image_config(),
            )
            result_url = None
            result_text = ""
            if response.candidates and response.candidates[0].content:
                for part in response.candidates[0].content.parts or []:
                    if getattr(part, "thought", False):
                        continue
                    if (
                        hasattr(part, "inline_data")
                        and part.inline_data
                        and part.inline_data.data
                    ):
                        result_url = save_image(part.inline_data.data)
                    elif hasattr(part, "text") and part.text:
                        result_text += part.text
            cost = 0.0
            um = getattr(response, "usage_metadata", None)
            if um:
                cost = google_provider.usage_cost(um)

        item["result_url"] = result_url
        item["result_text"] = result_text
        item["cost"] = cost
        if result_url:
            item["status"] = "done"
        else:
            item["status"] = "failed"
            item["error"] = (
                item.get("error") or "\u6a21\u578b\u672a\u8fd4\u56de\u56fe\u7247"
            )
    except Exception as e:
        log.error(f"Batch {batch_id}/{item_id}: error: {e}")
        traceback.print_exc()
        item["status"] = "failed"
        item["error"] = str(e)[:300]
    finally:
        _global_sem.release()
        user_sem.release()
        _maybe_finish_batch(batch_id)


def _maybe_finish_batch(batch_id: str):
    """Mark batch as finished when all items are terminal, trigger cleanup."""
    batch = batches.get(batch_id)
    if not batch or batch.get("finished"):
        return
    if all(it["status"] in ("done", "failed") for it in batch["items"]):
        batch["finished"] = time.time()
        _cleanup_old_batches()





async def post_batch_start(request):
    form = await request.form()
    prompt = form.get("prompt", "").strip()
    uid = request.cookies.get("uid", "")
    if not has_any_client(uid):
        return JSONResponse(
            {"error": "\u8bf7\u5148\u8bbe\u7f6e API Key"}, status_code=400
        )
    if not prompt:
        return JSONResponse(
            {"error": "\u8bf7\u8f93\u5165\u63d0\u793a\u8bcd"}, status_code=400
        )
    # Rate-limit: max concurrent batches per user
    if _user_active_batches(uid) >= USER_MAX_BATCHES:
        return JSONResponse(
            {
                "error": f"\u6bcf\u4f4d\u7528\u6237\u6700\u591a\u540c\u65f6\u8fd0\u884c {USER_MAX_BATCHES} \u4e2a\u6279\u6b21"
            },
            status_code=429,
        )
    raw_images = form.getlist("images")
    if not raw_images:
        return JSONResponse(
            {"error": "\u8bf7\u4e0a\u4f20\u56fe\u7247"}, status_code=400
        )
    if len(raw_images) > BATCH_MAX_IMAGES:
        return JSONResponse(
            {
                "error": f"\u5355\u6b21\u6700\u591a {BATCH_MAX_IMAGES} \u5f20\u56fe\u7247"
            },
            status_code=400,
        )
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
        items.append(
            {
                "id": item_id,
                "status": "pending",
                "src_url": src_url,
                "src_path": src_path,
                "src_mime": mime,
                "result_url": None,
                "result_text": None,
                "error": None,
                "cost": 0.0,
            }
        )
    if not items:
        return JSONResponse(
            {"error": "\u672a\u68c0\u6d4b\u5230\u6709\u6548\u56fe\u7247"},
            status_code=400,
        )
    with _batches_lock:
        batches[batch_id] = {
            "prompt": prompt,
            "items": items,
            "uid": uid,
            "finished": None,
        }
    for item in items:
        batch_pool.submit(process_batch_item, batch_id, item["id"])
    return JSONResponse({"batch_id": batch_id})


def get_batch_status(batch_id: str):
    batch = batches.get(batch_id)
    if not batch:
        return JSONResponse(
            {"error": "\u6279\u6b21\u4e0d\u5b58\u5728"}, status_code=404
        )
    items_out = []
    total = len(batch["items"])
    done = failed = running = 0
    cost = 0.0
    for it in batch["items"]:
        s = it["status"]
        if s == "done":
            done += 1
        elif s == "failed":
            failed += 1
        elif s == "running":
            running += 1
        cost += it.get("cost", 0.0)
        items_out.append(
            {
                "id": it["id"],
                "status": s,
                "src_url": it["src_url"],
                "result_url": it.get("result_url"),
                "result_text": it.get("result_text"),
                "error": it.get("error"),
                "cost": it.get("cost", 0.0),
            }
        )
    finished = batch.get("finished") is not None
    return JSONResponse(
        {
            "total": total,
            "done": done,
            "failed": failed,
            "running": running,
            "cost": cost,
            "finished": finished,
            "items": items_out,
        }
    )


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


def get_batch_download(batch_id: str):
    batch = batches.get(batch_id)
    if not batch:
        return Response("Not found", status_code=404)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, it in enumerate(batch["items"]):
            if it["status"] == "done" and it.get("result_url"):
                fpath = os.path.join(GEN_DIR, os.path.basename(it["result_url"]))
                if os.path.exists(fpath):
                    zf.write(fpath, f"result_{i + 1}.jpg")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=batch_{batch_id}.zip"},
    )


def register_routes(rt):
    @rt("/batch")
    def batch_index():
        return batch_page()

    @rt("/api/batches", methods=["POST"])
    async def batch_start(request):
        return await post_batch_start(request)

    @rt("/api/batches/{batch_id}")
    def batch_status(batch_id: str):
        return get_batch_status(batch_id)

    @rt("/api/batches/{batch_id}/items/{item_id}/retry", methods=["POST"])
    def batch_retry(batch_id: str, item_id: str):
        return post_batch_retry(batch_id, item_id)

    @rt("/api/batches/{batch_id}/archive")
    def batch_download(batch_id: str):
        return get_batch_download(batch_id)
