import pytest

from ai.utils.blocks import make_block, make_lang_block
from manuscripts.utils.frontmatter import (
    _collect_payload_texts,
    _collect_remaining_blocks,
    _is_label_replaced,
    _is_text_covered,
    enrich_frontmatter,
)


def _paragraph(label, text, language=None):
    block_type = "paragraph_with_language" if language else "paragraph"
    value = {"label": label, "paragraph": text}
    if language:
        value["language"] = language
    return {"type": block_type, "value": value}


def _long_text(prefix="x", length=90):
    return prefix + ("a" * (length - len(prefix)))


@pytest.mark.django_db
def test_enrich_frontmatter_builds_all_block_types(article):
    original_front = [
        _paragraph("<abstract-title>", "Resumen", "es"),
        _paragraph("<abstract>", "Original Spanish abstract", "es"),
        _paragraph("<p>", "Keep this orphan paragraph"),
    ]
    payload = {
        "doi": "10.1234/example",
        "titles": [
            {"text": "Main Title", "language": "en"},
            {"text": "Título", "language": "es"},
        ],
        "authors": [
            {
                "display": "Smith, John",
                "surname": "Smith",
                "given_names": "John",
                "orcid": "0000-0001-2345-6789",
                "affiliations": ["aff1"],
                "symbol": "*",
            }
        ],
        "affiliations": [
            {
                "id": "aff1",
                "text": "University of Example",
                "symbol": "†",
                "orgname": "Example U",
                "orgdiv2": "Dept",
                "orgdiv1": "Faculty",
                "city": "City",
                "state": "ST",
                "country": "Country",
                "country_code": "XX",
            }
        ],
        "dates": [
            {"type": "received", "date": "2024-01-01"},
            {"type": "accepted", "raw": "2024-06-01"},
        ],
        "abstracts": [
            {"text": "New English abstract", "language": "en"},
            {"text": "Novo resumo", "language": "pt"},
        ],
        "keywords": [
            {"title": "Keywords", "terms": ["alpha", "beta"], "language": "en"},
            {"terms": ["gamma"], "language": "pt"},
        ],
    }

    blocks = enrich_frontmatter(original_front, payload, article)

    assert blocks[0] == make_block("<article-id>", "10.1234/example")
    assert blocks[1] == make_lang_block("<article-title>", "Main Title", "en")
    assert blocks[2] == make_lang_block("<trans-title>", "Título", "es")
    assert blocks[3]["type"] == "author_paragraph"
    assert blocks[3]["value"]["affid"] == "aff1"
    assert blocks[4]["type"] == "aff_paragraph"
    assert blocks[4]["value"]["code_country"] == "XX"
    assert make_block("<date-received>", "2024-01-01") in blocks
    assert make_block("<date-accepted>", "2024-06-01") in blocks
    assert make_lang_block("<abstract>", "New English abstract", "en") in blocks
    assert make_lang_block("<abstract-title>", "Resumo", "pt") in blocks
    assert make_lang_block("<kwd-title>", "Keywords", "en") in blocks
    assert make_lang_block("<kwd-group>", "alpha; beta", "en") in blocks
    assert make_lang_block("<kwd-group>", "gamma", "pt") in blocks
    assert _paragraph("<p>", "Keep this orphan paragraph") in blocks


@pytest.mark.django_db
def test_enrich_frontmatter_detects_abstract_language_from_title(article):
    for title_text, lang in [("Resumen", "es"), ("Resumo", "pt"), ("Abstract", "en")]:
        original_front = [
            _paragraph("<abstract-title>", title_text),
            _paragraph("<abstract>", f"Existing {lang} abstract"),
        ]
        payload = {"abstracts": [{"text": "Skipped duplicate", "language": lang}]}
        blocks = enrich_frontmatter(original_front, payload, article)
        assert not any(
            b.get("value", {}).get("label") == "<abstract>"
            and b["value"].get("paragraph") == "Skipped duplicate"
            for b in blocks
        )


@pytest.mark.django_db
def test_enrich_frontmatter_abstract_title_without_language_uses_detected_lang(article):
    original_front = [
        _paragraph("<abstract-title>", "Abstract"),
        _paragraph("<abstract>", "Existing abstract body"),
    ]
    payload = {"abstracts": [{"text": "Should be skipped", "language": "en"}]}
    blocks = enrich_frontmatter(original_front, payload, article)
    assert not any(
        b.get("value", {}).get("label") == "<abstract>" and b["value"].get("paragraph") == "Should be skipped"
        for b in blocks
    )


@pytest.mark.django_db
def test_enrich_frontmatter_uses_article_language_fallback(article):
    article.language = ""
    article.save(update_fields=["language"])
    payload = {
        "titles": [{"text": "Untitled language"}],
        "keywords": [{"terms": ["one"]}],
    }
    blocks = enrich_frontmatter([], payload, article)
    assert blocks[0] == make_lang_block("<article-title>", "Untitled language", "en")
    assert make_lang_block("<kwd-group>", "one", "en") in blocks


@pytest.mark.parametrize(
    ("label", "payload", "expected"),
    [
        ("<article-id>", {"doi": "10.1/x"}, True),
        ("<article-id>", {}, False),
        ("<article-title>", {"titles": [{"text": "T"}]}, True),
        ("<trans-title>", {"titles": [{"text": "T"}]}, True),
        ("<article-title>", {}, False),
        ("<contrib>", {"authors": [{"display": "A"}]}, True),
        ("<contrib>", {}, False),
        ("<aff>", {"affiliations": [{"id": "1", "text": "X"}]}, True),
        ("<aff>", {}, False),
        ("<date-received>", {"dates": [{"type": "received"}]}, True),
        ("<date-received>", {"dates": [{"type": "accepted"}]}, False),
        ("<date-accepted>", {"dates": [{"type": "accepted"}]}, True),
        ("<date-accepted>", {}, False),
        ("<history>", {"dates": [{"type": "received"}]}, True),
        ("<history>", {}, False),
        ("<abstract-title>", {"abstracts": [{"text": "a"}]}, False),
        ("<abstract>", {}, False),
        ("<trans-abstract>", {}, False),
        ("<kwd-title>", {"keywords": [{"terms": ["k"]}]}, True),
        ("<kwd-group>", {}, False),
        ("<unknown>", {"doi": "10.1/x"}, False),
    ],
)
def test_is_label_replaced(label, payload, expected):
    assert _is_label_replaced(label, payload) is expected


def test_collect_payload_texts_gathers_normalized_unique_values():
    payload = {
        "doi": "10.1234/DOI",
        "titles": [{"text": "  Title  "}],
        "abstracts": [{"title": "Abs", "text": "Body"}],
        "keywords": [{"title": "Keys", "terms": ["a", "b"]}],
        "dates": [{"date": "2024", "raw": "raw-date"}],
    }
    texts = _collect_payload_texts(payload)
    assert "10.1234/doi" in texts
    assert "title" in texts
    assert "abs" in texts
    assert "body" in texts
    assert "keys" in texts
    assert "a; b" in texts
    assert "a, b" in texts
    assert "2024" in texts
    assert "raw-date" in texts


def test_collect_remaining_blocks_skips_replaced_and_covered_labels():
    payload = {
        "doi": "10.1/x",
        "titles": [{"text": "New title"}],
        "authors": [{"display": "Author"}],
        "affiliations": [{"id": "1", "text": "Aff"}],
        "keywords": [{"terms": ["kw"]}],
    }
    front = [
        _paragraph("<article-id>", "old doi"),
        _paragraph("<title>", "old title"),
        _paragraph("<author-notes>", "notes"),
        _paragraph("<p>", "new title"),
        _paragraph("<p>", "unique paragraph"),
    ]
    kept = _collect_remaining_blocks(front, payload)
    labels = [item["value"]["label"] for item in kept]
    assert "<article-id>" not in labels
    assert "<title>" not in labels
    assert "<author-notes>" not in labels
    assert any(item["value"]["paragraph"] == "unique paragraph" for item in kept)


def test_collect_remaining_blocks_keeps_author_notes_without_payload_authors():
    front = [_paragraph("<author-notes>", "editor note")]
    kept = _collect_remaining_blocks(front, {})
    assert kept == [{"type": "paragraph", "value": {"label": "<author-notes>", "paragraph": "editor note"}}]


def test_is_text_covered_empty_and_exact_match():
    seen = {"hello world"}
    assert _is_text_covered("", seen) is True
    assert _is_text_covered("  Hello   World  ", seen) is True


def test_is_text_covered_long_overlap_branches():
    long_a = _long_text("a", 90)
    long_b = _long_text("b", 90)
    assert _is_text_covered(long_a, {long_a[:85]}) is True
    assert _is_text_covered(long_a + " tail", {long_a}) is True
    assert _is_text_covered("prefix " + long_b, {long_b}) is True


def test_is_text_covered_strips_tags_and_matches_seen():
    tagged = "<b>Keyword</b>  section"
    seen = {"keyword section"}
    assert _is_text_covered(tagged, seen) is True
    long_inner = _long_text("inner", 70)
    tagged_long = f"<i>{long_inner}</i>"
    assert _is_text_covered(tagged_long + " suffix", {long_inner}) is True


@pytest.mark.parametrize(
    "text",
    [
        "This is the resumen of the paper",
        "Este es el resumo final",
        "Paper abstract goes here",
        "Palabras clave: science",
        "Palavras-chave: ciência",
        "Keywords: biology",
        "Received: 2020",
        "Recibido enero 2020",
        "Recebido em 2020",
        "Accepted March 2021",
        "Aceptado marzo 2021",
        "Aceito em 2021",
        "Published online 2022",
        "Publicado em 2022",
        "doi: 10.1234/5678/sample",
        "Contact orcid.org/0000-0001-2345-6789",
        "Author 0000-0001-2345-6789",
        "Reach us at author@example.org",
    ],
)
def test_is_text_covered_heuristic_patterns(text):
    assert _is_text_covered(text, set()) is True


def test_is_text_covered_matches_seen_item_after_tag_removal(monkeypatch):
    import re

    import manuscripts.utils.frontmatter as frontmatter_module

    item = "a" * 65
    text = "prefix " + item[:30] + "<b>" + item[30:60] + "</b>" + item[60:]

    class _TagRe:
        @staticmethod
        def sub(repl, value, count=0):
            return re.sub(r"<[^>]+>", "", value)

    monkeypatch.setattr(frontmatter_module, "_TAG_RE", _TagRe())
    assert frontmatter_module._is_text_covered(text, {item}) is True


def test_is_text_covered_returns_false_for_unmatched_text():
    assert _is_text_covered("Short unique body paragraph.", {"other"}) is False
