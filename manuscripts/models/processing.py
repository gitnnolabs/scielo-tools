from django.db import models
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel, MultiFieldPanel

from core.forms import CoreAdminModelForm
from core.models import CommonControlField

from manuscripts.choices import EventStatus, InputType, ProcessingAction, ProcessStatus


class Processing(CommonControlField):
    title = models.CharField(_("Identification"), max_length=255, blank=True)
    input_file = models.FileField(_("File to be uploaded"), upload_to="processings/input/%Y/%m/%d/")
    input_checksum = models.CharField(_("SHA256"), max_length=64, blank=True, db_index=True)
    detected_type = models.CharField(
        _("Detected type"), max_length=32, choices=InputType.choices, default=InputType.UNKNOWN
    )
    confirmed_type = models.CharField(
        _("Confirmed type"), max_length=32, choices=InputType.choices, default=InputType.UNKNOWN
    )
    inspection = models.JSONField(_("Detected content"), default=dict, blank=True)
    requested_actions = models.JSONField(_("Requested actions"), default=list, blank=True)
    status = models.CharField(
        _("Status"), max_length=20, choices=ProcessStatus.choices, default=ProcessStatus.AWAITING_REVIEW
    )
    current_action = models.CharField(
        _("Current action"), max_length=32, choices=ProcessingAction.choices, blank=True
    )
    articles = models.ManyToManyField("Article", related_name="processings", blank=True)
    error_message = models.TextField(_("Last error"), blank=True)
    error_details = models.JSONField(_("Error details"), default=dict, blank=True)
    error_traceback = models.TextField(_("Traceback"), blank=True)
    retry_count = models.PositiveIntegerField(_("Attempts"), default=0)
    processing_started_at = models.DateTimeField(_("Started at"), null=True, blank=True)
    completed_at = models.DateTimeField(_("Completed at"), null=True, blank=True)
    panels = [
        MultiFieldPanel([FieldPanel("title"), FieldPanel("input_file")], heading=_("Input")),
        MultiFieldPanel(
            [FieldPanel("detected_type", read_only=True), FieldPanel("confirmed_type"), FieldPanel("requested_actions")],
            heading=_("Review"),
        ),
        MultiFieldPanel(
            [FieldPanel("status", read_only=True), FieldPanel("current_action", read_only=True), FieldPanel("error_message", read_only=True)],
            heading=_("Execution"),
        ),
    ]
    base_form_class = CoreAdminModelForm

    @property
    def article_count(self):
        return self.articles.count()

    def __str__(self):
        return self.title or self.input_file.name.rsplit("/", 1)[-1]

    class Meta:
        verbose_name = _("Processing")
        verbose_name_plural = _("Processings")
        ordering = ["-created"]


class ProcessingEvent(CommonControlField):
    processing = models.ForeignKey(Processing, on_delete=models.CASCADE, related_name="events")
    article = models.ForeignKey(
        "Article", on_delete=models.CASCADE, related_name="events", null=True, blank=True
    )
    action = models.CharField(_("Action"), max_length=32, choices=ProcessingAction.choices, blank=True)
    status = models.CharField(_("Status"), max_length=20, choices=EventStatus.choices, default=EventStatus.PENDING)
    message = models.TextField(_("Message"), blank=True)
    details = models.JSONField(_("Details"), default=dict, blank=True)
    task_id = models.CharField(_("Task ID"), max_length=255, blank=True)
    started_at = models.DateTimeField(_("Started at"), null=True, blank=True)
    completed_at = models.DateTimeField(_("Completed at"), null=True, blank=True)

    def __str__(self):
        return f"{self.get_action_display() or 'Input'} - {self.get_status_display()}"

    class Meta:
        verbose_name = _("Processing event")
        verbose_name_plural = _("Processing trail")
        ordering = ["processing", "created"]
        indexes = [models.Index(fields=["processing", "article", "action", "status"])]


class ArticleInputManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(
            models.Q(confirmed_type__in=[InputType.DOCUMENT, InputType.SOURCE_PACKAGE]) |
            (models.Q(confirmed_type=InputType.UNKNOWN) & models.Q(detected_type__in=[InputType.DOCUMENT, InputType.SOURCE_PACKAGE]))
        )


class XMLImportManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(
            models.Q(confirmed_type=InputType.XML) |
            (models.Q(confirmed_type=InputType.UNKNOWN) & models.Q(detected_type=InputType.XML))
        )


class SPSPackageImportManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(
            models.Q(confirmed_type__in=[InputType.SPS_PACKAGE, InputType.AMBIGUOUS_ZIP]) |
            (models.Q(confirmed_type=InputType.UNKNOWN) & models.Q(detected_type__in=[InputType.SPS_PACKAGE, InputType.AMBIGUOUS_ZIP]))
        )


class ArticleInput(Processing):
    objects = ArticleInputManager()

    class Meta:
        proxy = True
        verbose_name = _("DOCX")
        verbose_name_plural = _("DOCX")


class XMLImport(Processing):
    objects = XMLImportManager()

    class Meta:
        proxy = True
        verbose_name = _("XML")
        verbose_name_plural = _("XML")


class SPSPackageImport(Processing):
    objects = SPSPackageImportManager()

    class Meta:
        proxy = True
        verbose_name = _("SPS Package")
        verbose_name_plural = _("SPS Packages")
