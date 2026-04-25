import logging

from fasthtml.common import *
from monsterui.all import *

from config import EXTRA_CSS
from routes import batch, key, single

log = logging.getLogger("retouch")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s"
)

app, rt = fast_app(
    hdrs=Theme.blue.headers(mode="auto") + [Style(EXTRA_CSS)],
    title="Retouch",
    live=False,
)

key.register_routes(rt)
single.register_routes(rt)
batch.register_routes(rt)

if __name__ == "__main__":
    serve(host="0.0.0.0", port=8000)
