from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from wagtail.admin.forms import WagtailAdminModelForm

from reference.exceptions import DocxReferencesError
from reference.models import Reference
from reference.utils.references import references_from_docx_upload


class ReferenceCreateAdminForm(WagtailAdminModelForm):
    docx_file = forms.FileField(
        label=_("DOCX file"),
        required=False,
        help_text=_(
            "Optional. If provided, references are extracted from the file "
            "(takes precedence over the text field)."
        ),
    )

    class Meta:
        model = Reference
        fields = ("mixed_citation",)

    def clean_docx_file(self):
        docx_file = self.cleaned_data.get("docx_file")
        if not docx_file:
            return docx_file
        name = (getattr(docx_file, "name", "") or "").lower()
        if not name.endswith(".docx"):
            raise ValidationError(_("Only .docx files are accepted."))
        if getattr(docx_file, "size", None) == 0:
            raise ValidationError(_("Empty file."))
        return docx_file

    def clean(self):
        cleaned = super().clean()
        docx_file = cleaned.get("docx_file")
        text = (cleaned.get("mixed_citation") or "").strip()
        if docx_file:
            try:
                cleaned["mixed_citation"] = references_from_docx_upload(docx_file)
            except DocxReferencesError as exc:
                raise ValidationError(str(exc)) from exc
        elif not text:
            raise ValidationError(_("Provide reference text or a .docx file."))
        return cleaned
