import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


class ResponseStub:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_ollama_tags_returns_models(client, monkeypatch):
    def fake_get(url, timeout):
        assert url == "http://localhost:11434/api/tags"
        assert timeout == 10
        return ResponseStub({"models": [{"name": "llama3.2"}, {"name": "qwen2.5"}]})

    monkeypatch.setattr("ia.wagtail_hooks.req.get", fake_get)

    response = client.get(
        reverse("ia:ollama_tags"),
        {"url": "http://localhost:11434"},
    )

    assert response.status_code == 200
    assert response.json() == {"models": ["llama3.2", "qwen2.5"]}


def test_ollama_tags_requires_url(client):
    response = client.get(reverse("ia:ollama_tags"))

    assert response.status_code == 400
    assert response.json() == {"error": "URL is required"}


def test_ollama_model_info_returns_context(client, monkeypatch):
    payload = {
        "details": {"parameter_size": "8B"},
        "model_info": {"llama.context_length": 8192},
    }

    def fake_post(url, json, timeout):
        assert url == "http://localhost:11434/api/show"
        assert json == {"name": "llama3.2"}
        assert timeout == 15
        return ResponseStub(payload)

    monkeypatch.setattr("ia.wagtail_hooks.req.post", fake_post)

    response = client.get(
        reverse("ia:ollama_model_info"),
        {"url": "http://localhost:11434", "model": "llama3.2"},
    )

    assert response.status_code == 200
    assert response.json() == {"context_length": 8192, "parameter_size": "8B"}


def test_ollama_model_info_requires_params(client):
    response = client.get(reverse("ia:ollama_model_info"), {"url": "http://localhost"})

    assert response.status_code == 400
    assert response.json() == {"error": "URL and model are required"}


def test_ollama_tags_returns_502_on_upstream_error(client, monkeypatch):
    def fake_get(url, timeout):
        raise RuntimeError("upstream unavailable")

    monkeypatch.setattr("ia.wagtail_hooks.req.get", fake_get)
    response = client.get(
        reverse("ia:ollama_tags"),
        {"url": "http://localhost:11434"},
    )

    assert response.status_code == 502
    assert "upstream unavailable" in response.json()["error"]


def test_ollama_model_info_without_context_length(client, monkeypatch):
    payload = {
        "details": {"parameter_size": "7B"},
        "model_info": {"other_key": 2048},
    }

    def fake_post(url, json, timeout):
        return ResponseStub(payload)

    monkeypatch.setattr("ia.wagtail_hooks.req.post", fake_post)
    response = client.get(
        reverse("ia:ollama_model_info"),
        {"url": "http://localhost:11434", "model": "llama3.2"},
    )

    assert response.status_code == 200
    assert response.json() == {"context_length": None, "parameter_size": "7B"}
