import logging
import time

import google.generativeai as genai

GEMINI_MODEL = "models/gemini-3.1-flash-lite-preview"
logger = logging.getLogger(__name__)


class GeminiProvider:
    def __init__(self, model, response_format=None):
        genai.configure(api_key=model.api_key)
        self.model = model
        self.response_format = response_format

    def chat(self, messages):
        started = time.monotonic()
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "system":
                prompt_parts.append(f"System instruction:\n{content}\n")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
        prompt = "\n".join(prompt_parts)

        generation_config = {}
        if self.response_format and self.response_format.get("type") == "json_object":
            generation_config["response_mime_type"] = "application/json"

        model = genai.GenerativeModel(GEMINI_MODEL)
        response_text = model.generate_content(prompt, generation_config=generation_config).text
        elapsed = time.monotonic() - started
        logger.info("Gemini chat: %d chars in %.2fs", len(response_text or ""), elapsed)
        time.sleep(15)
        return {"choices": [{"message": {"content": response_text}}]}

    def prompt(self, user_input, response_format=None):
        started = time.monotonic()
        model = genai.GenerativeModel(GEMINI_MODEL)
        generation_config = {"response_mime_type": "application/json"}
        if response_format:
            generation_config["response_schema"] = response_format
        response_text = model.generate_content(
            user_input,
            generation_config=generation_config,
        ).text
        elapsed = time.monotonic() - started
        logger.info("Gemini prompt: %d chars in %.2fs", len(response_text or ""), elapsed)
        time.sleep(15)
        return response_text
