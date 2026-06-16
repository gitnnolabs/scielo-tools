from datetime import date
from pathlib import Path

import pytest
from lxml import etree

from journals.models import Journal
from manuscripts.choices import InputType
from manuscripts.models.article import ArticleStructureVersion
from manuscripts.utils.xml_utils import (
    _article_adapter,
    _get_inner_xml,
    _plain_text,
    extract_article_metadata,
    generate_structure_xml,
    parse_xml_structure,
)

SOUZA_XML = Path(__file__).resolve().parents[2] / "fixtures" / "xml" / "souza_2021.xml"

COMPREHENSIVE_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<article xml:lang="pt" xmlns:xml="http://www.w3.org/XML/1998/namespace">
  <front>
    <article-meta>
      <title-group>
        <article-title>Main   Title</article-title>
        <trans-title-group xml:lang="en">
          <trans-title>English Title</trans-title>
        </trans-title-group>
        <trans-title-group xml:lang="es">
          <trans-title></trans-title>
        </trans-title-group>
      </title-group>
      <contrib-group>
        <contrib contrib-type="author">
          <contrib-id contrib-id-type="orcid">0000-0001</contrib-id>
          <name>
            <given-names>John</given-names>
            <surname>Doe</surname>
          </name>
          <xref ref-type="aff" rid="aff1">1</xref>
        </contrib>
        <contrib contrib-type="author">
          <name>
            <given-names>Jane</given-names>
            <surname>Smith</surname>
          </name>
        </contrib>
        <contrib contrib-type="editor">
          <name><surname>Editor</surname></name>
        </contrib>
      </contrib-group>
      <aff id="aff1">
        <label>1</label>
        <institution content-type="orgname">University</institution>
        <institution content-type="orgdiv1">Dept</institution>
        <institution content-type="orgdiv2">Lab</institution>
        <addr-line>
          <city>Campinas</city>
          <state>SP</state>
          <country country="BR">Brazil</country>
        </addr-line>
      </aff>
      <abstract>
        <title>Resumo</title>
        <p>Abstract <italic>text</italic> here.</p>
      </abstract>
      <trans-abstract xml:lang="en">
        <p><bold>Trans</bold> abstract.</p>
      </trans-abstract>
      <kwd-group xml:lang="pt">
        <title>Palavras-chave</title>
        <kwd>alpha</kwd>
        <kwd>beta</kwd>
        <kwd></kwd>
      </kwd-group>
      <kwd-group>
        <kwd>only</kwd>
      </kwd-group>
      <permissions/>
    </article-meta>
  </front>
  <body>
    <sec>
      <title>Section  One</title>
      <p>Body <bold>paragraph</bold>.</p>
    </sec>
  </body>
  <back>
    <ref-list>
      <ref id="R1"><mixed-citation>First ref</mixed-citation></ref>
      <ref><element-citation>Second ref</element-citation></ref>
    </ref-list>
  </back>
</article>
"""

METADATA_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<article xml:lang="pt"
         xmlns:xml="http://www.w3.org/XML/1998/namespace"
         xmlns:xlink="http://www.w3.org/1999/xlink">
  <front>
    <article-meta>
      <article-id pub-id-type="doi">10.1234/TEST</article-id>
      <article-id pub-id-type="publisher-id">PUB-123</article-id>
      <title-group>
        <article-title>Metadata <italic>Title</italic></article-title>
      </title-group>
      <elocation-id>e12345</elocation-id>
      <fpage seq="1">10</fpage>
      <lpage>20</lpage>
      <pub-date date-type="pub">
        <day>99</day>
        <month>13</month>
        <year>2024</year>
      </pub-date>
      <permissions>
        <license xlink:href="https://creativecommons.org/licenses/by/4.0/"/>
      </permissions>
    </article-meta>
  </front>
  <body>
    <graphic xlink:href="figures/fig1.png"/>
    <graphic xlink:href="#internal"/>
  </body>
</article>
"""


def _make_structure(article, processing, **kwargs):
    return ArticleStructureVersion.objects.create(
        article=article,
        processing=processing,
        version=1,
        is_current=True,
        source_kind=InputType.XML,
        front=kwargs.get("front", []),
        body=kwargs.get("body", []),
        back=kwargs.get("back", []),
        base_xml=kwargs.get("base_xml", ""),
        creator=processing.creator,
    )


def test_plain_text_collapses_whitespace():
    node = etree.fromstring("<title>  Hello   <italic>world</italic>  </title>")
    assert _plain_text(node) == "Hello world"


def test_get_inner_xml_strips_p_wrapper():
    node = etree.fromstring("<p>Inner <bold>text</bold>.</p>")
    assert _get_inner_xml(node) == "Inner <bold>text</bold>."


def test_get_inner_xml_returns_raw_xml_without_p_wrapper():
    node = etree.fromstring("<italic>standalone</italic>")
    assert _get_inner_xml(node) == "<italic>standalone</italic>"


def test_parse_xml_structure_extracts_all_sections_and_warnings():
    front, body, back, warnings = parse_xml_structure(COMPREHENSIVE_XML)

    assert front[0] == {
        "type": "paragraph_with_language",
        "value": {"label": "<article-title>", "language": "pt", "paragraph": "Main Title"},
    }
    assert front[1]["value"]["label"] == "<trans-title>"
    assert front[1]["value"]["paragraph"] == "English Title"

    authors = [item for item in front if item["type"] == "author_paragraph"]
    assert len(authors) == 2
    assert authors[0]["value"] == {
        "label": "<contrib>",
        "paragraph": "John Doe",
        "surname": "Doe",
        "given_names": "John",
        "orcid": "0000-0001",
        "affid": "1",
        "char": "1",
    }
    assert authors[1]["value"]["char"] == ""

    aff = next(item for item in front if item["type"] == "aff_paragraph")
    assert aff["value"]["affid"] == "1"
    assert aff["value"]["orgname"] == "University"
    assert aff["value"]["city"] == "Campinas"
    assert aff["value"]["code_country"] == "BR"

    abstract_titles = [
        item["value"]["paragraph"]
        for item in front
        if item["type"] == "paragraph" and item["value"].get("label") == "<abstract-title>"
    ]
    assert abstract_titles == ["Resumo", "Abstract"]

    abstract_blocks = [item for item in front if item["value"].get("label") == "<abstract>"]
    assert abstract_blocks[0]["value"]["paragraph"] == "Abstract <italic>text</italic> here."
    assert abstract_blocks[1]["value"]["language"] == "en"
    assert abstract_blocks[1]["value"]["paragraph"] == "<bold>Trans</bold> abstract."

    kwd_titles = [item for item in front if item["value"].get("label") == "<kwd-title>"]
    assert kwd_titles[0]["value"]["paragraph"] == "Palavras-chave"
    assert kwd_titles[1]["value"]["paragraph"] == "Keywords"

    assert body == [
        {"type": "paragraph", "value": {"label": "<sec>", "paragraph": "Section One"}},
        {"type": "paragraph", "value": {"label": "<p>", "paragraph": "Body <bold>paragraph</bold>."}},
    ]

    assert len(back) == 2
    assert back[0]["value"]["refid"] == "R1"
    assert back[0]["value"]["paragraph"] == "First ref"
    assert back[1]["value"]["refid"] == "B2"
    assert back[1]["value"]["paragraph"] == "Second ref"

    assert len(warnings) == 1
    assert warnings[0]["code"] == "UNMODELED_XML_NODES"
    assert "permissions" in warnings[0]["nodes"]
    assert warnings[0]["message"] == "Nós preservados somente no XML-base."


def test_parse_xml_structure_handles_minimal_xml_without_warnings():
    xml = b"<article><front><article-meta/></front><body/><back/></article>"
    front, body, back, warnings = parse_xml_structure(xml)
    assert front == []
    assert body == []
    assert back == []
    assert warnings == []


def test_parse_xml_structure_with_souza_fixture():
    content = SOUZA_XML.read_bytes()
    front, body, back, warnings = parse_xml_structure(content)

    assert any(item["value"].get("label") == "<article-title>" for item in front)
    assert any(item["type"] == "author_paragraph" for item in front)
    assert any(item["type"] == "aff_paragraph" for item in front)
    assert body
    assert back
    assert warnings


def test_extract_article_metadata_all_fields_and_normalization():
    metadata = extract_article_metadata(METADATA_XML)

    assert metadata["title"] == "Metadata  Title"
    assert metadata["doi"] == "10.1234/test"
    assert metadata["pid"] == "PUB-123"
    assert "figures/fig1.png" in metadata["assets"]
    assert all(not asset.startswith("#") for asset in metadata["assets"])
    assert metadata["language"] == "pt"
    assert metadata["license"] == "https://creativecommons.org/licenses/by/4.0/"
    assert metadata["elocatid"] == "e12345"
    assert metadata["fpage"] == "10"
    assert metadata["lpage"] == "20"
    assert metadata["seq"] == "1"
    assert metadata["artdate"] == "2024-01-01"


def test_extract_article_metadata_falls_back_to_other_pid_and_defaults():
    xml = b"""<article xml:lang="en">
      <front><article-meta>
        <article-id pub-id-type="other">OTHER-99</article-id>
        <pub-date><month>3</month><year>2023</year></pub-date>
      </article-meta></front>
    </article>"""
    metadata = extract_article_metadata(xml)

    assert metadata["title"] == ""
    assert metadata["pid"] == "OTHER-99"
    assert metadata["language"] == "en"
    assert metadata["license"] == ""
    assert metadata["assets"] == []
    assert metadata["artdate"] == "2023-03-01"


def test_extract_article_metadata_skips_artdate_without_year():
    xml = b"""<article><front><article-meta>
      <pub-date><month>5</month><day>10</day></pub-date>
    </article-meta></front></article>"""
    assert extract_article_metadata(xml)["artdate"] is None


def test_extract_article_metadata_normalizes_non_digit_month_and_day():
    xml = b"""<article><front><article-meta>
      <pub-date><month>ab</month><day>xy</day><year>2022</year></pub-date>
    </article-meta></front></article>"""
    assert extract_article_metadata(xml)["artdate"] == "2022-01-01"


def test_article_adapter_without_journal(article):
    article.language = ""
    article.license = None
    article.elocatid = ""
    article.fpage = ""
    article.lpage = ""
    article.seq = ""
    article.artdate = None
    article.ahpdate = None

    adapted = _article_adapter(article)

    assert adapted.title == article.title
    assert adapted.content == []
    assert adapted.acronym == ""
    assert adapted.title_nlm == ""
    assert adapted.journal_title == ""
    assert adapted.short_title == ""
    assert adapted.pissn == ""
    assert adapted.eissn == ""
    assert adapted.pubname == ""
    assert adapted.issue is None
    assert adapted.language == "en"
    assert adapted.license == ""
    assert adapted.dateiso == ""


@pytest.mark.django_db
def test_article_adapter_with_journal(article, db):
    journal = Journal.objects.create(
        title="Journal Title",
        short_title="J Short",
        title_nlm="J NLM",
        acronym="JT",
        pissn="1111-1111",
        eissn="2222-2222",
        publisher_name="Publisher",
    )
    article.journal = journal
    article.language = "pt"
    article.license = "https://license.example"
    article.elocatid = "e1"
    article.fpage = "1"
    article.lpage = "9"
    article.seq = "2"
    article.artdate = date(2024, 6, 15)

    adapted = _article_adapter(article)

    assert adapted.acronym == "JT"
    assert adapted.title_nlm == "J NLM"
    assert adapted.journal_title == "Journal Title"
    assert adapted.short_title == "J Short"
    assert adapted.pissn == "1111-1111"
    assert adapted.eissn == "2222-2222"
    assert adapted.pubname == "Publisher"
    assert adapted.language == "pt"
    assert adapted.license == "https://license.example"
    assert adapted.elocatid == "e1"
    assert adapted.fpage == "1"
    assert adapted.lpage == "9"
    assert adapted.seq == "2"
    assert adapted.dateiso == "2024-06-15"


@pytest.mark.django_db
def test_generate_structure_xml_without_base_xml(processing, article, monkeypatch):
    structure = _make_structure(
        article,
        processing,
        body=[{"type": "paragraph", "value": {"label": "<p>", "paragraph": "Body"}}],
    )
    monkeypatch.setattr(
        "manuscripts.utils.xml_utils.get_xml",
        lambda article_docx, front, body, back: ('<?xml version="1.0"?><article/>', body),
    )

    result = generate_structure_xml(structure)

    assert result == b'<?xml version="1.0"?><article/>'


@pytest.mark.django_db
def test_generate_structure_xml_saves_normalized_body(processing, article, monkeypatch):
    initial_body = [{"type": "paragraph", "value": {"label": "<p>", "paragraph": "Before"}}]
    normalized_body = [{"type": "paragraph", "value": {"label": "<p>", "paragraph": "After"}}]
    structure = _make_structure(article, processing, body=initial_body)
    monkeypatch.setattr(
        "manuscripts.utils.xml_utils.get_xml",
        lambda *_args: ('<article/>', normalized_body),
    )

    generate_structure_xml(structure)

    structure.refresh_from_db()
    assert len(structure.body) == 1
    assert structure.body[0].block_type == "paragraph"
    assert structure.body[0].value["paragraph"] == "After"


@pytest.mark.django_db
def test_generate_structure_xml_merges_base_xml_paths(processing, article, monkeypatch):
    base_xml = """<?xml version="1.0" encoding="utf-8"?>
<article>
  <front>
    <article-meta>
      <title-group><article-title>Old title</article-title></title-group>
      <contrib-group><contrib contrib-type="author"/></contrib-group>
      <aff id="aff1"/>
      <abstract/>
      <trans-abstract/>
      <kwd-group/>
      <permissions><license href="https://old.example"/></permissions>
    </article-meta>
  </front>
  <body><sec><title>Old body</title></sec></body>
  <back><ref-list><ref id="old"/></ref-list></back>
</article>"""
    structure = _make_structure(article, processing, base_xml=base_xml)

    generated_xml = """<?xml version="1.0" encoding="utf-8"?>
<article>
  <front>
    <article-meta>
      <title-group><article-title>New title</article-title></title-group>
      <contrib-group><contrib contrib-type="author"><name><surname>New</surname></name></contrib></contrib-group>
      <aff id="aff2"><label>2</label></aff>
      <abstract><p>New abstract</p></abstract>
      <trans-abstract xml:lang="en"><p>Trans</p></trans-abstract>
      <kwd-group><kwd>term</kwd></kwd-group>
    </article-meta>
  </front>
  <body><sec><title>New body</title><p>Paragraph</p></sec></body>
  <back><ref-list><ref id="new"><mixed-citation>New ref</mixed-citation></ref></ref-list></back>
</article>"""

    monkeypatch.setattr(
        "manuscripts.utils.xml_utils.get_xml",
        lambda *_args: (generated_xml, []),
    )

    result = generate_structure_xml(structure)
    merged = etree.fromstring(result)

    assert merged.xpath("string(.//article-title)") == "New title"
    assert merged.xpath("string(.//contrib/name/surname)") == "New"
    assert merged.xpath("string(.//aff/@id)") == "aff2"
    assert merged.xpath("string(.//abstract/p)") == "New abstract"
    assert merged.xpath("string(.//trans-abstract/p)") == "Trans"
    assert merged.xpath("string(.//kwd-group/kwd)") == "term"
    assert merged.xpath("string(.//body/sec/title)") == "New body"
    assert merged.xpath("string(.//ref/@id)") == "new"
    assert merged.xpath(".//permissions") == []


@pytest.mark.django_db
def test_generate_structure_xml_appends_when_target_missing(processing, article, monkeypatch):
    base_xml = """<?xml version="1.0" encoding="utf-8"?>
<article>
  <front><article-meta/></front>
  <body/>
  <back/>
</article>"""
    structure = _make_structure(article, processing, base_xml=base_xml)

    generated_xml = """<?xml version="1.0" encoding="utf-8"?>
<article>
  <front>
    <article-meta>
      <title-group><article-title>Appended title</article-title></title-group>
      <kwd-group><kwd>keyword</kwd></kwd-group>
    </article-meta>
  </front>
  <body><sec><p>Body</p></sec></body>
  <back><ref-list><ref id="B1"/></ref-list></back>
</article>"""

    monkeypatch.setattr(
        "manuscripts.utils.xml_utils.get_xml",
        lambda *_args: (generated_xml, []),
    )

    result = generate_structure_xml(structure)
    merged = etree.fromstring(result)
    article_meta = merged.xpath(".//article-meta")[0]

    assert merged.xpath("string(.//kwd-group/kwd)") == "keyword"
    assert merged.xpath("string(.//body/sec/p)") == "Body"
    assert merged.xpath("string(.//ref/@id)") == "B1"
    assert article_meta.xpath("./kwd-group") != []


@pytest.mark.django_db
def test_generate_structure_xml_removes_targets_when_sources_empty(processing, article, monkeypatch):
    base_xml = """<?xml version="1.0" encoding="utf-8"?>
<article>
  <front>
    <article-meta>
      <permissions><license href="https://keep.example"/></permissions>
    </article-meta>
  </front>
  <body><sec><p>Keep in base only</p></sec></body>
  <back><ref-list><ref id="old-ref"/></ref-list></back>
</article>"""
    structure = _make_structure(article, processing, base_xml=base_xml)

    generated_xml = """<?xml version="1.0" encoding="utf-8"?>
<article>
  <front><article-meta/></front>
</article>"""

    monkeypatch.setattr(
        "manuscripts.utils.xml_utils.get_xml",
        lambda *_args: (generated_xml, []),
    )

    result = generate_structure_xml(structure)
    merged = etree.fromstring(result)

    assert merged.xpath(".//permissions") == []
    assert merged.xpath(".//body") == []
    assert merged.xpath(".//ref-list") == []
