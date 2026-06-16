import hashlib
import json

from django.http import JsonResponse
from rest_framework.mixins import CreateModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import GenericViewSet

from ai.utils.normalizers import stz_norm
from references.api.v1.serializers import ReferenceSerializer
from references.data_utils import get_reference
from references.models import Reference, ReferenceStatus

# Create your views here.

class ReferenceViewSet(
    GenericViewSet,  # generic view functionality
    CreateModelMixin,  # handles POSTs
):
    serializer_class = ReferenceSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = [
        "post",
    ]

    def create(self, request, *args, **kwargs):
        # Redirigir a la función api_reference()
        return self.api_reference(request)

    def api_reference(self, request):
        try:
            data = json.loads(request.body)
            post_reference = data.get('references')  # Obtiene el parámetro
            post_type = data.get('type')  # Obtiene el parámetro
            normalized = stz_norm(post_reference)
            checksum = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

            try:
                reference = Reference.objects.get(checksum=checksum)

            except Reference.DoesNotExist:
                new_reference = Reference.objects.create(
                    mixed_citation=post_reference,
                    status=ReferenceStatus.CREATING,
                    creator=self.request.user,
                )

                get_reference(new_reference.id)
                reference = Reference.objects.get(checksum=checksum)
           
            if post_type == 'xml':
                reference_data = reference.element_citation.first().marked_xml
            else:
                reference_data = reference.element_citation.first().marked

            response_data = {
                'message': f'reference: {reference_data}',
            }
        except json.JSONDecodeError:
            response_data = {
                'error': 'Error processing'
            }

        return JsonResponse(response_data)
