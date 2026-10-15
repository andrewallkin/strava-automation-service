from app.services.telegram_markdown import MARKDOWN_V2, escape_markdown_v2


def test_markdown_v2_constant() -> None:
    assert MARKDOWN_V2 == "MarkdownV2"


def test_escape_markdown_v2_empty() -> None:
    assert escape_markdown_v2("") == ""


def test_escape_markdown_v2_dots_parens_exclamation() -> None:
    assert escape_markdown_v2("12.34km (easy)!") == r"12\.34km \(easy\)\!"


def test_escape_markdown_v2_reserved_in_activity_title() -> None:
    raw = "*Morning_ run* [test] (block)"
    assert escape_markdown_v2(raw) == r"\*Morning\_ run\* \[test\] \(block\)"


def test_escape_markdown_v2_backslash_preserved_via_doubling() -> None:
    assert escape_markdown_v2(r"a\b") == r"a\\b"
