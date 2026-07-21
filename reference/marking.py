import logging

from reference.exceptions import (
    ReferenceLlamaDisabledError,
    ReferenceLlamaMisconfiguredError,
    ReferenceLlamaUnavailableError,
)
from reference.prompts import MESSAGES, RESPONSE_FORMAT
from reference.providers import get_provider
from reference.utils.references import parse_reference_list

logger = logging.getLogger(__name__)


def mark_reference(reference_text):
    try:
        reference_marker = get_provider(MESSAGES, RESPONSE_FORMAT)
        output = reference_marker.run(reference_text)
        for item in output.get("choices", []):
            yield item.get("message", {}).get("content", "")

    except (
        ReferenceLlamaDisabledError,
        ReferenceLlamaMisconfiguredError,
        ReferenceLlamaUnavailableError,
    ) as exc:
        logger.error(
            "Error marking reference via Llama: %s — ref=%s", exc, reference_text
        )
        raise

    except Exception as exc:
        logger.exception("Unexpected error marking reference: ref=%s", reference_text)
        yield f"An unexpected error occurred: {str(exc)}"


def mark_references(reference_block):
    for ref_row in parse_reference_list(reference_block):
        choices = mark_reference(ref_row)
        yield {"references": ref_row, "choices": list(choices)}
