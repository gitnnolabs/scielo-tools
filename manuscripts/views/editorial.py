import copy
import csv
import io
import json
import mimetypes
import re

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from lxml import etree
import packtools
from wagtail.admin.panels import ObjectList

from manuscripts.artifacts import save_artifact
from manuscripts.choices import ArtifactType, InputType, ProcessingAction, ProcessStatus
from manuscripts.forms import ProcessingReviewForm
from manuscripts.models.article import (
    Article,
    ArticleArtifact,
    ArticleReference,
    ArticleStructureVersion,
    CitationOccurrence,
)
from manuscripts.models.processing import Processing
from manuscripts.structure import create_structure_version
from manuscripts.utils.helpers import to_dict_list
from manuscripts.utils.xml_utils import generate_structure_xml
from manuscripts.tasks import process_input

GENERATED_ARTIFACT_TYPES = [
    ArtifactType.MARKED_DOCUMENT,
    ArtifactType.STRUCTURE,
    ArtifactType.XML,
    ArtifactType.ASSET,
    ArtifactType.SPS_PACKAGE,
    ArtifactType.VALIDATION_REPORT,
    ArtifactType.VALIDATION_EXCEPTIONS,
    ArtifactType.HTML,
    ArtifactType.PDF,
    ArtifactType.INTERMEDIATE_DOCUMENT,
]


def _delete_artifacts(artifacts):
    deleted = 0
    for artifact in list(artifacts):
        file_field = artifact.file
        artifact.delete()
        if file_field:
            file_field.delete(save=False)
        deleted += 1
    return deleted


def _confirmed_cleanup(request):
    return request.POST.get("confirmation", "").strip().upper() == "LIMPAR"


def _ensure_current_structure(article):
    if article.structure_versions.filter(is_current=True).exists():
        return True
    latest = article.structure_versions.order_by("-version").first()
    if not latest:
        return False
    latest.is_current = True
    latest.save(update_fields=["is_current", "updated"])
    return True


def _save_corrected_structure(article, structure, front, body, back):
    front_raw = to_dict_list(front)
    body_raw = to_dict_list(body)
    back_raw = to_dict_list(back)
    new_structure = create_structure_version(
        article,
        structure.processing,
        InputType.DOCUMENT,
        front_raw,
        body_raw,
        back_raw,
        base_xml=structure.base_xml,
        warnings=structure.roundtrip_warnings,
        xref_status=structure.xref_status,
    )
    article.artifacts.filter(
        artifact_type__in=[
            ArtifactType.XML,
            ArtifactType.VALIDATION_REPORT,
            ArtifactType.VALIDATION_EXCEPTIONS,
            ArtifactType.SPS_PACKAGE,
            ArtifactType.HTML,
            ArtifactType.PDF,
        ],
        is_current=True,
    ).update(is_stale=True)
    save_artifact(
        new_structure.processing,
        ArtifactType.XML,
        f"article-{article.pk}.xml",
        generate_structure_xml(new_structure),
        article,
        structure=new_structure,
    )
    return new_structure


@staff_member_required
def processing_review(request, pk):
    processing = get_object_or_404(Processing, pk=pk)
    if request.method == "POST":
        form = ProcessingReviewForm(request.POST, instance=processing)
        if form.is_valid():
            processing = form.save(commit=False)
            processing.confirmed_type = processing.detected_type
            processing.status = ProcessStatus.PENDING
            processing.save()
            process_input.delay(processing.pk)
            messages.success(request, _("Processing started."))
            return redirect("wagtailsnippets_manuscripts_processing:inspect", pk=pk)
    else:
        form = ProcessingReviewForm(instance=processing, initial={
            "requested_actions": processing.requested_actions,
        })
    return render(
        request,
        "manuscripts/processing_review.html",
        {"processing": processing, "form": form},
    )


@staff_member_required
@require_POST
def processing_cancel(request, pk):
    processing = get_object_or_404(Processing, pk=pk)
    processing.status = ProcessStatus.CANCELLED
    processing.save(update_fields=["status", "updated"])
    messages.success(request, _("Processing cancelled."))
    return redirect("wagtailsnippets_manuscripts_processing:inspect", pk=pk)


@staff_member_required
@require_POST
def processing_reprocess(request, pk):
    processing = get_object_or_404(Processing, pk=pk)
    action = request.POST.get("action")
    if action not in ProcessingAction.values:
        action = None
    processing.retry_count += 1
    processing.save(update_fields=["retry_count", "updated"])
    process_input.delay(processing.pk, start_action=action)
    messages.success(request, _("Reprocessing started."))
    return redirect("wagtailsnippets_manuscripts_processing:inspect", pk=pk)


@staff_member_required
@require_POST
def processing_cleanup_artifacts(request, pk):
    processing = get_object_or_404(Processing, pk=pk)
    if not _confirmed_cleanup(request):
        messages.error(request, _('Enter "LIMPAR" to confirm cleanup.'))
        return redirect("wagtailsnippets_manuscripts_processing:inspect", pk=pk)

    include_input = request.POST.get("include_input") == "1"
    artifact_types = None if include_input else GENERATED_ARTIFACT_TYPES
    artifacts = processing.artifacts.all()
    if artifact_types is not None:
        artifacts = artifacts.filter(artifact_type__in=artifact_types)

    with transaction.atomic():
        deleted = _delete_artifacts(artifacts)
        article_ids = list(processing.articles.values_list("pk", flat=True))
        deleted_structures = ArticleStructureVersion.objects.filter(processing=processing).count()
        ArticleStructureVersion.objects.filter(processing=processing).delete()
        processing.events.all().delete()
        for article in Article.objects.filter(pk__in=article_ids):
            if not _ensure_current_structure(article):
                article.status = ProcessStatus.PENDING
                article.save(update_fields=["status", "updated"])
        if include_input and processing.input_file:
            input_file = processing.input_file
            processing.status = ProcessStatus.CANCELLED
            processing.current_action = ""
            processing.save(update_fields=["status", "current_action", "updated"])
            input_file.delete(save=False)
        else:
            processing.status = ProcessStatus.AWAITING_REVIEW
            processing.current_action = ""
            processing.error_message = ""
            processing.error_details = {}
            processing.error_traceback = ""
            processing.save(
                update_fields=[
                    "status",
                    "current_action",
                    "error_message",
                    "error_details",
                    "error_traceback",
                    "updated",
                ]
            )

    messages.success(
        request,
        _("Cleanup concluded: %(artifacts)s artifact(s) and %(structures)s structural version(s) removed.")
        % {"artifacts": deleted, "structures": deleted_structures},
    )
    return redirect("wagtailsnippets_manuscripts_processing:inspect", pk=pk)


@staff_member_required
@require_POST
def article_cleanup_artifacts(request, pk):
    article = get_object_or_404(Article, pk=pk)
    if not _confirmed_cleanup(request):
        messages.error(request, _('Enter "LIMPAR" to confirm cleanup.'))
        return redirect("wagtailsnippets_manuscripts_article:inspect", pk=pk)

    with transaction.atomic():
        deleted_artifacts = _delete_artifacts(article.artifacts.all())
        deleted_structures = article.structure_versions.count()
        article.structure_versions.all().delete()
        article.events.all().delete()
        article.status = ProcessStatus.PENDING
        article.save(update_fields=["status", "updated"])

    messages.success(
        request,
        _("Cleanup concluded: %(artifacts)s artifact(s) and %(structures)s structural version(s) removed.")
        % {"artifacts": deleted_artifacts, "structures": deleted_structures},
    )
    return redirect("wagtailsnippets_manuscripts_article:inspect", pk=pk)


@staff_member_required
def artifact_download(request, pk):
    artifact = get_object_or_404(ArticleArtifact, pk=pk)
    return FileResponse(
        artifact.file.open("rb"),
        as_attachment=True,
        filename=artifact.file.name.rsplit("/", 1)[-1],
    )


@staff_member_required
def artifact_preview(request, pk):
    """Serve o artefato inline no browser (sem download). Ideal para preview de HTML."""
    artifact = get_object_or_404(ArticleArtifact, pk=pk)
    filename = artifact.file.name.rsplit("/", 1)[-1]
    content_type, _ = mimetypes.guess_type(filename)
    content_type = content_type or "application/octet-stream"

    return FileResponse(
        artifact.file.open("rb"),
        as_attachment=False,
        content_type=content_type,
    )


@staff_member_required
def article_validation_view(request, pk):
    """Renderiza o relatório de validação (JSON) como tabela no admin."""
    article = get_object_or_404(Article, pk=pk)
    report_artifact = article.current_artifact(ArtifactType.VALIDATION_REPORT)
    exceptions_artifact = article.current_artifact(ArtifactType.VALIDATION_EXCEPTIONS)
    xml_artifact = article.current_artifact(ArtifactType.XML)

    rows = []
    exceptions = []

    if report_artifact:
        try:
            content = report_artifact.file.open("r").read()
            if content.strip().startswith("[") or content.strip().startswith("{"):
                try:
                    rows = json.loads(content)
                    if not isinstance(rows, list):
                        rows = [rows]
                except json.JSONDecodeError:
                    rows = [json.loads(line) for line in content.splitlines() if line.strip()]
            else:
                f = io.StringIO(content)
                reader = csv.DictReader(f)
                rows = []
                for r in reader:
                    rows.append({
                        "group": r.get("context", "—"),
                        "title": "—",
                        "attribute": "—",
                        "validation_type": "—",
                        "response": r.get("response", "—"),
                        "expected_value": "—",
                        "got_value": r.get("detail", "—"),
                        "advice": r.get("advice", ""),
                    })
        except Exception:
            rows = []

    if exceptions_artifact:
        try:
            content = exceptions_artifact.file.open("r").read()
            try:
                exceptions = json.loads(content)
                if not isinstance(exceptions, list):
                    exceptions = [exceptions]
            except json.JSONDecodeError:
                exceptions = [json.loads(line) for line in content.splitlines() if line.strip()]
        except Exception:
            exceptions = []

    # Validação de schema DTD/SPS via packtools.XMLValidator
    schema_valid = None
    schema_errors = []
    annotated_xml = None

    if xml_artifact:
        try:
            validator = packtools.XMLValidator.parse(xml_artifact.file.path)
            schema_valid, _errors = validator.validate_all()
            schema_errors = [
                {"message": e.message, "line": getattr(e, "line", None)}
                for e in _errors
            ]
            err_tree = validator.annotate_errors()
            annotated_xml = etree.tostring(
                err_tree,
                pretty_print=True,
                encoding="unicode",
                xml_declaration=False,
            )
        except Exception as exc:
            schema_valid = None
            annotated_xml = None
            schema_errors = [{"message": str(exc), "line": None}]

    return render(
        request,
        "manuscripts/article_validation.html",
        {
            "article": article,
            "rows": rows,
            "exceptions": exceptions,
            "report_artifact": report_artifact,
            "exceptions_artifact": exceptions_artifact,
            "xml_artifact": xml_artifact,
            "schema_valid": schema_valid,
            "schema_errors": schema_errors,
            "annotated_xml": annotated_xml,
        },
    )



@staff_member_required
def article_structure_edit(request, pk):
    article = get_object_or_404(Article, pk=pk)
    
    version_num = request.GET.get("version")
    if version_num:
        structure = get_object_or_404(ArticleStructureVersion, article=article, version=version_num)
    else:
        structure = article.current_structure

    if not structure:
        messages.error(request, _("The article does not yet have an editable structure."))
        return redirect("wagtailsnippets_manuscripts_article:inspect", pk=pk)

    edit_handler = ObjectList(ArticleStructureVersion.panels).bind_to_model(ArticleStructureVersion)
    form_class = edit_handler.get_form_class()

    if request.method == "POST":
        form = form_class(request.POST, request.FILES, instance=structure)
        if form.is_valid():
            _save_corrected_structure(
                article,
                structure,
                form.cleaned_data["front"],
                form.cleaned_data["body"],
                form.cleaned_data["back"],
            )
            messages.success(request, _("New structural version saved and XML regenerated."))
            return redirect("wagtailsnippets_manuscripts_article:inspect", pk=pk)
    else:
        form = form_class(instance=structure)

    bound_edit_handler = edit_handler.get_bound_panel(
        instance=structure, form=form, request=request
    )

    xml_artifact = article.current_artifact(ArtifactType.XML)

    versions = article.structure_versions.order_by("-version")
    current_structure = article.current_structure

    return render(
        request,
        "manuscripts/article_structure_edit.html",
        {
            "article": article,
            "structure": structure,
            "form": form,
            "edit_handler": bound_edit_handler,
            "xml_artifact": xml_artifact,
            "versions": versions,
            "current_structure": current_structure,
            "is_historical_version": bool(current_structure and structure.pk != current_structure.pk),
        },
    )


@staff_member_required
@require_POST
def article_structure_revert(request, pk, version):
    article = get_object_or_404(Article, pk=pk)
    target = get_object_or_404(ArticleStructureVersion, article=article, version=version)
    
    new_structure = _save_corrected_structure(
        article,
        target,
        target.front,
        target.body,
        target.back,
    )
    
    messages.success(
        request,
        _("Structure reverted to version %(version)s. New version %(new_version)s created.") % {
            "version": version,
            "new_version": new_structure.version,
        }
    )
    return redirect("manuscripts:article_structure_edit", pk=pk)


@staff_member_required
def article_references_edit(request, pk):
    article = get_object_or_404(Article, pk=pk)
    structure = article.current_structure
    if not structure:
        messages.error(request, _("The article does not yet have an editable structure."))
        return redirect("wagtailsnippets_manuscripts_article:inspect", pk=pk)

    references = structure.references.select_related(
        "reference", "selected_element"
    ).prefetch_related("reference__element_citation")
    citations = structure.citations.prefetch_related("references")

    return render(
        request,
        "manuscripts/article_references_edit.html",
        {
            "article": article,
            "structure": structure,
            "references": references,
            "citations": citations,
        },
    )


@staff_member_required
@require_POST
def citation_update(request, pk):
    citation = get_object_or_404(CitationOccurrence, pk=pk)
    references = citation.structure.references.filter(pk__in=request.POST.getlist("references"))
    structure = citation.structure
    body_raw = to_dict_list(structure.body)
    body = copy.deepcopy(body_raw)
    block_index = citation.location.get("block")
    if block_index is not None and block_index < len(body):
        paragraph = body[block_index].get("value", {}).get("paragraph", "")
        rid = " ".join(references.values_list("ref_id", flat=True))
        replacement = (
            f'<xref ref-type="bibr" rid="{rid}">{citation.text}</xref>'
            if rid
            else citation.text
        )
        paragraph = re.sub(
            rf'<xref[^>]*>{re.escape(citation.text)}</xref>',
            replacement,
            paragraph,
            count=1,
        )
        body[block_index]["value"]["paragraph"] = paragraph
    front_raw = to_dict_list(structure.front)
    back_raw = to_dict_list(structure.back)
    _save_corrected_structure(
        structure.article, structure, copy.deepcopy(front_raw), body, copy.deepcopy(back_raw)
    )
    messages.success(request, _("Link updated in a new structural version."))
    return redirect("manuscripts:article_references_edit", pk=structure.article_id)


@staff_member_required
@require_POST
def article_reference_select(request, pk):
    article_reference = get_object_or_404(ArticleReference, pk=pk)
    selected_element = request.POST.get("selected_element")
    candidate = None
    if selected_element:
        candidate = article_reference.reference.element_citation.filter(
            pk=selected_element
        ).first()
    structure = article_reference.structure
    back_raw = to_dict_list(structure.back)
    back = copy.deepcopy(back_raw)
    if candidate:
        for block in back:
            value = block.get("value", {})
            if value.get("refid") == article_reference.ref_id:
                value.update(candidate.marked)
                value["refid"] = article_reference.ref_id
                value["label"] = "<p>"
                value["paragraph"] = article_reference.mixed_citation
                break
    front_raw = to_dict_list(structure.front)
    body_raw = to_dict_list(structure.body)
    new_structure = _save_corrected_structure(
        structure.article, structure, copy.deepcopy(front_raw), copy.deepcopy(body_raw), back
    )
    new_reference = new_structure.references.get(ref_id=article_reference.ref_id)
    new_reference.selected_element = candidate
    new_reference.save(update_fields=["selected_element", "updated"])
    messages.success(request, _("Interpretation updated in a new structural version."))
    return redirect(
        "manuscripts:article_references_edit",
        pk=article_reference.structure.article_id,
    )


@staff_member_required
@require_POST
def article_reprocess(request, pk):
    article = get_object_or_404(Article, pk=pk)
    processing = article.processings.order_by("-created").first()
    if not processing:
        messages.error(request, _("This article has no associated processings."))
        return redirect("wagtailsnippets_manuscripts_article:inspect", pk=pk)

    action = request.POST.get("action")
    if action not in ProcessingAction.values:
        action = None

    processing.retry_count += 1
    processing.save(update_fields=["retry_count", "updated"])
    process_input.delay(processing.pk, start_action=action)
    messages.success(request, _("Reprocessing started."))
    return redirect("wagtailsnippets_manuscripts_article:inspect", pk=pk)
