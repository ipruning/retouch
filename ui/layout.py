from fasthtml.common import *
from monsterui.all import *

def key_modal():
    """Shared API Key settings modal with provider/model selection."""
    return Modal(
        Div(
            P("\u63d0\u4f9b\u5546", cls="text-sm font-medium mb-1"),
            # Use raw <select> to avoid uk-select web component issues with JS
            NotStr(
                '<select id="provider-select" class="uk-select" onchange="onProviderChange(this)">'
                '<option value="google" selected>Google \u5b98\u65b9</option>'
                '<option value="apiyi">Apiyi \u4ee3\u7406</option>'
                "</select>"
            ),
            cls="mb-3",
        ),
        Div(
            P("\u6a21\u578b", cls="text-sm font-medium mb-1"),
            NotStr(
                '<select id="model-select" class="uk-select">'
                '<option value="gemini-3.1-flash-image-preview" selected>Gemini 3.1 Flash Image</option>'
                '<option value="gemini-3-pro-image-preview">Gemini 3 Pro Image</option>'
                "</select>"
            ),
            cls="mb-3",
        ),
        P(
            "\u5728 ",
            A(
                "Google AI Studio",
                href="https://aistudio.google.com/apikey",
                target="_blank",
                cls="text-primary underline",
            ),
            " \u6216 ",
            A(
                "Apiyi",
                href="https://api.apiyi.com",
                target="_blank",
                cls="text-primary underline",
            ),
            " \u83b7\u53d6 Key",
            cls="text-sm text-muted-foreground",
        ),
        Input(
            type="password",
            id="key-input",
            placeholder="AIzaSy...",
            cls="uk-input font-mono",
        ),
        Div(id="key-msg"),
        header=H3("\u8bbe\u7f6e API Key", cls="text-lg font-semibold"),
        footer=DivFullySpaced(
            Button("\u6e05\u9664", cls=ButtonT.ghost, onclick="clearKey()"),
            Button(
                "\u4fdd\u5b58",
                cls=ButtonT.primary,
                onclick="saveKey()",
                id="key-save-btn",
            ),
        ),
        id="key-modal",
    )


def page_header(title, *extra_buttons):
    return Div(
        Div(
            Div(
                H3(title, cls="font-bold text-lg sm:text-xl whitespace-nowrap"),
                Span(id="model-indicator", cls="text-xs text-muted-foreground"),
                cls="flex items-center gap-2",
            ),
            Div(
                Span(id="key-status", cls="text-xs text-muted-foreground"),
                Button(
                    id="dark-toggle",
                    cls=ButtonT.ghost,
                    onclick="toggleDark()",
                    title="切换深色模式",
                    style="font-size:16px;min-width:32px;padding:4px;",
                ),
                Button(
                    UkIcon("key", height=16),
                    cls=ButtonT.ghost,
                    onclick="toggleKeyModal()",
                    title="\u8bbe\u7f6e API Key",
                ),
                *extra_buttons,
                cls="flex items-center gap-1 flex-shrink-0",
            ),
            cls="flex items-center justify-between gap-2 py-3",
        ),
    )
