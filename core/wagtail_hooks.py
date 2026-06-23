import os

from django.db.models.signals import pre_save
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.admin.menu import Menu, MenuItem, SubmenuMenuItem
from wagtail.images import get_image_model

from core.celery_wagtail import *  # noqa: F401,F403


def ensure_image_title(sender, instance, **kwargs):
    if (instance.title or "").strip():
        return
    if not instance.file:
        return
    basename = os.path.basename(instance.file.name)
    instance.title = os.path.splitext(basename)[0]


pre_save.connect(ensure_image_title, sender=get_image_model())


@hooks.register("construct_main_menu")
def group_wagtail_cms_menu_items(request, menu_items):
    cms_item_names = {"explorer", "images", "documents", "xml_sps"}
    menu_items[:] = [item for item in menu_items if item.name not in cms_item_names]
    cms_menu = Menu(
        items=[
            MenuItem(
                _("Pages"),
                reverse("wagtailadmin_explore_root"),
                name="cms_pages",
                icon_name="doc-empty-inverse",
                order=100,
            ),
            MenuItem(
                _("Images"),
                reverse("wagtailimages:index"),
                name="cms_images",
                icon_name="image",
                order=200,
            ),
            MenuItem(
                _("Documents"),
                reverse("wagtaildocs:index"),
                name="cms_documents",
                icon_name="doc-full-inverse",
                order=300,
            ),
        ]
    )
    menu_items.append(
        SubmenuMenuItem(
            _("Content Manager"),
            cms_menu,
            icon_name="folder-open-inverse",
            name="wagtail_cms",
            order=800,
        )
    )
    settings_index = next(
        (index for index, item in enumerate(menu_items) if item.name == "settings"),
        None,
    )
    report_index = next(
        (index for index, item in enumerate(menu_items) if item.name == "reports"),
        None,
    )
    if settings_index is not None and report_index is not None:
        reports_item = menu_items.pop(report_index)
        if report_index < settings_index:
            settings_index -= 1
        menu_items.insert(settings_index + 1, reports_item)


@hooks.register("construct_help_menu")
def replace_help_menu_items(request, help_menu_items):
    help_menu_items[:] = [
        MenuItem(
            _("Project Wiki"),
            "https://github.com/scieloorg/scielo-tools/wiki",
            name="project_wiki",
            icon_name="link-external",
            attrs={"target": "_blank", "rel": "noopener noreferrer"},
            order=100,
        )
    ]

