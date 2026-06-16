from unittest.mock import MagicMock

import pytest
from django.urls import reverse

from manuscripts.artifacts import save_artifact
from manuscripts.choices import ArtifactType, InputType, ProcessingAction, ProcessStatus


@pytest.mark.django_db
def test_processing_review_post_starts_processing(staff_client, xml_processing, monkeypatch):
    delay = MagicMock()
    monkeypatch.setattr("manuscripts.views.editorial.process_input.delay", delay)

    response = staff_client.post(
        reverse("manuscripts:processing_review", kwargs={"pk": xml_processing.pk}),
        {"requested_actions": [ProcessingAction.XML_VALIDATION]},
    )

    xml_processing.refresh_from_db()
    assert response.status_code == 302
    assert xml_processing.status == ProcessStatus.PENDING
    assert xml_processing.confirmed_type == InputType.XML
    assert xml_processing.requested_actions == [ProcessingAction.XML_VALIDATION]
    delay.assert_called_once_with(xml_processing.pk)


@pytest.mark.django_db
def test_processing_cancel_marks_processing_as_cancelled(staff_client, processing):
    response = staff_client.post(
        reverse("manuscripts:processing_cancel", kwargs={"pk": processing.pk}),
    )

    processing.refresh_from_db()
    assert response.status_code == 302
    assert processing.status == ProcessStatus.CANCELLED


@pytest.mark.django_db
def test_processing_reprocess_increments_retry_and_dispatches_task(staff_client, processing, monkeypatch):
    delay = MagicMock()
    monkeypatch.setattr("manuscripts.views.editorial.process_input.delay", delay)

    response = staff_client.post(
        reverse("manuscripts:processing_reprocess", kwargs={"pk": processing.pk}),
        {"action": ProcessingAction.XML_VALIDATION},
    )

    processing.refresh_from_db()
    assert response.status_code == 302
    assert processing.retry_count == 1
    delay.assert_called_once_with(processing.pk, start_action=ProcessingAction.XML_VALIDATION)


@pytest.mark.django_db
def test_processing_reprocess_ignores_invalid_action(staff_client, processing, monkeypatch):
    delay = MagicMock()
    monkeypatch.setattr("manuscripts.views.editorial.process_input.delay", delay)

    staff_client.post(
        reverse("manuscripts:processing_reprocess", kwargs={"pk": processing.pk}),
        {"action": "invalid-action"},
    )

    delay.assert_called_once_with(processing.pk, start_action=None)


@pytest.mark.django_db
def test_artifact_download_returns_file_content(staff_client, processing, article):
    artifact = save_artifact(
        processing,
        ArtifactType.XML,
        "article.xml",
        b"<article />",
        article=article,
    )

    response = staff_client.get(
        reverse("manuscripts:artifact_download", kwargs={"pk": artifact.pk}),
    )

    assert response.status_code == 200
    assert b"".join(response.streaming_content) == b"<article />"


@pytest.mark.django_db
def test_processing_cancel_get_is_not_allowed(staff_client, processing):
    response = staff_client.get(
        reverse("manuscripts:processing_cancel", kwargs={"pk": processing.pk}),
    )

    assert response.status_code == 405


@pytest.mark.django_db
def test_processing_reprocess_get_is_not_allowed(staff_client, processing):
    response = staff_client.get(
        reverse("manuscripts:processing_reprocess", kwargs={"pk": processing.pk}),
    )

    assert response.status_code == 405
