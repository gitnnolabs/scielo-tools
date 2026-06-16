import io
import os
import zipfile
from types import SimpleNamespace

import pytest

from manuscripts.artifacts import save_artifact, save_path_artifact
from manuscripts.choices import ArtifactType, EventStatus, InputType, ProcessingAction
from manuscripts.models.article import ArticleArtifact
from manuscripts.models.processing import ProcessingEvent
from manuscripts.tests.test_structure import _make_structure, _paragraph_block
from manuscripts.utils.processing_actions import (
    _ensure_article_title,
    _unwrap_item,
    run_action,
)


class FakeDocx:
    def __init__(self, payload=b"docx-bytes"):
        self._payload = payload
        self.save_calls = 0

    def save(self, buffer):
        self.save_calls += 1
        buffer.write(self._payload)


@pytest.fixture
def linked_processing(processing, article):
    processing.articles.add(article)
    processing.confirmed_type = InputType.DOCUMENT
    processing.save(update_fields=["confirmed_type"])
    return processing


@pytest.fixture
def source_document(linked_processing, article, tmp_path):
    docx_path = tmp_path / "article.docx"
    docx_path.write_bytes(b"source-docx")
    return save_path_artifact(
        linked_processing,
        ArtifactType.SOURCE_DOCUMENT,
        str(docx_path),
        article=article,
    )


@pytest.fixture
def structure(linked_processing, article):
    return _make_structure(article, linked_processing, body=[_paragraph_block("Body text.")])


@pytest.fixture
def xml_artifact(linked_processing, article, structure, tmp_path):
    xml_path = tmp_path / "article.xml"
    xml_path.write_bytes(b'<article><front><article-meta/></front></article>')
    return save_path_artifact(
        linked_processing,
        ArtifactType.XML,
        str(xml_path),
        article=article,
        structure=structure,
    )


def _mock_docx_parser(monkeypatch, document):
    monkeypatch.setattr(
        "manuscripts.utils.processing_actions.DocxParser.open_docx",
        lambda _path: document,
    )


def _mock_citation_externals(
    monkeypatch,
    *,
    marked=True,
    validation=None,
    front=None,
    body=None,
    back=None,
    xref_status=None,
    article_updates=None,
    frontmatter_warnings=None,
    frontmatter_ai=None,
):
    document = FakeDocx()
    marked_calls = {"mark": 0}

    def fake_is_marked(_doc):
        return marked

    def fake_mark_references(doc):
        marked_calls["mark"] += 1
        return doc

    monkeypatch.setattr("manuscripts.utils.processing_actions.is_marked", fake_is_marked)
    monkeypatch.setattr("manuscripts.utils.processing_actions.mark_references", fake_mark_references)
    monkeypatch.setattr(
        "manuscripts.utils.processing_actions.validate_marks",
        lambda _doc: validation or {"valid": True, "issues": 0},
    )
    monkeypatch.setattr(
        "manuscripts.utils.processing_actions.extract_docx_structure",
        lambda _doc, _path: (
            front if front is not None else [],
            body if body is not None else [_paragraph_block("Body.")],
            back if back is not None else [],
            xref_status if xref_status is not None else {},
        ),
    )
    monkeypatch.setattr(
        "manuscripts.utils.processing_actions.extract_frontmatter",
        lambda _article, _front, _body, docx_path=None: (
            front if front is not None else [],
            article_updates or {},
            frontmatter_warnings or [],
            frontmatter_ai or {"status": "completed", "provider": "test"},
        ),
    )
    _mock_docx_parser(monkeypatch, document)
    return document, marked_calls


def _mock_structure_sync(monkeypatch):
    monkeypatch.setattr("manuscripts.structure.get_reference.delay", lambda _pk: None)
    monkeypatch.setattr("manuscripts.structure.transaction.on_commit", lambda callback: callback())


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("rows", "exceptions", "expected"),
    [
        ([{"line": 1}], [], True),
        ([], [{"type": "error"}], True),
        ([], [], False),
    ],
)
def test_run_action_sps_package_validation(processing, monkeypatch, rows, exceptions, expected):
    monkeypatch.setattr(
        "manuscripts.utils.processing_actions.xml_utils.validate_zip",
        lambda _path: (rows, exceptions),
    )

    result = run_action(processing, ProcessingAction.SPS_PACKAGE_VALIDATION, "task-sps")

    assert result is expected
    event = ProcessingEvent.objects.get(
        processing=processing,
        action=ProcessingAction.SPS_PACKAGE_VALIDATION,
    )
    assert event.status == EventStatus.COMPLETED
    assert event.details == {"issues": len(rows), "exceptions": len(exceptions)}
    assert ArticleArtifact.objects.filter(
        processing=processing,
        artifact_type=ArtifactType.VALIDATION_REPORT,
        is_current=True,
    ).exists()
    assert ArticleArtifact.objects.filter(
        processing=processing,
        artifact_type=ArtifactType.VALIDATION_EXCEPTIONS,
        is_current=True,
    ).exists()


@pytest.mark.django_db
def test_run_action_citation_markup_unmarked_document(
    linked_processing, article, source_document, monkeypatch
):
    _mock_structure_sync(monkeypatch)
    article.title = ""
    article.save(update_fields=["title"])
    front = [
        {
            "type": "paragraph_with_language",
            "value": {"label": "<article-title>", "paragraph": "Derived title"},
        }
    ]
    document, marked_calls = _mock_citation_externals(
        monkeypatch,
        marked=False,
        front=front,
        article_updates={"doi": "10.0000/updated"},
        frontmatter_warnings=["warn-one"],
        frontmatter_ai={"status": "completed", "provider": "ollama"},
    )

    result = run_action(linked_processing, ProcessingAction.CITATION_MARKUP, "task-cite")

    assert result is False
    assert marked_calls["mark"] == 1
    assert document.save_calls == 1
    article.refresh_from_db()
    assert article.doi == "10.0000/updated"
    assert article.title == "Derived title"
    marked = ArticleArtifact.objects.get(
        processing=linked_processing,
        article=article,
        artifact_type=ArtifactType.MARKED_DOCUMENT,
        is_current=True,
    )
    assert marked.metadata == {"valid": True, "issues": 0}
    event = ProcessingEvent.objects.get(
        processing=linked_processing,
        article=article,
        action=ProcessingAction.CITATION_MARKUP,
    )
    assert event.status == EventStatus.COMPLETED
    assert event.details["structure_version"] == 1
    assert event.details["body_blocks"] == 1
    assert event.details["frontmatter_ai_warnings"] == ["warn-one"]


@pytest.mark.django_db
def test_run_action_citation_markup_marked_document_skips_mark_references(
    linked_processing, article, source_document, monkeypatch
):
    _mock_structure_sync(monkeypatch)
    article.title = "Preset title"
    article.save(update_fields=["title"])
    _document, marked_calls = _mock_citation_externals(monkeypatch, marked=True, article_updates={})

    run_action(linked_processing, ProcessingAction.CITATION_MARKUP, "task-cite")

    assert marked_calls["mark"] == 0
    article.refresh_from_db()
    assert article.title == "Preset title"


@pytest.mark.django_db
def test_run_action_xml_generation_without_structure_raises(linked_processing, article):
    linked_processing.articles.add(article)

    with pytest.raises(ValueError, match="não possui estrutura"):
        run_action(linked_processing, ProcessingAction.XML_GENERATION, "task-xml")


@pytest.mark.django_db
def test_run_action_xml_generation_creates_xml(
    linked_processing, article, structure, monkeypatch
):
    monkeypatch.setattr(
        "manuscripts.utils.processing_actions.generate_structure_xml",
        lambda _structure: b"<article generated='true' />",
    )

    run_action(linked_processing, ProcessingAction.XML_GENERATION, "task-xml")

    artifact = ArticleArtifact.objects.get(
        processing=linked_processing,
        article=article,
        artifact_type=ArtifactType.XML,
        is_current=True,
    )
    assert artifact.file.read() == b"<article generated='true' />"
    event = ProcessingEvent.objects.get(
        processing=linked_processing,
        article=article,
        action=ProcessingAction.XML_GENERATION,
    )
    assert event.status == EventStatus.COMPLETED


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("validation_content", "exceptions_content", "expected_partial"),
    [
        ("header\nissue\n", "", True),
        ("header\n", "exception details", True),
        ("header\n", "   \n", False),
    ],
)
def test_run_action_xml_validation_issues(
    linked_processing,
    article,
    xml_artifact,
    tmp_path,
    monkeypatch,
    validation_content,
    exceptions_content,
    expected_partial,
):
    validation_path = tmp_path / "validation.tsv"
    exceptions_path = tmp_path / "exceptions.txt"
    validation_path.write_text(validation_content, encoding="utf-8")
    exceptions_path.write_text(exceptions_content, encoding="utf-8")
    monkeypatch.setattr(
        "manuscripts.utils.processing_actions.xml_utils.validate_xml_document",
        lambda _xml_path, _output_dir, _config: (str(validation_path), str(exceptions_path)),
    )

    result = run_action(linked_processing, ProcessingAction.XML_VALIDATION, "task-validate")

    assert result is expected_partial
    event = ProcessingEvent.objects.get(
        processing=linked_processing,
        article=article,
        action=ProcessingAction.XML_VALIDATION,
    )
    assert event.details["has_issues"] is expected_partial


@pytest.mark.django_db
def test_run_action_sps_package_generation_includes_referenced_assets_only(
    linked_processing, article, xml_artifact, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "manuscripts.utils.processing_actions.extract_article_metadata",
        lambda _xml: {"assets": ["media/fig1.png?v=1", "fig2.png"]},
    )
    save_artifact(
        linked_processing,
        ArtifactType.ASSET,
        "fig1.png",
        b"png-one",
        article=article,
        original_path="media/fig1.png",
    )
    save_artifact(
        linked_processing,
        ArtifactType.ASSET,
        "ignored.png",
        b"ignored",
        article=article,
        original_path="media/ignored.png",
    )

    run_action(linked_processing, ProcessingAction.SPS_PACKAGE_GENERATION, "task-sps-gen")

    package = ArticleArtifact.objects.get(
        processing=linked_processing,
        article=article,
        artifact_type=ArtifactType.SPS_PACKAGE,
        is_current=True,
    )
    with zipfile.ZipFile(io.BytesIO(package.file.read())) as archive:
        names = set(archive.namelist())
    assert os.path.basename(xml_artifact.file.name) in names
    assert "media/fig1.png" in names
    assert "media/ignored.png" not in names


@pytest.mark.django_db
def test_run_action_html_generation(
    linked_processing, article, xml_artifact, tmp_path, monkeypatch
):
    html_path = tmp_path / "article.html"
    html_path.write_text("<html>preview</html>", encoding="utf-8")
    captured = {}

    def fake_generate_html(xml_path, output_dir, config, asset_url_map=None):
        captured["xml_path"] = xml_path
        captured["output_dir"] = output_dir
        captured["config"] = config
        captured["asset_url_map"] = asset_url_map
        return str(html_path), "en"

    monkeypatch.setattr(
        "manuscripts.utils.processing_actions.xml_utils.generate_html_for_xml_document",
        fake_generate_html,
    )
    monkeypatch.setattr(
        "manuscripts.utils.processing_actions.article_asset_url_map",
        lambda _processing, _article: {"fig.png": "/media/fig.png"},
    )

    run_action(linked_processing, ProcessingAction.HTML_GENERATION, "task-html")

    artifact = ArticleArtifact.objects.get(
        processing=linked_processing,
        article=article,
        artifact_type=ArtifactType.HTML,
        is_current=True,
    )
    assert artifact.metadata == {"language": "en"}
    assert captured["asset_url_map"] == {"fig.png": "/media/fig.png"}


@pytest.mark.django_db
def test_run_action_pdf_generation_without_docx_path_cleans_assets_dir(
    linked_processing, article, xml_artifact, tmp_path, monkeypatch
):
    assets_dir = tmp_path / "pdf-assets"
    assets_dir.mkdir()
    (assets_dir / "figure.png").write_bytes(b"png")
    pdf_path = tmp_path / "article.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    monkeypatch.setattr(
        "manuscripts.utils.processing_actions.article_assets_dir",
        lambda _processing, _article: str(assets_dir),
    )
    monkeypatch.setattr(
        "manuscripts.utils.processing_actions.article_asset_url_map",
        lambda _processing, _article: {},
    )
    monkeypatch.setattr(
        "manuscripts.utils.processing_actions.xml_utils.generate_pdf_for_xml_document",
        lambda _xml_path, _output_dir, _params: (str(pdf_path), None, "pt"),
    )

    run_action(linked_processing, ProcessingAction.PDF_GENERATION, "task-pdf")

    assert not assets_dir.exists()
    assert ArticleArtifact.objects.filter(
        processing=linked_processing,
        article=article,
        artifact_type=ArtifactType.PDF,
        is_current=True,
    ).exists()
    assert not ArticleArtifact.objects.filter(
        processing=linked_processing,
        article=article,
        artifact_type=ArtifactType.INTERMEDIATE_DOCUMENT,
    ).exists()


@pytest.mark.django_db
def test_run_action_pdf_generation_with_docx_path(
    linked_processing, article, xml_artifact, tmp_path, monkeypatch
):
    assets_dir = tmp_path / "pdf-assets-with-docx"
    assets_dir.mkdir()
    pdf_path = tmp_path / "article.pdf"
    docx_path = tmp_path / "article.docx"
    pdf_path.write_bytes(b"%PDF-1.4")
    docx_path.write_bytes(b"docx")

    monkeypatch.setattr(
        "manuscripts.utils.processing_actions.article_assets_dir",
        lambda _processing, _article: str(assets_dir),
    )
    monkeypatch.setattr(
        "manuscripts.utils.processing_actions.article_asset_url_map",
        lambda _processing, _article: {"fig.png": "/media/fig.png"},
    )
    monkeypatch.setattr(
        "manuscripts.utils.processing_actions.xml_utils.generate_pdf_for_xml_document",
        lambda _xml_path, _output_dir, _params: (str(pdf_path), str(docx_path), "en"),
    )

    run_action(linked_processing, ProcessingAction.PDF_GENERATION, "task-pdf")

    assert not assets_dir.exists()
    assert ArticleArtifact.objects.filter(
        processing=linked_processing,
        article=article,
        artifact_type=ArtifactType.INTERMEDIATE_DOCUMENT,
        is_current=True,
    ).exists()


def test_unwrap_item_object_with_block_type():
    item = SimpleNamespace(
        block_type="paragraph_with_language",
        value={"label": "<article-title>", "paragraph": "Title"},
    )

    assert _unwrap_item(item) == (
        "paragraph_with_language",
        {"label": "<article-title>", "paragraph": "Title"},
    )


def test_unwrap_item_dict():
    assert _unwrap_item({"type": "paragraph", "value": {"label": "<p>", "paragraph": "Text"}}) == (
        "paragraph",
        {"label": "<p>", "paragraph": "Text"},
    )


def test_unwrap_item_dict_without_value():
    assert _unwrap_item({"type": "paragraph"}) == ("paragraph", {})


def test_unwrap_item_fallback():
    assert _unwrap_item("unsupported") == (None, {})


@pytest.mark.django_db
def test_ensure_article_title_from_block_type_object(article):
    article.title = ""
    article.save(update_fields=["title"])
    front = [
        SimpleNamespace(
            block_type="paragraph_with_language",
            value={"label": "<article-title>", "paragraph": "Object block title"},
        )
    ]

    _ensure_article_title(article, front)

    article.refresh_from_db()
    assert article.title == "Object block title"


@pytest.mark.django_db
def test_ensure_article_title_from_dict_front(article):
    article.title = ""
    article.save(update_fields=["title"])
    front = [
        {
            "type": "paragraph",
            "value": {"label": "<article-title>", "paragraph": "Dict block title"},
        }
    ]

    _ensure_article_title(article, front)

    article.refresh_from_db()
    assert article.title == "Dict block title"


@pytest.mark.django_db
def test_ensure_article_title_falls_back_to_first_front_block(article):
    article.title = ""
    article.save(update_fields=["title"])
    front = [
        {"type": "paragraph", "value": {"label": "<p>", "paragraph": "First paragraph title"}},
        {"type": "paragraph", "value": {"label": "<p>", "paragraph": "Second paragraph"}},
    ]

    _ensure_article_title(article, front)

    article.refresh_from_db()
    assert article.title == "First paragraph title"


@pytest.mark.django_db
def test_ensure_article_title_skips_when_title_already_set(article):
    article.title = "Existing title"
    article.save(update_fields=["title"])
    front = [{"type": "paragraph", "value": {"label": "<article-title>", "paragraph": "Ignored"}}]

    _ensure_article_title(article, front)

    article.refresh_from_db()
    assert article.title == "Existing title"


@pytest.mark.django_db
def test_ensure_article_title_skips_when_front_is_empty(article):
    article.title = ""
    article.save(update_fields=["title"])

    _ensure_article_title(article, [])

    article.refresh_from_db()
    assert article.title == ""
