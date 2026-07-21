from collections.abc import Mapping

from django.http import JsonResponse
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from reference.api.v1.serializers import (
    ReferenceDocxRequestSerializer,
    ReferenceMarkRequestSerializer,
)
from reference.data_utils import build_ref_list, resolve_references_result
from reference.exceptions import (
    DocxReferencesError,
    ReferenceLlamaDisabledError,
    ReferenceLlamaMisconfiguredError,
    ReferenceLlamaUnavailableError,
)
from reference.utils.references import parse_reference_list, references_from_docx_upload


class ReferenceViewSet(GenericViewSet):
    serializer_class = ReferenceMarkRequestSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = [
        "get",
        "post",
        "head",
        "options",
    ]

    def get_serializer_class(self):
        if getattr(self, "action", None) == "docx":
            return ReferenceDocxRequestSerializer
        return ReferenceMarkRequestSerializer

    def create(self, request, *args, **kwargs):
        return self.api_reference(request)

    def api_reference(self, request):
        data = request.data
        if not isinstance(data, Mapping):
            return JsonResponse({"error": "Error processing"}, status=400)

        serializer = self.get_serializer(data=data)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)

        post_references = serializer.validated_data.get("references")
        post_type = serializer.validated_data.get("type", "json")
        return self.mark_and_respond(post_references, post_type)

    @action(
        detail=False,
        methods=["get", "post"],
        url_path="docx",
        parser_classes=[MultiPartParser, FormParser],
    )
    def docx(self, request):
        if request.method == "GET":
            return Response({})

        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)

        uploaded = serializer.validated_data["file"]
        post_type = serializer.validated_data.get("type", "json")
        try:
            references = references_from_docx_upload(uploaded)
        except DocxReferencesError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        return self.mark_and_respond(references, post_type)

    def mark_and_respond(self, references, output_type):
        reference_list = parse_reference_list(references)
        if not reference_list:
            return JsonResponse({"error": "No references provided"}, status=400)

        try:
            if output_type == "jats":
                results = resolve_references_result(
                    references,
                    user=self.request.user,
                    output_type="xml",
                )
                return JsonResponse({"ref_list": build_ref_list(results)})

            results = resolve_references_result(
                references,
                user=self.request.user,
                output_type=output_type,
            )
        except (
            ReferenceLlamaDisabledError,
            ReferenceLlamaMisconfiguredError,
            ReferenceLlamaUnavailableError,
        ) as exc:
            return JsonResponse(
                {"error": f"Llama model is not available: {exc}"},
                status=503,
            )

        if isinstance(references, str) and len(results) == 1:
            response_data = {
                "message": f"reference: {results[0]['data']}",
            }
        else:
            response_data = {"references": results}

        return JsonResponse(response_data)
