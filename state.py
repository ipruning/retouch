from config import DEFAULT_MODEL

user_api_keys: dict = {}  # uid -> provider API key
google_clients: dict = {}  # uid -> google genai Client
apiyi_clients: dict = {}  # uid -> OpenAI-compatible Apiyi Client
user_providers: dict = {}  # uid -> "google" | "apiyi"
user_models: dict = {}  # uid -> selected model name
sessions: dict = {}  # "{uid}_{sid}" -> Google chat, or "{uid}_oai_{sid}" -> Apiyi history


def google_session_key(uid: str, sid: str) -> str:
    return f"{uid}_{sid}"


def apiyi_history_key(uid: str, sid: str) -> str:
    return f"{uid}_oai_{sid}"


def get_client(uid: str):
    return google_clients.get(uid)


def get_oai_client(uid: str):
    return apiyi_clients.get(uid)


def get_provider(uid: str) -> str:
    return user_providers.get(uid, "google")


def get_user_model(uid: str) -> str:
    return user_models.get(uid, DEFAULT_MODEL)


def has_any_client(uid: str) -> bool:
    return uid in google_clients or uid in apiyi_clients


def clear_sessions_for_user(uid: str):
    to_del = [k for k in sessions if k.startswith(uid + "_")]
    for k in to_del:
        del sessions[k]


def clear_user(uid: str):
    user_api_keys.pop(uid, None)
    google_clients.pop(uid, None)
    apiyi_clients.pop(uid, None)
    user_providers.pop(uid, None)
    user_models.pop(uid, None)
    clear_sessions_for_user(uid)
