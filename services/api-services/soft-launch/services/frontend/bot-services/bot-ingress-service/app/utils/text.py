def normalize_text(text: str) -> str:
    if not text:
        return ""
    return text.strip().lower()
