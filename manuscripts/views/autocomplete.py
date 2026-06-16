from http import HTTPStatus
from urllib.parse import unquote

from django.apps import apps
from django.db.models import Q
from django.http import HttpResponseBadRequest, JsonResponse
from django.urls import re_path
from django.views.decorators.http import require_POST
from wagtail.admin.auth import require_admin_access
from wagtailautocomplete.views import create, objects, render_page
from wagtailautocomplete.views import search as default_search


@require_POST
def search(request):
    target_model = request.POST.get("type", "wagtailcore.Page")
    is_article_issue_filter = request.POST.get("article_issue_filter") == "1"
    if target_model != "journals.Issue" or not is_article_issue_filter:
        return default_search(request)

    journal_id = request.POST.get("journal_id")
    if not journal_id:
        return JsonResponse({"items": []})

    try:
        limit = int(request.POST.get("limit", 100))
        model = apps.get_model(target_model)
    except (LookupError, ValueError):
        return HttpResponseBadRequest()

    search_query = request.POST.get("query", "")
    queryset = model.objects.filter(journal_id=journal_id)
    if search_query:
        queryset = queryset.filter(
            Q(number__icontains=search_query)
            | Q(volume__icontains=search_query)
            | Q(year__icontains=search_query)
            | Q(supplement__icontains=search_query)
            | Q(journal__title__icontains=search_query)
        )

    exclude = request.POST.get("exclude", "")
    if exclude:
        exclusions = [unquote(item) for item in exclude.split(",") if item]
        queryset = queryset.exclude(pk__in=exclusions)

    results = map(render_page, queryset.order_by("volume", "number", "year")[:limit])
    return JsonResponse({"items": list(results)}, status=HTTPStatus.OK)


urlpatterns = [
    re_path(r"^create/", require_admin_access(create)),
    re_path(r"^objects/", require_admin_access(objects)),
    re_path(r"^search/", require_admin_access(search)),
]
