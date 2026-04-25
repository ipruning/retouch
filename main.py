# Compatibility entrypoint. The app is implemented in app.py.
from app import *  # noqa: F401,F403
from fasthtml.common import serve

if __name__ == "__main__":
    serve(host="0.0.0.0", port=8000)
