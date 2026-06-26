import os

from django.db.models.signals import pre_save
from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.admin.menu import MenuItem
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
def keep_only_sps_validation_menu(request, menu_items):
    menu_items[:] = [
        item for item in menu_items if item.name == "sps_package_validation"
    ]


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
