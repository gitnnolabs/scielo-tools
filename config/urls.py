from django.conf import settings
from django.conf.urls.i18n import i18n_patterns  # ← Adicionar esta linha
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

from config import api_router as api_router
from core.search import views as search_views
from manuscripts import urls as manuscripts_urls
from manuscripts.views.autocomplete import urlpatterns as autocomplete_admin_urls

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("admin/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("search/", search_views.search, name="search"),
    # Manuscripts editorial views
    path("manuscripts/", include(manuscripts_urls, namespace="manuscripts")),
    # JWT
    path("api/v1/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path(
        "api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"
    ),
    path("api/v1/", include(api_router)),
    # URL para trocar idioma
    path("i18n/", include("django.conf.urls.i18n")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# URLs com prefixo de idioma
urlpatterns += i18n_patterns(
    path("admin/autocomplete/", include(autocomplete_admin_urls)),
    # Wagtail pages - deve ser o último
    path("", include(wagtail_urls)),
    # prefix_default_language=False  # Remove /pt-br/ da URL padrão se quiser
)

if settings.DEBUG:
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    # Serve static and media files from development server
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
