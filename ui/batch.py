from fasthtml.common import *
from monsterui.all import *
from config import BATCH_JS
from ui.layout import key_modal, page_header

def batch_page():
    return Container(
        page_header(
            "\u6279\u91cf\u5904\u7406",
            A(
                "\u2190 \u5355\u5f20",
                href="/",
                cls="uk-btn uk-btn-default uk-btn-sm whitespace-nowrap",
            ),
        ),
        Card(
            Textarea(
                id="b-prompt",
                placeholder="\u8f93\u5165\u63d0\u793a\u8bcd\uff0c\u5c06\u5e94\u7528\u5230\u6240\u6709\u56fe\u7247\u2026",
                cls="uk-textarea",
                rows=3,
            ),
        ),
        Div(
            Input(type="file", id="b-files", multiple=True, accept="image/*"),
            DivCentered(
                UkIcon("upload", height=32, cls="text-muted-foreground"),
                P(
                    "\u62d6\u62fd\u6216\u70b9\u51fb\u4e0a\u4f20\u56fe\u7247\uff08\u652f\u6301\u591a\u9009\uff09",
                    cls="text-sm text-muted-foreground",
                ),
            ),
            id="b-drop",
            cls="b-drop",
        ),
        Div(id="b-grid", cls="b-grid"),
        Div(
            DivFullySpaced(
                Span(id="b-estimate", cls="text-sm text-muted-foreground"),
                Button(
                    "\u5f00\u59cb\u5904\u7406",
                    id="b-start",
                    cls=(ButtonT.primary, "min-w-[120px] justify-center"),
                    onclick="startBatch()",
                ),
            ),
            id="b-controls",
            style="display:none",
        ),
        Div(
            Div(id="b-progress-text", cls="b-progress-text"),
            Div(Div(id="b-bar-fill", cls="b-bar-fill"), cls="b-bar"),
            id="b-progress",
            style="display:none",
        ),
        Card(
            Div(id="b-compare-title", cls="b-compare-title"),
            Div(
                Div(
                    Div("\u539f\u56fe", cls="b-compare-label"),
                    Img(id="b-cmp-src", src=""),
                ),
                Div(
                    Div("\u7ed3\u679c", cls="b-compare-label"),
                    Img(id="b-cmp-res", src=""),
                ),
                cls="b-compare-imgs",
            ),
            Div(id="b-compare-error", cls="b-compare-error", style="display:none"),
            Div(id="b-compare-meta", cls="b-compare-meta"),
            Button(
                "\u91cd\u8bd5",
                id="b-retry-btn",
                cls=ButtonT.destructive,
                style="display:none",
                onclick="retrySelected()",
            ),
            id="b-compare",
            style="display:none",
        ),
        Div(
            Button(
                UkIcon("download", height=16),
                " \u6253\u5305\u4e0b\u8f7d",
                cls=ButtonT.primary,
                onclick="downloadZip()",
            ),
            id="b-done",
            cls="mt-4",
            style="display:none",
        ),
        key_modal(),
        Script(BATCH_JS),
        cls=(ContainerT.sm, "space-y-4"),
    )
