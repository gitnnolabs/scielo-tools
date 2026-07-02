class IADatabaseRouter:
    app_label = "ia"
    db_alias = "ia_db"

    def _ia_db_configured(self):
        from django.conf import settings

        return self.db_alias in settings.DATABASES

    def db_for_read(self, model, **hints):
        if model._meta.app_label == self.app_label and self._ia_db_configured():
            return self.db_alias
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == self.app_label and self._ia_db_configured():
            return self.db_alias
        return None

    def allow_relation(self, obj1, obj2, **hints):
        if (
            obj1._meta.app_label == self.app_label
            or obj2._meta.app_label == self.app_label
        ):
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label != self.app_label:
            return None
        if self._ia_db_configured():
            return db == self.db_alias
        return db == "default"
