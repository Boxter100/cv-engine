import os

import httpx


class LlamaServerClient:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        thinking: bool | None = None,
    ):
        self.base_url = (
            base_url
            or os.getenv("LLAMA_SERVER_URL")
            or "http://127.0.0.1:8080/v1"
        ).rstrip("/")

        self.model = model or os.getenv("LLAMA_MODEL") or None

        if timeout is None:
            timeout = float(os.getenv("LLAMA_TIMEOUT", "1800"))

        self.timeout = timeout

        if thinking is None:
            flag = os.getenv("LLAMA_THINKING")
            thinking = (
                False
                if flag is None
                else flag.lower() in {"1", "true", "yes"}
            )

        self.thinking = thinking

        self._resolved_model: str | None = None

    def models(self) -> dict:
        response = httpx.get(
            f"{self.base_url}/models",
            timeout=min(self.timeout, 60.0),
        )
        response.raise_for_status()
        return response.json()

    def _resolve_model(self) -> str:
        if self._resolved_model:
            return self._resolved_model

        if self.model:
            self._resolved_model = self.model
            return self._resolved_model

        data = self.models()

        models = data.get("data", [])
        if not models:
            raise RuntimeError("llama-server no tiene modelos disponibles.")

        self._resolved_model = models[0]["id"]
        return self._resolved_model

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> str:
        model = self._resolve_model()

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if self.thinking is not None:
            payload["chat_template_kwargs"] = {
                "enable_thinking": self.thinking
            }

        response = httpx.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            timeout=self.timeout,
        )

        response.raise_for_status()

        data = response.json()

        choice = data["choices"][0]
        content = choice["message"].get("content") or ""

        if not content.strip():
            reason = choice.get("finish_reason")
            completion = data.get("usage", {}).get("completion_tokens")

            if reason == "length":
                raise RuntimeError(
                    f"El modelo agotó max_tokens={max_tokens} sin devolver "
                    "contenido. Sube max_tokens o revisa si el modelo está "
                    f"razonando (completion_tokens={completion})."
                )

            raise RuntimeError(
                "El modelo devolvió una respuesta vacía "
                f"(finish_reason={reason})."
            )

        return content
