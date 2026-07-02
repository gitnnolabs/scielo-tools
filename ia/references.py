import logging

from ia.exceptions import (
    LlamaDisabledError,
    LlamaModelNotFoundError,
    LlamaNotInstalledError,
)
from ia.prompts.back import MESSAGES, RESPONSE_FORMAT
from ia.service import LLMService

logger = logging.getLogger(__name__)


def mark_reference(reference_text):
    try:
        reference_marker = LLMService(MESSAGES, RESPONSE_FORMAT)
        output = reference_marker.run(reference_text)
        for item in output.get("choices", []):
            yield item.get("message", {}).get("content", "")

    except (LlamaDisabledError, LlamaNotInstalledError, LlamaModelNotFoundError) as exc:
        logger.error("Error marking reference: %s — ref=%s", exc, reference_text)
        if isinstance(exc, LlamaModelNotFoundError):
            yield f"Llama model file not found: {str(exc)}"
        else:
            yield f"Llama model is not available: {str(exc)}"

    except Exception as exc:
        logger.exception("Unexpected error marking reference: ref=%s", reference_text)
        yield f"An unexpected error occurred: {str(exc)}"


def mark_references(reference_block):
    for ref_row in reference_block.split("\n"):
        ref_row = ref_row.strip()
        if ref_row:
            choices = mark_reference(ref_row)
            yield {"references": ref_row, "choices": list(choices)}
