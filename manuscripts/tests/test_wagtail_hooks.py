from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from django.urls import reverse

from manuscripts.choices import ArtifactType, InputType, ProcessStatus
from manuscripts.wagtail_hooks import (
    article_listing_buttons,
    processing_listing_buttons,
    register_manuscripts_icons,
    simplify_editorial_menu,
)


@pytest.mark.django_db
def test_register_manuscripts_icons_appends_custom_icons():
    icons = ["existing.svg"]
    result = register_manuscripts_icons(icons)
    assert result == icons + [
        "wagtailadmin/icons/package-zip.svg",
        "wagtailadmin/icons/doc-docx.svg",
    ]


@pytest.mark.parametrize(
    "status,expected_label,expected_url_name",
    [
        (ProcessStatus.AWAITING_REVIEW, "Review", "manuscripts:processing_review"),
        (ProcessStatus.COMPLETED, "View trail", "wagtailsnippets_manuscripts_processing:inspect"),
    ],
)
@pytest.mark.django_db
def test_processing_listing_buttons_for_processing_status(
    processing, staff_user, status, expected_label, expected_url_name
):
    processing.status = status
    processing.save(update_fields=["status"])

    buttons = list(processing_listing_buttons(processing, staff_user))
    assert len(buttons) == 1
    assert buttons[0].label == expected_label
    assert buttons[0].url == reverse(expected_url_name, args=[processing.pk])


@pytest.mark.django_db
def test_processing_listing_buttons_ignores_non_processing_snippets(article, staff_user):
    assert list(processing_listing_buttons(article, staff_user)) == []


@pytest.mark.django_db
def test_article_listing_buttons_structure_and_validation(article, processing, staff_user):
    from manuscripts.artifacts import save_artifact
    from manuscripts.structure import create_structure_version

    structure = create_structure_version(article, processing, InputType.DOCUMENT, [], [], [])
    save_artifact(
        processing,
        ArtifactType.VALIDATION_REPORT,
        "report.json",
        b'[{"group": "test"}]',
        article=article,
    )

    buttons = list(article_listing_buttons(article, staff_user))
    labels = [button.label for button in buttons]
    assert "View Structure" in labels
    assert "View Validation" in labels
    assert buttons[0].attrs == {"target": "_blank"}
    assert structure is not None


@pytest.mark.django_db
def test_article_listing_buttons_all_artifact_types(article, processing, staff_user):
    from manuscripts.artifacts import save_artifact

    artifact_specs = [
        (ArtifactType.HTML, "Preview HTML", "artifact_preview"),
        (ArtifactType.SPS_PACKAGE, "Download SPS Package", "artifact_download"),
        (ArtifactType.MARKED_DOCUMENT, "Download Marked DOCX", "artifact_download"),
        (ArtifactType.XML, "Download XML", "artifact_download"),
    ]
    for artifact_type, _label, _url_name in artifact_specs:
        save_artifact(
            processing,
            artifact_type,
            f"{artifact_type}.bin",
            b"content",
            article=article,
        )

    buttons = list(article_listing_buttons(article, staff_user))
    labels = [button.label for button in buttons]
    assert labels == [
        "Preview HTML",
        "Download SPS Package",
        "Download Marked DOCX",
        "Download XML",
    ]
    preview_button = next(button for button in buttons if button.label == "Preview HTML")
    assert preview_button.attrs == {"target": "_blank"}


def test_article_listing_buttons_ignores_non_article_snippets(processing, staff_user):
    assert list(article_listing_buttons(processing, staff_user)) == []


def test_article_listing_buttons_without_structure_or_artifacts(article, staff_user):
    assert list(article_listing_buttons(article, staff_user)) == []


def test_simplify_editorial_menu_hides_snippets_and_scielo():
    request = MagicMock()
    menu_items = [
        SimpleNamespace(name="snippets"),
        SimpleNamespace(name="articles"),
        SimpleNamespace(name="scielo"),
        SimpleNamespace(name="images"),
    ]

    simplify_editorial_menu(request, menu_items)

    assert [item.name for item in menu_items] == ["articles", "images"]
