from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel


class SPSPackageValidationStatus(models.TextChoices):
    PENDING = "pending", _("Pending")
    RUNNING = "running", _("Running")
    DONE = "done", _("Done")
    ERROR = "error", _("Error")


class SPSPackageValidation(models.Model):
    package_document = models.OneToOneField(
        "wagtaildocs.Document",
        on_delete=models.CASCADE,
        related_name="sps_validation",
        verbose_name=_("SPS package document"),
    )
    validation_document = models.ForeignKey(
        "wagtaildocs.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("Validation file"),
    )
    exceptions_document = models.ForeignKey(
        "wagtaildocs.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("Exceptions file"),
    )
    zip_size_bytes = models.PositiveBigIntegerField(
        verbose_name=_("ZIP size (bytes)"),
        default=0,
    )
    validated_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("Validated at"),
    )
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sps_package_validations",
        verbose_name=_("Validated by"),
    )
    status = models.CharField(
        max_length=16,
        choices=SPSPackageValidationStatus.choices,
        default=SPSPackageValidationStatus.PENDING,
        verbose_name=_("Status"),
    )
    error_message = models.TextField(
        blank=True,
        verbose_name=_("Error message"),
    )

    panels = [
        FieldPanel("package_document"),
        FieldPanel("status"),
        FieldPanel("zip_size_bytes"),
        FieldPanel("validated_by"),
        FieldPanel("validated_at"),
        FieldPanel("validation_document"),
        FieldPanel("exceptions_document"),
        FieldPanel("error_message"),
    ]

    def __str__(self):
        return self.package_document.title

    class Meta:
        verbose_name = _("SPS package validation")
        verbose_name_plural = _("SPS package validations")
