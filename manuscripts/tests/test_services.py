import pytest

from manuscripts.artifacts import save_artifact
from manuscripts.choices import ArtifactType, EventStatus, InputType, ProcessingAction
from manuscripts.controller import event_complete, event_start, get_or_create_article
from manuscripts.models.article import Article, ArticleStructureVersion
from manuscripts.structure import create_structure_version


@pytest.mark.django_db
def test_get_or_create_article_creates_article_and_links_to_processing(processing, monkeypatch):
    metadata = {
        "title": "Imported title",
        "doi": "10.1234/example.doi",
        "language": "en",
    }
    monkeypatch.setattr("manuscripts.controller.extract_article_metadata", lambda _xml: metadata)

    article, returned_metadata = get_or_create_article(
        processing=processing,
        xml_content=b"<article><front /></article>",
    )

    assert article.pk is not None
    assert article.title == "Imported title"
    assert article.doi == "10.1234/example.doi"
    assert processing.articles.filter(pk=article.pk).exists()
    assert returned_metadata == metadata


@pytest.mark.django_db
def test_get_or_create_article_reuses_existing_article_by_doi(processing, article, monkeypatch):
    monkeypatch.setattr(
        "manuscripts.controller.extract_article_metadata",
        lambda _xml: {"title": "Updated title", "doi": article.doi},
    )

    reused, _metadata = get_or_create_article(
        processing=processing,
        xml_content=b"<article />",
    )

    assert reused.pk == article.pk
    assert Article.objects.filter(doi=article.doi).count() == 1
    assert processing.articles.filter(pk=article.pk).exists()


@pytest.mark.django_db
def test_event_start_and_complete_track_processing_action(processing):
    event = event_start(
        processing=processing,
        action=ProcessingAction.XML_VALIDATION,
        task_id="task-123",
    )

    processing.refresh_from_db()
    assert processing.current_action == ProcessingAction.XML_VALIDATION
    assert event.status == EventStatus.RUNNING
    assert event.task_id == "task-123"

    event_complete(event, message="done", details={"ok": True})

    event.refresh_from_db()
    assert event.status == EventStatus.COMPLETED
    assert event.message == "done"
    assert event.details == {"ok": True}
    assert event.completed_at is not None


@pytest.mark.django_db
def test_event_complete_can_mark_failure(processing):
    event = event_start(
        processing=processing,
        action=ProcessingAction.XML_VALIDATION,
        task_id="task-999",
    )

    event_complete(event, message="broken", details={"error": "boom"}, status=EventStatus.FAILED)

    event.refresh_from_db()
    assert event.status == EventStatus.FAILED
    assert event.message == "broken"
    assert event.details == {"error": "boom"}


@pytest.mark.django_db
def test_save_artifact_versions_current_artifact(processing, article):
    first = save_artifact(
        processing,
        ArtifactType.XML,
        "article.xml",
        b"<article />",
        article=article,
    )
    second = save_artifact(
        processing,
        ArtifactType.XML,
        "article.xml",
        b"<article updated />",
        article=article,
    )

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.version == 1
    assert second.version == 2
    assert first.is_current is False
    assert second.is_current is True
    assert second.checksum != first.checksum


@pytest.mark.django_db
def test_create_structure_version_increments_version_and_marks_current(processing, article):
    first = create_structure_version(
        article,
        processing,
        InputType.XML,
        front=[],
        body=[],
        back=[],
    )
    second = create_structure_version(
        article,
        processing,
        InputType.XML,
        front=[{"type": "paragraph", "value": {"label": "<p>", "paragraph": "Updated"}}],
        body=[],
        back=[],
    )

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.version == 1
    assert second.version == 2
    assert first.is_current is False
    assert second.is_current is True
    assert ArticleStructureVersion.objects.filter(article=article).count() == 2
