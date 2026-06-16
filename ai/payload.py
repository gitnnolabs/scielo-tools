import logging
import re

from ai.utils.normalizers import (
    DOI_RE,
    ORCID_RE,
    stz_affiliation_id,
    stz_country_code,
    stz_date,
    stz_first_number,
    stz_language,
    stz_norm,
    stz_text,
)

logger = logging.getLogger(__name__)


def payload_counts(payload):
    return {
        "doi": 1 if payload.get("doi") else 0,
        "titles": len(payload.get("titles") or []),
        "authors": len(payload.get("authors") or []),
        "affiliations": len(payload.get("affiliations") or []),
        "dates": len(payload.get("dates") or []),
        "abstracts": len(payload.get("abstracts") or []),
        "keywords": len(payload.get("keywords") or []),
    }


def is_invalid_title(text):
    clean = stz_norm(text)
    heading_words = {
        "abstract", "resumo", "resumen", "resumén", "sumário", "sumario",
        "keywords", "palavras-chave", "palabras clave", "introduction",
        "introdução", "introducción", "methodology", "metodologia",
        "conclusion", "conclusão", "conclusión", "references",
        "referências", "referencias", "bibliography", "bibliografia",
    }
    if clean in heading_words:
        return True
    return (
        len(clean) > 320
        or bool(DOI_RE.search(clean))
        or bool(ORCID_RE.search(clean))
        or "@" in clean
        or len(re.findall(
            r"\b(universidad|university|instituto|department|facultad|doctor|graduad|research|analysis|study|approach)",
            clean,
        )) > 2
    )


def normalize_payload(payload, article):
    if not isinstance(payload, dict):
        return {}, ["LLM response was not a JSON object."]

    warnings = [str(w).strip() for w in payload.get("warnings") or [] if str(w).strip()]
    normalized = {
        "doi": stz_text(payload.get("doi")),
        "titles": [],
        "authors": [],
        "affiliations": [],
        "dates": [],
        "abstracts": [],
        "keywords": [],
    }

    seen_titles = set()
    for item in payload.get("titles") or []:
        if isinstance(item, str):
            text = stz_text(item)
            language = stz_language("", article.language)
            kind = "main"
        else:
            text = stz_text(item.get("text"))
            language = stz_language(item.get("language"), article.language)
            kind = (item.get("kind") or "translated").lower()
        if not text or is_invalid_title(text):
            if text:
                warnings.append(f"Title discarded: {text[:120]}")
            continue
        key = stz_norm(text)
        if key in seen_titles:
            continue
        seen_titles.add(key)
        normalized["titles"].append({
            "text": text,
            "language": language,
            "kind": kind,
        })

    for index, item in enumerate(payload.get("authors") or [], 1):
        if isinstance(item, str):
            continue
        given_names = stz_text(item.get("given_names"))
        surname = stz_text(item.get("surname"))
        display = stz_text(item.get("display")) or " ".join(
            p for p in [given_names, surname] if p
        )
        if not display:
            continue
        if not given_names and not surname:
            parts = display.rsplit(" ", 1)
            surname = parts[-1] if len(parts) > 1 else display
            given_names = parts[0] if len(parts) > 1 else ""
        normalized["authors"].append({
            "given_names": given_names,
            "surname": surname,
            "display": display,
            "orcid": stz_text(item.get("orcid")),
            "affiliations": stz_affiliation_id(item.get("affiliations")) or [str(index)],
            "symbol": stz_text(item.get("symbol")),
        })

    for index, item in enumerate(payload.get("affiliations") or [], 1):
        if isinstance(item, str):
            continue
        text = stz_text(item.get("text"))
        if not text:
            continue
        normalized["affiliations"].append({
            "id": stz_first_number(item.get("id")) or str(index),
            "symbol": stz_text(item.get("symbol")),
            "text": text,
            "orgname": stz_text(item.get("orgname")),
            "orgdiv1": stz_text(item.get("orgdiv1")),
            "orgdiv2": stz_text(item.get("orgdiv2")),
            "city": stz_text(item.get("city")),
            "state": stz_text(item.get("state")),
            "country": stz_text(item.get("country")),
            "country_code": stz_country_code(item.get("country_code")),
        })

    for item in payload.get("dates") or []:
        if isinstance(item, str):
            continue
        date_type = (item.get("type") or "other").lower()
        normalized_date = stz_date(item.get("date") or item.get("raw"))
        raw = stz_text(item.get("raw")) or stz_text(item.get("date"))
        if date_type not in {"received", "accepted", "published", "ahp", "other"}:
            date_type = "other"
        if normalized_date or raw:
            normalized["dates"].append({
                "type": date_type, "date": normalized_date, "raw": raw,
            })

    for item in payload.get("abstracts") or []:
        if isinstance(item, str):
            continue
        text = stz_text(item.get("text"))
        if not text:
            continue
        normalized["abstracts"].append({
            "title": stz_text(item.get("title")),
            "text": text,
            "language": stz_language(item.get("language"), article.language),
        })

    for item in payload.get("keywords") or []:
        if isinstance(item, str):
            continue
        terms = [stz_text(t) for t in item.get("terms") or []]
        terms = [t for t in terms if t]
        if not terms:
            continue
        normalized["keywords"].append({
            "title": stz_text(item.get("title")),
            "terms": terms,
            "language": stz_language(item.get("language"), article.language),
        })

    if normalized["titles"] and not any(t["kind"] == "main" for t in normalized["titles"]):
        normalized["titles"][0]["kind"] = "main"
    normalized["titles"].sort(key=lambda t: 0 if t["kind"] == "main" else 1)

    return normalized, warnings


def has_useful_payload(payload):
    return any(
        payload.get(key)
        for key in ("doi", "titles", "authors", "affiliations", "dates", "abstracts", "keywords")
    )
