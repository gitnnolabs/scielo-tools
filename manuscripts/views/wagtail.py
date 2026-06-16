from pathlib import PurePosixPath

from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from wagtail.snippets.views.snippets import CreateView, InspectView

from manuscripts.choices import ArtifactType, ProcessingAction
from manuscripts.forms import (
    DOCXUploadForm,
    ProcessingUploadForm,
    SPSPackageUploadForm,
    XMLUploadForm,
)
from manuscripts.utils.inspection import inspect_processing


class ProcessingCreateView(CreateView):
    page_title = _("Upload file")
    submit_button_label = _("Upload and review")

    def get_form_class(self):
        return ProcessingUploadForm

    def save_instance(self):
        self.form.instance.creator = self.request.user
        processing = super().save_instance()
        inspect_processing(processing)
        return processing

    def get_success_url(self):
        return reverse("manuscripts:processing_review", args=[self.object.pk])


class XMLImportCreateView(ProcessingCreateView):
    page_title = _("XML")

    def get_form_class(self):
        return XMLUploadForm


class ArticleInputCreateView(ProcessingCreateView):
    page_title = _("DOCX")

    def get_form_class(self):
        return DOCXUploadForm


class SPSPackageImportCreateView(ProcessingCreateView):
    page_title = _("SPS Package")

    def get_form_class(self):
        return SPSPackageUploadForm


class OwnedCreateView(CreateView):
    def save_instance(self):
        self.form.instance.creator = self.request.user
        return super().save_instance()


class ProcessingInspectView(InspectView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["events"] = self.object.events.select_related("article").all()
        artifacts = self.object.artifacts.select_related("article").all()
        context["artifacts"] = artifacts
        context["artifact_rows"] = [
            {
                "artifact": artifact,
                "filename": PurePosixPath(artifact.file.name).name,
            }
            for artifact in artifacts
        ]
        context["articles"] = self.object.articles.all()
        context["action_choices"] = ProcessingAction.choices
        return context


class ArticleInspectView(InspectView):
    artifact_order = {
        ArtifactType.XML: 10,
        ArtifactType.HTML: 20,
        ArtifactType.PDF: 30,
        ArtifactType.SPS_PACKAGE: 40,
        ArtifactType.VALIDATION_REPORT: 50,
        ArtifactType.VALIDATION_EXCEPTIONS: 60,
        ArtifactType.MARKED_DOCUMENT: 70,
        ArtifactType.INTERMEDIATE_DOCUMENT: 80,
        ArtifactType.INPUT: 90,
        ArtifactType.SOURCE_DOCUMENT: 100,
        ArtifactType.ASSET: 110,
    }

    def get_artifact_rows(self, artifacts):
        current_xml = self.object.current_artifact(ArtifactType.XML)
        current_structure = current_xml.structure if current_xml else None
        rows = []
        for artifact in artifacts:
            structure = artifact.structure
            if not structure and artifact.is_current and artifact.artifact_type in {
                ArtifactType.HTML,
                ArtifactType.PDF,
                ArtifactType.SPS_PACKAGE,
                ArtifactType.VALIDATION_REPORT,
                ArtifactType.VALIDATION_EXCEPTIONS,
                ArtifactType.INTERMEDIATE_DOCUMENT,
            }:
                structure = current_structure
            rows.append(
                {
                    "artifact": artifact,
                    "filename": PurePosixPath(artifact.file.name).name,
                    "structure": structure,
                    "order": self.artifact_order.get(artifact.artifact_type, 999),
                }
            )
        return rows

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        processings = list(self.object.processings.all())
        events = (
            self.object.events.filter(details__has_key="frontmatter_ai")
            .select_related("processing")
            .order_by("processing_id", "-created")
        )
        latest_ai_by_processing = {}
        for event in events:
            latest_ai_by_processing.setdefault(event.processing_id, event.details.get("frontmatter_ai"))
        context["processings"] = processings
        context["processing_rows"] = [
            {"processing": processing, "frontmatter_ai": latest_ai_by_processing.get(processing.pk)}
            for processing in processings
        ]
        artifacts = list(self.object.artifacts.select_related("processing", "structure").order_by("-created"))
        artifact_rows = self.get_artifact_rows(artifacts)
        context["artifacts"] = artifacts
        context["current_artifact_rows"] = sorted(
            [row for row in artifact_rows if row["artifact"].is_current],
            key=lambda row: (row["order"], row["filename"]),
        )
        context["historical_artifact_rows"] = [
            row for row in artifact_rows if not row["artifact"].is_current
        ]
        context["structure"] = self.object.current_structure
        if context["structure"]:
            context["references"] = context["structure"].references.select_related(
                "reference", "selected_element"
            )
            context["citations"] = context["structure"].citations.prefetch_related("references")
        context["action_choices"] = ProcessingAction.choices
        context["latest_processing"] = self.object.processings.order_by("-created").first()
        context["current_xml_artifact"] = self.object.current_artifact(ArtifactType.XML)
        context["current_html_artifact"] = self.object.current_artifact(ArtifactType.HTML)
        context["current_pdf_artifact"] = self.object.current_artifact(ArtifactType.PDF)
        context["current_sps_package_artifact"] = self.object.current_artifact(ArtifactType.SPS_PACKAGE)
        context["current_marked_document_artifact"] = self.object.current_artifact(ArtifactType.MARKED_DOCUMENT)
        context["current_validation_report_artifact"] = self.object.current_artifact(ArtifactType.VALIDATION_REPORT)
        return context
