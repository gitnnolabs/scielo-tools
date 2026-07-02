from ia.utils.normalizers import stz_language


def plain_paragraph_text(value):
    return str(value or "")


def block_parts(item):
    if hasattr(item, "block_type") and hasattr(item, "value"):
        return item.block_type, dict(item.value)
    if isinstance(item, dict):
        return item.get("type", ""), item.get("value") or {}
    return "", {}


def block_text(value):
    text = (
        value.get("paragraph")
        or value.get("text_aff")
        or value.get("original")
        or value.get("title")
        or ""
    )
    return plain_paragraph_text(str(text)).strip()


def make_block(label, text):
    return {"type": "paragraph", "value": {"label": label, "paragraph": text or ""}}


def make_lang_block(label, text, language):
    return {
        "type": "paragraph_with_language",
        "value": {
            "label": label,
            "language": stz_language(language, "en"),
            "paragraph": text or "",
        },
    }


def source_blocks(front, body, limit=60):
    blocks = []
    body_items = body[:25] if isinstance(body, list) else body
    for section, items in (("front", front), ("body", body_items)):
        for index, item in enumerate(items or []):
            block_type, value = block_parts(item)
            text = block_text(value)
            if not text:
                continue
            max_text = 6000 if limit >= 60 else 2000
            blocks.append(
                {
                    "section": section,
                    "index": index,
                    "type": block_type,
                    "label": value.get("label", ""),
                    "text": text[:max_text],
                }
            )
            if len(blocks) >= limit:
                return blocks
    return blocks
