from django import forms
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel

from core.forms import CoreAdminModelForm
from core.models import CommonControlField


class MaskedPasswordWidget(forms.PasswordInput):
    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, render_value=True)


class DownloadStatus(models.IntegerChoices):
    NO_MODEL = 1, _("No model")
    DOWNLOADING = 2, _("Downloading")
    DOWNLOADED = 3, _("Downloaded")
    ERROR = 4, _("Download error")



class HuggingFaceModel(CommonControlField):
    name_model = models.CharField(_("Model name"), max_length=255, help_text="e.g. bartowski/Llama-3.2-3B-Instruct-GGUF")
    name_file = models.CharField(_("Model file"), max_length=255, help_text="e.g. Llama-3.2-3B-Instruct-Q4_K_M.gguf")
    hf_token = models.CharField(_("HuggingFace token"), max_length=255, blank=True)
    download_status = models.IntegerField(
        _("Download status"),
        choices=DownloadStatus.choices,
        default=DownloadStatus.NO_MODEL,
        blank=True,
    )
    is_active = models.BooleanField(_("Active"), default=False)

    panels = [
        FieldPanel("name_model"),
        FieldPanel("name_file"),
        FieldPanel("hf_token", widget=MaskedPasswordWidget()),
        FieldPanel("download_status", widget=forms.Select(choices=DownloadStatus.choices, attrs={"disabled": True})),
        FieldPanel("is_active"),
    ]
    base_form_class = CoreAdminModelForm

    class Meta:
        verbose_name = _("HuggingFace model")
        verbose_name_plural = _("HuggingFace models")

    def __str__(self):
        return self.name_model or self.name_file or "HuggingFace"

    def clean(self):
        if not self.name_model:
            raise ValidationError({"name_model": _("Model name is required.")})
        if not self.name_file:
            raise ValidationError({"name_file": _("Model file is required.")})

    def save(self, *args, **kwargs):
        if self.is_active:
            HuggingFaceModel.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)



class OllamaModel(CommonControlField):
    url = models.URLField(_("Ollama URL"), help_text="e.g. http://host:11434")
    model = models.CharField(_("Model"), max_length=255, blank=True, help_text="Select after fetching")
    is_vision = models.BooleanField(
        _("Vision model"),
        default=False,
        help_text="Enable to use vision pipeline (page images). When disabled, text pipeline is used.",
    )

    class DocxExtractor(models.TextChoices):
        ZIPFILE = "zipfile", _("Zipfile (built-in)")
        DOCLING = "docling", _("Docling (OCR-capable, requires pytorch)")

    docx_extractor = models.CharField(
        _("DOCX text extractor"),
        max_length=16,
        choices=DocxExtractor.choices,
        default=DocxExtractor.ZIPFILE,
        help_text="Method to extract plain text from DOCX for LLM prompts.",
    )
    context_limit = models.PositiveIntegerField(
        _("Context tokens"),
        blank=True,
        null=True,
        help_text="Max input tokens for this model. Leave empty for auto-detect via API.",
    )
    is_active = models.BooleanField(_("Active"), default=False)

    panels = [
        FieldPanel("url"),
        FieldPanel("model", widget=forms.Select(attrs={"data-ai": "ollama-model-select"})),
        FieldPanel("is_vision"),
        FieldPanel("docx_extractor"),
        FieldPanel("context_limit"),
        FieldPanel("is_active"),
    ]
    base_form_class = CoreAdminModelForm

    class Meta:
        verbose_name = _("Ollama model")
        verbose_name_plural = _("Ollama models")

    def __str__(self):
        return f"{self.model or '?'} @ {self.url or '?'}" if self.model else "Ollama"

    def clean(self):
        if not self.url:
            raise ValidationError({"url": _("Ollama URL is required.")})
        if not self.model:
            raise ValidationError({"model": _("Please select a model.")})

    def save(self, *args, **kwargs):
        if self.is_active:
            OllamaModel.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)



class GeminiModel(CommonControlField):
    api_key = models.CharField(_("API Key"), max_length=255)
    is_active = models.BooleanField(_("Active"), default=False)

    panels = [
        FieldPanel("api_key", widget=MaskedPasswordWidget()),
        FieldPanel("is_active"),
    ]
    base_form_class = CoreAdminModelForm

    class Meta:
        verbose_name = _("Gemini model")
        verbose_name_plural = _("Gemini models")

    def __str__(self):
        return "Gemini"

    def clean(self):
        if not self.api_key:
            raise ValidationError({"api_key": _("API Key is required.")})

    def save(self, *args, **kwargs):
        if self.is_active:
            GeminiModel.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)
