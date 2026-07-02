import logging
import os
import time

from ia.exceptions import (
    LlamaDisabledError,
    LlamaModelNotFoundError,
    LlamaNotInstalledError,
)
from ia.providers import JSON_INSTRUCTION

logger = logging.getLogger(__name__)


class LocalProvider:
    _cached_llm = None

    def __init__(
        self,
        model,
        response_format=None,
        temperature=0.0,
        top_p=0.1,
        max_tokens=4000,
        stop=None,
        n_ctx=None,
        nthreads=2,
    ):
        from django.conf import settings

        self.model = model
        self.response_format = response_format
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.stop = stop
        self.n_ctx = n_ctx or 32768
        llama_enabled = getattr(settings, "LLAMA_ENABLED", True)
        llama_model_dir = getattr(
            settings, "LLAMA_MODEL_DIR", settings.ROOT_DIR / "ia/download"
        )

        if not llama_enabled:
            raise LlamaDisabledError("LLaMA is disabled.")

        if LocalProvider._cached_llm is None:
            try:
                from llama_cpp import Llama
            except ImportError as exc:
                raise LlamaNotInstalledError("llama-cpp-python not installed.") from exc

            model_path = os.path.join(str(llama_model_dir), self.model.name_file)
            if not os.path.isfile(model_path):
                raise LlamaModelNotFoundError(f"Model file not found at {model_path}.")

            logger.info("Loading local Llama: %s", model_path)
            LocalProvider._cached_llm = Llama(
                model_path=model_path, n_ctx=self.n_ctx, n_threads=nthreads
            )
            logger.info("Local Llama loaded.")

        self.llm = LocalProvider._cached_llm

    def chat(self, messages):
        started = time.monotonic()
        logger.info("Local Llama chat. Preview: %r", messages[-1]["content"][:150])
        response = self.llm.create_chat_completion(
            messages=messages,
            response_format=self.response_format,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
        )
        elapsed = time.monotonic() - started
        try:
            response_text = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            response_text = ""
        logger.info("Local Llama chat: %d chars in %.2fs", len(response_text), elapsed)
        return response

    def prompt(self, user_input, response_format=None):
        started = time.monotonic()
        logger.info("Local Llama prompt. Preview: %r", user_input[:150])
        messages = [
            {"role": "system", "content": JSON_INSTRUCTION},
            {"role": "user", "content": user_input},
        ]
        response = self.llm.create_chat_completion(
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            stop=self.stop,
        )
        elapsed = time.monotonic() - started
        try:
            response_text = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            response_text = ""
        logger.info(
            "Local Llama prompt: %d chars in %.2fs", len(response_text), elapsed
        )
        return response_text
