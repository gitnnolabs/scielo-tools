WAGTAIL_MENU_GROUPS_ORDER = [
    "manuscripts",
    "references",
    "xml_manager",
    "journals",
    "ai",
    "celery_wagtail",
]


def get_menu_order(app_name):
    try:
        return WAGTAIL_MENU_GROUPS_ORDER.index(app_name) + 1
    except ValueError:
        return 9000


MANUSCRIPTS_SUBMENU_ORDER = {
    "upload": 1,
    "processed": 2,
    "xml_editor": 3,
    "issue": 4,
}


def get_manuscripts_submenu_order(item_name):
    return MANUSCRIPTS_SUBMENU_ORDER.get(item_name, 9000)
