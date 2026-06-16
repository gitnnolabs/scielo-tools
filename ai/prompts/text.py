import json

JSON_SCHEMAS = {
    "titles": {
        "type": "object",
        "properties": {
            "titles": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "language": {"type": "string"},
                        "kind": {"type": "string", "enum": ["main", "translated"]},
                    },
                    "required": ["text", "language", "kind"],
                },
            },
        },
        "required": ["titles"],
    },
    "authors_affs": {
        "type": "object",
        "properties": {
            "authors": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "given_names": {"type": "string"},
                        "surname": {"type": "string"},
                        "orcid": {"type": "string"},
                        "affiliations": {"type": "array", "items": {"type": "string"}},
                        "symbol": {"type": "string"},
                        "display": {"type": "string"},
                    },
                    "required": ["given_names", "surname", "orcid", "affiliations", "display"],
                },
            },
            "affiliations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "symbol": {"type": "string"},
                        "text": {"type": "string"},
                        "orgname": {"type": "string"},
                        "orgdiv1": {"type": "string"},
                        "orgdiv2": {"type": "string"},
                        "city": {"type": "string"},
                        "state": {"type": "string"},
                        "country": {"type": "string"},
                        "country_code": {"type": "string"},
                    },
                    "required": ["id", "text"],
                },
            },
        },
    },
    "abstracts": {
        "type": "object",
        "properties": {
            "abstracts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "text": {"type": "string"},
                        "language": {"type": "string"},
                    },
                    "required": ["title", "text", "language"],
                },
            },
        },
    },
    "keywords": {
        "type": "object",
        "properties": {
            "keywords": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "terms": {"type": "array", "items": {"type": "string"}},
                        "language": {"type": "string"},
                    },
                    "required": ["title", "terms", "language"],
                },
            },
        },
    },
    "dates": {
        "type": "object",
        "properties": {
            "dates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": ["received", "accepted", "published", "ahp", "other"]},
                        "date": {"type": "string"},
                        "raw": {"type": "string"},
                    },
                    "required": ["type", "date", "raw"],
                },
            },
        },
    },
    "meta": {
        "type": "object",
        "properties": {
            "doi": {"type": "string"},
            "journal": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "issn": {"type": "string"},
                },
                "required": ["title", "issn"],
            },
            "issue": {
                "type": "object",
                "properties": {
                    "volume": {"type": "string"},
                    "number": {"type": "string"},
                    "year": {"type": "string"},
                    "supplement": {"type": "string"},
                },
                "required": ["volume", "number", "year", "supplement"],
            },
        },
    },
}


def build_title_prompt(content_str, article_language):
    return (
        f"Extract the article title and any translated titles from this academic paper. "
        f"The title is the main heading at the top. Section headings such as Abstract, "
        f"Introduction, Methodology, Results, Discussion, Conclusion, and References are NOT "
        f"titles — skip them. There must be exactly one main title. "
        f"The article language is {article_language}. "
        f'Return a JSON object with a "titles" key containing a list of objects, each with '
        f'"text" (the title string), "language" (ISO 639-1 code: en, es, pt, fr), and '
        f'"kind" ("main" for the primary title, "translated" for translations). '
        f'If no title is found, return an empty titles array. '
        f'Example: {{"titles":[{{"text":"The Main Title","language":"en","kind":"main"}},'
        f'{{"text":"El Título","language":"es","kind":"translated"}}]}}. '
        f"Content:\n{content_str}"
    )


def build_auth_prompt(content_str):
    return (
        "Extract all authors and their affiliations from this academic paper. "
        "For each author, collect given names, surname (compound surnames like "
        "\"de la Torre\" or \"da Silva\" go entirely in surname), ORCID (look for "
        "0000-0000-0000-0000 pattern near the name; use empty string if not found), "
        "affiliation IDs (e.g. [\"1\"] or [\"1\",\"3\"] for multiple), the affiliation "
        "symbol next to the name (*, **, \u2020, etc.), and a display name with the "
        "full author name text. Never invent author names or ORCIDs — only extract "
        "what is in the content. "
        "For each affiliation, extract the id (e.g. \"1\"), the symbol, the full original "
        "text, institution name (orgname), division/department (orgdiv1), sub-division "
        "(orgdiv2), city, state, country, and country code (ISO alpha-2 uppercase: BR, US, ES). "
        "If no authors are found, return empty arrays for both authors and affiliations. "
        'Return a JSON object with "authors" and "affiliations" keys. '
        'Example: {"authors":[{"given_names":"John","surname":"Smith","orcid":"0000-0000-0000-0000",'
        '"affiliations":["1"],"symbol":"*","display":"John Smith"}],'
        '"affiliations":[{"id":"1","symbol":"*","text":"University of Example, City, Country",'
        '"orgname":"University of Example","orgdiv1":"","orgdiv2":"","city":"City","state":"",'
        '"country":"Country","country_code":"US"}]}. '
        f"Content:\n{content_str}"
    )


def build_abstracts_prompt(content_str):
    return (
        "Extract all abstracts from this academic paper. Copy the exact original text "
        "verbatim — do not summarize, truncate, paraphrase, or translate. "
        "Join multi-paragraph abstracts with a single space. "
        "Detect the language from the heading: Resumen\u2192es, Resumo\u2192pt, Abstract\u2192en, "
        "R\u00e9sum\u00e9\u2192fr. If no heading label is present, infer the language from "
        "the text itself. Do NOT include keyword sections — only the abstract body. "
        'Return a JSON object with an "abstracts" key containing a list of objects, each '
        'with "title" (the exact label: "Abstract", "Resumo", "Resumen", etc.), '
        '"text" (the abstract body), and "language" (ISO 639-1 code). '
        'Example: {"abstracts":[{"title":"Abstract","text":"The full abstract text...","language":"en"}]}. '
        f"Content:\n{content_str}"
    )


def build_keywords_prompt(content_str):
    return (
        "Extract all keyword groups from this academic paper. Split terms on semicolons, "
        "commas, bullets (\u00b7 \u2022), hyphens, tabs, or newlines. "
        "Multi-word phrases are single terms (e.g. \"climate change\", "
        "\"inteligencia artificial\") — do not split on spaces within a concept. "
        "Deduplicate case-insensitively, keeping the first occurrence's casing. "
        'Return a JSON object with a "keywords" key containing a list of objects, each '
        'with "title" (the label: "Keywords", "Palavras-chave", "Palabras clave"), '
        '"terms" (list of keyword strings), and "language" (ISO 639-1 code). '
        'Example: {"keywords":[{"title":"Keywords","terms":["climate change","ecology"],"language":"en"}]}. '
        f"Content:\n{content_str}"
    )


def build_dates_prompt(content_str):
    return (
        "Extract all dates from this academic paper. Normalize to YYYY-MM-DD format "
        "(or YYYY-MM, YYYY for partial dates). "
        "Recognize month names in English, Spanish, Portuguese, and French "
        "(January/enero/janeiro/janvier, etc.) and their abbreviations (Jan/Ene/Jan/F\u00e9v). "
        "Latin American articles typically use DD-MM-YYYY format — convert appropriately. "
        "Types: received, accepted, published, ahp (ahead of print/Epub/online first), other. "
        "The \"raw\" field must contain the original source text exactly as found. "
        'Return a JSON object with a "dates" key containing a list of objects, each with '
        '"type", "date" (YYYY-MM-DD), and "raw". '
        'Example: {"dates":[{"type":"received","date":"2023-01-15","raw":"Received 15 January 2023"},'
        '{"type":"accepted","date":"2023-06-20","raw":"Accepted: 20/06/2023"}]}. '
        f"Content:\n{content_str}"
    )


def build_meta_prompt(content_str):
    return (
        "Extract DOI, journal ISSN, and issue metadata from this academic paper. "
        "Look for the DOI pattern 10.XXXX/... near the top, often after \"DOI:\" or "
        "\"https://doi.org/\". For ISSN, look for \"ISSN:\", \"ISSN-L:\", \"eISSN:\", "
        "\"pISSN:\" or the 8-digit pattern (1234-5678). For the issue, look for "
        "patterns like \"Vol. 15, No. 3\", \"v.15, n.3\". Supplements appear as "
        "\"Suppl 1\", \"Suplemento 2\", \"S1\". Extract the publication year, not the "
        "copyright year. Use empty strings for any field not found. "
        'Return a JSON object with "doi", "journal" (with "title" and "issn"), and '
        '"issue" (with "volume", "number", "year", "supplement"). '
        'Example: {"doi":"10.1234/example.2023","journal":{"title":"Journal of Examples","issn":"1234-5678"},'
        '"issue":{"volume":"15","number":"3","year":"2023","supplement":""}}. '
        f"Content:\n{content_str}"
    )


def build_split_task_prompts(content, is_xml, article_language):
    if is_xml:
        content_str = content
    else:
        content_str = json.dumps(content, ensure_ascii=False, indent=2)

    return [
        ("titles", build_title_prompt(content_str, article_language), JSON_SCHEMAS["titles"]),
        ("authors_affs", build_auth_prompt(content_str), JSON_SCHEMAS["authors_affs"]),
        ("abstracts", build_abstracts_prompt(content_str), JSON_SCHEMAS["abstracts"]),
        ("keywords", build_keywords_prompt(content_str), JSON_SCHEMAS["keywords"]),
        ("dates", build_dates_prompt(content_str), JSON_SCHEMAS["dates"]),
        ("meta", build_meta_prompt(content_str), JSON_SCHEMAS["meta"]),
    ]
