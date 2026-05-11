"""Telegram Bot API MarkdownV2 helpers."""

MARKDOWN_V2 = "MarkdownV2"

# Characters that must be escaped in plain text when using parse_mode MarkdownV2.
# See https://core.telegram.org/bots/api#markdownv2-style
_MARKDOWN_V2_RESERVED = r"_*[]()~`>#+-=|{}.!"


def escape_markdown_v2(text: str) -> str:
    out: list[str] = []
    for ch in text:
        if ch == "\\":
            out.append("\\\\")
        elif ch in _MARKDOWN_V2_RESERVED:
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)
