from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import (
    CreateView,
    SnippetViewSet,
    SnippetViewSetGroup,
)

from config.menu import get_menu_order

from .models import Issue, Journal


class OwnedCreateView(CreateView):
    def save_instance(self):
        self.form.instance.creator = self.request.user
        return super().save_instance()


class JournalViewSet(SnippetViewSet):
    model = Journal
    menu_label = _("Journals")
    menu_icon = "journal"
    menu_order = 20
    add_to_admin_menu = False
    list_display = ("title", "acronym", "issn")
    search_fields = ("title", "acronym", "issn", "pissn", "eissn")


class IssueViewSet(SnippetViewSet):
    model = Issue
    add_view_class = OwnedCreateView
    menu_label = _("Issues")
    menu_icon = "issue"
    menu_order = 30
    add_to_admin_menu = False
    list_display = ("journal", "volume", "number", "year")
    search_fields = ("journal__title", "volume", "number", "year")
    list_filter = ("journal", "year")


class JournalManagerViewSetGroup(SnippetViewSetGroup):
    menu_name = "journals"
    menu_label = _("Journal Manager")
    menu_icon = "journal"
    menu_order = get_menu_order("journals")
    items = (JournalViewSet, IssueViewSet)


register_snippet(JournalManagerViewSetGroup)


@hooks.register("register_icons")
def register_journals_icons(icons):
    return icons + [
        "wagtailadmin/icons/journal.svg",
        "wagtailadmin/icons/issue.svg",
    ]
