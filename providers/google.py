from google import genai
from google.genai import types as genai_types


def create_client(key: str):
    return genai.Client(api_key=key)


def validate_key(key: str, model: str):
    c = create_client(key)
    c.models.get(model=f"models/{model}")
    return c


def create_chat(client, model: str):
    return client.chats.create(
        model=model,
        config=genai_types.GenerateContentConfig(
            thinking_config=genai_types.ThinkingConfig(
                thinking_level=genai_types.ThinkingLevel.HIGH
            ),
            response_modalities=["TEXT", "IMAGE"],
        ),
    )


def image_part(data: bytes, mime_type: str):
    return genai_types.Part.from_bytes(data=data, mime_type=mime_type)


def image_config():
    return genai_types.GenerateContentConfig(
        thinking_config=genai_types.ThinkingConfig(
            thinking_level=genai_types.ThinkingLevel.HIGH
        ),
        response_modalities=["TEXT", "IMAGE"],
    )


def usage_cost(um) -> float:
    if not um:
        return 0.0
    inp_t = um.prompt_token_count or 0
    out_t = um.candidates_token_count or 0
    think_t = um.thoughts_token_count or 0
    img_t = 0
    for d in um.candidates_tokens_details or []:
        if d.modality and d.modality.value == "IMAGE":
            img_t = d.token_count or 0
    txt_out_t = out_t - img_t
    return (inp_t * 0.50 + (txt_out_t + think_t) * 3.0 + img_t * 60.0) / 1_000_000
