import io
import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from manuscripts.choices import InputType, ProcessingAction
from manuscripts.forms import (
    DOCXUploadForm,
    ProcessingReviewForm,
    ProcessingUploadForm,
    SPSPackageUploadForm,
    XMLUploadForm,
)
from manuscripts.models.processing import Processing


@pytest.mark.django_db
def test_processing_upload_form_accepts_xml_file():
    form = ProcessingUploadForm(
        data={"title": "XML upload"},
        files={"input_file": SimpleUploadedFile("article.xml", b"<article />", content_type="application/xml")},
    )

    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_processing_upload_form_rejects_unsupported_extension():
    form = ProcessingUploadForm(
        data={"title": "Bad upload"},
        files={"input_file": SimpleUploadedFile("article.txt", b"plain text", content_type="text/plain")},
    )

    assert not form.is_valid()
    assert "input_file" in form.errors


@pytest.mark.django_db
def test_processing_upload_form_rejects_empty_file():
    form = ProcessingUploadForm(
        data={"title": "Empty upload"},
        files={"input_file": SimpleUploadedFile("article.xml", b"", content_type="application/xml")},
    )

    assert not form.is_valid()
    assert "input_file" in form.errors


@pytest.mark.django_db
def test_processing_upload_form_clean_input_file_rejects_empty_upload():
    form = ProcessingUploadForm()
    uploaded = SimpleUploadedFile("article.xml", b"", content_type="application/xml")
    form.cleaned_data = {"input_file": uploaded}

    from django.core.exceptions import ValidationError

    with pytest.raises(ValidationError, match="empty"):
        form.clean_input_file()


@pytest.mark.django_db
def test_processing_review_form_accepts_applicable_actions(xml_processing):
    form = ProcessingReviewForm(
        data={"requested_actions": [ProcessingAction.XML_VALIDATION]},
        instance=xml_processing,
    )

    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_processing_review_form_rejects_incompatible_actions(user):
    processing = Processing.objects.create(
        title="doc",
        creator=user,
        detected_type=InputType.DOCUMENT,
        input_file="processings/input/doc.docx",
    )
    form = ProcessingReviewForm(
        data={"requested_actions": [ProcessingAction.SPS_PACKAGE_VALIDATION]},
        instance=processing,
    )

    assert not form.is_valid()
    assert "requested_actions" in form.errors


@pytest.mark.django_db
def test_processing_upload_form_rejects_oversized_file():
    form = ProcessingUploadForm(
        data={"title": "Huge upload"},
        files={
            "input_file": SimpleUploadedFile(
                "article.xml",
                b"x" * (250 * 1024 * 1024 + 1),
                content_type="application/xml",
            )
        },
    )

    assert not form.is_valid()
    assert "input_file" in form.errors


@pytest.mark.django_db
def test_processing_upload_form_rejects_invalid_zip():
    form = ProcessingUploadForm(
        data={"title": "Bad zip"},
        files={"input_file": SimpleUploadedFile("package.zip", b"not-a-zip", content_type="application/zip")},
    )

    assert not form.is_valid()
    assert "input_file" in form.errors


@pytest.mark.django_db
def test_xml_upload_form_rejects_non_xml_extension():
    form = XMLUploadForm(
        data={"title": "Wrong ext"},
        files={"input_file": SimpleUploadedFile("article.docx", b"docx", content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert not form.is_valid()
    assert "input_file" in form.errors


@pytest.mark.django_db
def test_docx_upload_form_rejects_non_docx_extension():
    form = DOCXUploadForm(
        data={"title": "Wrong ext"},
        files={"input_file": SimpleUploadedFile("article.xml", b"<article />", content_type="application/xml")},
    )

    assert not form.is_valid()
    assert "input_file" in form.errors


@pytest.mark.django_db
def test_sps_package_upload_form_rejects_non_zip_extension():
    form = SPSPackageUploadForm(
        data={"title": "Wrong ext"},
        files={"input_file": SimpleUploadedFile("article.xml", b"<article />", content_type="application/xml")},
    )

    assert not form.is_valid()
    assert "input_file" in form.errors


@pytest.mark.django_db
def test_processing_review_form_sps_package_includes_html_pdf_actions(user):
    processing = Processing.objects.create(
        title="sps",
        creator=user,
        detected_type=InputType.SPS_PACKAGE,
        input_file="processings/input/package.zip",
    )
    form = ProcessingReviewForm(instance=processing)

    action_values = {value for value, _label in form.fields["requested_actions"].choices}
    assert ProcessingAction.HTML_GENERATION in action_values
    assert ProcessingAction.PDF_GENERATION in action_values


@pytest.mark.django_db
def test_processing_review_form_clean_rejects_invalid_sps_actions(user, monkeypatch):
    processing = Processing.objects.create(
        title="sps",
        creator=user,
        detected_type=InputType.SPS_PACKAGE,
        input_file="processings/input/package.zip",
    )
    form = ProcessingReviewForm(instance=processing)
    form.cleaned_data = {"requested_actions": [ProcessingAction.CITATION_MARKUP]}
    monkeypatch.setattr("manuscripts.forms.suggested_actions", lambda _input_type: [])

    from django.core.exceptions import ValidationError

    with pytest.raises(ValidationError, match="incompatible"):
        form.clean()


@pytest.mark.django_db
def test_xml_upload_form_accepts_xml_file():
    form = XMLUploadForm(
        data={"title": "XML upload"},
        files={"input_file": SimpleUploadedFile("article.xml", b"<article />", content_type="application/xml")},
    )

    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_docx_upload_form_accepts_docx_file():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", "<w:document />")
    form = DOCXUploadForm(
        data={"title": "DOCX upload"},
        files={"input_file": SimpleUploadedFile("article.docx", buffer.getvalue(), content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_sps_package_upload_form_accepts_zip_file():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("article.xml", "<article />")
    form = SPSPackageUploadForm(
        data={"title": "ZIP upload"},
        files={"input_file": SimpleUploadedFile("package.zip", buffer.getvalue(), content_type="application/zip")},
    )

    assert form.is_valid(), form.errors
