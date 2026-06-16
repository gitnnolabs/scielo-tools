import logging

import requests as req
from django.contrib import messages
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import path
from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import (
    CreateView,
    EditView,
    SnippetViewSet,
    SnippetViewSetGroup,
)

from ai.models import DownloadStatus, GeminiModel, HuggingFaceModel, OllamaModel
from config.menu import get_menu_order

logger = logging.getLogger(__name__)


def ollama_tags(request):
    url = request.GET.get("url", "").strip().rstrip("/")
    if not url:
        return JsonResponse({"error": "URL is required"}, status=400)
    try:
        logger.info("Fetching Ollama tags from %s/api/tags", url)
        resp = req.get(f"{url}/api/tags", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        models = data.get("models", [])
        tags = [m["name"] for m in models]
        logger.info("Ollama tags: %d found", len(tags))
        return JsonResponse({"models": tags})
    except Exception as e:
        logger.error("Ollama tags error: %s", e)
        return JsonResponse({"error": str(e)}, status=502)


def ollama_model_info(request):
    url = request.GET.get("url", "").strip().rstrip("/")
    model = request.GET.get("model", "").strip()
    if not url or not model:
        return JsonResponse({"error": "URL and model are required"}, status=400)
    try:
        logger.info("Fetching Ollama model info for %s from %s", model, url)
        resp = req.post(f"{url}/api/show", json={"name": model}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        info = {
            "context_length": None,
            "parameter_size": data.get("details", {}).get("parameter_size"),
        }
        model_info = data.get("model_info", {})
        for key in model_info:
            if "context_length" in key or "num_ctx" in key:
                info["context_length"] = model_info[key]
                break
        logger.info("Ollama model info: %s", info)
        return JsonResponse(info)
    except Exception as e:
        logger.error("Ollama model info error: %s", e)
        return JsonResponse({"error": str(e)}, status=502)



class HFModelCreateView(CreateView):
    def form_invalid(self, form):
        self.produced_error_message = True
        return super().form_invalid(form)

    def form_valid(self, form):
        self.object = form.save_all(self.request.user)
        if self.object.hf_token:
            self.object.download_status = DownloadStatus.DOWNLOADING
            self.object.save()
            from ai.tasks import download_model
            download_model.delay(self.object.pk)
            messages.success(self.request, _("Model created, download started."))
        else:
            messages.success(self.request, _("Model created. Add a token to download."))
        return HttpResponseRedirect(self.get_success_url())


class HFModelEditView(EditView):
    def form_invalid(self, form):
        self.produced_error_message = True
        return super().form_invalid(form)

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        form.instance.save()
        if form.instance.hf_token and form.instance.download_status != DownloadStatus.DOWNLOADING:
            form.instance.download_status = DownloadStatus.DOWNLOADING
            form.instance.save()
            from ai.tasks import download_model
            download_model.delay(form.instance.pk)
            messages.success(self.request, _("Download started."))
        else:
            messages.success(self.request, _("Model updated."))
        return HttpResponseRedirect(self.get_success_url())


class HuggingFaceViewSet(SnippetViewSet):
    model = HuggingFaceModel
    add_view_class = HFModelCreateView
    edit_view_class = HFModelEditView
    menu_label = _("HuggingFace")
    menu_icon = "download"
    list_display = ("__str__", "get_download_status_display", "is_active")
    search_fields = ("name_model", "name_file")



class OllamaModelCreateView(CreateView):
    def form_invalid(self, form):
        self.produced_error_message = True
        return super().form_invalid(form)

    def form_valid(self, form):
        self.object = form.save_all(self.request.user)
        messages.success(self.request, _("Ollama model created."))
        return HttpResponseRedirect(self.get_success_url())


class OllamaModelEditView(EditView):
    def form_invalid(self, form):
        self.produced_error_message = True
        return super().form_invalid(form)

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        form.instance.save()
        messages.success(self.request, _("Ollama model updated."))
        return HttpResponseRedirect(self.get_success_url())


class OllamaViewSet(SnippetViewSet):
    model = OllamaModel
    add_view_class = OllamaModelCreateView
    edit_view_class = OllamaModelEditView
    menu_label = _("Ollama")
    menu_icon = "link-external"
    list_display = ("__str__", "url", "is_active")



class GeminiCreateView(CreateView):
    def form_invalid(self, form):
        self.produced_error_message = True
        return super().form_invalid(form)

    def form_valid(self, form):
        self.object = form.save_all(self.request.user)
        messages.success(self.request, _("Gemini model created."))
        return HttpResponseRedirect(self.get_success_url())


class GeminiEditView(EditView):
    def form_invalid(self, form):
        self.produced_error_message = True
        return super().form_invalid(form)

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        form.instance.save()
        messages.success(self.request, _("Gemini model updated."))
        return HttpResponseRedirect(self.get_success_url())


class GeminiViewSet(SnippetViewSet):
    model = GeminiModel
    add_view_class = GeminiCreateView
    edit_view_class = GeminiEditView
    menu_label = _("Gemini")
    menu_icon = "key"
    list_display = ("__str__", "is_active")



class AIModelGroup(SnippetViewSetGroup):
    menu_name = "ai"
    menu_label = _("AI Models")
    menu_icon = "ai-brain"
    menu_order = get_menu_order("ai")
    add_to_settings_menu = True
    items = (HuggingFaceViewSet, OllamaViewSet, GeminiViewSet)


register_snippet(AIModelGroup)



@hooks.register("register_admin_urls")
def register_ai_admin_urls():
    return [
        path("ai/ollama-tags/", ollama_tags, name="ai_ollama_tags"),
        path("ai/ollama-model-info/", ollama_model_info, name="ai_ollama_model_info"),
    ]



@hooks.register("insert_global_admin_js")
def ai_model_admin_js():
    return """<script>
(function() {
var tries = 0;
function init() {
    if (tries++ > 40) return;
    var urlInput = document.querySelector('[name="url"]');
    var modelSelect = document.querySelector('[data-ai="ollama-model-select"]');
    if (!urlInput || !modelSelect) { setTimeout(init, 150); return; }
    console.log('[ai] ollama form detected');

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = 'Fetch models';
    btn.style.cssText = 'display:block;margin:6px 0;padding:4px 12px;font-size:13px;';

    var row = urlInput.closest('[data-contentpath]') || urlInput.closest('.w-field__wrapper') || urlInput.parentElement;
    if (row && row.parentElement) row.appendChild(btn);

    btn.addEventListener('click', function(e) {
        e.preventDefault();
        var u = urlInput.value.trim();
        if (!u) { alert('Enter an Ollama URL first.'); return; }
        btn.disabled = true;
        btn.textContent = 'Fetching...';
        fetch('/admin/ai/ollama-tags/?url=' + encodeURIComponent(u), {credentials: 'same-origin'})
            .then(function(r) {
                if (!r.ok) return r.json().then(function(d) { throw new Error(d.error || 'HTTP ' + r.status); });
                return r.json();
            })
            .then(function(d) {
                modelSelect.innerHTML = '<option value="">-- Select model --</option>';
                if (d.models && d.models.length) {
                    d.models.forEach(function(n) {
                        var o = document.createElement('option');
                        o.value = n; o.textContent = n;
                        modelSelect.appendChild(o);
                    });
                    console.log('[ai] loaded ' + d.models.length + ' models');
                } else {
                    alert('No models found. Check URL and server connectivity.');
                }
            })
            .catch(function(err) { alert(err.message); })
            .finally(function() { btn.disabled = false; btn.textContent = 'Fetch models'; });
    });

    modelSelect.addEventListener('change', function() {
        var u = urlInput.value.trim();
        var mdl = modelSelect.value;
        var ctxInput = document.querySelector('[name="context_limit"]');
        if (!u || !mdl || !ctxInput) return;
        fetch('/admin/ai/ollama-model-info/?url=' + encodeURIComponent(u) + '&model=' + encodeURIComponent(mdl), {credentials: 'same-origin'})
            .then(function(r) {
                if (!r.ok) return r.json().then(function(d) { throw new Error(d.error || 'HTTP ' + r.status); });
                return r.json();
            })
            .then(function(d) {
                if (d.context_length) {
                    ctxInput.value = d.context_length;
                    ctxInput.placeholder = 'Auto: ' + d.context_length;
                    console.log('[ai] auto context: ' + d.context_length + ' for ' + mdl);
                }
            })
            .catch(function(err) { console.log('[ai] model info fetch failed: ' + err.message); });
    });
}
setTimeout(init, 100);
})();
</script>"""


@hooks.register("register_icons")
def register_ai_icons(icons):
    return icons + ["wagtailadmin/icons/ai-brain.svg"]
