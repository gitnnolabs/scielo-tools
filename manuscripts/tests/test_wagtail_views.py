from unittest.mock import MagicMock, patch

import pytest
from django.test import RequestFactory
from django.urls import reverse

from manuscripts.choices import ArtifactType, InputType
from manuscripts.forms import (
    DOCXUploadForm,
    ProcessingUploadForm,
    SPSPackageUploadForm,
    XMLUploadForm,
)
from manuscripts.models.processing import ProcessingEvent
from manuscripts.views.wagtail import (
    ArticleInputCreateView,
    ArticleInspectView,
    OwnedCreateView,
    ProcessingCreateView,
    ProcessingInspectView,
    SPSPackageImportCreateView,
    XMLImportCreateView,
)


@pytest.fixture
def request_factory():
    return RequestFactory()


@pytest.mark.django_db
def test_processing_create_view_save_instance_calls_inspect_processing(
    request_factory, staff_user, monkeypatch
):
    inspected = []
    monkeypatch.setattr(
        "manuscripts.views.wagtail.inspect_processing",
        lambda processing: inspected.append(processing),
    )

    processing = MagicMock()
    view = ProcessingCreateView()
    view.request = request_factory.get("/")
    view.request.user = staff_user
    view.form = MagicMock()
    view.form.instance = MagicMock()

    with patch.object(ProcessingCreateView.__bases__[0], "save_instance", return_value=processing):
        result = view.save_instance()

    assert result is processing
    assert view.form.instance.creator is staff_user
    assert inspected == [processing]


@pytest.mark.parametrize(
    "view_class,expected_form",
    [
        (ProcessingCreateView, ProcessingUploadForm),
        (XMLImportCreateView, XMLUploadForm),
        (ArticleInputCreateView, DOCXUploadForm),
        (SPSPackageImportCreateView, SPSPackageUploadForm),
    ],
)
def test_processing_create_view_subclasses_form_class(view_class, expected_form):
    assert view_class().get_form_class() is expected_form


@pytest.mark.django_db
def test_owned_create_view_sets_creator(request_factory, staff_user):
    view = OwnedCreateView()
    view.request = request_factory.get("/")
    view.request.user = staff_user
    view.form = MagicMock()
    view.form.instance = MagicMock()
    saved = MagicMock()

    with patch.object(OwnedCreateView.__bases__[0], "save_instance", return_value=saved):
        result = view.save_instance()

    assert result is saved
    assert view.form.instance.creator is staff_user


@pytest.mark.django_db
def test_processing_create_view_success_url(processing):
    view = ProcessingCreateView()
    view.object = processing
    assert view.get_success_url() == reverse("manuscripts:processing_review", args=[processing.pk])


@pytest.mark.django_db
def test_processing_inspect_view_get_context_data(processing, article, user):
    from manuscripts.artifacts import save_artifact

    processing.articles.add(article)
    ProcessingEvent.objects.create(
        processing=processing,
        article=article,
        creator=user,
        message="Trail event",
    )
    artifact = save_artifact(
        processing,
        ArtifactType.XML,
        "nested/path/article.xml",
        b"<article />",
        article=article,
    )

    view = ProcessingInspectView()
    view.object = processing
    context = view.get_context_data()

    assert context["events"].count() == 1
    xml_row = next(row for row in context["artifact_rows"] if row["artifact"] == artifact)
    assert xml_row["filename"].startswith("article")
    assert xml_row["filename"].endswith(".xml")
    assert article in context["articles"]
    assert context["action_choices"]


@pytest.mark.django_db
def test_article_inspect_view_get_artifact_rows_uses_current_xml_structure(
    processing, article, user
):
    from manuscripts.artifacts import save_artifact
    from manuscripts.structure import create_structure_version

    structure = create_structure_version(
        article,
        processing,
        InputType.XML,
        [],
        [],
        [],
    )
    xml_artifact = save_artifact(
        processing,
        ArtifactType.XML,
        "article.xml",
        b"<article />",
        article=article,
        structure=structure,
    )
    html_artifact = save_artifact(
        processing,
        ArtifactType.HTML,
        "article.html",
        b"<html />",
        article=article,
    )

    view = ArticleInspectView()
    view.object = article
    rows = view.get_artifact_rows([xml_artifact, html_artifact])

    xml_row = next(row for row in rows if row["artifact"].artifact_type == ArtifactType.XML)
    html_row = next(row for row in rows if row["artifact"].artifact_type == ArtifactType.HTML)
    assert xml_row["structure"] is structure
    assert html_row["structure"] == structure
    assert html_row["order"] == 20


@pytest.mark.django_db
def test_article_inspect_view_get_context_data(processing, article, user):
    from manuscripts.artifacts import save_artifact
    from manuscripts.models.processing import ProcessingEvent
    from manuscripts.structure import create_structure_version

    processing.articles.add(article)
    structure = create_structure_version(
        article,
        processing,
        InputType.XML,
        [],
        [{"type": "paragraph", "value": {"label": "<p>", "paragraph": "Body"}}],
        [{"type": "ref_paragraph", "value": {"label": "<p>", "paragraph": "Ref", "refid": "B1"}}],
    )
    stale_xml = save_artifact(
        processing,
        ArtifactType.XML,
        "old.xml",
        b"<old />",
        article=article,
        structure=structure,
    )
    current_xml = save_artifact(
        processing,
        ArtifactType.XML,
        "article.xml",
        b"<article />",
        article=article,
        structure=structure,
    )
    save_artifact(
        processing,
        ArtifactType.HTML,
        "article.html",
        b"<html />",
        article=article,
    )
    save_artifact(
        processing,
        ArtifactType.VALIDATION_REPORT,
        "report.json",
        b"[]",
        article=article,
    )
    ProcessingEvent.objects.create(
        processing=processing,
        article=article,
        creator=user,
        details={"frontmatter_ai": {"title": "AI title"}},
    )

    view = ArticleInspectView()
    view.object = article
    context = view.get_context_data()

    assert context["processings"] == [processing]
    assert context["processing_rows"][0]["frontmatter_ai"] == {"title": "AI title"}
    assert len(context["current_artifact_rows"]) >= 2
    assert any(row["artifact"].pk == stale_xml.pk for row in context["historical_artifact_rows"])
    assert context["structure"] == structure
    assert context["references"].count() == 1
    assert context["citations"].count() >= 0
    assert context["latest_processing"] == processing
    assert context["current_xml_artifact"].pk == current_xml.pk
    assert context["current_html_artifact"] is not None
    assert context["current_validation_report_artifact"] is not None
