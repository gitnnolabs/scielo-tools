import pytest

from manuscripts.utils.docx_utils import extract_docx_structure


class _ImageWithPk:
    pk = 42


def _labeled_block(label, paragraph, section="front"):
    return (
        {"type": "paragraph", "value": {"label": label, "paragraph": paragraph}},
        {"label": label, "body": section == "body", "back": section == "back"},
        {"label": label, "body": section == "body", "back": section == "back"},
    )


@pytest.fixture
def docx_mocks(monkeypatch):
    sections = [{"name": "body"}]
    content = [
        {"type": "first_block", "text": "  Article headline  "},
        {"type": "first_block", "text": "   "},
        {"type": "image", "image": _ImageWithPk()},
        {"type": "table", "table": "<table/>"},
        {"type": "list", "list": "item one"},
        {"type": "compound", "text": "formula"},
        {"type": "paragraph", "text": "   "},
        {"type": "paragraph", "text": "Front section note"},
        {"type": "paragraph", "text": "Body paragraph cites Smith 2020 here."},
        {"type": "paragraph", "text": "Back matter note"},
        {"type": "paragraph", "text": "Reference one"},
        {"type": "paragraph", "text": "Reference two"},
    ]

    class FakeParser:
        def extract_content(self, document, source_path, merge_front=False):
            return sections, content

    labeled_calls = []

    def fake_create_labeled_object(index, item, state, section_list):
        labeled_calls.append(item)
        text = item.get("text") or ""
        if not text.strip():
            return None, None, state
        if text.startswith("Body paragraph"):
            return _labeled_block("<p>", text, "body")
        if text == "Front section note":
            return _labeled_block("<p>", text, "front")
        if text == "Back matter note":
            return _labeled_block("<sec>", text, "back")
        if text.startswith("Reference"):
            state = {"label": "<p>", "body": False, "back": True}
            return _labeled_block("<p>", text, "back")
        return None, None, state

    special_calls = []

    def fake_create_special_content_object(item, body, counts):
        special_calls.append((item, list(body)))
        item_type = item.get("type")
        if item_type == "image":
            return {
                "type": "image",
                "value": {"label": "<fig>", "image": item.get("image"), "title": "", "content": ""},
            }, counts
        if item_type == "table":
            return {
                "type": "table",
                "value": {"label": "<table>", "title": "Affiliation", "content": "University"},
            }, counts
        if item_type == "list":
            return {"type": "paragraph", "value": {"label": "<list>", "paragraph": item.get("list")}}, counts
        if item_type == "compound":
            return {"type": "compound_paragraph", "value": {"label": "<disp-formula>", "content": item.get("text")}}, counts
        return None, counts

    frontmatter_texts = []

    def fake_looks_like_frontmatter(text):
        frontmatter_texts.append(text)
        return "Affiliation" in text

    replacer_calls = []

    def fake_replacer(text):
        replacer_calls.append(text)
        return text + " [replaced]"

    monkeypatch.setattr("manuscripts.utils.docx_utils.DocxParser", FakeParser)
    monkeypatch.setattr("manuscripts.utils.docx_utils.create_labeled_object", fake_create_labeled_object)
    monkeypatch.setattr("manuscripts.utils.docx_utils.create_special_content_object", fake_create_special_content_object)
    monkeypatch.setattr("manuscripts.utils.docx_utils._looks_like_frontmatter", fake_looks_like_frontmatter)
    monkeypatch.setattr(
        "manuscripts.utils.docx_utils.read_marks",
        lambda document: [
            {"rid": "B1", "citations": ["Smith 2020", ""]},
            {"rid": "B2", "citations": ["Smith"]},
        ],
    )
    monkeypatch.setattr("manuscripts.utils.docx_utils.build_text_xref_replacer", lambda document: fake_replacer)
    monkeypatch.setattr("manuscripts.utils.docx_utils.validate_marks", lambda document: {"valid": True})

    return {
        "labeled_calls": labeled_calls,
        "special_calls": special_calls,
        "frontmatter_texts": frontmatter_texts,
        "replacer_calls": replacer_calls,
    }


@pytest.mark.django_db
def test_extract_docx_structure_routes_content_and_applies_xrefs(article, docx_mocks):
    document = object()
    front, body, back, xref_status = extract_docx_structure(document, "/tmp/sample.docx")

    assert front[0]["value"]["label"] == "<article-title>"
    assert front[0]["value"]["paragraph"] == "  Article headline  "
    assert any(item["type"] == "table" for item in front)
    assert any(item["type"] == "image" and item["value"]["image"] == 42 for item in body)
    assert any(item["value"]["label"] == "<list>" for item in body)
    assert any(item["value"]["label"] == "<disp-formula>" for item in body)
    assert any(item["value"]["label"] == "<p>" and item["value"]["paragraph"].endswith("[replaced]") for item in body)
    paragraph = next(item for item in body if item["value"].get("label") == "<p>")
    assert 'rid="B1"' in paragraph["value"]["paragraph"]
    assert 'rid="B2"' in paragraph["value"]["paragraph"]
    assert paragraph["value"]["paragraph"].endswith("[replaced]")
    assert any(item.get("value", {}).get("paragraph") == "Front section note" for item in front)
    assert back[0]["value"]["label"] == "<sec>"
    assert back[1]["type"] == "ref_paragraph"
    assert back[1]["value"]["refid"] == "B1"
    assert back[2]["value"]["refid"] == "B2"
    assert xref_status == {"valid": True}
    assert docx_mocks["replacer_calls"]


def test_extract_docx_structure_empty_body_fallback(monkeypatch):
    sections = []
    content = [
        {"type": "first_block", "text": ""},
        {"type": "paragraph", "text": "Only front paragraph"},
    ]

    class FakeParser:
        def extract_content(self, document, source_path, merge_front=False):
            return sections, content

    monkeypatch.setattr("manuscripts.utils.docx_utils.DocxParser", FakeParser)
    monkeypatch.setattr("manuscripts.utils.docx_utils.create_labeled_object", lambda *args: (None, None, args[2]))
    monkeypatch.setattr("manuscripts.utils.docx_utils.create_special_content_object", lambda *args: (None, args[2]))
    monkeypatch.setattr("manuscripts.utils.docx_utils.read_marks", lambda document: [])
    monkeypatch.setattr("manuscripts.utils.docx_utils.build_text_xref_replacer", lambda document: lambda text: text)
    monkeypatch.setattr("manuscripts.utils.docx_utils.validate_marks", lambda document: [])

    front, body, back, xref_status = extract_docx_structure(object(), "draft.docx")

    assert front == []
    assert body == [{"type": "paragraph", "value": {"label": "<p>", "paragraph": "Only front paragraph"}}]
    assert back == []
    assert xref_status == []


def test_extract_docx_structure_skips_none_special_object(monkeypatch):
    sections = []
    content = [{"type": "image", "image": None}]

    class FakeParser:
        def extract_content(self, document, source_path, merge_front=False):
            return sections, content

    monkeypatch.setattr("manuscripts.utils.docx_utils.DocxParser", FakeParser)
    monkeypatch.setattr(
        "manuscripts.utils.docx_utils.create_special_content_object",
        lambda item, body, counts: (None, counts),
    )
    monkeypatch.setattr("manuscripts.utils.docx_utils.read_marks", lambda document: [])
    monkeypatch.setattr("manuscripts.utils.docx_utils.build_text_xref_replacer", lambda document: lambda text: text)
    monkeypatch.setattr("manuscripts.utils.docx_utils.validate_marks", lambda document: None)

    front, body, back, xref_status = extract_docx_structure(object(), "empty.docx")

    assert front == []
    assert body == []
    assert back == []
    assert xref_status is None


def test_extract_docx_structure_xref_skips_non_paragraph_and_existing_markup(monkeypatch):
    sections = []
    content = [{"type": "paragraph", "text": "Already linked"}]

    class FakeParser:
        def extract_content(self, document, source_path, merge_front=False):
            return sections, content

    def fake_create_labeled_object(index, item, state, section_list):
        return (
            {"type": "paragraph", "value": {"label": "<sec>", "paragraph": item["text"]}},
            {},
            state,
        )

    monkeypatch.setattr("manuscripts.utils.docx_utils.DocxParser", FakeParser)
    monkeypatch.setattr("manuscripts.utils.docx_utils.create_labeled_object", fake_create_labeled_object)
    monkeypatch.setattr("manuscripts.utils.docx_utils.create_special_content_object", lambda *args: (None, args[2]))
    monkeypatch.setattr("manuscripts.utils.docx_utils._looks_like_frontmatter", lambda text: False)
    monkeypatch.setattr(
        "manuscripts.utils.docx_utils.read_marks",
        lambda document: [{"rid": "B9", "citations": ["linked"]}],
    )
    monkeypatch.setattr("manuscripts.utils.docx_utils.build_text_xref_replacer", lambda document: lambda text: text)
    monkeypatch.setattr("manuscripts.utils.docx_utils.validate_marks", lambda document: "ok")

    body_item = {
        "type": "paragraph",
        "value": {
            "label": "<p>",
            "paragraph": 'See <xref ref-type="bibr" rid="B9">linked</xref> citation.',
        },
    }

    monkeypatch.setattr(
        "manuscripts.utils.docx_utils.create_labeled_object",
        lambda index, item, state, section_list: (
            body_item,
            {},
            {"body": True, "back": False},
        ),
    )

    _, body, _, _ = extract_docx_structure(object(), "xref.docx")

    assert ">linked</xref>" in body[0]["value"]["paragraph"]
    assert body[0]["value"]["paragraph"].count("<xref") == 1
