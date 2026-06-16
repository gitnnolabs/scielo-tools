from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.admin.widgets.button import Button
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from .choices import ArtifactType
from .models.article import Article
from .models.processing import (
    ArticleInput,
    Processing,
    SPSPackageImport,
    XMLImport,
)
from .views.wagtail import (
    ArticleInputCreateView,
    ArticleInspectView,
    OwnedCreateView,
    ProcessingCreateView,
    ProcessingInspectView,
    SPSPackageImportCreateView,
    XMLImportCreateView,
)


class ProcessingViewSet(SnippetViewSet):
    model = Processing
    add_view_class = ProcessingCreateView
    inspect_view_class = ProcessingInspectView
    inspect_view_enabled = True
    inspect_template_name = "manuscripts/processing_inspect.html"
    inspect_view_fields = (
        "title", "input_file", "detected_type", "status",
        "current_action", "error_message", "created", "updated",
    )
    menu_name = "processings"
    menu_label = _("Processings")
    menu_icon = "tasks"
    menu_order = 1
    add_to_admin_menu = False
    copy_view_enabled = False
    list_display = ("__str__", "detected_type", "status", "current_action", "article_count", "updated")
    list_filter = ("status", "detected_type", "current_action")
    search_fields = ("title", "input_file", "input_checksum", "error_message")


class ArticleViewSet(SnippetViewSet):
    model = Article
    add_view_class = OwnedCreateView
    inspect_view_class = ArticleInspectView
    inspect_view_enabled = True
    inspect_template_name = "manuscripts/article_inspect.html"
    inspect_view_fields = ("title", "doi", "pid", "journal", "issue", "status", "created", "updated")
    menu_name = "articles"
    menu_label = _("Articles")
    menu_icon = "doc-full"
    menu_order = 3
    add_to_admin_menu = True
    copy_view_enabled = False
    list_display = ("title", "doi", "pid", "journal", "status", "updated")
    list_filter = ("status", "journal")
    search_fields = ("title", "doi", "pid", "content_checksum")


class ArticleInputViewSet(SnippetViewSet):
    model = ArticleInput
    add_view_class = ArticleInputCreateView
    menu_label = _("DOCX")
    menu_icon = "doc-docx"
    add_to_admin_menu = False
    list_display = ("__str__", "status", "updated")


class XMLImportViewSet(SnippetViewSet):
    model = XMLImport
    add_view_class = XMLImportCreateView
    menu_label = _("XML")
    menu_icon = "code"
    add_to_admin_menu = False
    list_display = ("__str__", "status", "updated")


class SPSPackageImportViewSet(SnippetViewSet):
    model = SPSPackageImport
    add_view_class = SPSPackageImportCreateView
    menu_label = _("SPS Package")
    menu_icon = "package-zip"
    add_to_admin_menu = False
    list_display = ("__str__", "status", "updated")


class EntryViewSetGroup(SnippetViewSetGroup):
    menu_name = "entries"
    menu_label = _("Entries")
    menu_icon = "upload"
    menu_order = 1
    items = (ArticleInputViewSet, XMLImportViewSet, SPSPackageImportViewSet)


register_snippet(EntryViewSetGroup)
register_snippet(ArticleViewSet)
register_snippet(ProcessingViewSet)


@hooks.register("register_icons")
def register_manuscripts_icons(icons):
    return icons + [
        "wagtailadmin/icons/package-zip.svg",
        "wagtailadmin/icons/doc-docx.svg",
    ]


@hooks.register("register_snippet_listing_buttons")
def processing_listing_buttons(snippet, user, next_url=None):
    if isinstance(snippet, Processing):
        yield Button(
            _("Review") if snippet.status == "awaiting_review" else _("View trail"),
            reverse(
                "manuscripts:processing_review",
                args=[snippet.pk],
            ) if snippet.status == "awaiting_review" else reverse(
                "wagtailsnippets_manuscripts_processing:inspect", args=[snippet.pk]
            ),
            icon_name="view",
            priority=10,
        )


@hooks.register("register_snippet_listing_buttons")
def article_listing_buttons(snippet, user, next_url=None):
    if not isinstance(snippet, Article):
        return

    if snippet.current_structure:
        yield Button(
            _("View Structure"),
            reverse("manuscripts:article_structure_edit", args=[snippet.pk]),
            icon_name="code",
            priority=50,
            attrs={"target": "_blank"},
        )

    if snippet.current_artifact(ArtifactType.VALIDATION_REPORT):
        yield Button(
            _("View Validation"),
            reverse("manuscripts:article_validation", args=[snippet.pk]),
            icon_name="tick-inverse",
            priority=40,
            attrs={"target": "_blank"},
        )

    artifact_buttons = [
        (ArtifactType.HTML, _("Preview HTML"), "site", 60, "artifact_preview", {"target": "_blank"}),
        (ArtifactType.SPS_PACKAGE, _("Download SPS Package"), "download", 65, "artifact_download", {}),
        (ArtifactType.MARKED_DOCUMENT, _("Download Marked DOCX"), "doc-full", 70, "artifact_download", {}),
        (ArtifactType.XML, _("Download XML"), "download", 75, "artifact_download", {}),
    ]

    for artifact_type, label, icon, priority, url_name, attrs in artifact_buttons:
        artifact = snippet.current_artifact(artifact_type)
        if artifact:
            yield Button(
                label,
                reverse(f"manuscripts:{url_name}", args=[artifact.pk]),
                icon_name=icon,
                priority=priority,
                attrs=attrs or None,
            )


@hooks.register("construct_main_menu")
def simplify_editorial_menu(request, menu_items):
    hidden_names = {"snippets", "scielo"}
    menu_items[:] = [item for item in menu_items if item.name not in hidden_names]
