from django.conf import settings
from rest_framework.routers import DefaultRouter, SimpleRouter

from reference.api.v1.views import ReferenceViewSet

if settings.DEBUG:
    router = DefaultRouter()
else:
    router = SimpleRouter()

router.register("reference", ReferenceViewSet, basename="reference")

urlpatterns = router.urls
