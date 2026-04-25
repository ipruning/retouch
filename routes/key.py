import uuid
from fasthtml.common import JSONResponse

from config import DEFAULT_MODEL, PROVIDERS
from providers import apiyi as apiyi_provider
from providers import google as google_provider
from state import (
    user_api_keys,
    google_clients,
    apiyi_clients,
    user_providers,
    user_models,
    get_provider,
    get_user_model,
    clear_sessions_for_user,
)


def model_label_for(provider: str, model: str) -> str:
    for mid, mlbl in PROVIDERS.get(provider, {}).get("models", []):
        if mid == model:
            return mlbl
    return model


def register_routes(rt):
    @rt("/api/key", methods=["POST"])
    async def post_api_key(request):
        body = await request.json()
        key = (body.get("key") or "").strip()
        provider = (body.get("provider") or "google").strip()
        model = (body.get("model") or DEFAULT_MODEL).strip()
        if not key:
            return JSONResponse({"ok": False, "error": "Key 不能为空"})
        uid = request.cookies.get("uid", "")
        if not uid:
            uid = uuid.uuid4().hex[:16]
        model_label = model_label_for(provider, model)

        if provider == "apiyi":
            try:
                apiyi_provider.validate_key(key)
            except Exception as e:
                return JSONResponse({"ok": False, "error": f"Key 无效: {e}"})
            apiyi_clients[uid] = apiyi_provider.create_client(key)
            google_clients.pop(uid, None)
        else:
            try:
                c = google_provider.validate_key(key, model)
            except Exception as e:
                return JSONResponse({"ok": False, "error": f"Key 无效: {e}"})
            google_clients[uid] = c
            apiyi_clients.pop(uid, None)

        user_api_keys[uid] = key
        user_providers[uid] = provider
        user_models[uid] = model
        clear_sessions_for_user(uid)
        resp = JSONResponse(
            {"ok": True, "masked": key[:6] + "..." + key[-4:], "model_label": model_label}
        )
        resp.set_cookie("uid", uid, max_age=86400 * 365, httponly=True, samesite="lax")
        return resp

    @rt("/api/key", methods=["GET"])
    def get_api_key(request):
        uid = request.cookies.get("uid", "")
        if uid and uid in user_api_keys:
            k = user_api_keys[uid]
            prov = get_provider(uid)
            model = get_user_model(uid)
            return JSONResponse(
                {
                    "has_key": True,
                    "masked": k[:6] + "..." + k[-4:],
                    "provider": prov,
                    "model": model,
                    "model_label": model_label_for(prov, model),
                }
            )
        return JSONResponse({"has_key": False})

    @rt("/api/key", methods=["DELETE"])
    def delete_api_key(request):
        uid = request.cookies.get("uid", "")
        if uid:
            user_api_keys.pop(uid, None)
            google_clients.pop(uid, None)
            apiyi_clients.pop(uid, None)
            user_providers.pop(uid, None)
            user_models.pop(uid, None)
            clear_sessions_for_user(uid)
        return JSONResponse({"ok": True})
