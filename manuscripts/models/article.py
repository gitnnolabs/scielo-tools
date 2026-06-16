from django.db import models
from django.utils.translation import gettext_lazy as _
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import StreamField
from wagtailautocomplete.edit_handlers import AutocompletePanel

from core.choices import LANGUAGE
from core.forms import CoreAdminModelForm
from core.models import CommonControlField

from manuscripts.blocks import (
    AffParagraphBlock,
    AuthorParagraphBlock,
    CompoundParagraphBlock,
    ImageBlock,
    ParagraphBlock,
    ParagraphWithLanguageBlock,
    RefParagraphBlock,
    TableBlock,
)
from manuscripts.choices import (
    ArtifactType,
    InputType,
    ProcessStatus,
)


class Article(CommonControlField, ClusterableModel):
    title = models.TextField(_("Provisional title"), blank=True)
    doi = models.CharField(_("DOI"), max_length=255, blank=True, db_index=True)
    pid = models.CharField(_("PID"), max_length=255, blank=True, db_index=True)
    content_checksum = models.CharField(_("Content checksum"), max_length=64, blank=True, db_index=True)
    journal = models.ForeignKey(
        "journals.Journal", on_delete=models.SET_NULL, related_name="articles", null=True, blank=True
    )
    issue = models.ForeignKey(
        "journals.Issue", on_delete=models.SET_NULL, related_name="articles", null=True, blank=True
    )
    status = models.CharField(
        _("Status"), max_length=20, choices=ProcessStatus.choices, default=ProcessStatus.PENDING
    )
    language = models.CharField(_("Language"), max_length=10, choices=LANGUAGE, blank=True, default="en")
    license = models.URLField(_("License (URL)"), max_length=500, blank=True, null=True)
    fpage = models.CharField(_("First page"), max_length=32, blank=True)
    lpage = models.CharField(_("Last page"), max_length=32, blank=True)
    seq = models.CharField(_("Sequence"), max_length=32, blank=True)
    elocatid = models.CharField(_("Elocation ID"), max_length=255, blank=True)
    artdate = models.DateField(_("Publication date"), null=True, blank=True)
    ahpdate = models.DateField(_("AHP date"), null=True, blank=True)
    metadata = models.JSONField(_("Metadata"), default=dict, blank=True)

    panels = [
        MultiFieldPanel([FieldPanel("title"), FieldPanel("doi"), FieldPanel("pid")], heading=_("Article")),
        MultiFieldPanel([AutocompletePanel("journal"), AutocompletePanel("issue")], heading=_("Editorial link")),
        MultiFieldPanel([
            FieldPanel("language"),
            FieldPanel("license"),
            FieldPanel("fpage"),
            FieldPanel("lpage"),
            FieldPanel("seq"),
            FieldPanel("elocatid"),
            FieldPanel("artdate"),
            FieldPanel("ahpdate"),
        ], heading=_("Article metadata")),
        FieldPanel("status", read_only=True),
    ]
    base_form_class = CoreAdminModelForm

    def current_artifact(self, artifact_type):
        return self.artifacts.filter(artifact_type=artifact_type, is_current=True).first()

    @property
    def current_structure(self):
        return self.structure_versions.filter(is_current=True).first()

    def __str__(self):
        return self.title or self.doi or self.pid or f"Article {self.pk}"

    class Meta:
        verbose_name = _("Article")
        verbose_name_plural = _("Articles")
        ordering = ["-created"]


class ArticleStructureVersion(CommonControlField):
    article = models.ForeignKey(
        Article, on_delete=models.CASCADE, related_name="structure_versions"
    )
    processing = models.ForeignKey(
        "Processing",
        on_delete=models.SET_NULL,
        related_name="structure_versions",
        null=True,
        blank=True,
    )
    version = models.PositiveIntegerField(_("Version"), default=1)
    is_current = models.BooleanField(_("Current version"), default=True)
    source_kind = models.CharField(
        _("Origin"), max_length=32, choices=InputType.choices, default=InputType.DOCUMENT
    )
    front = StreamField(
        [
            ("paragraph_with_language", ParagraphWithLanguageBlock()),
            ("paragraph", ParagraphBlock()),
            ("author_paragraph", AuthorParagraphBlock()),
            ("aff_paragraph", AffParagraphBlock()),
        ],
        blank=True,
    )
    body = StreamField(
        [
            ("paragraph", ParagraphBlock()),
            ("paragraph_with_language", ParagraphWithLanguageBlock()),
            ("compound_paragraph", CompoundParagraphBlock()),
            ("image", ImageBlock()),
            ("table", TableBlock()),
        ],
        blank=True,
    )
    back = StreamField(
        [
            ("paragraph", ParagraphBlock()),
            ("ref_paragraph", RefParagraphBlock()),
        ],
        blank=True,
    )
    base_xml = models.TextField(_("Preserved base XML"), blank=True)
    roundtrip_warnings = models.JSONField(_("Round-trip warnings"), default=list, blank=True)
    xref_status = models.JSONField(_("Citation status"), default=dict, blank=True)
    panels = [
        MultiFieldPanel(
            [FieldPanel("version", read_only=True), FieldPanel("source_kind", read_only=True)],
            heading=_("Structural version"),
        ),
        FieldPanel("front"),
        FieldPanel("body"),
        FieldPanel("back"),
        FieldPanel("roundtrip_warnings", read_only=True),
        FieldPanel("xref_status", read_only=True),
    ]

    def __str__(self):
        return f"{self.article} - structure v{self.version}"

    class Meta:
        verbose_name = _("Article structural version")
        verbose_name_plural = _("Article structural versions")
        ordering = ["article", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["article", "version"], name="unique_article_structure_version"
            )
        ]


class ArticleReference(CommonControlField):
    structure = models.ForeignKey(
        ArticleStructureVersion, on_delete=models.CASCADE, related_name="references"
    )
    reference = models.ForeignKey(
        "references.Reference",
        on_delete=models.SET_NULL,
        related_name="article_references",
        null=True,
        blank=True,
    )
    selected_element = models.ForeignKey(
        "references.ElementCitation",
        on_delete=models.SET_NULL,
        related_name="article_references",
        null=True,
        blank=True,
    )
    position = models.PositiveIntegerField(_("Order"))
    ref_id = models.CharField(_("SPS ID"), max_length=32)
    mixed_citation = models.TextField(_("Original reference"))
    metadata = models.JSONField(_("Structured data"), default=dict, blank=True)

    def __str__(self):
        return f"{self.ref_id}: {self.mixed_citation[:80]}"

    class Meta:
        verbose_name = _("Article reference")
        verbose_name_plural = _("Article references")
        ordering = ["structure", "position"]
        constraints = [
            models.UniqueConstraint(fields=["structure", "ref_id"], name="unique_structure_ref_id"),
            models.UniqueConstraint(
                fields=["structure", "position"], name="unique_structure_ref_position"
            ),
        ]


class CitationOccurrence(CommonControlField):
    class Status(models.TextChoices):
        LINKED = "linked", _("Linked")
        ORPHAN = "orphan", _("Orphan")
        AMBIGUOUS = "ambiguous", _("Ambiguous")
        MANUAL = "manual", _("Manually corrected")

    structure = models.ForeignKey(
        ArticleStructureVersion, on_delete=models.CASCADE, related_name="citations"
    )
    text = models.TextField(_("In-text citation"))
    location = models.JSONField(_("Location"), default=dict, blank=True)
    status = models.CharField(_("Status"), max_length=16, choices=Status.choices)
    references = models.ManyToManyField(ArticleReference, related_name="citations", blank=True)

    def __str__(self):
        return self.text

    class Meta:
        verbose_name = _("Citation occurrence")
        verbose_name_plural = _("Citation occurrences")
        ordering = ["structure", "created"]


class ArticleArtifact(CommonControlField):
    processing = models.ForeignKey("Processing", on_delete=models.CASCADE, related_name="artifacts")
    article = models.ForeignKey(
        Article, on_delete=models.CASCADE, related_name="artifacts", null=True, blank=True
    )
    structure = models.ForeignKey(
        ArticleStructureVersion,
        on_delete=models.SET_NULL,
        related_name="artifacts",
        null=True,
        blank=True,
    )
    artifact_type = models.CharField(_("Type"), max_length=32, choices=ArtifactType.choices)
    file = models.FileField(_("File"), upload_to="processings/artifacts/%Y/%m/%d/")
    original_path = models.CharField(_("Original path"), max_length=1024, blank=True)
    source_url = models.URLField(_("Source URL"), max_length=2048, blank=True)
    version = models.PositiveIntegerField(_("Version"), default=1)
    is_current = models.BooleanField(_("Current version"), default=True)
    file_size_bytes = models.PositiveBigIntegerField(_("Size"), default=0)
    checksum = models.CharField(_("SHA256"), max_length=64, blank=True, db_index=True)
    metadata = models.JSONField(_("Metadata"), default=dict, blank=True)
    is_stale = models.BooleanField(_("Outdated"), default=False)

    def __str__(self):
        return f"{self.get_artifact_type_display()} v{self.version}"

    class Meta:
        verbose_name = _("Artifact")
        verbose_name_plural = _("Artifacts")
        ordering = ["processing", "article", "artifact_type", "-version"]
        indexes = [models.Index(fields=["processing", "article", "artifact_type", "is_current"])]
