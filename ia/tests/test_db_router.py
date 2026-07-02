from ia.db_router import IADatabaseRouter


class MetaStub:
    def __init__(self, app_label):
        self.app_label = app_label


class ModelStub:
    def __init__(self, app_label):
        self._meta = MetaStub(app_label)


def test_router_uses_default_when_ia_db_not_configured(settings):
    settings.DATABASES.clear()
    settings.DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
    router = IADatabaseRouter()
    model = ModelStub("ia")

    assert router.db_for_read(model) is None
    assert router.db_for_write(model) is None
    assert router.allow_migrate("default", "ia") is True
    assert router.allow_migrate("ia_db", "ia") is False


def test_router_uses_ia_db_when_configured(settings):
    settings.DATABASES.clear()
    settings.DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
    settings.DATABASES["ia_db"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
    router = IADatabaseRouter()
    model = ModelStub("ia")
    other_model = ModelStub("xml_manager")

    assert router.db_for_read(model) == "ia_db"
    assert router.db_for_write(model) == "ia_db"
    assert router.db_for_read(other_model) is None
    assert router.allow_migrate("ia_db", "ia") is True
    assert router.allow_migrate("default", "ia") is False
    assert router.allow_migrate("default", "xml_manager") is None


def test_router_allows_relations_with_ia_models():
    router = IADatabaseRouter()
    ia_obj = ModelStub("ia")
    other_obj = ModelStub("xml_manager")
    no_ia_obj_a = ModelStub("users")
    no_ia_obj_b = ModelStub("core")

    assert router.allow_relation(ia_obj, other_obj) is True
    assert router.allow_relation(no_ia_obj_a, no_ia_obj_b) is None
