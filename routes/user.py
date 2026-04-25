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


def providers_payload() -> dict:
    return {
        "providers": [
            {
                "id": pid,
                "name": cfg["name"],
                "models": [
                    {
                        "id": mid,
                        "name": label,
                        "supports_stream": pid == "google",
                        "supports_image_input": True,
                        "supports_image_output": True,
                    }
                    for mid, label in cfg.get("models", [])
                ],
            }
            for pid, cfg in PROVIDERS.items()
        ]
    }


def register_routes(rt):
    @rt("/api/providers", methods=["GET"])
    def get_providers():
        return JSONResponse(providers_payload())

    @rt("/api/user/config", methods=["PUT"])
    async def put_user_config(request):
        body = await request.json()
        key = (body.get("api_key") or body.get("key") or "").strip()
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
        masked_key = key[:6] + "..." + key[-4:]
        resp = JSONResponse(
            {"ok": True, "masked_key": masked_key, "masked": masked_key, "model_label": model_label}
        )
        resp.set_cookie("uid", uid, max_age=86400 * 365, httponly=True, samesite="lax")
        return resp

    @rt("/api/user/config", methods=["GET"])
    def get_user_config(request):
        uid = request.cookies.get("uid", "")
        if uid and uid in user_api_keys:
            k = user_api_keys[uid]
            prov = get_provider(uid)
            model = get_user_model(uid)
            return JSONResponse(
                {
                    "has_key": True,
                    "masked_key": k[:6] + "..." + k[-4:],
                    "masked": k[:6] + "..." + k[-4:],
                    "provider": prov,
                    "model": model,
                    "model_label": model_label_for(prov, model),
                }
            )
        return JSONResponse({"has_key": False})

    @rt("/api/user/config", methods=["DELETE"])
    def delete_user_config(request):
        uid = request.cookies.get("uid", "")
        if uid:
            user_api_keys.pop(uid, None)
            google_clients.pop(uid, None)
            apiyi_clients.pop(uid, None)
            user_providers.pop(uid, None)
            user_models.pop(uid, None)
            clear_sessions_for_user(uid)
        return JSONResponse({"ok": True})
