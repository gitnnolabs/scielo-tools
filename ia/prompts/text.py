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
            "authors": {"type": "array", "items": {"type": "object"}},
            "affiliations": {"type": "array", "items": {"type": "object"}},
        },
    },
    "abstracts": {
        "type": "object",
        "properties": {"abstracts": {"type": "array", "items": {"type": "object"}}},
    },
    "keywords": {
        "type": "object",
        "properties": {"keywords": {"type": "array", "items": {"type": "object"}}},
    },
    "dates": {
        "type": "object",
        "properties": {"dates": {"type": "array", "items": {"type": "object"}}},
    },
    "meta": {"type": "object", "properties": {}},
}


def build_title_prompt(content_str, article_language):
    return (
        f"Extract the article title and any translated titles from this academic paper. "
        f"The title is the main heading at the top. Section headings such as Abstract, "
        f"Introduction, Methodology, Results, Discussion, Conclusion, and References are NOT "
        f"titles. There must be exactly one main title. "
        f"The article language is {article_language}. "
        f'Return a JSON object with a "titles" key containing objects with '
        f'"text", "language", and "kind" ("main" or "translated"). '
        f"Content:\n{content_str}"
    )


def build_auth_prompt(content_str):
    return (
        "Extract all authors and their affiliations from this academic paper. "
        'Return a JSON object with "authors" and "affiliations" keys. '
        f"Content:\n{content_str}"
    )


def build_abstracts_prompt(content_str):
    return (
        "Extract all abstracts from this academic paper and keep the original text. "
        'Return a JSON object with an "abstracts" key. '
        f"Content:\n{content_str}"
    )


def build_keywords_prompt(content_str):
    return (
        "Extract all keyword groups from this academic paper. "
        'Return a JSON object with a "keywords" key. '
        f"Content:\n{content_str}"
    )


def build_dates_prompt(content_str):
    return (
        "Extract all dates from this academic paper and normalize to YYYY-MM-DD when possible. "
        'Return a JSON object with a "dates" key. '
        f"Content:\n{content_str}"
    )


def build_meta_prompt(content_str):
    return (
        "Extract DOI, journal ISSN and issue metadata from this academic paper. "
        'Return a JSON object with keys "doi", "journal" and "issue". '
        f"Content:\n{content_str}"
    )


def build_split_task_prompts(content, is_xml, article_language):
    content_str = (
        content if is_xml else json.dumps(content, ensure_ascii=False, indent=2)
    )
    return [
        (
            "titles",
            build_title_prompt(content_str, article_language),
            JSON_SCHEMAS["titles"],
        ),
        ("authors_affs", build_auth_prompt(content_str), JSON_SCHEMAS["authors_affs"]),
        ("abstracts", build_abstracts_prompt(content_str), JSON_SCHEMAS["abstracts"]),
        ("keywords", build_keywords_prompt(content_str), JSON_SCHEMAS["keywords"]),
        ("dates", build_dates_prompt(content_str), JSON_SCHEMAS["dates"]),
        ("meta", build_meta_prompt(content_str), JSON_SCHEMAS["meta"]),
    ]
