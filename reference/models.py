import hashlib

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.forms import WagtailAdminModelForm
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.models import Orderable
from wagtail_json_widget.widgets import JSONEditorWidget

from reference.utils.references import stz_norm


class ReferenceMetadataModel(models.Model):
    created = models.DateTimeField(verbose_name=_("Creation date"), auto_now_add=True)
    updated = models.DateTimeField(verbose_name=_("Last update date"), auto_now=True)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Creator"),
        related_name="%(class)s_creator",
        editable=False,
        on_delete=models.SET_NULL,
        null=True,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Updater"),
        related_name="%(class)s_last_mod_user",
        editable=False,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        abstract = True


class ReferenceStatus(models.IntegerChoices):
    NO_REFERENCE = 0, _("No reference")
    CREATING = 1, _("Creating reference")
    READY = 2, _("Reference ready")


class Reference(ReferenceMetadataModel, ClusterableModel):
    mixed_citation = models.TextField(_("Mixed Citation"), null=False, blank=True)
    normalized_citation = models.TextField(
        _("Normalized citation"), blank=True, db_index=True
    )
    checksum = models.CharField(_("SHA256"), max_length=64, blank=True, unique=True)

    status = models.IntegerField(
        _("Reference status"),
        choices=ReferenceStatus.choices,
        blank=True,
        default=ReferenceStatus.NO_REFERENCE,
    )

    panels = [
        FieldPanel("mixed_citation"),
        InlinePanel("element_citation", label=_("Cited Elements")),
    ]

    base_form_class = WagtailAdminModelForm

    def __str__(self):
        return self.mixed_citation

    def save(self, *args, **kwargs):
        self.normalized_citation = stz_norm(self.mixed_citation)
        self.checksum = hashlib.sha256(
            self.normalized_citation.encode("utf-8")
        ).hexdigest()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _("Reference")
        verbose_name_plural = _("References")


class ElementCitation(Orderable):
    reference = ParentalKey(
        Reference,
        on_delete=models.SET_NULL,
        related_name="element_citation",
        null=True,
    )
    marked = models.JSONField(_("Marked"), default=dict, blank=True)
    marked_xml = models.TextField(_("Marked XML"), blank=True)

    score = models.IntegerField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(10),
        ],
        help_text=_("Rating from 1 to 10"),
    )

    panels = [
        FieldPanel(
            "marked",
            widget=JSONEditorWidget(
                options={
                    "mode": "code",
                    "modes": ["code", "tree"],
                    "search": True,
                }
            ),
        ),
        FieldPanel("marked_xml"),
        FieldPanel("score"),
    ]
