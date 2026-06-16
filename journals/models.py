from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel
from wagtailautocomplete.edit_handlers import AutocompletePanel

from core.models import CommonControlField


class Journal(models.Model):
    title = models.TextField(_("Title"), unique=True)
    short_title = models.TextField(_("Short title"), blank=True)
    title_nlm = models.TextField(_("NLM title"), blank=True)
    acronym = models.CharField(_("Acronym"), max_length=50, blank=True)
    issn = models.CharField(_("SciELO ISSN"), max_length=32, blank=True)
    pissn = models.CharField(_("Print ISSN"), max_length=32, blank=True)
    eissn = models.CharField(_("Electronic ISSN"), max_length=32, blank=True)
    publisher_name = models.TextField(_("Publisher name"), blank=True)
    autocomplete_search_field = "title"

    def autocomplete_label(self):
        return str(self)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = _("Journal")
        verbose_name_plural = _("Journals")
        ordering = ["title"]


class Issue(CommonControlField, ClusterableModel):
    journal = models.ForeignKey(
        Journal, on_delete=models.CASCADE, related_name="issues", verbose_name=_("Journal")
    )
    number = models.CharField(_("Number"), max_length=20, blank=True)
    volume = models.CharField(_("Volume"), max_length=20, blank=True)
    season = models.CharField(_("Season"), max_length=20, blank=True)
    year = models.CharField(_("Year"), max_length=4, blank=True)
    month = models.CharField(_("Month"), max_length=20, blank=True)
    supplement = models.CharField(_("Supplement"), max_length=20, blank=True)
    panels = [
        AutocompletePanel("journal"),
        FieldPanel("number"),
        FieldPanel("volume"),
        FieldPanel("season"),
        FieldPanel("year"),
        FieldPanel("month"),
        FieldPanel("supplement"),
    ]
    autocomplete_search_field = "number"

    @classmethod
    def autocomplete_custom_queryset_filter(cls, search_query):
        return cls.objects.filter(
            Q(number__icontains=search_query)
            | Q(volume__icontains=search_query)
            | Q(year__icontains=search_query)
            | Q(journal__title__icontains=search_query)
        )

    def autocomplete_label(self):
        return str(self)

    @property
    def identifier(self):
        return "".join(
            f"{label}{value}"
            for label, value in zip(("v", "n", "s"), (self.volume, self.number, self.supplement))
            if value
        )

    def __str__(self):
        return f"{self.identifier} - {self.journal}"

    class Meta:
        verbose_name = _("Issue")
        verbose_name_plural = _("Issues")
        ordering = ["-year", "journal", "volume", "number"]
