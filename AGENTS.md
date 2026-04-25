# Retouch – AI Image Studio

## Run

```bash
uv run main.py          # starts on 0.0.0.0:8000
```

No tests or linter configured. Deploy via systemd (`retouch.service`).

## Architecture

FastHTML + MonsterUI app split into focused modules. `main.py` is a compatibility entrypoint; `app.py` creates the app and registers route modules.

- **Providers**: Google GenAI (native streaming) and Apiyi (OpenAI-compatible, non-streaming).
- **State**: In-memory dicts (`user_api_keys`, `google_clients`, `apiyi_clients`, `user_providers`, `user_models`, `sessions`, `batches`) keyed by cookie `uid` / session `sid`. No database.
- **Routes**: pages at `/` and `/batch`; API under `/api/*`; generated files under `/files/{fname}`.
- **Generated files**: saved to `generated/` dir, served at `/files/{fname}`.
- **Batch processing**: `ThreadPoolExecutor` (`batch_pool`); items tracked in `batches` dict; download as ZIP.

## Code Style

- **Frameworks**: `fasthtml.common`, `monsterui.all`, `google.genai`, `openai`, `httpx`, `starlette`.
- **Formatting**: Compact/dense style; multiple statements per line separated by `;`. No formatter enforced.
- **JS/CSS**: Inline as Python string constants (`EXTRA_CSS`, `KEY_JS`, `MAIN_JS`, `BATCH_JS_BODY`).
- **Naming**: `snake_case` for Python, `camelCase` for JS. Route handlers match HTTP method (`get`, `post_*`).
- **UI text**: Chinese (Simplified). Keep all user-facing strings in Chinese.
- **Error handling**: Minimal; `try/except` with `traceback.print_exc()` in streaming generators.
- **Logging**: `logging.getLogger('retouch')` at INFO level.
