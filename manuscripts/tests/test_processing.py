import pytest
from types import SimpleNamespace

from django.utils import timezone

from manuscripts.choices import (
    ArtifactType,
    EventStatus,
    InputType,
    ProcessingAction,
    ProcessStatus,
)
from manuscripts.models.processing import Processing, ProcessingEvent
from manuscripts.processing import (
    _begin_processing,
    _complete_processing,
    _execute_actions,
    _fail_processing,
    _ingest_input,
    _record_skipped_actions,
    _resolve_pipeline_actions,
    process_input,
)

MINIMAL_XML = b"<article></article>"


@pytest.mark.django_db
def test_begin_processing_resets_error_fields_and_sets_processing(processing):
    processing.status = ProcessStatus.FAILED
    processing.error_message = "old error"
    processing.error_details = {"action": "old"}
    processing.error_traceback = "traceback"
    processing.completed_at = timezone.now()
    processing.save()

    result = _begin_processing(processing.pk)

    result.refresh_from_db()
    assert result.status == ProcessStatus.PROCESSING
    assert result.processing_started_at is not None
    assert result.completed_at is None
    assert result.error_message == ""
    assert result.error_details == {}
    assert result.error_traceback == ""


@pytest.mark.django_db
def test_ingest_input_rejects_unknown_confirmed_type(processing):
    processing.confirmed_type = InputType.UNKNOWN
    processing.save(update_fields=["confirmed_type"])

    with pytest.raises(ValueError, match="Confirme o tipo de entrada"):
        _ingest_input(processing)


@pytest.mark.django_db
def test_ingest_input_rejects_unprocessable_confirmed_type(processing):
    processing.confirmed_type = InputType.AMBIGUOUS_ZIP
    processing.save(update_fields=["confirmed_type"])

    with pytest.raises(ValueError, match="não processável"):
        _ingest_input(processing)


@pytest.mark.django_db
def test_ingest_input_document_path(processing, article, monkeypatch):
    processing.confirmed_type = InputType.DOCUMENT
    processing.save(update_fields=["confirmed_type"])
    source = SimpleNamespace(file=SimpleNamespace(name="article.docx"))
    calls = {"extract": 0}

    monkeypatch.setattr(
        "manuscripts.processing.ingest_document",
        lambda proc: source if proc.pk == processing.pk else None,
    )
    monkeypatch.setattr(
        "manuscripts.processing.get_or_create_article",
        lambda proc, title: (article, {}) if proc.pk == processing.pk else None,
    )

    def fake_extract(proc, src, art):
        calls["extract"] += 1
        assert proc.pk == processing.pk
        assert src is source
        assert art.pk == article.pk

    monkeypatch.setattr("manuscripts.processing.extract_docx_assets", fake_extract)

    _ingest_input(processing)

    assert calls["extract"] == 1


@pytest.mark.django_db
def test_ingest_input_source_package_path(processing, article, monkeypatch):
    processing.confirmed_type = InputType.SOURCE_PACKAGE
    processing.save(update_fields=["confirmed_type"])
    source = SimpleNamespace(file=SimpleNamespace(name="package/article.docx"))
    calls = {"extract": 0}

    monkeypatch.setattr("manuscripts.processing.ingest_document", lambda proc: source)
    monkeypatch.setattr(
        "manuscripts.processing.get_or_create_article",
        lambda proc, title: (article, {}),
    )
    monkeypatch.setattr(
        "manuscripts.processing.extract_docx_assets",
        lambda proc, src, art: calls.update(extract=calls["extract"] + 1),
    )

    _ingest_input(processing)

    assert calls["extract"] == 1


@pytest.mark.django_db
def test_ingest_input_xml_path(processing, monkeypatch):
    processing.confirmed_type = InputType.XML
    processing.save(update_fields=["confirmed_type"])
    article = SimpleNamespace(pk=1)
    xml_artifact = SimpleNamespace(metadata={"referenced_assets": ["fig1.png"]})
    resolved = []

    monkeypatch.setattr(
        "manuscripts.processing.ingest_xml",
        lambda proc, name, content: (article, xml_artifact),
    )
    monkeypatch.setattr(
        "manuscripts.processing.resolve_article_assets",
        lambda proc, art, refs: resolved.append((proc.pk, art, refs)),
    )

    _ingest_input(processing)

    assert resolved == [(processing.pk, article, ["fig1.png"])]


@pytest.mark.django_db
def test_ingest_input_sps_package_path(processing, monkeypatch):
    processing.confirmed_type = InputType.SPS_PACKAGE
    processing.save(update_fields=["confirmed_type"])
    ingested = []

    monkeypatch.setattr(
        "manuscripts.processing.ingest_zip",
        lambda proc: ingested.append(proc.pk) or ("source", []),
    )

    _ingest_input(processing)

    assert ingested == [processing.pk]


@pytest.mark.django_db
def test_resolve_pipeline_actions_without_start_action(processing):
    processing.confirmed_type = InputType.XML
    processing.requested_actions = [ProcessingAction.XML_VALIDATION]
    processing.save(update_fields=["confirmed_type", "requested_actions"])

    actions = _resolve_pipeline_actions(processing, start_action=None)

    assert actions == [ProcessingAction.XML_VALIDATION]


@pytest.mark.django_db
def test_resolve_pipeline_actions_with_start_action(processing):
    processing.confirmed_type = InputType.DOCUMENT
    processing.requested_actions = [ProcessingAction.XML_GENERATION]
    processing.save(update_fields=["confirmed_type", "requested_actions"])

    actions = _resolve_pipeline_actions(processing, start_action=ProcessingAction.XML_VALIDATION)

    assert actions == [
        ProcessingAction.XML_VALIDATION,
        ProcessingAction.SPS_PACKAGE_GENERATION,
        ProcessingAction.HTML_GENERATION,
        ProcessingAction.PDF_GENERATION,
    ]


@pytest.mark.django_db
def test_resolve_pipeline_actions_rejects_invalid_start_action(processing):
    processing.confirmed_type = InputType.XML
    processing.save(update_fields=["confirmed_type"])

    with pytest.raises(ValueError, match="não se aplica"):
        _resolve_pipeline_actions(processing, start_action=ProcessingAction.CITATION_MARKUP)


@pytest.mark.django_db
def test_resolve_pipeline_actions_invalidates_stale_artifacts(processing, article):
    processing.confirmed_type = InputType.DOCUMENT
    processing.requested_actions = [ProcessingAction.XML_GENERATION]
    processing.save(update_fields=["confirmed_type", "requested_actions"])
    from manuscripts.artifacts import save_artifact

    artifact = save_artifact(
        processing,
        ArtifactType.HTML,
        "article.html",
        b"<html></html>",
        article=article,
    )
    assert artifact.is_current is True
    assert artifact.is_stale is False

    _resolve_pipeline_actions(processing, start_action=ProcessingAction.XML_VALIDATION)

    artifact.refresh_from_db()
    assert artifact.is_current is False
    assert artifact.is_stale is True


@pytest.mark.django_db
def test_record_skipped_actions_creates_events_for_unselected_actions(processing):
    processing.confirmed_type = InputType.XML
    processing.save(update_fields=["confirmed_type"])
    selected = [ProcessingAction.XML_VALIDATION]

    _record_skipped_actions(processing, selected)

    skipped = {
        event.action
        for event in ProcessingEvent.objects.filter(
            processing=processing, status=EventStatus.SKIPPED
        )
    }
    assert ProcessingAction.SPS_PACKAGE_GENERATION in skipped
    assert ProcessingAction.XML_VALIDATION not in skipped


@pytest.mark.django_db
def test_execute_actions_without_task_instance(processing, monkeypatch):
    calls = []

    monkeypatch.setattr(
        "manuscripts.processing.run_action",
        lambda proc, action, task_id: calls.append((action, task_id)) or False,
    )

    partial = _execute_actions(
        processing,
        [ProcessingAction.XML_VALIDATION, ProcessingAction.HTML_GENERATION],
        task_instance=None,
    )

    assert partial is False
    assert calls == [
        (ProcessingAction.XML_VALIDATION, None),
        (ProcessingAction.HTML_GENERATION, None),
    ]


@pytest.mark.django_db
def test_execute_actions_with_task_instance(processing, monkeypatch):
    task_instance = SimpleNamespace(request=SimpleNamespace(id="celery-task-42"))
    calls = []

    monkeypatch.setattr(
        "manuscripts.processing.run_action",
        lambda proc, action, task_id: calls.append(task_id) or (action == ProcessingAction.XML_VALIDATION),
    )

    partial = _execute_actions(processing, [ProcessingAction.XML_VALIDATION], task_instance)

    assert partial is True
    assert calls == ["celery-task-42"]


@pytest.mark.django_db
def test_complete_processing_marks_completed(processing, article):
    processing.articles.add(article)
    processing.current_action = ProcessingAction.XML_VALIDATION
    processing.save(update_fields=["current_action"])

    _complete_processing(processing, partial=False)

    processing.refresh_from_db()
    article.refresh_from_db()
    assert processing.status == ProcessStatus.COMPLETED
    assert processing.completed_at is not None
    assert processing.current_action == ""
    assert article.status == ProcessStatus.COMPLETED


@pytest.mark.django_db
def test_complete_processing_marks_partial_from_flag(processing, article):
    processing.articles.add(article)

    _complete_processing(processing, partial=True)

    processing.refresh_from_db()
    article.refresh_from_db()
    assert processing.status == ProcessStatus.PARTIAL
    assert article.status == ProcessStatus.PARTIAL


@pytest.mark.django_db
def test_complete_processing_marks_partial_from_warning_event(processing, article):
    processing.articles.add(article)
    ProcessingEvent.objects.create(
        processing=processing,
        article=article,
        status=EventStatus.FAILED,
        details={"severity": "warning"},
    )

    _complete_processing(processing, partial=False)

    processing.refresh_from_db()
    assert processing.status == ProcessStatus.PARTIAL


@pytest.mark.django_db
def test_fail_processing_records_error_and_fails_running_events(processing):
    processing.current_action = ProcessingAction.XML_VALIDATION
    processing.save(update_fields=["current_action"])
    running = ProcessingEvent.objects.create(
        processing=processing,
        action=ProcessingAction.XML_VALIDATION,
        status=EventStatus.RUNNING,
    )

    with pytest.raises(RuntimeError, match="boom"):
        try:
            raise RuntimeError("boom")
        except RuntimeError as exc:
            _fail_processing(processing, exc)
            raise

    processing.refresh_from_db()
    running.refresh_from_db()
    assert processing.status == ProcessStatus.FAILED
    assert processing.error_message == "boom"
    assert processing.error_details["type"] == "RuntimeError"
    assert processing.error_details["action"] == ProcessingAction.XML_VALIDATION
    assert processing.error_traceback
    assert running.status == EventStatus.FAILED
    assert running.message == "boom"
    assert running.completed_at is not None


@pytest.mark.django_db
def test_process_input_success_path(processing, monkeypatch):
    processing.confirmed_type = InputType.XML
    processing.save(update_fields=["confirmed_type"])
    pipeline = []

    monkeypatch.setattr("manuscripts.processing._ingest_input", lambda proc: pipeline.append("ingest"))
    monkeypatch.setattr(
        "manuscripts.processing._resolve_pipeline_actions",
        lambda proc, start: pipeline.append(("resolve", start)) or [ProcessingAction.XML_VALIDATION],
    )
    monkeypatch.setattr(
        "manuscripts.processing._record_skipped_actions",
        lambda proc, actions: pipeline.append(("skipped", actions)),
    )
    monkeypatch.setattr(
        "manuscripts.processing._execute_actions",
        lambda proc, actions, task: pipeline.append(("execute", task)) or False,
    )
    monkeypatch.setattr(
        "manuscripts.processing._complete_processing",
        lambda proc, partial: pipeline.append(("complete", partial)),
    )
    task = SimpleNamespace(request=SimpleNamespace(id="task-1"))

    process_input(task, processing.pk, start_action=ProcessingAction.XML_VALIDATION)

    assert pipeline[0] == "ingest"
    assert pipeline[1] == ("resolve", ProcessingAction.XML_VALIDATION)
    processing.refresh_from_db()
    assert processing.status == ProcessStatus.PROCESSING


@pytest.mark.django_db
def test_process_input_failure_path(processing, monkeypatch):
    processing.confirmed_type = InputType.XML
    processing.save(update_fields=["confirmed_type"])

    def fail_ingest(_proc):
        raise ValueError("ingest failed")

    monkeypatch.setattr("manuscripts.processing._ingest_input", fail_ingest)

    with pytest.raises(ValueError, match="ingest failed"):
        process_input(None, processing.pk)

    processing.refresh_from_db()
    assert processing.status == ProcessStatus.FAILED
    assert processing.error_message == "ingest failed"
