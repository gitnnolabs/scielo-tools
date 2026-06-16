import os
import traceback
from pathlib import PurePosixPath

from django.utils import timezone

from .artifacts import extract_docx_assets, resolve_article_assets
from .choices import (
    ArtifactType,
    EventStatus,
    InputType,
    ProcessingAction,
    ProcessStatus,
)
from .controller import get_or_create_article
from .models.processing import Processing, ProcessingEvent
from .utils.ingestion import ingest_document, ingest_xml, ingest_zip
from .utils.inspection import ACTION_ARTIFACT_TYPES, resolve_actions
from .utils.processing_actions import run_action


def process_input(task_instance, processing_id, start_action=None):
    processing = _begin_processing(processing_id)
    try:
        _ingest_input(processing)
        actions = _resolve_pipeline_actions(processing, start_action)
        _record_skipped_actions(processing, actions)
        partial = _execute_actions(processing, actions, task_instance)
        _complete_processing(processing, partial)
    except Exception as exc:
        _fail_processing(processing, exc)
        raise


def _begin_processing(processing_id):
    processing = Processing.objects.get(pk=processing_id)
    processing.status = ProcessStatus.PROCESSING
    processing.processing_started_at = timezone.now()
    processing.completed_at = None
    processing.error_message = ""
    processing.error_details = {}
    processing.error_traceback = ""
    processing.save()
    return processing


def _ingest_input(processing):
    if not processing.confirmed_type or processing.confirmed_type == InputType.UNKNOWN:
        raise ValueError("Confirme o tipo de entrada antes de iniciar.")

    if processing.confirmed_type in (InputType.DOCUMENT, InputType.SOURCE_PACKAGE):
        source = ingest_document(processing)
        article, _metadata = get_or_create_article(processing, title=PurePosixPath(source.file.name).stem)
        processing.artifacts.filter(
            article__isnull=True, artifact_type=ArtifactType.ASSET
        ).update(article=article)
        extract_docx_assets(processing, source, article)

    elif processing.confirmed_type == InputType.XML:
        with processing.input_file.open("rb") as source:
            article, xml_artifact = ingest_xml(
                processing, os.path.basename(processing.input_file.name), source.read()
            )
        resolve_article_assets(
            processing, article, xml_artifact.metadata.get("referenced_assets", [])
        )

    elif processing.confirmed_type == InputType.SPS_PACKAGE:
        _source, _xmls = ingest_zip(processing)

    else:
        raise ValueError("Tipo de entrada não processável.")


def _resolve_pipeline_actions(processing, start_action):
    actions = resolve_actions(processing.requested_actions, processing.confirmed_type)
    applicable = resolve_actions(
        [value for value, _label in ProcessingAction.choices],
        processing.confirmed_type,
    )

    if not start_action:
        return actions

    if start_action not in applicable:
        raise ValueError("A etapa escolhida não se aplica a este processamento.")

    actions = applicable[applicable.index(start_action):]
    invalidated_types = {
        artifact_type
        for action in actions
        for artifact_type in ACTION_ARTIFACT_TYPES.get(action, [])
    }
    processing.artifacts.filter(
        artifact_type__in=invalidated_types, is_current=True
    ).update(is_current=False, is_stale=True)
    return actions


def _record_skipped_actions(processing, actions):
    applicable = resolve_actions(
        [value for value, _label in ProcessingAction.choices],
        processing.confirmed_type,
    )
    for action in applicable:
        if action not in actions:
            ProcessingEvent.objects.create(
                processing=processing,
                action=action,
                status=EventStatus.SKIPPED,
                message="Ação não selecionada para esta execução.",
                completed_at=timezone.now(),
            )


def _execute_actions(processing, actions, task_instance):
    partial = False
    for action in actions:
        task_id = task_instance.request.id if task_instance else None
        partial = run_action(processing, action, task_id) or partial
    return partial


def _complete_processing(processing, partial):
    partial = partial or processing.events.filter(
        status=EventStatus.FAILED, details__severity="warning"
    ).exists()
    processing.status = ProcessStatus.PARTIAL if partial else ProcessStatus.COMPLETED
    processing.completed_at = timezone.now()
    processing.current_action = ""
    processing.save()
    processing.articles.update(status=processing.status)


def _fail_processing(processing, exc):
    processing.status = ProcessStatus.FAILED
    processing.error_message = str(exc)
    processing.error_details = {"action": processing.current_action, "type": exc.__class__.__name__}
    processing.error_traceback = traceback.format_exc()
    processing.save()
    processing.events.filter(status=EventStatus.RUNNING).update(
        status=EventStatus.FAILED,
        message=str(exc),
        completed_at=timezone.now(),
    )
