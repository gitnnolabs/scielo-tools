import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from manuscripts.choices import ArtifactType, InputType
from manuscripts.models.article import ArticleArtifact
from manuscripts.models.processing import Processing
from manuscripts.utils.ingestion import ingest_document, ingest_xml, ingest_zip

MINIMAL_XML = b"<article></article>"


def _processing_with_file(user, filename, content, confirmed_type=InputType.XML):
    uploaded = SimpleUploadedFile(filename, content, content_type="application/octet-stream")
    processing = Processing.objects.create(
        title="Ingestion test",
        creator=user,
        input_file=uploaded,
        confirmed_type=confirmed_type,
    )
    return processing


def _write_zip(path, members):
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in members:
            archive.writestr(name, data)


@pytest.mark.django_db
def test_ingest_xml_creates_article_artifact_and_structure(processing, monkeypatch):
    processing.confirmed_type = InputType.XML
    processing.save(update_fields=["confirmed_type"])

    monkeypatch.setattr(
        "manuscripts.utils.ingestion.parse_xml_structure",
        lambda content: ([], [], [], []),
    )

    article, artifact = ingest_xml(processing, "article.xml", MINIMAL_XML, "pkg/article.xml")

    assert article.pk is not None
    assert processing.articles.filter(pk=article.pk).exists()
    assert artifact.artifact_type == ArtifactType.XML
    assert artifact.original_path == "pkg/article.xml"
    assert artifact.metadata["referenced_assets"] == []
    artifact.refresh_from_db()
    assert artifact.structure is not None
    assert artifact.structure.article_id == article.pk


@pytest.mark.django_db
def test_ingest_document_saves_source_document(user):
    processing = _processing_with_file(user, "manuscript.docx", b"docx-bytes", InputType.DOCUMENT)

    artifact = ingest_document(processing)

    assert artifact.artifact_type == ArtifactType.SOURCE_DOCUMENT
    assert artifact.file.read() == b"docx-bytes"


@pytest.mark.django_db
def test_ingest_document_source_package_returns_docx_from_zip(user, tmp_path):
    zip_path = tmp_path / "source.zip"
    _write_zip(zip_path, [("article.docx", b"docx-content"), ("notes.txt", b"ignore")])
    processing = _processing_with_file(
        user,
        "source.zip",
        zip_path.read_bytes(),
        InputType.SOURCE_PACKAGE,
    )

    artifact = ingest_document(processing)

    assert artifact.artifact_type == ArtifactType.SOURCE_DOCUMENT
    assert artifact.file.read() == b"docx-content"


@pytest.mark.django_db
def test_ingest_document_source_package_without_docx_raises(user, monkeypatch):
    processing = _processing_with_file(user, "source.zip", b"zip", InputType.SOURCE_PACKAGE)
    monkeypatch.setattr(
        "manuscripts.utils.ingestion.ingest_zip",
        lambda proc: (None, []),
    )

    with pytest.raises(ValueError, match="Documento não encontrado"):
        ingest_document(processing)


@pytest.mark.django_db
def test_ingest_zip_source_package_requires_single_document(user, tmp_path):
    zip_path = tmp_path / "multi-doc.zip"
    _write_zip(
        zip_path,
        [("a.docx", b"a"), ("b.docx", b"b"), ("article.xml", MINIMAL_XML)],
    )
    processing = _processing_with_file(
        user,
        "multi-doc.zip",
        zip_path.read_bytes(),
        InputType.SOURCE_PACKAGE,
    )

    with pytest.raises(ValueError, match="exatamente um documento"):
        ingest_zip(processing)


@pytest.mark.django_db
def test_ingest_zip_processes_xml_docx_and_assets(user, tmp_path, monkeypatch):
    zip_path = tmp_path / "sps.zip"
    _write_zip(
        zip_path,
        [
            ("article.xml", MINIMAL_XML),
            ("figures/fig1.png", b"png"),
            ("notes.txt", b"other"),
        ],
    )
    processing = _processing_with_file(
        user,
        "sps.zip",
        zip_path.read_bytes(),
        InputType.SPS_PACKAGE,
    )
    resolved = []
    monkeypatch.setattr(
        "manuscripts.utils.ingestion.resolve_article_assets",
        lambda proc, article, refs: resolved.append((article.pk, refs)),
    )
    monkeypatch.setattr(
        "manuscripts.utils.ingestion.parse_xml_structure",
        lambda content: ([], [], [], []),
    )

    source_document, xml_artifacts = ingest_zip(processing)

    assert source_document is None
    assert len(xml_artifacts) == 1
    article, xml_artifact = xml_artifacts[0]
    assert article.pk is not None
    assert xml_artifact.artifact_type == ArtifactType.XML
    assert resolved == [(article.pk, [])]
    assets = ArticleArtifact.objects.filter(
        processing=processing, artifact_type=ArtifactType.ASSET
    )
    assert assets.count() == 2
    assert {asset.original_path for asset in assets} == {"figures/fig1.png", "notes.txt"}


@pytest.mark.django_db
def test_ingest_zip_with_docx_sets_source_document(user, tmp_path, monkeypatch):
    zip_path = tmp_path / "package.zip"
    _write_zip(
        zip_path,
        [("draft.docx", b"docx"), ("article.xml", MINIMAL_XML)],
    )
    processing = _processing_with_file(
        user,
        "package.zip",
        zip_path.read_bytes(),
        InputType.SPS_PACKAGE,
    )
    monkeypatch.setattr(
        "manuscripts.utils.ingestion.parse_xml_structure",
        lambda content: ([], [], [], []),
    )
    monkeypatch.setattr(
        "manuscripts.utils.ingestion.resolve_article_assets",
        lambda *args, **kwargs: None,
    )

    source_document, xml_artifacts = ingest_zip(processing)

    assert source_document.artifact_type == ArtifactType.SOURCE_DOCUMENT
    assert source_document.file.read() == b"docx"
    assert len(xml_artifacts) == 1
