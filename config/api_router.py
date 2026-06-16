from django.conf import settings
from rest_framework.routers import DefaultRouter, SimpleRouter

from manuscripts.api.v1.views import ArticleViewSet
from references.api.v1.views import ReferenceViewSet

if settings.DEBUG:
    router = DefaultRouter()
else:
    router = SimpleRouter()

router.register("references", ReferenceViewSet, basename="references")
router.register("first_block", ArticleViewSet, basename="first_block")

urlpatterns = router.urls