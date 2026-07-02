from django.urls import path

from ia.wagtail_hooks import ollama_model_info, ollama_tags

app_name = "ia"

urlpatterns = [
    path("ollama-tags/", ollama_tags, name="ollama_tags"),
    path("ollama-model-info/", ollama_model_info, name="ollama_model_info"),
]
