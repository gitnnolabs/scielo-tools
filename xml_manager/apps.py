from django.apps import AppConfig


class XmlManagerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "xml_manager"

    def ready(self):
        import xml_manager.signals  # noqa: F401
