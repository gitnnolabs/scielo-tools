from django.templatetags.static import static
from django.utils.html import format_html
from wagtail import hooks


@hooks.register("insert_global_admin_css")
def admin_logo_css():
    return format_html(
        '<link rel="stylesheet" href="{}"><link rel="icon" type="image/x-icon" href="{}">',
        static("core_settings/css/admin_logo.css"),
        static("core_settings/img/favicon.ico"),
    )
