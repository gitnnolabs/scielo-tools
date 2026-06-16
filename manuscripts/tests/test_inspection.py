import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from manuscripts.choices import ArtifactType, InputType, ProcessingAction, ProcessStatus
from manuscripts.models.processing import Processing
from manuscripts.utils.inspection import (
    inspect_input,
    inspect_processing,
    inspect_zip,
    resolve_actions,
    suggested_actions,
)

MINIMAL_XML = b"<article></article>"
METADATA_XML = b"""<article xmlns:xlink="http://www.w3.org/1999/xlink" xml:lang="en">
  <front><article-meta>
    <title-group><article-title>Sample title</article-title></title-group>
    <article-id pub-id-type="doi">10.1234/sample</article-id>
  </article-meta></front>
</article>"""


def _write_zip(path, members):
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in members:
            archive.writestr(name, data)


@pytest.mark.parametrize(
    "input_type,expected",
    [
        (
            InputType.DOCUMENT,
            [
                ProcessingAction.CITATION_MARKUP,
                ProcessingAction.XML_GENERATION,
                ProcessingAction.XML_VALIDATION,
                ProcessingAction.SPS_PACKAGE_GENERATION,
                ProcessingAction.HTML_GENERATION,
                ProcessingAction.PDF_GENERATION,
            ],
        ),
        (
            InputType.SOURCE_PACKAGE,
            [
                ProcessingAction.CITATION_MARKUP,
                ProcessingAction.XML_GENERATION,
                ProcessingAction.XML_VALIDATION,
                ProcessingAction.SPS_PACKAGE_GENERATION,
                ProcessingAction.HTML_GENERATION,
                ProcessingAction.PDF_GENERATION,
            ],
        ),
        (
            InputType.XML,
            [
                ProcessingAction.XML_VALIDATION,
                ProcessingAction.SPS_PACKAGE_GENERATION,
                ProcessingAction.HTML_GENERATION,
                ProcessingAction.PDF_GENERATION,
            ],
        ),
        (
            InputType.SPS_PACKAGE,
            [
                ProcessingAction.SPS_PACKAGE_VALIDATION,
                ProcessingAction.XML_VALIDATION,
            ],
        ),
        (InputType.UNKNOWN, []),
        (InputType.AMBIGUOUS_ZIP, []),
    ],
)
def test_suggested_actions_for_all_input_types(input_type, expected):
    assert suggested_actions(input_type) == expected


def test_inspect_input_detects_docx_file(tmp_path):
    docx_path = tmp_path / "manuscript.docx"
    docx_path.write_bytes(b"docx")

    result = inspect_input(str(docx_path))

    assert result["detected_type"] == InputType.DOCUMENT
    assert result["contents"] == [{"path": "manuscript.docx", "kind": "document"}]
    assert ProcessingAction.CITATION_MARKUP in result["suggested_actions"]


def test_inspect_input_detects_xml_file(tmp_path):
    xml_path = tmp_path / "article.xml"
    xml_path.write_text("<article></article>", encoding="utf-8")

    result = inspect_input(str(xml_path))

    assert result["detected_type"] == InputType.XML
    assert result["contents"] == [{"path": "article.xml", "kind": "xml"}]


def test_inspect_input_detects_zip_via_inspect_zip(tmp_path):
    zip_path = tmp_path / "package.zip"
    _write_zip(zip_path, [("article.xml", MINIMAL_XML)])

    result = inspect_input(str(zip_path))

    assert result["detected_type"] == InputType.SPS_PACKAGE
    assert result["contents"][0]["kind"] == "xml"


def test_inspect_input_returns_unknown_for_unsupported_extension(tmp_path):
    raw_path = tmp_path / "article.txt"
    raw_path.write_text("hello", encoding="utf-8")

    result = inspect_input(str(raw_path))

    assert result["detected_type"] == InputType.UNKNOWN
    assert result["contents"] == []
    assert result["suggested_actions"] == []


def test_inspect_zip_classifies_members_and_detects_source_package(tmp_path):
    zip_path = tmp_path / "source.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("nested/", b"")
        archive.writestr("article.docx", b"docx")
        archive.writestr("assets/photo.jpg", b"jpg")
        archive.writestr("readme.txt", b"txt")

    detected, contents = inspect_zip(str(zip_path))

    assert detected == InputType.SOURCE_PACKAGE
    kinds = {item["path"]: item["kind"] for item in contents}
    assert kinds["article.docx"] == "document"
    assert kinds["assets/photo.jpg"] == "asset"
    assert kinds["readme.txt"] == "other"
    assert "nested/" not in kinds


def test_inspect_zip_detects_sps_package(tmp_path):
    zip_path = tmp_path / "sps.zip"
    _write_zip(zip_path, [("article.xml", MINIMAL_XML), ("fig1.png", b"png")])

    detected, contents = inspect_zip(str(zip_path))

    assert detected == InputType.SPS_PACKAGE
    assert {item["kind"] for item in contents} == {"xml", "asset"}


def test_inspect_zip_detects_ambiguous_zip(tmp_path):
    zip_path = tmp_path / "ambiguous.zip"
    _write_zip(
        zip_path,
        [("article.docx", b"docx"), ("article.xml", MINIMAL_XML)],
    )

    detected, _contents = inspect_zip(str(zip_path))

    assert detected == InputType.AMBIGUOUS_ZIP


def test_resolve_actions_adds_dependencies_for_document_pipeline():
    actions = resolve_actions([ProcessingAction.XML_GENERATION], InputType.DOCUMENT)

    assert actions == [
        ProcessingAction.CITATION_MARKUP,
        ProcessingAction.XML_GENERATION,
    ]


def test_resolve_actions_allows_html_and_pdf_for_sps_package():
    actions = resolve_actions(
        [ProcessingAction.HTML_GENERATION, ProcessingAction.PDF_GENERATION],
        InputType.SPS_PACKAGE,
    )

    assert actions == [
        ProcessingAction.XML_VALIDATION,
        ProcessingAction.HTML_GENERATION,
        ProcessingAction.PDF_GENERATION,
    ]


def test_resolve_actions_ignores_invalid_actions():
    actions = resolve_actions(["not-real-action"], InputType.XML)
    assert actions == []


@pytest.mark.django_db
def test_inspect_processing_for_xml_file(user):
    uploaded = SimpleUploadedFile("article.xml", METADATA_XML, content_type="application/xml")
    processing = Processing.objects.create(
        title="XML inspection",
        creator=user,
        input_file=uploaded,
    )

    result = inspect_processing(processing)

    processing.refresh_from_db()
    assert result.pk == processing.pk
    assert processing.detected_type == InputType.XML
    assert processing.status == ProcessStatus.AWAITING_REVIEW
    assert processing.requested_actions == suggested_actions(InputType.XML)
    assert processing.input_checksum
    assert processing.inspection["article_candidates"][0]["title"] == "Sample title"
    assert processing.artifacts.filter(artifact_type=ArtifactType.INPUT).exists()


@pytest.mark.django_db
def test_inspect_processing_for_sps_zip(user, tmp_path):
    zip_path = tmp_path / "sps.zip"
    _write_zip(zip_path, [("articles/sample.xml", METADATA_XML)])
    uploaded = SimpleUploadedFile("sps.zip", zip_path.read_bytes(), content_type="application/zip")
    processing = Processing.objects.create(
        title="SPS inspection",
        creator=user,
        input_file=uploaded,
    )

    inspect_processing(processing)

    processing.refresh_from_db()
    assert processing.detected_type == InputType.SPS_PACKAGE
    assert len(processing.inspection["article_candidates"]) == 1
    assert processing.inspection["article_candidates"][0]["path"] == "articles/sample.xml"
    assert processing.inspection["article_candidates"][0]["title"] == "Sample title"


@pytest.mark.django_db
def test_inspect_processing_records_warning_on_metadata_failure(user, monkeypatch):
    uploaded = SimpleUploadedFile("article.xml", METADATA_XML, content_type="application/xml")
    processing = Processing.objects.create(
        title="XML warning",
        creator=user,
        input_file=uploaded,
    )

    def broken_metadata(_content):
        raise ValueError("invalid metadata")

    monkeypatch.setattr(
        "manuscripts.utils.inspection.extract_article_metadata",
        broken_metadata,
    )

    inspect_processing(processing)

    processing.refresh_from_db()
    assert processing.inspection["inspection_warning"] == "invalid metadata"
    assert processing.inspection["article_candidates"] == []
