from __future__ import annotations

from pydantic import ValidationError

from scrum_updates_bot.core.fallbacks import fallback_generate, fallback_normalize, has_structured_story_blocks
from scrum_updates_bot.core.models import NormalizedStoryCollection, YTBReport
from scrum_updates_bot.core.prompts import (
    build_direct_generation_system_prompt,
    build_direct_generation_user_prompt,
    build_generation_system_prompt,
    build_generation_user_prompt,
    build_normalization_system_prompt,
    build_normalization_user_prompt,
)
from scrum_updates_bot.services.ollama import OllamaClient, OllamaError


class YTBGeneratorService:
    def __init__(self, ollama_client: OllamaClient) -> None:
        self.ollama_client = ollama_client
        self._report_cache: dict[tuple[str, str, str], YTBReport] = {}

    def generate_report(self, raw_input: str, model_name: str, preset_name: str, progress_callback=None) -> YTBReport:
        cache_key = (raw_input.strip(), model_name, preset_name)
        cached_report = self._report_cache.get(cache_key)
        if cached_report is not None:
            if progress_callback:
                progress_callback("Using cached result.")
            return cached_report.model_copy(deep=True)

        if has_structured_story_blocks(raw_input):
            if progress_callback:
                progress_callback(f"Formatting structured notes using the {preset_name} preset.")
            normalized = fallback_normalize(raw_input)
            report = fallback_generate(normalized, preset_name)
            self._report_cache[cache_key] = report
            return report.model_copy(deep=True)

        if progress_callback:
            progress_callback(f"Contacting {model_name} for direct generation...")
        direct = self._generate_direct(raw_input=raw_input, model_name=model_name, preset_name=preset_name, progress_callback=progress_callback)
        if direct is not None and direct.entries:
            self._report_cache[cache_key] = direct
            return direct.model_copy(deep=True)

        if progress_callback:
            progress_callback("Direct generation incomplete. Normalizing notes...")
        normalized = self.normalize(raw_input=raw_input, model_name=model_name)
        if not normalized.stories:
            return YTBReport(entries=[], preset_name=preset_name)

        try:
            if progress_callback:
                progress_callback("Rendering final YTB report...")
            payload = self.ollama_client.generate_json(
                model_name=model_name,
                system_prompt=build_generation_system_prompt(preset_name),
                user_prompt=build_generation_user_prompt(normalized),
            )
            report = YTBReport(**payload)
            report.preset_name = preset_name
            self._report_cache[cache_key] = report
            return report.model_copy(deep=True)
        except (OllamaError, ValidationError, ValueError):
            report = fallback_generate(normalized, preset_name)
            self._report_cache[cache_key] = report
            return report.model_copy(deep=True)

    def _generate_direct(self, raw_input: str, model_name: str, preset_name: str, progress_callback=None) -> YTBReport | None:
        try:
            streamed_text = ""
            chunk_count = 0
            for streamed_text in self.ollama_client.stream_json_text(
                model_name=model_name,
                system_prompt=build_direct_generation_system_prompt(preset_name),
                user_prompt=build_direct_generation_user_prompt(raw_input),
            ):
                chunk_count += 1
                if progress_callback and (chunk_count == 1 or chunk_count % 10 == 0):
                    progress_callback(f"Streaming model response... {len(streamed_text)} characters received.")
            if not streamed_text:
                return None
            payload = self.ollama_client._coerce_json(streamed_text)
            report = YTBReport(**payload)
            report.preset_name = preset_name
            return report
        except (OllamaError, ValidationError, ValueError):
            return None

    def normalize(self, raw_input: str, model_name: str) -> NormalizedStoryCollection:
        if not raw_input.strip():
            return NormalizedStoryCollection()
        try:
            payload = self.ollama_client.generate_json(
                model_name=model_name,
                system_prompt=build_normalization_system_prompt(),
                user_prompt=build_normalization_user_prompt(raw_input),
            )
            return NormalizedStoryCollection(**payload)
        except (OllamaError, ValidationError, ValueError):
            return fallback_normalize(raw_input)