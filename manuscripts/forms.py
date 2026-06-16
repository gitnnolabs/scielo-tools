import os
import zipfile

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from core.forms import CoreAdminModelForm

from .choices import InputType, ProcessingAction
from .models.article import ArticleStructureVersion
from .models.processing import Processing
from .utils.inspection import suggested_actions


class ProcessingUploadForm(CoreAdminModelForm):
    class Meta:
        model = Processing
        fields = ["title", "input_file"]

    def clean_input_file(self):
        uploaded = self.cleaned_data["input_file"]
        extension = os.path.splitext(uploaded.name)[1].lower()
        if extension not in {".docx", ".xml", ".zip"}:
            raise ValidationError(_("Upload a DOCX document, SPS XML, or ZIP package."))
        if uploaded.size == 0:
            raise ValidationError(_("The file is empty."))
        if uploaded.size > 250 * 1024 * 1024:
            raise ValidationError(_("The file cannot exceed 250 MB."))
        if extension == ".zip" and not zipfile.is_zipfile(uploaded):
            raise ValidationError(_("The ZIP file is invalid."))
        return uploaded


class XMLUploadForm(ProcessingUploadForm):
    def clean_input_file(self):
        uploaded = super().clean_input_file()
        if os.path.splitext(uploaded.name)[1].lower() != ".xml":
            raise ValidationError(_("Upload a SPS XML file."))
        return uploaded


class DOCXUploadForm(ProcessingUploadForm):
    def clean_input_file(self):
        uploaded = super().clean_input_file()
        if os.path.splitext(uploaded.name)[1].lower() != ".docx":
            raise ValidationError(_("Upload a DOCX file."))
        return uploaded


class SPSPackageUploadForm(ProcessingUploadForm):
    def clean_input_file(self):
        uploaded = super().clean_input_file()
        if os.path.splitext(uploaded.name)[1].lower() != ".zip":
            raise ValidationError(_("Upload a SPS ZIP package."))
        return uploaded


class ArticleStructureForm(CoreAdminModelForm):
    class Meta:
        model = ArticleStructureVersion
        fields = ["front", "body", "back"]


class ProcessingReviewForm(forms.ModelForm):
    requested_actions = forms.MultipleChoiceField(
        label=_("Actions to execute"),
        choices=ProcessingAction.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = Processing
        fields = ["requested_actions"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        applicable = set(suggested_actions(self.instance.detected_type))
        if self.instance.detected_type == InputType.SPS_PACKAGE:
            applicable.update({ProcessingAction.HTML_GENERATION, ProcessingAction.PDF_GENERATION})
        self.fields["requested_actions"].choices = [
            c for c in ProcessingAction.choices if c[0] in applicable
        ]

    def clean(self):
        cleaned = super().clean()
        actions = cleaned.get("requested_actions") or []
        allowed = set(suggested_actions(self.instance.detected_type))
        if self.instance.detected_type == InputType.SPS_PACKAGE:
            allowed.update({ProcessingAction.HTML_GENERATION, ProcessingAction.PDF_GENERATION})
        invalid = set(actions) - allowed
        if invalid:
            raise ValidationError(_("Some actions are incompatible with the input type."))
        return cleaned
