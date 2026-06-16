import os
import shutil
import socket
import zipfile

import pytest

from manuscripts.artifacts import (
    NoRedirectHandler,
    article_asset_url_map,
    article_assets_dir,
    current_xml,
    extract_docx_assets,
    is_safe_external_url,
    resolve_article_assets,
    save_artifact,
    save_path_artifact,
)
from manuscripts.choices import ArtifactType, EventStatus
from manuscripts.models.article import Article, ArticleArtifact
from manuscripts.models.processing import ProcessingEvent


def test_no_redirect_handler_raises_on_redirect():
    handler = NoRedirectHandler()

    with pytest.raises(ValueError, match="Redirecionamentos não são permitidos"):
        handler.redirect_request(None, None, 302, "", {}, "https://example.com/new")


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/asset.png",
        "http://",
        "https:///path",
        "not-a-url",
    ],
)
def test_is_safe_external_url_rejects_invalid_urls(url):
    assert is_safe_external_url(url) is False


def test_is_safe_external_url_returns_false_on_dns_failure(monkeypatch):
    def raise_gaierror(*_args, **_kwargs):
        raise socket.gaierror("name resolution failed")

    monkeypatch.setattr("manuscripts.artifacts.socket.getaddrinfo", raise_gaierror)

    assert is_safe_external_url("https://example.com/asset.png") is False


def test_is_safe_external_url_rejects_non_global_addresses(monkeypatch):
    monkeypatch.setattr(
        "manuscripts.artifacts.socket.getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))],
    )

    assert is_safe_external_url("https://example.com/asset.png") is False


def test_is_safe_external_url_accepts_global_addresses(monkeypatch):
    monkeypatch.setattr(
        "manuscripts.artifacts.socket.getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))],
    )

    assert is_safe_external_url("https://example.com/asset.png") is True


def test_is_safe_external_url_uses_explicit_port(monkeypatch):
    captured = {}

    def capture_getaddrinfo(host, port, *_args, **_kwargs):
        captured["host"] = host
        captured["port"] = port
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", port))]

    monkeypatch.setattr("manuscripts.artifacts.socket.getaddrinfo", capture_getaddrinfo)

    assert is_safe_external_url("http://cdn.example.com:8080/image.png") is True
    assert captured == {"host": "cdn.example.com", "port": 8080}


@pytest.mark.django_db
def test_save_artifact_asset_uses_basename_when_original_path_missing(processing, article):
    artifact = save_artifact(
        processing,
        ArtifactType.ASSET,
        "nested/path/figure.png",
        b"png-bytes",
        article=article,
    )

    assert artifact.original_path == "figure.png"
    assert artifact.file.name.endswith("figure.png")


@pytest.mark.django_db
def test_save_artifact_asset_versions_by_original_path(processing, article):
    first = save_artifact(
        processing,
        ArtifactType.ASSET,
        "a.png",
        b"first",
        article=article,
        original_path="media/a.png",
    )
    second = save_artifact(
        processing,
        ArtifactType.ASSET,
        "b.png",
        b"second",
        article=article,
        original_path="media/b.png",
    )
    updated = save_artifact(
        processing,
        ArtifactType.ASSET,
        "a.png",
        b"updated",
        article=article,
        original_path="media/a.png",
    )

    first.refresh_from_db()
    second.refresh_from_db()
    updated.refresh_from_db()
    assert first.version == 1
    assert second.version == 1
    assert updated.version == 2
    assert first.is_current is False
    assert second.is_current is True
    assert updated.is_current is True


@pytest.mark.django_db
def test_save_path_artifact_reads_file_content(processing, article, tmp_path):
    source = tmp_path / "article.xml"
    source.write_bytes(b"<article />")

    artifact = save_path_artifact(
        processing,
        ArtifactType.XML,
        str(source),
        article=article,
        metadata={"source": "disk"},
    )

    assert artifact.artifact_type == ArtifactType.XML
    assert artifact.metadata == {"source": "disk"}
    with artifact.file.open("rb") as stored:
        assert stored.read() == b"<article />"


@pytest.mark.django_db
def test_current_xml_returns_current_artifact(processing, article):
    xml_artifact = save_artifact(
        processing,
        ArtifactType.XML,
        "article.xml",
        b"<article />",
        article=article,
    )

    assert current_xml(processing, article) == xml_artifact


@pytest.mark.django_db
def test_current_xml_raises_when_missing(processing, article):
    with pytest.raises(ValueError, match=f"Artigo {article} não possui XML"):
        current_xml(processing, article)


@pytest.mark.django_db
def test_article_asset_url_map_uses_original_path_and_file_name(processing, article):
    with_path = save_artifact(
        processing,
        ArtifactType.ASSET,
        "stored-a.png",
        b"a",
        article=article,
        original_path="word/media/a.png",
    )
    without_path = save_artifact(
        processing,
        ArtifactType.ASSET,
        "stored-b.png",
        b"b",
        article=article,
    )

    url_map = article_asset_url_map(processing, article)

    assert url_map == {
        "a.png": with_path.file.url,
        "stored-b.png": without_path.file.url,
    }


@pytest.mark.django_db
def test_article_assets_dir_returns_none_when_no_assets(processing, article):
    assert article_assets_dir(processing, article) is None


@pytest.mark.django_db
def test_article_assets_dir_creates_symlinks(processing, article):
    save_artifact(
        processing,
        ArtifactType.ASSET,
        "figure.png",
        b"png",
        article=article,
        original_path="word/media/figure.png",
    )

    assets_dir = article_assets_dir(processing, article)
    try:
        target = os.path.join(assets_dir, "figure.png")
        assert os.path.islink(target)
        with open(target, "rb") as linked:
            assert linked.read() == b"png"
    finally:
        shutil_rmtree(assets_dir)


@pytest.mark.django_db
def test_article_assets_dir_falls_back_to_copy_when_symlink_fails(processing, article, monkeypatch):
    save_artifact(
        processing,
        ArtifactType.ASSET,
        "figure.png",
        b"png",
        article=article,
        original_path="word/media/figure.png",
    )

    def fail_symlink(*_args, **_kwargs):
        raise OSError("symlinks not supported")

    monkeypatch.setattr("manuscripts.artifacts.os.symlink", fail_symlink)

    assets_dir = article_assets_dir(processing, article)
    try:
        target = os.path.join(assets_dir, "figure.png")
        assert os.path.isfile(target)
        assert not os.path.islink(target)
        with open(target, "rb") as copied:
            assert copied.read() == b"png"
    finally:
        shutil_rmtree(assets_dir)


@pytest.mark.django_db
def test_resolve_article_assets_reassigns_local_asset_for_same_article(processing, article):
    local = save_artifact(
        processing,
        ArtifactType.ASSET,
        "figure.png",
        b"png",
        article=article,
        original_path="figure.png",
    )

    resolve_article_assets(processing, article, ["figure.png"])

    local.refresh_from_db()
    assert local.article_id == article.pk
    assert ArticleArtifact.objects.filter(
        processing=processing,
        article=article,
        artifact_type=ArtifactType.ASSET,
        original_path="figure.png",
        is_current=True,
    ).count() == 1


@pytest.mark.django_db
def test_resolve_article_assets_copies_local_asset_from_other_article(processing, article, user):
    other_article = Article.objects.create(title="Other", doi="10.0000/other", creator=user)
    shared = save_artifact(
        processing,
        ArtifactType.ASSET,
        "shared.png",
        b"shared",
        article=other_article,
        original_path="shared.png",
        source_url="https://example.com/shared.png",
    )

    resolve_article_assets(processing, article, ["shared.png"])

    copied = ArticleArtifact.objects.get(
        processing=processing,
        article=article,
        artifact_type=ArtifactType.ASSET,
        original_path="shared.png",
        is_current=True,
    )
    shared.refresh_from_db()
    assert copied.pk != shared.pk
    assert copied.source_url == "https://example.com/shared.png"
    with copied.file.open("rb") as stored:
        assert stored.read() == b"shared"


@pytest.mark.django_db
def test_resolve_article_assets_records_blocked_external_url(processing, article):
    resolve_article_assets(processing, article, ["file:///etc/passwd"])

    event = ProcessingEvent.objects.get(processing=processing, article=article)
    assert event.status == EventStatus.FAILED
    assert "bloqueada" in event.message
    assert event.details["asset"] == "file:///etc/passwd"


@pytest.mark.django_db
def test_resolve_article_assets_downloads_safe_external_asset(processing, article, monkeypatch):
    monkeypatch.setattr("manuscripts.artifacts.is_safe_external_url", lambda _url: True)
    monkeypatch.setattr("manuscripts.artifacts.build_opener", mock_external_opener(b"remote-png"))

    resolve_article_assets(
        processing,
        article,
        ["https://cdn.example.com/assets/remote.png?version=1"],
    )

    artifact = ArticleArtifact.objects.get(
        processing=processing,
        article=article,
        artifact_type=ArtifactType.ASSET,
        original_path="remote.png",
        is_current=True,
    )
    assert artifact.source_url == "https://cdn.example.com/assets/remote.png?version=1"
    with artifact.file.open("rb") as stored:
        assert stored.read() == b"remote-png"


@pytest.mark.django_db
def test_resolve_article_assets_skips_downloads_larger_than_25mb(processing, article, monkeypatch):
    monkeypatch.setattr("manuscripts.artifacts.is_safe_external_url", lambda _url: True)
    oversized = b"x" * (25 * 1024 * 1024 + 1)
    monkeypatch.setattr("manuscripts.artifacts.build_opener", mock_external_opener(oversized))

    resolve_article_assets(processing, article, ["https://cdn.example.com/huge.bin"])

    assert not ArticleArtifact.objects.filter(
        processing=processing,
        article=article,
        artifact_type=ArtifactType.ASSET,
    ).exists()
    assert not ProcessingEvent.objects.filter(processing=processing, article=article).exists()


@pytest.mark.django_db
def test_resolve_article_assets_records_download_exception(processing, article, monkeypatch):
    monkeypatch.setattr("manuscripts.artifacts.is_safe_external_url", lambda _url: True)

    class BrokenOpener:
        def open(self, *_args, **_kwargs):
            raise OSError("connection reset")

    monkeypatch.setattr(
        "manuscripts.artifacts.build_opener",
        lambda _handler: BrokenOpener(),
    )

    resolve_article_assets(processing, article, ["https://cdn.example.com/missing.png"])

    event = ProcessingEvent.objects.get(processing=processing, article=article)
    assert event.status == EventStatus.FAILED
    assert "Não foi possível baixar o asset" in event.message
    assert event.details["error"] == "connection reset"


@pytest.mark.django_db
def test_extract_docx_assets_saves_word_media_members(processing, article, tmp_path):
    docx_path = tmp_path / "article.docx"
    with zipfile.ZipFile(docx_path, "w") as archive:
        archive.writestr("word/media/figure1.png", b"png-one")
        archive.writestr("word/media/figure2.jpg", b"jpg-two")
        archive.writestr("word/document.xml", b"<w:document />")
        archive.writestr("../escape.png", b"ignored")

    source = save_path_artifact(
        processing,
        ArtifactType.SOURCE_DOCUMENT,
        str(docx_path),
        article=article,
    )

    extract_docx_assets(processing, source, article)

    saved = {
        artifact.original_path: artifact.file.read()
        for artifact in ArticleArtifact.objects.filter(
            processing=processing,
            article=article,
            artifact_type=ArtifactType.ASSET,
            is_current=True,
        )
    }
    assert saved == {
        "figure1.png": b"png-one",
        "figure2.jpg": b"jpg-two",
    }


@pytest.mark.django_db
def test_extract_docx_assets_ignores_bad_zip_files(processing, article, tmp_path):
    broken = tmp_path / "broken.docx"
    broken.write_bytes(b"not-a-zip")
    source = save_path_artifact(
        processing,
        ArtifactType.SOURCE_DOCUMENT,
        str(broken),
        article=article,
    )

    extract_docx_assets(processing, source, article)

    assert not ArticleArtifact.objects.filter(
        processing=processing,
        article=article,
        artifact_type=ArtifactType.ASSET,
    ).exists()


def mock_external_opener(content):
    class MockResponse:
        def read(self, _max_bytes):
            return content

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class MockOpener:
        def open(self, _request, timeout=10):
            return MockResponse()

    return lambda _handler: MockOpener()


def shutil_rmtree(path):
    shutil.rmtree(path, ignore_errors=True)
