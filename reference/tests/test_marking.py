import hashlib
import json

import pytest

from reference.data_utils import get_xml
from reference.exceptions import ReferenceLlamaMisconfiguredError
from reference.models import Reference
from reference.utils.references import stz_norm


class HttpProviderStub:
    def __init__(self, *_args, **_kwargs):
        pass

    def run(self, _reference_text):
        return {
            "choices": [
                {"message": {"content": '{"reftype":"journal","title":"Remote"}'}},
            ]
        }


def test_marking_uses_http_llama(monkeypatch):
    monkeypatch.setattr(
        "reference.marking.get_provider", lambda *a, **k: HttpProviderStub()
    )

    from reference.marking import mark_reference

    result = list(mark_reference("Ref A"))

    assert result == ['{"reftype":"journal","title":"Remote"}']


def test_marking_reports_llama_misconfigured(monkeypatch):
    def raise_misconfigured(*_args, **_kwargs):
        raise ReferenceLlamaMisconfiguredError("REFERENCE_URL is required.")

    monkeypatch.setattr("reference.marking.get_provider", raise_misconfigured)

    from reference.marking import mark_reference

    result = list(mark_reference("Ref A"))

    assert len(result) == 1
    assert "Llama model is not available" in result[0]
    assert "REFERENCE_URL is required" in result[0]


def test_get_xml_journal():
    sample_json = json.dumps(
        {
            "reftype": "journal",
            "authors": [{"surname": "Smith", "fname": "J"}],
            "title": "Test Title",
            "source": "Nature",
            "date": "2024",
            "doi": "10.1000/test",
        }
    )
    xml_node = get_xml(sample_json)
    xml_text = json.dumps(
        {
            "tag": xml_node.tag,
            "publication_type": xml_node.get("publication-type"),
            "children": {child.tag: child.text for child in xml_node},
        }
    )
    parsed = json.loads(xml_text)

    assert parsed["tag"] == "element-citation"
    assert parsed["publication_type"] == "journal"
    assert parsed["children"]["article-title"] == "Test Title"
    assert parsed["children"]["source"] == "Nature"
    assert parsed["children"]["year"] == "2024"

    person_group = xml_node.find("person-group")
    name = person_group.find("name")
    assert name.find("surname").text == "Smith"
    assert name.find("given-names").text == "J"
    pub_id = xml_node.find("pub-id")
    assert pub_id.get("pub-id-type") == "doi"
    assert pub_id.text == "10.1000/test"


def test_get_xml_book():
    sample_json = json.dumps(
        {
            "reftype": "book",
            "title": "Tropical soil biology",
            "organization": "CAB International",
            "date": 1993,
        }
    )
    xml_node = get_xml(sample_json)
    assert xml_node.get("publication-type") == "book"
    assert xml_node.find("source").text == "Tropical soil biology"
    assert xml_node.find("publisher-name").text == "CAB International"
    assert xml_node.find("year").text == "1993"


def test_get_xml_book_chapter_uses_part_title():
    xml_node = get_xml(
        json.dumps(
            {
                "reftype": "book",
                "chapter_title": "Mapping wetlands",
                "source": "IGARSS proceedings",
                "date": 2003,
                "pages": "1375-1377",
            }
        )
    )
    assert xml_node.find("part-title").text == "Mapping wetlands"
    assert xml_node.find("chapter-title") is None
    assert xml_node.find("source").text == "IGARSS proceedings"
    assert xml_node.find("fpage").text == "1375"
    assert xml_node.find("lpage").text == "1377"


def test_get_xml_journal_pages_and_elocation():
    ranged = get_xml(
        json.dumps(
            {
                "reftype": "journal",
                "title": "A",
                "source": "B",
                "pages": "117-126",
            }
        )
    )
    assert ranged.find("fpage").text == "117"
    assert ranged.find("lpage").text == "126"

    single = get_xml(
        json.dumps(
            {
                "reftype": "journal",
                "title": "A",
                "source": "B",
                "pages": "244",
            }
        )
    )
    assert single.find("fpage").text == "244"
    assert single.find("lpage").text == "244"

    elocation = get_xml(
        json.dumps(
            {
                "reftype": "journal",
                "title": "A",
                "source": "B",
                "pages": "e240058",
            }
        )
    )
    assert elocation.find("elocation-id").text == "e240058"
    assert elocation.find("fpage") is None


def test_get_xml_data_uses_data_title():
    xml_node = get_xml(
        json.dumps(
            {
                "reftype": "data",
                "title": "Replication data for X",
                "source": "SciELO Data",
                "doi": "10.48331/scielodata.abc",
                "date": 2025,
            }
        )
    )
    assert xml_node.get("publication-type") == "data"
    assert xml_node.find("data-title").text == "Replication data for X"
    assert xml_node.find("source").text == "SciELO Data"


def test_get_xml_software():
    xml_node = get_xml(
        json.dumps(
            {
                "reftype": "software",
                "title": "R: A language and environment",
                "organization": "R Foundation",
                "uri": "https://www.R-project.org/",
                "date": 2021,
            }
        )
    )
    assert xml_node.get("publication-type") == "software"
    assert xml_node.find("source").text == "R: A language and environment"
    assert xml_node.find("ext-link").text == "https://www.R-project.org/"


def test_get_xml_missing_reftype_returns_error():
    xml_node = get_xml(json.dumps({"title": "No type"}))
    assert xml_node.tag == "error"


def test_build_ref_list():
    from lxml import etree

    from reference.data_utils import build_ref_list

    results = [
        {
            "mixed_citation": "Smith J. Nature. 2024.",
            "data": (
                '<element-citation publication-type="journal">'
                "<article-title>Nature paper</article-title>"
                '<pub-id pub-id-type="doi">10.1/abc</pub-id>'
                "</element-citation>"
            ),
        },
        {
            "mixed_citation": "Doe A. Book title. Publisher.",
            "data": (
                '<element-citation publication-type="book">'
                "<source>Book title</source>"
                "</element-citation>"
            ),
        },
    ]
    xml_text = build_ref_list(results)
    root = etree.fromstring(xml_text.encode("utf-8"))

    assert root.tag == "ref-list"
    assert root.find("title").text == "References"
    refs = root.findall("ref")
    assert len(refs) == 2
    assert refs[0].get("id") == "B1"
    assert refs[1].get("id") == "B2"
    assert refs[0].find("mixed-citation").text == "Smith J. Nature. 2024."
    assert refs[0].find("element-citation").get("publication-type") == "journal"
    assert refs[0].find("element-citation/pub-id").text == "10.1/abc"
    assert refs[1].find("element-citation").get("publication-type") == "book"


def test_build_ref_list_skips_error_element_citation():
    from lxml import etree

    from reference.data_utils import build_ref_list

    xml_text = build_ref_list(
        [
            {
                "mixed_citation": "Broken ref",
                "data": "<error/>",
            }
        ]
    )
    root = etree.fromstring(xml_text.encode("utf-8"))
    ref = root.find("ref")
    assert ref.find("mixed-citation").text == "Broken ref"
    assert ref.find("element-citation") is None


@pytest.mark.django_db
def test_stz_norm_checksum():
    citation = "Smith J.  Nature.  2024."
    reference = Reference(mixed_citation=citation)
    reference.save()

    expected_normalized = stz_norm(citation)
    expected_checksum = hashlib.sha256(expected_normalized.encode("utf-8")).hexdigest()

    assert reference.normalized_citation == expected_normalized
    assert reference.checksum == expected_checksum
