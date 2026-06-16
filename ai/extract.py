import logging

import requests
from django.conf import settings

from ai.exceptions import (
    LlamaDisabledError,
    LlamaModelNotFoundError,
    LlamaNotInstalledError,
)
from ai.utils.blocks import source_blocks
from manuscripts.controller import enrich_article
from manuscripts.utils.frontmatter import enrich_frontmatter
from ai.payload import (
    has_useful_payload,
    normalize_payload,
    payload_counts,
)
from ai.utils.json import try_parse_json
from ai.utils.text import extract_text_from_docx as text_extract_docx
from ai.utils.text import extract_text_from_docx_via_docling
from ai.utils.vision import extract_page_images
from ai.providers.ollama import OllamaProvider
from ai.service import LLMService
from ai.models import GeminiModel, OllamaModel
from ai.prompts.vision import VISION_TASKS
from ai.prompts.text import build_split_task_prompts

logger = logging.getLogger(__name__)


def _detect_provider():
    try:
        if GeminiModel.objects.filter(is_active=True).exists():
            return "gemini"
        elif OllamaModel.objects.filter(is_active=True).exists():
            return "ollama"
        return "llama"
    except Exception:
        return "unknown"


def _fetch_ollama_context(url, model_name):
    try:
        resp = requests.post(f"{url.rstrip('/')}/api/show", json={"name": model_name}, timeout=10)
        if resp.ok:
            data = resp.json()
            info = data.get("model_info", {})
            for key in info:
                if "context_length" in key or "num_ctx" in key:
                    return info[key]
    except Exception:
        pass
    return None


def _effective_limits(provider):
    if provider == "gemini":
        return 32768, 30000, 60
    if provider == "ollama":
        model = OllamaModel.objects.filter(is_active=True).first()
        if model:
            n_ctx = model.context_limit or _fetch_ollama_context(model.url, model.model)
            if n_ctx and n_ctx > 0:
                limit_chars = min(int(n_ctx * 3), 200000)
                blocks = max(8, min(limit_chars // 500, 60))
                return int(n_ctx), limit_chars, blocks
    return 32768, 30000, 15


def _prepare_content(front, body, docx_path, limit_chars, block_limit, use_docling=False):
    if docx_path:
        try:
            extract = extract_text_from_docx_via_docling if use_docling else text_extract_docx
            return extract(docx_path, limit_chars), True
        except Exception as e:
            logger.warning("Failed to extract text from DOCX: %s", e)

    blocks = source_blocks(front, body, limit=block_limit)
    if not blocks:
        return None, False
    return blocks, False


def _should_use_vision(docx_path):
    if not docx_path:
        return False
    ollama = OllamaModel.objects.filter(is_active=True).first()
    return bool(ollama and ollama.is_vision)


def _extract_via_llm_service(article, front, body, docx_path, provider):
    n_ctx, limit_chars, block_limit = _effective_limits(provider)

    use_docling = False
    if docx_path and provider == "ollama":
        ollama = OllamaModel.objects.filter(is_active=True).first()
        if ollama:
            use_docling = ollama.docx_extractor == OllamaModel.DocxExtractor.DOCLING

    content, is_xml = _prepare_content(front, body, docx_path, limit_chars, block_limit, use_docling)

    if content is None:
        return None, {"status": "skipped", "provider": provider, "reason": "no_source_blocks"}

    try:
        service = LLMService(mode="prompt", max_tokens=2500, temperature=0.0, top_p=0.1, stop=None, n_ctx=n_ctx)
        payload = _run_split_tasks(service, content, is_xml, article.language)
        return payload, None
    except (LlamaDisabledError, LlamaModelNotFoundError, LlamaNotInstalledError) as exc:
        logger.info("LLM unavailable: %s", exc)
        return None, {"status": "unavailable", "provider": provider, "error": str(exc)}
    except ValueError as exc:
        logger.warning("LLM unusable response: %s", exc)
        status = "empty_response" if str(exc) == "empty_response" else "invalid_response"
        return None, {"status": status, "provider": provider, "error": str(exc)}
    except Exception as exc:
        logger.exception("LLM extraction failed")
        return None, {"status": "failed", "provider": provider, "error": str(exc)}


def _make_empty_payload():
    return {
        "doi": "", "journal": {"title": "", "issn": ""},
        "issue": {"volume": "", "number": "", "year": "", "supplement": ""},
        "titles": [], "authors": [], "affiliations": [],
        "dates": [], "abstracts": [], "keywords": [], "warnings": [],
    }


def _merge_task_result(payload, name, data):
    if name == "titles" and "titles" in data:
        payload["titles"] = data["titles"]
    elif name in ("authors_affs", "authors"):
        if "authors" in data:
            payload["authors"] = data["authors"]
        if "affiliations" in data:
            payload["affiliations"] = data["affiliations"]
    elif name == "abstracts" and "abstracts" in data:
        payload["abstracts"] = data["abstracts"]
    elif name == "keywords" and "keywords" in data:
        payload["keywords"] = data["keywords"]
    elif name == "dates" and "dates" in data:
        payload["dates"] = data["dates"]
    elif name == "meta":
        for key in ("doi", "journal", "issue"):
            if key in data:
                payload[key] = data[key]


def _run_vision_tasks(provider, images):
    payload = _make_empty_payload()
    del payload["warnings"]

    for name, prompt in VISION_TASKS:
        try:
            logger.info("Vision sub-task: %s", name)
            response = provider.chat_with_images(images, prompt)
            data = try_parse_json(response)
            if not data:
                logger.warning("Vision sub-task %s: could not parse JSON", name)
                continue

            _merge_task_result(payload, name, data)
        except Exception as exc:
            logger.error("Vision sub-task %s failed: %s", name, exc)

    has_data = any(
        payload.get(k)
        for k in ("titles", "authors", "affiliations", "abstracts", "keywords", "dates", "doi")
    )
    if not has_data:
        logger.info("Vision: no data extracted")
        return None

    logger.info(
        "Vision: titles=%d authors=%d affiliations=%d abstracts=%d keywords=%d dates=%d doi=%s",
        len(payload.get("titles") or []),
        len(payload.get("authors") or []),
        len(payload.get("affiliations") or []),
        len(payload.get("abstracts") or []),
        len(payload.get("keywords") or []),
        len(payload.get("dates") or []),
        bool(payload.get("doi")),
    )
    return payload


def _run_split_tasks(service, content, is_xml, article_language):
    payload = _make_empty_payload()
    tasks = build_split_task_prompts(content, is_xml, article_language)

    for name, task_prompt, task_format in tasks:
        try:
            logger.info("Frontmatter sub-task: %s", name)
            response_text = service.run(task_prompt, response_format=task_format)
            res_json = try_parse_json(response_text)
            if not isinstance(res_json, dict):
                continue

            _merge_task_result(payload, name, res_json)

            if "warnings" in res_json:
                payload["warnings"].extend(res_json["warnings"])
        except Exception as e:
            logger.error("Sub-task %s failed: %s", name, e)
            payload["warnings"].append(f"Sub-task {name} failed: {e}")

    return payload


def extract_frontmatter(article, front, body, docx_path=None):
    provider = _detect_provider()

    if not getattr(settings, "MARKUP_DOC_LLM_FRONTMATTER_ENABLED", True):
        return front, {}, [], {"status": "disabled", "provider": provider}

    if _should_use_vision(docx_path):
        ollama = OllamaModel.objects.filter(is_active=True).first()

        try:
            logger.info("Frontmatter: using vision path")
            images = extract_page_images(docx_path)
            if not images:
                logger.info("Frontmatter: no images extracted from DOCX")
                return front, {}, [], {"status": "no_data", "provider": provider}

            payload = _run_vision_tasks(OllamaProvider(ollama), images)
            if not payload:
                return front, {}, [], {"status": "no_data", "provider": provider}
        except Exception as exc:
            logger.exception("Vision extraction failed")
            return front, {}, [{"frontmatter_ai": f"Falha: {exc}"}], {"status": "failed", "provider": provider, "error": str(exc)}
    else:
        payload, early_return = _extract_via_llm_service(article, front, body, docx_path, provider)
        if early_return:
            status = early_return["status"]
            if status == "unavailable":
                msg = "LLM indisponível."
            elif status in ("empty_response", "invalid_response"):
                msg = f"Resposta inutilizável ({early_return.get('error', status)})."
            elif status == "failed":
                msg = f"Falha: {early_return.get('error', '')}"
            else:
                msg = early_return.get("error", "")
            return front, {}, [{"frontmatter_ai": msg}] if msg else [], early_return

    normalized, warnings = normalize_payload(payload, article)

    if not has_useful_payload(normalized):
        warnings.append("LLM não retornou metadados suficientes.")
        return front, {}, [{"frontmatter_ai": w} for w in warnings], {"status": "no_data", "provider": provider, "counts": payload_counts(normalized)}

    enriched_front = enrich_frontmatter(front, normalized, article)
    updates = enrich_article(normalized, article)
    return enriched_front, updates, [{"frontmatter_ai": w} for w in warnings], {"status": "applied", "provider": provider, "counts": payload_counts(normalized), "updated_fields": sorted(updates)}
