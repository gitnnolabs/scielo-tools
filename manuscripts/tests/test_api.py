import pytest
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_first_block_post_returns_deprecated_message(user):
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        reverse("first_block-list"),
        {"text": "sample", "metadata": {"lang": "en"}},
        format="json",
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Article marking API is deprecated."}


@pytest.mark.django_db
def test_first_block_post_requires_authentication():
    client = APIClient()

    response = client.post(
        reverse("first_block-list"),
        {"text": "sample", "metadata": {"lang": "en"}},
        format="json",
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_first_block_post_with_invalid_json_returns_error_message(user):
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.generic(
        "POST",
        reverse("first_block-list"),
        "{invalid-json",
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {"error": "Error processing"}
