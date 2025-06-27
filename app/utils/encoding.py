def fix_encoding(text: str) -> str:
    try:
        if any(char in text for char in ["Ã", "�", "Ã©", "Ã¨"]):  # symboles typiques de corruption
            return text.encode("latin1").decode("utf-8")
        return text
    except Exception:
        return text  # fallback sans crash