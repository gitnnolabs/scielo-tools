import logging

from ia.exceptions import LlamaModelNotFoundError
from ia.models import GeminiModel, HuggingFaceModel, OllamaModel
from ia.providers.gemini import GeminiProvider
from ia.providers.local import LocalProvider
from ia.providers.ollama import OllamaProvider

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(
        self,
        messages=None,
        response_format=None,
        max_tokens=4000,
        temperature=0.0,
        top_p=0.1,
        mode="chat",
        nthreads=2,
        stop=None,
        n_ctx=None,
    ):
        self.messages = messages or []
        self.response_format = response_format
        self.mode = mode

        provider_kwargs = {
            "response_format": response_format,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stop": stop,
        }

        gemini = GeminiModel.objects.filter(is_active=True).first()
        if gemini:
            logger.info("LLMService: using Gemini")
            self.provider = GeminiProvider(gemini, response_format=response_format)
            return

        ollama = OllamaModel.objects.filter(is_active=True).first()
        if ollama:
            logger.info("LLMService: using Ollama at %s", ollama.url)
            self.provider = OllamaProvider(ollama, **provider_kwargs)
            return

        hf = HuggingFaceModel.objects.filter(is_active=True).first()
        if hf:
            logger.info("LLMService: using local Llama")
            self.provider = LocalProvider(
                hf, n_ctx=n_ctx, nthreads=nthreads, **provider_kwargs
            )
            return

        raise LlamaModelNotFoundError("No IA model configured.")

    def run(self, user_input, response_format=None):
        if self.mode == "chat":
            messages = self.messages.copy()
            messages.append({"role": "user", "content": user_input})
            return self.provider.chat(messages)
        if self.mode == "prompt":
            return self.provider.prompt(
                user_input, response_format or self.response_format
            )
        return ""
