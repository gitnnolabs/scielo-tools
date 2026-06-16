from django.urls import path

from .views import editorial as editorial_views

app_name = "manuscripts"

urlpatterns = [
    path("processings/<int:pk>/review/", editorial_views.processing_review, name="processing_review"),
    path("processings/<int:pk>/cancel/", editorial_views.processing_cancel, name="processing_cancel"),
    path("processings/<int:pk>/reprocess/", editorial_views.processing_reprocess, name="processing_reprocess"),
    path("processings/<int:pk>/cleanup-artifacts/", editorial_views.processing_cleanup_artifacts, name="processing_cleanup_artifacts"),
    path("artifacts/<int:pk>/download/", editorial_views.artifact_download, name="artifact_download"),
    path("artifacts/<int:pk>/preview/", editorial_views.artifact_preview, name="artifact_preview"),
    path("articles/<int:pk>/validation/", editorial_views.article_validation_view, name="article_validation"),
    path("articles/<int:pk>/structure/", editorial_views.article_structure_edit, name="article_structure_edit"),
    path("articles/<int:pk>/structure/revert/<int:version>/", editorial_views.article_structure_revert, name="article_structure_revert"),
    path("articles/<int:pk>/references/", editorial_views.article_references_edit, name="article_references_edit"),
    path("articles/<int:pk>/reprocess/", editorial_views.article_reprocess, name="article_reprocess"),
    path("articles/<int:pk>/cleanup-artifacts/", editorial_views.article_cleanup_artifacts, name="article_cleanup_artifacts"),
    path("citations/<int:pk>/update/", editorial_views.citation_update, name="citation_update"),
    path("article-references/<int:pk>/select/", editorial_views.article_reference_select, name="article_reference_select"),
]
