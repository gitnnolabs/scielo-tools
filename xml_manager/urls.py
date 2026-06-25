from django.urls import path

from . import views

urlpatterns = [
    path(
        "revalidate-sps/<int:pk>/",
        views.revalidate_sps_package_pk,
        name="revalidate_sps_package_pk",
    ),
]
