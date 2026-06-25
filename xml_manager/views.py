from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .models import SPSPackageValidation, SPSPackageValidationStatus
from .services import run_sps_package_validation


@staff_member_required
def revalidate_sps_package_pk(request, pk):
    validation = get_object_or_404(SPSPackageValidation, pk=pk)
    validation.status = SPSPackageValidationStatus.PENDING
    validation.validated_by = request.user
    validation.validated_at = None
    validation.error_message = ""
    validation.save()
    run_sps_package_validation(validation.pk)
    messages.success(
        request,
        _("Validation started for “%(title)s”.") % {"title": validation},
    )
    list_url = reverse(validation.snippet_viewset.get_url_name("list"))
    return redirect(list_url)
