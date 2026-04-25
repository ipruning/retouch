from config import DEFAULT_MODEL

api_keys: dict = {}  # uid -> key
clients: dict = {}  # uid -> google genai Client
oai_clients: dict = {}  # uid -> OpenAI Client
providers: dict = {}  # uid -> "google" | "apiyi"
user_models: dict = {}  # uid -> selected model name
sessions: dict = {}  # sid -> google chat session or apiyi history


def get_client(uid: str):
    return clients.get(uid)


def get_oai_client(uid: str):
    return oai_clients.get(uid)


def get_provider(uid: str) -> str:
    return providers.get(uid, "google")


def get_user_model(uid: str) -> str:
    return user_models.get(uid, DEFAULT_MODEL)


def has_any_client(uid: str) -> bool:
    return uid in clients or uid in oai_clients


def clear_sessions_for_user(uid: str):
    to_del = [k for k in sessions if k.startswith(uid + "_")]
    for k in to_del:
        del sessions[k]


def clear_user(uid: str):
    api_keys.pop(uid, None)
    clients.pop(uid, None)
    oai_clients.pop(uid, None)
    providers.pop(uid, None)
    user_models.pop(uid, None)
    clear_sessions_for_user(uid)
