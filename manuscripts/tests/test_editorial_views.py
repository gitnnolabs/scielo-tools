import json
from unittest.mock import MagicMock, patch

from lxml import etree

import pytest
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import reverse

from manuscripts.artifacts import save_artifact
from manuscripts.choices import ArtifactType, InputType, ProcessingAction, ProcessStatus
from manuscripts.models.article import (
    Article,
    ArticleArtifact,
    ArticleReference,
    ArticleStructureVersion,
    CitationOccurrence,
)
from manuscripts.models.processing import Processing, ProcessingEvent
from manuscripts.structure import create_structure_version, sync_references
from manuscripts.views import editorial as editorial_views
from references.models import ElementCitation


@pytest.fixture
def request_factory():
    return RequestFactory()


@pytest.fixture
def mock_render(monkeypatch):
    captured = {}

    def _render(request, template_name, context=None, **kwargs):
        captured["template"] = template_name
        captured["context"] = context or {}
        return HttpResponse("rendered")

    monkeypatch.setattr("manuscripts.views.editorial.render", _render)
    return captured


def _staff_request(request_factory, staff_user, method, path, data=None):
    factory_method = getattr(request_factory, method.lower())
    if data is not None:
        request = factory_method(path, data)
    else:
        request = factory_method(path)
    request.user = staff_user
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


@pytest.mark.django_db
def test_processing_review_get_renders_form(request_factory, staff_user, xml_processing, mock_render):
    request = _staff_request(
        request_factory,
        staff_user,
        "get",
        reverse("manuscripts:processing_review", kwargs={"pk": xml_processing.pk}),
    )

    response = editorial_views.processing_review(request, xml_processing.pk)

    assert response.status_code == 200
    assert mock_render["template"] == "manuscripts/processing_review.html"
    assert mock_render["context"]["processing"] == xml_processing
    assert mock_render["context"]["form"].instance == xml_processing


@pytest.mark.django_db
def test_processing_review_invalid_post_renders_form(
    request_factory, staff_user, processing, mock_render
):
    processing.detected_type = InputType.UNKNOWN
    processing.save(update_fields=["detected_type"])
    request = _staff_request(
        request_factory,
        staff_user,
        "post",
        reverse("manuscripts:processing_review", kwargs={"pk": processing.pk}),
        {"requested_actions": [ProcessingAction.XML_VALIDATION]},
    )

    response = editorial_views.processing_review(request, processing.pk)

    assert response.status_code == 200
    assert mock_render["template"] == "manuscripts/processing_review.html"
    processing.refresh_from_db()
    assert processing.status != ProcessStatus.PENDING


@pytest.mark.django_db
def test_processing_cleanup_artifacts_requires_confirmation(request_factory, staff_user, processing):
    request = _staff_request(
        request_factory,
        staff_user,
        "post",
        reverse("manuscripts:processing_cleanup_artifacts", kwargs={"pk": processing.pk}),
        {"confirmation": "wrong"},
    )

    response = editorial_views.processing_cleanup_artifacts(request, processing.pk)

    assert response.status_code == 302
    messages = [message.message for message in get_messages(request)]
    assert any("LIMPAR" in message for message in messages)


@pytest.mark.django_db
def test_processing_cleanup_artifacts_deletes_generated_artifacts(
    request_factory, staff_user, processing, article, user
):
    processing.articles.add(article)
    structure = create_structure_version(article, processing, InputType.XML, [], [], [])
    artifact = save_artifact(
        processing,
        ArtifactType.HTML,
        "article.html",
        b"<html />",
        article=article,
        structure=structure,
    )
    ProcessingEvent.objects.create(processing=processing, article=article, creator=user)
    request = _staff_request(
        request_factory,
        staff_user,
        "post",
        reverse("manuscripts:processing_cleanup_artifacts", kwargs={"pk": processing.pk}),
        {"confirmation": "LIMPAR"},
    )

    response = editorial_views.processing_cleanup_artifacts(request, processing.pk)

    processing.refresh_from_db()
    article.refresh_from_db()
    assert response.status_code == 302
    assert not ArticleArtifact.objects.filter(pk=artifact.pk).exists()
    assert not ArticleStructureVersion.objects.filter(pk=structure.pk).exists()
    assert processing.status == ProcessStatus.AWAITING_REVIEW
    assert article.status == ProcessStatus.PENDING


@pytest.mark.django_db
def test_processing_cleanup_artifacts_include_input_cancels_processing(
    request_factory, staff_user, processing, article
):
    processing.articles.add(article)
    request = _staff_request(
        request_factory,
        staff_user,
        "post",
        reverse("manuscripts:processing_cleanup_artifacts", kwargs={"pk": processing.pk}),
        {"confirmation": "LIMPAR", "include_input": "1"},
    )

    response = editorial_views.processing_cleanup_artifacts(request, processing.pk)

    processing.refresh_from_db()
    assert response.status_code == 302
    assert processing.status == ProcessStatus.CANCELLED
    assert not processing.input_file.storage.exists(processing.input_file.name)


@pytest.mark.django_db
def test_processing_cleanup_artifacts_sets_article_pending_without_structure(
    request_factory, staff_user, processing, article
):
    processing.articles.add(article)
    article.status = ProcessStatus.COMPLETED
    article.save(update_fields=["status"])
    request = _staff_request(
        request_factory,
        staff_user,
        "post",
        reverse("manuscripts:processing_cleanup_artifacts", kwargs={"pk": processing.pk}),
        {"confirmation": "LIMPAR"},
    )

    editorial_views.processing_cleanup_artifacts(request, processing.pk)

    article.refresh_from_db()
    assert article.status == ProcessStatus.PENDING


@pytest.mark.django_db
def test_processing_cleanup_artifacts_restores_latest_structure_version(
    request_factory, staff_user, processing, article, user
):
    other_processing = Processing.objects.create(
        title="Other processing",
        creator=user,
        input_file=SimpleUploadedFile("other.xml", b"<article></article>", content_type="application/xml"),
    )
    processing.articles.add(article)
    older = ArticleStructureVersion.objects.create(
        article=article,
        processing=other_processing,
        version=1,
        is_current=False,
        source_kind=InputType.XML,
        front=[],
        body=[],
        back=[],
        creator=user,
    )
    ArticleStructureVersion.objects.create(
        article=article,
        processing=processing,
        version=2,
        is_current=True,
        source_kind=InputType.XML,
        front=[],
        body=[],
        back=[],
        creator=user,
    )
    request = _staff_request(
        request_factory,
        staff_user,
        "post",
        reverse("manuscripts:processing_cleanup_artifacts", kwargs={"pk": processing.pk}),
        {"confirmation": "LIMPAR"},
    )

    editorial_views.processing_cleanup_artifacts(request, processing.pk)

    older.refresh_from_db()
    assert older.is_current is True


@pytest.mark.django_db
def test_article_cleanup_artifacts_requires_confirmation(request_factory, staff_user, article):
    request = _staff_request(
        request_factory,
        staff_user,
        "post",
        reverse("manuscripts:article_cleanup_artifacts", kwargs={"pk": article.pk}),
        {},
    )

    response = editorial_views.article_cleanup_artifacts(request, article.pk)

    assert response.status_code == 302
    messages = [message.message for message in get_messages(request)]
    assert any("LIMPAR" in message for message in messages)


@pytest.mark.django_db
def test_article_cleanup_artifacts_deletes_all_related_records(
    request_factory, staff_user, processing, article, user
):
    structure = create_structure_version(article, processing, InputType.XML, [], [], [])
    artifact = save_artifact(
        processing,
        ArtifactType.XML,
        "article.xml",
        b"<article />",
        article=article,
        structure=structure,
    )
    ProcessingEvent.objects.create(processing=processing, article=article, creator=user)
    request = _staff_request(
        request_factory,
        staff_user,
        "post",
        reverse("manuscripts:article_cleanup_artifacts", kwargs={"pk": article.pk}),
        {"confirmation": "LIMPAR"},
    )

    response = editorial_views.article_cleanup_artifacts(request, article.pk)

    article.refresh_from_db()
    assert response.status_code == 302
    assert not ArticleArtifact.objects.filter(pk=artifact.pk).exists()
    assert not ArticleStructureVersion.objects.filter(pk=structure.pk).exists()
    assert article.status == ProcessStatus.PENDING


@pytest.mark.django_db
def test_artifact_preview_serves_inline_content(staff_client, processing, article):
    artifact = save_artifact(
        processing,
        ArtifactType.HTML,
        "preview.html",
        b"<html><body>Preview</body></html>",
        article=article,
    )

    response = staff_client.get(
        reverse("manuscripts:artifact_preview", kwargs={"pk": artifact.pk}),
    )

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/html")
    assert b"Preview" in b"".join(response.streaming_content)


@pytest.mark.django_db
def test_article_validation_view_json_array_report(request_factory, staff_user, article, processing, mock_render):
    save_artifact(
        processing,
        ArtifactType.VALIDATION_REPORT,
        "report.json",
        json.dumps([{"group": "meta", "response": "ok"}]).encode(),
        article=article,
    )
    request = _staff_request(
        request_factory,
        staff_user,
        "get",
        reverse("manuscripts:article_validation", kwargs={"pk": article.pk}),
    )

    response = editorial_views.article_validation_view(request, article.pk)

    assert response.status_code == 200
    assert mock_render["context"]["rows"] == [{"group": "meta", "response": "ok"}]


@pytest.mark.django_db
def test_article_validation_view_json_object_report(request_factory, staff_user, article, processing, mock_render):
    save_artifact(
        processing,
        ArtifactType.VALIDATION_REPORT,
        "report.json",
        json.dumps({"group": "single"}).encode(),
        article=article,
    )
    request = _staff_request(
        request_factory,
        staff_user,
        "get",
        reverse("manuscripts:article_validation", kwargs={"pk": article.pk}),
    )

    editorial_views.article_validation_view(request, article.pk)

    assert mock_render["context"]["rows"] == [{"group": "single"}]


@pytest.mark.django_db
def test_article_validation_view_json_lines_report(request_factory, staff_user, article, processing, mock_render):
    save_artifact(
        processing,
        ArtifactType.VALIDATION_REPORT,
        "report.jsonl",
        b'{"group": "line-1"}\n{"group": "line-2"}',
        article=article,
    )
    request = _staff_request(
        request_factory,
        staff_user,
        "get",
        reverse("manuscripts:article_validation", kwargs={"pk": article.pk}),
    )

    editorial_views.article_validation_view(request, article.pk)

    assert len(mock_render["context"]["rows"]) == 2


@pytest.mark.django_db
def test_article_validation_view_csv_report(request_factory, staff_user, article, processing, mock_render):
    csv_content = "context,response,detail,advice\nmeta,error,wrong value,fix it\n"
    save_artifact(
        processing,
        ArtifactType.VALIDATION_REPORT,
        "report.csv",
        csv_content.encode(),
        article=article,
    )
    request = _staff_request(
        request_factory,
        staff_user,
        "get",
        reverse("manuscripts:article_validation", kwargs={"pk": article.pk}),
    )

    editorial_views.article_validation_view(request, article.pk)

    rows = mock_render["context"]["rows"]
    assert rows[0]["group"] == "meta"
    assert rows[0]["response"] == "error"
    assert rows[0]["got_value"] == "wrong value"
    assert rows[0]["advice"] == "fix it"


@pytest.mark.django_db
def test_article_validation_view_exceptions_and_packtools(
    request_factory, staff_user, article, processing, mock_render, monkeypatch
):
    save_artifact(
        processing,
        ArtifactType.VALIDATION_EXCEPTIONS,
        "exceptions.json",
        json.dumps([{"rule": "x"}]).encode(),
        article=article,
    )
    xml_artifact = save_artifact(
        processing,
        ArtifactType.XML,
        "article.xml",
        b"<article></article>",
        article=article,
    )

    validator = MagicMock()
    validator.validate_all.return_value = (False, [MagicMock(message="schema error", line=3)])
    validator.annotate_errors.return_value = etree.Element("article")
    monkeypatch.setattr("manuscripts.views.editorial.packtools.XMLValidator.parse", lambda _path: validator)

    request = _staff_request(
        request_factory,
        staff_user,
        "get",
        reverse("manuscripts:article_validation", kwargs={"pk": article.pk}),
    )

    editorial_views.article_validation_view(request, article.pk)

    assert mock_render["context"]["exceptions"] == [{"rule": "x"}]
    assert mock_render["context"]["schema_valid"] is False
    assert mock_render["context"]["schema_errors"] == [{"message": "schema error", "line": 3}]
    assert mock_render["context"]["annotated_xml"] is not None


@pytest.mark.django_db
def test_article_validation_view_handles_packtools_errors(
    request_factory, staff_user, article, processing, mock_render, monkeypatch
):
    xml_artifact = save_artifact(
        processing,
        ArtifactType.XML,
        "article.xml",
        b"<article></article>",
        article=article,
    )
    monkeypatch.setattr(
        "manuscripts.views.editorial.packtools.XMLValidator.parse",
        MagicMock(side_effect=RuntimeError("packtools failed")),
    )
    request = _staff_request(
        request_factory,
        staff_user,
        "get",
        reverse("manuscripts:article_validation", kwargs={"pk": article.pk}),
    )

    editorial_views.article_validation_view(request, article.pk)

    assert mock_render["context"]["schema_errors"] == [{"message": "packtools failed", "line": None}]


@pytest.mark.django_db
def test_article_structure_edit_redirects_without_structure(request_factory, staff_user, article):
    request = _staff_request(
        request_factory,
        staff_user,
        "get",
        reverse("manuscripts:article_structure_edit", kwargs={"pk": article.pk}),
    )

    response = editorial_views.article_structure_edit(request, article.pk)

    assert response.status_code == 302


@pytest.mark.django_db
def test_article_structure_edit_get_renders_version(
    request_factory, staff_user, article, processing, mock_render
):
    structure = create_structure_version(article, processing, InputType.XML, [], [], [])
    request = request_factory.get(
        reverse("manuscripts:article_structure_edit", kwargs={"pk": article.pk}),
        {"version": str(structure.version)},
    )
    request.user = staff_user
    request.session = {}

    response = editorial_views.article_structure_edit(request, article.pk)

    assert response.status_code == 200
    assert mock_render["context"]["structure"] == structure
    assert mock_render["context"]["is_historical_version"] is False


@pytest.mark.django_db
def test_article_structure_edit_post_valid_saves_structure(
    request_factory, staff_user, article, processing, monkeypatch
):
    structure = create_structure_version(article, processing, InputType.XML, [], [], [])
    saved = MagicMock(version=2)
    monkeypatch.setattr("manuscripts.views.editorial._save_corrected_structure", lambda *args, **kwargs: saved)

    form = MagicMock()
    form.is_valid.return_value = True
    form.cleaned_data = {"front": [], "body": [], "back": []}
    handler = MagicMock()
    handler.get_form_class.return_value = MagicMock(return_value=form)
    handler.get_bound_panel.return_value = "bound-panel"
    monkeypatch.setattr(
        "manuscripts.views.editorial.ObjectList",
        MagicMock(return_value=MagicMock(bind_to_model=MagicMock(return_value=handler))),
    )

    request = _staff_request(
        request_factory,
        staff_user,
        "post",
        reverse("manuscripts:article_structure_edit", kwargs={"pk": article.pk}),
        {},
    )

    response = editorial_views.article_structure_edit(request, article.pk)

    assert response.status_code == 302


@pytest.mark.django_db
def test_article_structure_edit_post_invalid_renders(
    request_factory, staff_user, article, processing, mock_render, monkeypatch
):
    create_structure_version(article, processing, InputType.XML, [], [], [])
    form = MagicMock()
    form.is_valid.return_value = False
    handler = MagicMock()
    handler.get_form_class.return_value = MagicMock(return_value=form)
    handler.get_bound_panel.return_value = "bound-panel"
    monkeypatch.setattr(
        "manuscripts.views.editorial.ObjectList",
        MagicMock(return_value=MagicMock(bind_to_model=MagicMock(return_value=handler))),
    )
    request = _staff_request(
        request_factory,
        staff_user,
        "post",
        reverse("manuscripts:article_structure_edit", kwargs={"pk": article.pk}),
        {},
    )

    response = editorial_views.article_structure_edit(request, article.pk)

    assert response.status_code == 200
    assert mock_render["template"] == "manuscripts/article_structure_edit.html"


@pytest.mark.django_db
def test_article_structure_revert_creates_new_version(request_factory, staff_user, article, processing, monkeypatch):
    structure = create_structure_version(
        article,
        processing,
        InputType.XML,
        [],
        [{"type": "paragraph", "value": {"label": "<p>", "paragraph": "Body"}}],
        [],
    )
    new_structure = MagicMock(version=2)
    monkeypatch.setattr("manuscripts.views.editorial._save_corrected_structure", lambda *args, **kwargs: new_structure)
    request = _staff_request(
        request_factory,
        staff_user,
        "post",
        reverse(
            "manuscripts:article_structure_revert",
            kwargs={"pk": article.pk, "version": structure.version},
        ),
        {},
    )

    response = editorial_views.article_structure_revert(request, article.pk, structure.version)

    assert response.status_code == 302


@pytest.mark.django_db
def test_article_references_edit_redirects_without_structure(request_factory, staff_user, article):
    request = _staff_request(
        request_factory,
        staff_user,
        "get",
        reverse("manuscripts:article_references_edit", kwargs={"pk": article.pk}),
    )

    response = editorial_views.article_references_edit(request, article.pk)

    assert response.status_code == 302


@pytest.mark.django_db
def test_article_references_edit_renders_references(
    request_factory, staff_user, article, processing, mock_render
):
    structure = create_structure_version(
        article,
        processing,
        InputType.XML,
        [],
        [],
        [{"type": "ref_paragraph", "value": {"label": "<p>", "paragraph": "Ref", "refid": "B1"}}],
    )
    sync_references(structure)
    request = _staff_request(
        request_factory,
        staff_user,
        "get",
        reverse("manuscripts:article_references_edit", kwargs={"pk": article.pk}),
    )

    response = editorial_views.article_references_edit(request, article.pk)

    assert response.status_code == 200
    assert mock_render["context"]["structure"] == structure
    assert mock_render["context"]["references"].count() == 1


@pytest.mark.django_db
def test_citation_update_rewrites_xref_and_saves_structure(request_factory, staff_user, article, processing):
    structure = create_structure_version(
        article,
        processing,
        InputType.XML,
        [],
        [{"type": "paragraph", "value": {"label": "<p>", "paragraph": 'See <xref ref-type="bibr" rid="B1">Smith, 2020</xref>.'}}],
        [{"type": "ref_paragraph", "value": {"label": "<p>", "paragraph": "Smith J. 2020.", "refid": "B1"}}],
    )
    sync_references(structure)
    citation = structure.citations.get()
    reference = structure.references.get()
    request = _staff_request(
        request_factory,
        staff_user,
        "post",
        reverse("manuscripts:citation_update", kwargs={"pk": citation.pk}),
        {"references": [str(reference.pk)]},
    )

    response = editorial_views.citation_update(request, citation.pk)

    assert response.status_code == 302
    new_structure = article.structure_versions.order_by("-version").first()
    assert new_structure.version == 2
    paragraph = new_structure.body[0].value["paragraph"]
    assert 'rid="B1"' in paragraph


@pytest.mark.django_db
def test_citation_update_without_matching_block_still_saves(request_factory, staff_user, article, processing, monkeypatch):
    structure = create_structure_version(article, processing, InputType.XML, [], [], [])
    citation = CitationOccurrence.objects.create(
        structure=structure,
        text="Missing",
        location={"block": 99},
        status=CitationOccurrence.Status.ORPHAN,
    )
    monkeypatch.setattr("manuscripts.views.editorial._save_corrected_structure", MagicMock())
    request = _staff_request(
        request_factory,
        staff_user,
        "post",
        reverse("manuscripts:citation_update", kwargs={"pk": citation.pk}),
        {},
    )

    response = editorial_views.citation_update(request, citation.pk)

    assert response.status_code == 302


@pytest.mark.django_db
def test_article_reference_select_updates_selected_element(request_factory, staff_user, article, processing):
    structure = create_structure_version(
        article,
        processing,
        InputType.XML,
        [],
        [],
        [{"type": "ref_paragraph", "value": {"label": "<p>", "paragraph": "Smith J. 2020.", "refid": "B1"}}],
    )
    sync_references(structure)
    article_reference = structure.references.get()
    reference = article_reference.reference
    element = ElementCitation.objects.create(
        reference=reference,
        marked={"authors": ["Smith J"]},
        sort_order=0,
    )
    request = _staff_request(
        request_factory,
        staff_user,
        "post",
        reverse("manuscripts:article_reference_select", kwargs={"pk": article_reference.pk}),
        {"selected_element": str(element.pk)},
    )

    response = editorial_views.article_reference_select(request, article_reference.pk)

    assert response.status_code == 302
    new_reference = article.structure_versions.order_by("-version").first().references.get(ref_id="B1")
    assert new_reference.selected_element_id == element.pk


@pytest.mark.django_db
def test_article_reference_select_without_candidate(request_factory, staff_user, article, processing):
    structure = create_structure_version(
        article,
        processing,
        InputType.XML,
        [],
        [],
        [{"type": "ref_paragraph", "value": {"label": "<p>", "paragraph": "Smith J. 2020.", "refid": "B1"}}],
    )
    sync_references(structure)
    article_reference = structure.references.get()
    request = _staff_request(
        request_factory,
        staff_user,
        "post",
        reverse("manuscripts:article_reference_select", kwargs={"pk": article_reference.pk}),
        {},
    )

    response = editorial_views.article_reference_select(request, article_reference.pk)

    assert response.status_code == 302


@pytest.mark.django_db
def test_article_reprocess_without_processing_redirects(request_factory, staff_user, article):
    request = _staff_request(
        request_factory,
        staff_user,
        "post",
        reverse("manuscripts:article_reprocess", kwargs={"pk": article.pk}),
        {},
    )

    response = editorial_views.article_reprocess(request, article.pk)

    assert response.status_code == 302
    messages = [message.message for message in get_messages(request)]
    assert any("no associated processings" in message.lower() for message in messages)


@pytest.mark.django_db
def test_article_validation_view_handles_report_read_errors(
    request_factory, staff_user, article, processing, mock_render
):
    artifact = save_artifact(
        processing,
        ArtifactType.VALIDATION_REPORT,
        "broken.json",
        b"[",
        article=article,
    )
    artifact.file.storage.delete(artifact.file.name)
    request = _staff_request(
        request_factory,
        staff_user,
        "get",
        reverse("manuscripts:article_validation", kwargs={"pk": article.pk}),
    )

    editorial_views.article_validation_view(request, article.pk)

    assert mock_render["context"]["rows"] == []


@pytest.mark.django_db
def test_article_validation_view_parses_exception_json_lines(
    request_factory, staff_user, article, processing, mock_render
):
    save_artifact(
        processing,
        ArtifactType.VALIDATION_EXCEPTIONS,
        "exceptions.jsonl",
        b'{"rule": "line-1"}\n{"rule": "line-2"}',
        article=article,
    )
    request = _staff_request(
        request_factory,
        staff_user,
        "get",
        reverse("manuscripts:article_validation", kwargs={"pk": article.pk}),
    )

    editorial_views.article_validation_view(request, article.pk)

    assert mock_render["context"]["exceptions"] == [{"rule": "line-1"}, {"rule": "line-2"}]


@pytest.mark.django_db
def test_article_validation_view_wraps_single_exception_object(
    request_factory, staff_user, article, processing, mock_render
):
    save_artifact(
        processing,
        ArtifactType.VALIDATION_EXCEPTIONS,
        "exceptions.json",
        b'{"rule": "single"}',
        article=article,
    )
    request = _staff_request(
        request_factory,
        staff_user,
        "get",
        reverse("manuscripts:article_validation", kwargs={"pk": article.pk}),
    )

    editorial_views.article_validation_view(request, article.pk)

    assert mock_render["context"]["exceptions"] == [{"rule": "single"}]


@pytest.mark.django_db
def test_article_validation_view_handles_exception_read_errors(
    request_factory, staff_user, article, processing, mock_render
):
    artifact = save_artifact(
        processing,
        ArtifactType.VALIDATION_EXCEPTIONS,
        "broken.json",
        b"[]",
        article=article,
    )
    artifact.file.storage.delete(artifact.file.name)
    request = _staff_request(
        request_factory,
        staff_user,
        "get",
        reverse("manuscripts:article_validation", kwargs={"pk": article.pk}),
    )

    editorial_views.article_validation_view(request, article.pk)

    assert mock_render["context"]["exceptions"] == []


@pytest.mark.django_db
def test_article_reprocess_ignores_invalid_action(request_factory, staff_user, article, processing, monkeypatch):
    processing.articles.add(article)
    delay = MagicMock()
    monkeypatch.setattr("manuscripts.views.editorial.process_input.delay", delay)
    request = _staff_request(
        request_factory,
        staff_user,
        "post",
        reverse("manuscripts:article_reprocess", kwargs={"pk": article.pk}),
        {"action": "invalid-action"},
    )

    editorial_views.article_reprocess(request, article.pk)

    delay.assert_called_once_with(processing.pk, start_action=None)


@pytest.mark.django_db
def test_article_reprocess_dispatches_task(request_factory, staff_user, article, processing, monkeypatch):
    processing.articles.add(article)
    delay = MagicMock()
    monkeypatch.setattr("manuscripts.views.editorial.process_input.delay", delay)
    request = _staff_request(
        request_factory,
        staff_user,
        "post",
        reverse("manuscripts:article_reprocess", kwargs={"pk": article.pk}),
        {"action": ProcessingAction.XML_VALIDATION},
    )

    response = editorial_views.article_reprocess(request, article.pk)

    processing.refresh_from_db()
    assert response.status_code == 302
    assert processing.retry_count == 1
    delay.assert_called_once_with(processing.pk, start_action=ProcessingAction.XML_VALIDATION)


@pytest.mark.django_db
def test_delete_artifacts_removes_files(processing, article):
    artifacts = [
        save_artifact(processing, ArtifactType.XML, "one.xml", b"<one />", article=article),
        save_artifact(processing, ArtifactType.HTML, "two.html", b"<two />", article=article),
    ]

    deleted = editorial_views._delete_artifacts(artifacts)

    assert deleted == 2
    assert ArticleArtifact.objects.count() == 0


@pytest.mark.django_db
def test_confirmed_cleanup_helper(request_factory, staff_user):
    request = _staff_request(request_factory, staff_user, "post", "/", {"confirmation": "limpar"})
    assert editorial_views._confirmed_cleanup(request) is True
    request = _staff_request(request_factory, staff_user, "post", "/", {"confirmation": "nope"})
    assert editorial_views._confirmed_cleanup(request) is False


@pytest.mark.django_db
def test_ensure_current_structure_helper(processing, article):
    latest = ArticleStructureVersion.objects.create(
        article=article,
        processing=processing,
        version=1,
        is_current=False,
        source_kind=InputType.XML,
        front=[],
        body=[],
        back=[],
    )

    assert editorial_views._ensure_current_structure(article) is True
    latest.refresh_from_db()
    assert latest.is_current is True
    assert editorial_views._ensure_current_structure(article) is True


@pytest.mark.django_db
def test_save_corrected_structure_helper(processing, article, monkeypatch):
    structure = create_structure_version(article, processing, InputType.XML, [], [], [])
    monkeypatch.setattr(
        "manuscripts.views.editorial.generate_structure_xml",
        lambda _structure: b"<article />",
    )

    new_structure = editorial_views._save_corrected_structure(
        article,
        structure,
        [],
        [],
        [],
    )

    assert new_structure.version == 2
    assert article.current_artifact(ArtifactType.XML) is not None
