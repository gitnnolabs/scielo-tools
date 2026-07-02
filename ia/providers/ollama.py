import json
import logging
import time

import requests

from ia.providers import JSON_INSTRUCTION

logger = logging.getLogger(__name__)


class OllamaProvider:
    def __init__(
        self,
        model,
        response_format=None,
        temperature=0.0,
        top_p=0.1,
        max_tokens=4000,
        stop=None,
    ):
        self.model = model
        self.response_format = response_format
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.stop = stop

    def _url(self, path="api/chat"):
        return f"{self.model.url.rstrip('/')}/{path}"

    def chat(self, messages):
        started = time.monotonic()
        logger.info("Ollama chat. Preview: %r", messages[-1]["content"][:150])

        options = {"temperature": self.temperature, "top_p": self.top_p}
        if self.max_tokens:
            options["num_predict"] = self.max_tokens

        payload = {
            "model": self.model.model,
            "messages": messages,
            "options": options,
            "stream": False,
        }
        if self.response_format and self.response_format.get("type") == "json_object":
            payload["format"] = "json"

        try:
            resp = requests.post(self._url(), json=payload, timeout=300)
            resp.raise_for_status()
            response_text = resp.json()["message"]["content"]
        except Exception as exc:
            logger.error("Ollama chat error: %s", exc)
            response_text = ""

        elapsed = time.monotonic() - started
        logger.info("Ollama chat: %d chars in %.2fs", len(response_text), elapsed)
        return {"choices": [{"message": {"content": response_text}}]}

    def prompt(self, user_input, response_format=None):
        started = time.monotonic()
        logger.info("Ollama prompt. Preview: %r", user_input[:150])

        options = {"temperature": self.temperature, "enable_thinking": False}
        if self.max_tokens:
            options["num_predict"] = self.max_tokens
        if self.stop:
            options["stop"] = self.stop

        payload = {
            "model": self.model.model,
            "messages": [
                {"role": "system", "content": JSON_INSTRUCTION},
                {"role": "user", "content": user_input},
            ],
            "stream": False,
            "options": options,
        }
        if response_format:
            payload["format"] = response_format
        elif self.response_format and self.response_format.get("type") == "json_object":
            payload["format"] = "json"

        try:
            resp = requests.post(self._url(), json=payload, timeout=300)
            resp.raise_for_status()
            response_text = resp.json().get("message", {}).get("content") or ""
            elapsed = time.monotonic() - started
            logger.info("Ollama prompt: %d chars in %.2fs", len(response_text), elapsed)
            return response_text
        except Exception as exc:
            logger.error("Ollama prompt error: %s", exc)
            return ""

    def chat_with_images(self, images, prompt, model=None):
        started = time.monotonic()
        model_name = model or self.model.model
        logger.info(
            "Ollama vision. Model=%s images=%d prompt=%r",
            model_name,
            len(images),
            prompt[:150],
        )

        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt, "images": images}],
            "stream": True,
            "options": {"temperature": 0.0, "num_ctx": 16384, "num_predict": 16384},
        }
        try:
            resp = requests.post(self._url(), json=payload, timeout=300)
            resp.raise_for_status()
        except Exception as exc:
            logger.error("Ollama vision error: %s", exc)
            return ""

        parts = []
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                chunk = json.loads(line)
                content = chunk.get("message", {}).get("content", "")
                if content:
                    parts.append(content)
            except json.JSONDecodeError:
                continue

        response_text = "".join(parts)
        elapsed = time.monotonic() - started
        logger.info("Ollama vision: %d chars in %.2fs", len(response_text), elapsed)
        return response_text
