import base64
import httpx
from openai import OpenAI


def create_client(key: str, timeout=300.0):
    return OpenAI(
        api_key=key,
        base_url="https://api.apiyi.com/v1",
        timeout=httpx.Timeout(timeout, connect=30.0 if timeout > 30 else 10.0),
        max_retries=0,
    )


def validate_key(key: str):
    c = OpenAI(
        api_key=key,
        base_url="https://api.apiyi.com/v1",
        timeout=httpx.Timeout(15.0, connect=10.0),
    )
    c.models.list()

def parse_image_response(content: str):
    """Parse OpenAI-compatible response that contains markdown image(s).
    Returns list of (type, data) tuples:
      ('image', bytes)    — base64-decoded inline image
      ('image_url', str)  — external URL (e.g. OSS)
      ('text', str)       — plain text
    Supports both data:image base64 and https:// URL formats.
    """
    # Match both: ![image](data:image/...;base64,...) and ![image](https://...)
    IMG_RE = re.compile(r"!\[(?:image)?\]\(([^)]+)\)")
    parts = []
    last_end = 0
    for m in IMG_RE.finditer(content):
        text_before = content[last_end : m.start()].strip()
        if text_before:
            parts.append(("text", text_before))
        src = m.group(1)
        if src.startswith("data:image/"):
            # Inline base64
            try:
                b64 = src.split(",", 1)[1]
                img_data = base64.b64decode(b64)
                parts.append(("image", img_data))
            except Exception:
                pass
        elif src.startswith("http://") or src.startswith("https://"):
            # External URL — download it
            try:
                resp = httpx.get(src, timeout=30, follow_redirects=True)
                if resp.status_code == 200 and len(resp.content) > 100:
                    parts.append(("image", resp.content))
                else:
                    parts.append(("image_url", src))
            except Exception:
                parts.append(("image_url", src))
        last_end = m.end()
    # Remaining text
    text_after = content[last_end:].strip()
    if text_after:
        parts.append(("text", text_after))
    return parts
