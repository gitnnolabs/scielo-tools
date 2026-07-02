import pytest

from ia.models import GeminiModel, HuggingFaceModel, OllamaModel

pytestmark = pytest.mark.django_db


def test_huggingface_active_is_unique():
    first = HuggingFaceModel.objects.create(
        name_model="repo/a",
        name_file="a.gguf",
        is_active=True,
    )
    second = HuggingFaceModel.objects.create(
        name_model="repo/b",
        name_file="b.gguf",
        is_active=True,
    )

    first.refresh_from_db()
    second.refresh_from_db()

    assert first.is_active is False
    assert second.is_active is True


def test_ollama_active_is_unique():
    first = OllamaModel.objects.create(
        url="http://localhost:11434",
        model="llama3.2",
        is_active=True,
    )
    second = OllamaModel.objects.create(
        url="http://localhost:11434",
        model="qwen2.5",
        is_active=True,
    )

    first.refresh_from_db()
    second.refresh_from_db()

    assert first.is_active is False
    assert second.is_active is True


def test_gemini_active_is_unique():
    first = GeminiModel.objects.create(api_key="key-1", is_active=True)
    second = GeminiModel.objects.create(api_key="key-2", is_active=True)

    first.refresh_from_db()
    second.refresh_from_db()

    assert first.is_active is False
    assert second.is_active is True
