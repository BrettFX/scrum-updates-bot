from __future__ import annotations

from pydantic import ValidationError

from scrum_updates_bot.core.fallbacks import fallback_generate, fallback_normalize, has_structured_story_blocks
from scrum_updates_bot.core.models import NormalizedStoryCollection, YTBReport
from scrum_updates_bot.core.prompts import (
    build_normalization_system_prompt,
    build_normalization_user_prompt,
)
from scrum_updates_bot.core.react_agent import ReActYTBAgent
from scrum_updates_bot.services.ollama import OllamaClient, OllamaError


class YTBGeneratorService:
    """Entry point for YTB report generation.

    Delegates to :class:`~scrum_updates_bot.core.react_agent.ReActYTBAgent`
    for all LLM-based generation.  The service layer adds:
    - result caching (keyed on raw_input + model + preset)
    - structured-notes pre-normalisation path
    - deterministic fallback when Ollama is unreachable or the agent returns nothing
    """

    def __init__(self, ollama_client: OllamaClient, max_react_iterations: int = 3) -> None:
        self.ollama_client = ollama_client
        self._agent = ReActYTBAgent(ollama_client, max_iterations=max_react_iterations)
        self._report_cache: dict[tuple[str, str, str], YTBReport] = {}

    def generate_report(
        self,
        raw_input: str,
        model_name: str,
        preset_name: str,
        progress_callback=None,
        stream_callback=None,
    ) -> YTBReport:
        cache_key = (raw_input.strip(), model_name, preset_name)
        cached = self._report_cache.get(cache_key)
        if cached is not None:
            if progress_callback:
                progress_callback("Using cached result.")
            return cached.model_copy(deep=True)

        # ── Structured-block path ────────────────────────────────────────
        # When the input contains recognisable "Story title is …" blocks,
        # pre-normalise deterministically so the agent receives clean,
        # structured text rather than raw freeform input.
        if has_structured_story_blocks(raw_input):
            if progress_callback:
                progress_callback("Detected structured story blocks — normalising notes…")
            normalized = fallback_normalize(raw_input)
            structured_text = _normalized_to_text(normalized)
            report = self._agent.run(
                raw_input=structured_text,
                model_name=model_name,
                preset_name=preset_name,
                progress_callback=progress_callback,
                stream_callback=stream_callback,
            )
            if report.entries:
                _restore_ticket_metadata(report, normalized)
                self._report_cache[cache_key] = report
                return report.model_copy(deep=True)

            # Agent produced nothing — fall back to deterministic formatter
            if progress_callback:
                progress_callback("Agent returned empty report — using local formatting.")
            report = fallback_generate(normalized, preset_name)
            self._report_cache[cache_key] = report
            return report.model_copy(deep=True)

        # ── Direct / freeform path ───────────────────────────────────────
        report = self._agent.run(
            raw_input=raw_input,
            model_name=model_name,
            preset_name=preset_name,
            progress_callback=progress_callback,
            stream_callback=stream_callback,
        )
        if report.entries:
            self._report_cache[cache_key] = report
            return report.model_copy(deep=True)

        # Agent produced nothing — normalise then use deterministic fallback
        if progress_callback:
            progress_callback("Agent returned empty report — normalising notes as fallback…")
        normalized = self.normalize(raw_input=raw_input, model_name=model_name)
        if not normalized.stories:
            return YTBReport(entries=[], preset_name=preset_name)
        report = fallback_generate(normalized, preset_name)
        self._report_cache[cache_key] = report
        return report.model_copy(deep=True)

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalized_to_text(normalized: NormalizedStoryCollection) -> str:
    """Render a NormalizedStoryCollection back to readable text for the agent."""
    lines: list[str] = []
    for ns in normalized.stories:
        lines.append(f"Story: {ns.story.title}")
        if ns.story.ticket_id:
            lines.append(f"Ticket: {ns.story.ticket_id}")
        if ns.story.status and ns.story.status != "unknown":
            lines.append(f"Status: {ns.story.status}")
        if ns.yesterday_notes:
            lines.append(f"Yesterday: {ns.yesterday_notes}")
        if ns.today_notes:
            lines.append(f"Today: {ns.today_notes}")
        if ns.blockers:
            lines.append(f"Blockers: {ns.blockers}")
        lines.append("")
    return "\n".join(lines).strip()


def _restore_ticket_metadata(report: YTBReport, normalized: NormalizedStoryCollection) -> None:
    """Copy ticket ID / URL from normalised source into entries that are missing them.

    Unlike the old _patch_ticket_metadata, this does NOT override the agent's
    judgment on yesterday/today/completed — only fills in metadata fields.
    """
    for entry, ns in zip(report.entries, normalized.stories):
        if not entry.ticket_id and ns.story.ticket_id:
            entry.ticket_id = ns.story.ticket_id
        if not entry.ticket_url and ns.story.ticket_url:
            entry.ticket_url = ns.story.ticket_url