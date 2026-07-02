from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class IAConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ia"
    verbose_name = _("IA Model")
