import re

from ai.utils.blocks import (
    block_parts,
    block_text,
    make_block,
    make_lang_block,
)
from ai.utils.normalizers import stz_language, stz_norm


_TAG_RE = re.compile(r"<[^>]+>")


def enrich_frontmatter(original_front, payload, article):
    blocks = []

    if payload.get("doi"):
        blocks.append(make_block("<article-id>", payload["doi"]))

    titles = payload.get("titles") or []
    for index, item in enumerate(titles):
        label = "<article-title>" if index == 0 else "<trans-title>"
        blocks.append(make_lang_block(label, item["text"], item.get("language") or article.language or "en"))

    for author in payload.get("authors") or []:
        affids = ",".join(author.get("affiliations") or [])
        blocks.append({
            "type": "author_paragraph",
            "value": {
                "label": "<contrib>",
                "paragraph": author["display"],
                "surname": author.get("surname", ""),
                "given_names": author.get("given_names", ""),
                "orcid": author.get("orcid", ""),
                "affid": affids,
                "char": author.get("symbol", ""),
            },
        })

    for affiliation in payload.get("affiliations") or []:
        blocks.append({
            "type": "aff_paragraph",
            "value": {
                "label": "<aff>",
                "paragraph": affiliation["text"],
                "affid": affiliation["id"],
                "text_aff": affiliation["text"],
                "char": affiliation.get("symbol", ""),
                "orgname": affiliation.get("orgname", ""),
                "orgdiv2": affiliation.get("orgdiv2", ""),
                "orgdiv1": affiliation.get("orgdiv1", ""),
                "zipcode": "",
                "city": affiliation.get("city", ""),
                "state": affiliation.get("state", ""),
                "country": affiliation.get("country", ""),
                "code_country": affiliation.get("country_code", ""),
                "original": affiliation["text"],
            },
        })

    for item in payload.get("dates") or []:
        date_text = item.get("date") or item.get("raw")
        if item.get("type") == "received":
            blocks.append(make_block("<date-received>", date_text))
        elif item.get("type") == "accepted":
            blocks.append(make_block("<date-accepted>", date_text))

    original_abstract_langs = set()
    current_lang = None
    for item in original_front or []:
        _, value = block_parts(item)
        label = value.get("label", "")
        if label == "<abstract-title>":
            title_text = str(value.get("paragraph") or "").lower().strip()
            if "resumen" in title_text:
                current_lang = "es"
            elif "resumo" in title_text:
                current_lang = "pt"
            elif "abstract" in title_text:
                current_lang = "en"
        elif label == "<abstract>":
            if value.get("language"):
                original_abstract_langs.add(value.get("language"))
            elif current_lang:
                original_abstract_langs.add(current_lang)

    for item in payload.get("abstracts") or []:
        lang = stz_language(item.get("language"), article.language)
        if lang in original_abstract_langs:
            continue
        title = item.get("title") or {"pt": "Resumo", "en": "Abstract", "es": "Resumen"}.get(lang, "Abstract")
        blocks.append(make_lang_block("<abstract-title>", title, lang))
        blocks.append(make_lang_block("<abstract>", item["text"], lang))

    for item in payload.get("keywords") or []:
        if item.get("title"):
            blocks.append(make_lang_block("<kwd-title>", item["title"], item.get("language") or article.language or "en"))
        blocks.append(make_lang_block("<kwd-group>", "; ".join(item["terms"]), item.get("language") or article.language or "en"))

    return blocks + _collect_remaining_blocks(original_front, payload)


def _collect_remaining_blocks(front, payload):
    seen_texts = _collect_payload_texts(payload)
    kept = []
    for item in front or []:
        block_type, value = block_parts(item)
        label = value.get("label", "")
        text = block_text(value)
        if _is_label_replaced(label, payload):
            continue
        if label == "<title>" and payload.get("titles"):
            continue
        if label == "<author-notes>" and (payload.get("authors") or payload.get("affiliations")):
            continue
        if label == "<p>" and _is_text_covered(text, seen_texts):
            continue
        kept.append({"type": block_type, "value": value})
    return kept


def _is_label_replaced(label, payload):
    if label == "<article-id>":
        return bool(payload.get("doi"))
    if label in {"<article-title>", "<trans-title>"}:
        return bool(payload.get("titles"))
    if label == "<contrib>":
        return bool(payload.get("authors"))
    if label == "<aff>":
        return bool(payload.get("affiliations"))
    date_types = {item.get("type") for item in payload.get("dates") or []}
    if label == "<date-received>":
        return "received" in date_types
    if label == "<date-accepted>":
        return "accepted" in date_types
    if label == "<history>":
        return bool(date_types)
    if label in {"<abstract-title>", "<abstract>", "<trans-abstract>"}:
        return False
    if label in {"<kwd-title>", "<kwd-group>"}:
        return bool(payload.get("keywords"))
    return False


def _collect_payload_texts(payload):
    texts = []
    if payload.get("doi"):
        texts.append(payload["doi"])
    for item in payload.get("titles") or []:
        texts.append(item.get("text", ""))
    for item in payload.get("abstracts") or []:
        texts.extend([item.get("title", ""), item.get("text", "")])
    for item in payload.get("keywords") or []:
        texts.append(item.get("title", ""))
        texts.append("; ".join(item.get("terms") or []))
        texts.append(", ".join(item.get("terms") or []))
    for item in payload.get("dates") or []:
        texts.extend([item.get("date", ""), item.get("raw", "")])
    return {stz_norm(text) for text in texts if text}


def _is_text_covered(text, seen):
    clean = stz_norm(text)
    if not clean:
        return True
    if clean in seen:
        return True
    if any(clean and (clean in item or item in clean) and min(len(clean), len(item)) > 80 for item in seen):
        return True
    for item in seen:
        if item and len(item) > 60 and item in clean:
            return True
    clean_no_tags = _TAG_RE.sub(" ", clean).strip()
    clean_no_tags = re.sub(r"\s+", " ", clean_no_tags)
    if clean_no_tags in seen:
        return True
    for item in seen:
        if item and len(item) > 60 and item in clean_no_tags:
            return True
    return bool(
        re.search(r"\b(resumen|resumo|abstract|palabras?\s+clave|palavras[-\s]chave|keywords?)\b", clean)
        or re.search(r"\b(received|recibido|recebido|accepted|aceptado|aceito|published|publicado)\b", clean)
        or re.search(r"\bdoi\b.*\b10\.\d{4,}|10\.\d{4,}/", clean, re.I)
        or re.search(r"\b(orcid\.org/[0-9\-X]+|[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[X\d])\b", clean)
        or re.search(r"@\S+\.\S+", clean)
    )
