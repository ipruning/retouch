from fasthtml.common import *
from monsterui.all import *
from config import MAIN_JS
from ui.layout import key_modal, page_header

def single_page():
    return Container(
        page_header(
            "Retouch",
            A(
                "\u6279\u91cf",
                href="/batch",
                cls="uk-btn uk-btn-default uk-btn-sm whitespace-nowrap",
            ),
            Button(
                "\u65b0\u5bf9\u8bdd",
                cls=(ButtonT.default, ButtonT.sm, "whitespace-nowrap"),
                onclick="newChat()",
            ),
        ),
        Card(
            Div(Div("\u65b0\u5bf9\u8bdd", cls="ctx-empty"), id="ctx-list"),
            DividerLine(),
            Div(
                Img(src="", alt=""),
                Span(cls="upload-name"),
                Button("\u00d7", cls="upload-x", onclick="clearImage()"),
                id="upload-preview",
                cls="upload-preview hide",
            ),
            Textarea(
                id="prompt",
                placeholder="\u63cf\u8ff0\u4f60\u60f3\u8981\u7684\u56fe\u7247\u2026",
                cls="uk-textarea",
                rows=3,
            ),
            header=P("\u4e0a\u4e0b\u6587", cls=TextPresets.muted_sm),
            footer=Div(
                DivFullySpaced(
                    Label(
                        UkIcon("paperclip", height=16),
                        " \u4e0a\u4f20\u56fe\u7247",
                        Input(
                            type="file",
                            id="file",
                            accept="image/*",
                            onchange="onFile(this)",
                            cls="hidden",
                        ),
                        cls="cursor-pointer text-sm text-muted-foreground flex items-center gap-1",
                    ),
                    Button(
                        "\u751f\u6210",
                        id="btn",
                        cls=(ButtonT.primary, "min-w-[120px] justify-center"),
                        onclick="go()",
                    ),
                ),
                Div(id="env-footer", cls="text-xs text-muted-foreground mt-2"),
            ),
        ),
        Div(id="result-area", cls="mt-4"),
        key_modal(),
        Script(MAIN_JS),
        cls=ContainerT.sm,
        id="main",
        style="display:flex;flex-direction:column;min-height:100vh;",
    )
