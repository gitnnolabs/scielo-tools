import json

from django.http import JsonResponse
from rest_framework.mixins import CreateModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import GenericViewSet

from manuscripts.api.v1.serializers import ArticleSerializer

# Create your views here.

class ArticleViewSet(
    GenericViewSet,  # generic view functionality
    CreateModelMixin,  # handles POSTs
):
    serializer_class = ArticleSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = [
        "post",
    ]

    def create(self, request, *args, **kwargs):
        return self.api_article(request)

    def api_article(self, request):
        try:
            data = json.loads(request.body)
            _text = data.get('text')
            _metadata = data.get('metadata')

            response_data = {
                'message': 'Article marking API is deprecated.',
            }
        except json.JSONDecodeError:
            response_data = {
                'error': 'Error processing'
            }

        return JsonResponse(response_data)
