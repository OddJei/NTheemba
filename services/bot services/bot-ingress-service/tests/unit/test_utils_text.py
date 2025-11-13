from app.utils.text import normalize_text


def test_normalize_text_basic():
    assert normalize_text("  Hello World ") == "hello world"
    assert normalize_text("") == ""
    assert normalize_text(None) == ""
