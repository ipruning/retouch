import hashlib
import os
from fasthtml.common import FileResponse, Response
from config import GEN_DIR


def detect_image_ext(data: bytes) -> str:
    if data[:4] == b"\x89PNG":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return "jpg"


def file_url(fname: str) -> str:
    return f"/files/{fname}"


def save_image(data: bytes) -> str:
    h = hashlib.md5(data).hexdigest()
    ext = detect_image_ext(data)
    fname = f"{h}.{ext}"
    fpath = os.path.join(GEN_DIR, fname)
    if not os.path.exists(fpath):
        with open(fpath, "wb") as f:
            f.write(data)
    return file_url(fname)


def detect_mime(fpath: str) -> str:
    try:
        with open(fpath, "rb") as f:
            hdr = f.read(12)
        if hdr[:4] == b"\x89PNG":
            return "image/png"
        if hdr[:4] == b"RIFF" and hdr[8:12] == b"WEBP":
            return "image/webp"
    except Exception:
        pass
    return "image/jpeg"


def file_response(fname: str):
    fpath = os.path.join(GEN_DIR, fname)
    if os.path.exists(fpath):
        return FileResponse(fpath, media_type=detect_mime(fpath))
    return Response("Not found", status_code=404)
