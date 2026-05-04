from __future__ import annotations

import json
from typing import Any

import httpx


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, base_url: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def is_available(self) -> bool:
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=5.0)
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    def list_models(self) -> list[str]:
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=10.0)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaError(f"Failed to list Ollama models: {exc}") from exc
        return [item.get("name", "") for item in data.get("models", []) if item.get("name")]

    def pull_model(self, model_name: str) -> dict[str, Any]:
        try:
            response = httpx.post(
                f"{self.base_url}/api/pull",
                json={"name": model_name, "stream": False},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaError(f"Failed to pull model '{model_name}': {exc}") from exc

    def pull_model_stream(self, model_name: str):
        """Stream pull progress.  Yields ``(status, completed, total)`` tuples where
        *completed* and *total* are byte counts (0 when not applicable)."""
        timeout = httpx.Timeout(connect=30.0, read=60.0, write=None, pool=None)
        try:
            with httpx.stream(
                "POST",
                f"{self.base_url}/api/pull",
                json={"name": model_name, "stream": True},
                timeout=timeout,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    yield data.get("status", ""), data.get("completed", 0), data.get("total", 0)
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
            raise OllamaError(f"Failed to pull model '{model_name}': {exc}") from exc

    def delete_model(self, model_name: str) -> None:
        """Delete a locally installed model."""
        try:
            response = httpx.delete(
                f"{self.base_url}/api/delete",
                json={"name": model_name},
                timeout=30.0,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise OllamaError(f"Failed to delete model '{model_name}': {exc}") from exc

    def list_models_detail(self) -> list[dict[str, Any]]:
        """Return full model metadata dicts (name, size, modified_at, details) from /api/tags."""
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=10.0)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaError(f"Failed to list Ollama models: {exc}") from exc
        return data.get("models", [])

    def generate_json(self, model_name: str, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload = {
            "model": model_name,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "format": "json",
        }
        try:
            response = httpx.post(f"{self.base_url}/api/generate", json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            raw = data.get("response", "{}")
            return self._coerce_json(raw)
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
            raise OllamaError(f"Ollama generation failed: {exc}") from exc

    def stream_json_text(self, model_name: str, system_prompt: str, user_prompt: str):
        payload = {
            "model": model_name,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": True,
            "format": "json",
        }
        accumulated = ""
        try:
            with httpx.stream("POST", f"{self.base_url}/api/generate", json=payload, timeout=self.timeout) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    chunk = data.get("response", "")
                    if chunk:
                        accumulated += chunk
                        yield accumulated
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
            raise OllamaError(f"Ollama streaming generation failed: {exc}") from exc

    def _coerce_json(self, raw: str) -> dict[str, Any]:
        raw = raw.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                return json.loads(raw[start : end + 1])
            raise