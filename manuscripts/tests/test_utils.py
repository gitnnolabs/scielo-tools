import pytest

from manuscripts.choices import InputType, ProcessingAction
from manuscripts.utils.helpers import checksum_bytes, json_safe
from manuscripts.utils.inspection import inspect_input, resolve_actions, suggested_actions


def test_checksum_bytes_returns_sha256_hexdigest():
    assert checksum_bytes(b"sample") == checksum_bytes(b"sample")
    assert checksum_bytes(b"sample") != checksum_bytes(b"other")


def test_json_safe_serializes_sets_as_sorted_lists():
    assert json_safe({"tags": {"b", "a"}}) == {"tags": ["a", "b"]}


def test_suggested_actions_for_xml_input():
    assert suggested_actions(InputType.XML) == [
        ProcessingAction.XML_VALIDATION,
        ProcessingAction.SPS_PACKAGE_GENERATION,
        ProcessingAction.HTML_GENERATION,
        ProcessingAction.PDF_GENERATION,
    ]


def test_resolve_actions_adds_dependencies_for_document_pipeline():
    actions = resolve_actions(
        [ProcessingAction.XML_GENERATION],
        InputType.DOCUMENT,
    )

    assert actions == [
        ProcessingAction.CITATION_MARKUP,
        ProcessingAction.XML_GENERATION,
    ]


def test_inspect_input_detects_xml_file(tmp_path):
    xml_path = tmp_path / "article.xml"
    xml_path.write_text("<article></article>", encoding="utf-8")

    result = inspect_input(str(xml_path))

    assert result["detected_type"] == InputType.XML
    assert result["contents"] == [{"path": "article.xml", "kind": "xml"}]


def test_inspect_input_returns_unknown_for_unsupported_extension(tmp_path):
    raw_path = tmp_path / "article.txt"
    raw_path.write_text("hello", encoding="utf-8")

    result = inspect_input(str(raw_path))

    assert result["detected_type"] == InputType.UNKNOWN
    assert result["contents"] == []
    assert result["suggested_actions"] == []


def test_resolve_actions_ignores_invalid_actions():
    actions = resolve_actions(["not-real-action"], InputType.XML)
    assert actions == []
