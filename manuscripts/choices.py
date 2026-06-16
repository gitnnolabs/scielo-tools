from django.db import models
from django.utils.translation import gettext_lazy as _

front_labels = [
    ("<abstract>", "<abstract>"),
    ("<abstract-title>", "<abstract-title>"),
    ("<aff>", "<aff>"),
    ("<article-id>", "<article-id>"),
    ("<article-title>", "<article-title>"),
    ("<author-notes>", "<author-notes>"),
    ("<contrib>", "<contrib>"),
    ("<date-accepted>", "<date-accepted>"),
    ("<date-received>", "<date-received>"),
    ("<fig>", "<fig>"),
    ("<fig-attrib>", "<fig-attrib>"),
    ("<history>", "<history>"),
    ("<kwd-title>", "<kwd-title>"),
    ("<kwd-group>", "<kwd-group>"),
    ("<list>", "<list>"),
    ("<p>", "<p>"),
    ("<sec>", "<sec>"),
    ("<sub-sec>", "<sub-sec>"),
    ("<subject>", "<subject>"),
    ("<table>", "<table>"),
    ("<table-foot>", "<table-foot>"),
    ("<title>", "<title>"),
    ("<trans-abstract>", "<trans-abstract>"),
    ("<trans-title>", "<trans-title>"),
    ("<translate-front>", "<translate-front>"),
    ("<translate-body>", "<translate-body>"),
    ("<disp-formula>", "<disp-formula>"),
    ("<inline-formula>", "<inline-formula>"),
    ("<formula>", "<formula>"),
]

order_labels = {
    "<article-id>": {"pos": 1, "next": "<subject>"},
    "<subject>": {"pos": 2, "next": "<article-title>"},
    "<article-title>": {"pos": 3, "next": "<trans-title>", "lan": True},
    "<trans-title>": {"size": 14, "bold": True, "lan": True, "next": "<contrib>"},
    "<contrib>": {"reset": True, "size": 12, "next": "<aff>"},
    "<aff>": {
        "reset": True,
        "size": 12,
    },
    "<abstract>": {"size": 12, "bold": True, "lan": True, "next": "<p>"},
    "<p>": {"size": 12, "next": "<p>", "repeat": True},
    "<trans-abstract>": {"size": 12, "bold": True, "lan": True, "next": "<p>"},
    "<kwd-group>": {
        "size": 12,
        "regex": r"(?i)(palabra.*clave.*:|keyword.*:)",
    },
    "<history>": {
        "size": 12,
        "regex": r"\d{2}/\d{2}/\d{4}",
    },
    "<corresp>": {
        "size": 12,
        "regex": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    },
    "<sec>": {"size": 16, "bold": True, "next": None},
    "<sub-sec>": {"size": 12, "italic": True, "next": None},
    "<sub-sec-2>": {"size": 14, "bold": True, "next": None},
}

order_labels_body = {
    "<sec>": {
        "size": 16,
        "bold": True,
    },
    "<sub-sec>": {
        "size": 12,
        "italic": True,
    },
    "<p>": {
        "size": 12,
    },
}


class ProcessStatus(models.TextChoices):
    AWAITING_REVIEW = "awaiting_review", _("Awaiting review")
    PENDING = "pending", _("Pending")
    PROCESSING = "processing", _("Processing")
    COMPLETED = "completed", _("Completed")
    FAILED = "failed", _("Failed")
    PARTIAL = "partial", _("Partial")
    CANCELLED = "cancelled", _("Cancelled")


class InputType(models.TextChoices):
    UNKNOWN = "unknown", _("Unidentified")
    DOCUMENT = "document", _("Document")
    XML = "xml", _("XML SPS")
    SPS_PACKAGE = "sps_package", _("SPS Package")
    SOURCE_PACKAGE = "source_package", _("Source package")
    AMBIGUOUS_ZIP = "ambiguous_zip", _("Ambiguous ZIP package")


class ProcessingAction(models.TextChoices):
    CITATION_MARKUP = "citation_markup", _("Mark citations")
    XML_GENERATION = "xml_generation", _("Generate XML")
    XML_VALIDATION = "xml_validation", _("Validate XML")
    SPS_PACKAGE_VALIDATION = "sps_package_validation", _("Validate SPS package")
    SPS_PACKAGE_GENERATION = "sps_package_generation", _("Generate SPS package")
    HTML_GENERATION = "html_generation", _("Generate HTML")
    PDF_GENERATION = "pdf_generation", _("Generate PDF")


class ArtifactType(models.TextChoices):
    INPUT = "input", _("Uploaded file")
    SOURCE_DOCUMENT = "source_document", _("Original document")
    MARKED_DOCUMENT = "marked_document", _("Document with marked citations")
    STRUCTURE = "structure", _("XML structure")
    XML = "xml", _("XML SPS")
    ASSET = "asset", _("Asset")
    SPS_PACKAGE = "sps_package", _("SPS Package")
    VALIDATION_REPORT = "validation_report", _("Validation report")
    VALIDATION_EXCEPTIONS = "validation_exceptions", _("Validation exceptions")
    HTML = "html", _("HTML")
    PDF = "pdf", _("PDF")
    INTERMEDIATE_DOCUMENT = "intermediate_document", _("Intermediate document")


class EventStatus(models.TextChoices):
    PENDING = "pending", _("Pending")
    RUNNING = "running", _("Running")
    COMPLETED = "completed", _("Completed")
    FAILED = "failed", _("Failed")
    SKIPPED = "skipped", _("Skipped")
