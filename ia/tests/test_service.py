import pytest

from ia.exceptions import LlamaModelNotFoundError
from ia.models import GeminiModel, HuggingFaceModel, OllamaModel
from ia.service import LLMService

pytestmark = pytest.mark.django_db


class DummyProvider:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def chat(self, messages):
        return {"messages": messages, "provider": "chat"}

    def prompt(self, user_input, response_format):
        return {
            "user_input": user_input,
            "response_format": response_format,
            "provider": "prompt",
        }


def test_service_prefers_gemini(monkeypatch):
    GeminiModel.objects.create(api_key="gemini-key", is_active=True)
    OllamaModel.objects.create(
        url="http://localhost:11434",
        model="llama3.2",
        is_active=True,
    )
    HuggingFaceModel.objects.create(
        name_model="repo/model",
        name_file="model.gguf",
        is_active=True,
    )

    monkeypatch.setattr("ia.service.GeminiProvider", DummyProvider)
    monkeypatch.setattr("ia.service.OllamaProvider", DummyProvider)
    monkeypatch.setattr("ia.service.LocalProvider", DummyProvider)

    service = LLMService(messages=[{"role": "system", "content": "s"}], mode="chat")
    response = service.run("hello")

    assert response["provider"] == "chat"
    assert response["messages"][-1] == {"role": "user", "content": "hello"}
    assert isinstance(service.provider, DummyProvider)
    assert isinstance(service.provider.args[0], GeminiModel)


def test_service_uses_ollama_when_no_gemini(monkeypatch):
    OllamaModel.objects.create(
        url="http://localhost:11434",
        model="llama3.2",
        is_active=True,
    )

    monkeypatch.setattr("ia.service.OllamaProvider", DummyProvider)

    service = LLMService(mode="prompt", response_format={"type": "json_object"})
    response = service.run("hello", response_format={"type": "json_object"})

    assert response["provider"] == "prompt"
    assert response["user_input"] == "hello"
    assert isinstance(service.provider.args[0], OllamaModel)


def test_service_uses_local_when_only_hf(monkeypatch):
    HuggingFaceModel.objects.create(
        name_model="repo/model",
        name_file="model.gguf",
        is_active=True,
    )

    monkeypatch.setattr("ia.service.LocalProvider", DummyProvider)

    service = LLMService(mode="prompt")
    service.run("hello")

    assert isinstance(service.provider.args[0], HuggingFaceModel)


def test_service_raises_when_no_model():
    with pytest.raises(LlamaModelNotFoundError):
        LLMService()
