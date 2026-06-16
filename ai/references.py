import logging

from ai.exceptions import (
    LlamaDisabledError,
    LlamaModelNotFoundError,
    LlamaNotInstalledError,
)
from ai.service import LLMService
from ai.prompts.back import MESSAGES, RESPONSE_FORMAT

logger = logging.getLogger(__name__)


def mark_reference(reference_text):
    try:
        reference_marker = LLMService(MESSAGES, RESPONSE_FORMAT)
        output = reference_marker.run(reference_text)
        for item in output.get("choices", []):
            yield item.get("message", {}).get("content", "")

    except (LlamaDisabledError, LlamaNotInstalledError, LlamaModelNotFoundError) as e:
        logger.error("Error marking reference: %s — ref=%s", e, reference_text)
        if isinstance(e, LlamaModelNotFoundError):
            yield f"Llama model file not found: {str(e)}"
        else:
            yield f"Llama model is not available: {str(e)}"

    except Exception as e:
        logger.exception("Unexpected error marking reference: ref=%s", reference_text)
        yield f"An unexpected error occurred: {str(e)}"


def mark_references(reference_block):
    for ref_row in reference_block.split("\n"):
        ref_row = ref_row.strip()
        if ref_row:
            choices = mark_reference(ref_row)
            yield {
                "references": ref_row,
                "choices": list(choices)
            }
