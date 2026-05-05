from __future__ import annotations

"""ReAct (Reason + Act) agentic loop for YTB report generation.

Flow per iteration
------------------
1. GENERATE  — draft a YTB report from the raw input (streamed to UI).
2. CRITIQUE  — review the draft against the source notes; get structured
               feedback (acceptable flag + issues list + field corrections).
3. CORRECT   — apply any field-level corrections from the critique inline
               (no extra LLM call needed when the model provides them).
4. REVISE    — if the critique is not acceptable and iterations remain,
               call the model with the issues list to produce a full
               corrected report (streamed to UI).
5. REPEAT    — loop from step 2 until acceptable or max_iterations reached.

The agent returns the best available report, falling back to whatever was
last produced rather than raising.
"""

import json
import logging
from pydantic import ValidationError

from scrum_updates_bot.core.models import CritiqueResult, FieldCorrection, YTBEntry, YTBReport
from scrum_updates_bot.core.prompts import (
    build_critique_system_prompt,
    build_critique_user_prompt,
    build_direct_generation_system_prompt,
    build_direct_generation_user_prompt,
    build_revision_system_prompt,
    build_revision_user_prompt,
)
from scrum_updates_bot.services.ollama import OllamaClient, OllamaError

logger = logging.getLogger(__name__)

_DEFAULT_MAX_ITERATIONS = 3


class ReActYTBAgent:
    """Iterative generate → critique → revise agent for YTB updates."""

    def __init__(self, client: OllamaClient, max_iterations: int = _DEFAULT_MAX_ITERATIONS) -> None:
        self.client = client
        self.max_iterations = max(1, max_iterations)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(
        self,
        raw_input: str,
        model_name: str,
        preset_name: str,
        progress_callback=None,
        stream_callback=None,
    ) -> YTBReport:
        """Run the ReAct loop and return the best report produced."""
        report: YTBReport | None = None
        last_issues: list[str] = []

        for iteration in range(1, self.max_iterations + 1):
            is_last = iteration == self.max_iterations

            # ── GENERATE or REVISE ──────────────────────────────────────
            if report is None:
                self._emit(progress_callback, f"[{iteration}/{self.max_iterations}] Drafting YTB update…")
                report = self._generate(
                    raw_input=raw_input,
                    model_name=model_name,
                    preset_name=preset_name,
                    progress_callback=progress_callback,
                    stream_callback=stream_callback,
                )
            else:
                self._emit(
                    progress_callback,
                    f"[{iteration}/{self.max_iterations}] Revising — addressing {len(last_issues)} issue(s)…",
                )
                revised = self._revise(
                    raw_input=raw_input,
                    report=report,
                    issues=last_issues,
                    model_name=model_name,
                    preset_name=preset_name,
                    stream_callback=stream_callback,
                )
                if revised is not None and revised.entries:
                    report = revised

            if report is None or not report.entries:
                # Generation completely failed — nothing to critique
                break

            # On the last iteration skip critique — just return what we have
            if is_last:
                self._emit(progress_callback, f"Completed after {iteration} iteration(s).")
                break

            # ── CRITIQUE ────────────────────────────────────────────────
            self._emit(
                progress_callback,
                f"[{iteration}/{self.max_iterations}] Reviewing draft for accuracy…",
            )
            critique = self._critique(raw_input=raw_input, report=report, model_name=model_name)

            # Apply any inline field corrections the critic provided
            if critique.corrections:
                applied = self._apply_corrections(report, critique.corrections)
                if applied:
                    self._emit(
                        progress_callback,
                        f"Applied {applied} inline correction(s) from review.",
                    )

            if critique.acceptable or not critique.issues:
                self._emit(progress_callback, f"Draft accepted after {iteration} iteration(s).")
                break

            last_issues = critique.issues
            self._emit(
                progress_callback,
                f"Review found {len(last_issues)} issue(s) — will revise.",
            )

        return report or YTBReport(entries=[], preset_name=preset_name)

    # ------------------------------------------------------------------
    # Private: generation
    # ------------------------------------------------------------------

    def _generate(
        self,
        raw_input: str,
        model_name: str,
        preset_name: str,
        progress_callback=None,
        stream_callback=None,
    ) -> YTBReport | None:
        try:
            accumulated = ""
            chunk_count = 0
            for accumulated in self.client.stream_json_text(
                model_name=model_name,
                system_prompt=build_direct_generation_system_prompt(preset_name),
                user_prompt=build_direct_generation_user_prompt(raw_input),
            ):
                chunk_count += 1
                if stream_callback:
                    stream_callback(accumulated)
                if progress_callback and (chunk_count == 1 or chunk_count % 10 == 0):
                    progress_callback(f"Streaming draft… {len(accumulated)} chars received.")
            if not accumulated:
                return None
            payload = self.client._coerce_json(accumulated)
            report = YTBReport(**payload)
            report.preset_name = preset_name
            return report
        except (OllamaError, ValidationError, ValueError) as exc:
            logger.warning("Generation failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Private: critique
    # ------------------------------------------------------------------

    def _critique(self, raw_input: str, report: YTBReport, model_name: str) -> CritiqueResult:
        report_json = report.model_dump_json(indent=2)
        try:
            payload = self.client.generate_json(
                model_name=model_name,
                system_prompt=build_critique_system_prompt(),
                user_prompt=build_critique_user_prompt(raw_input, report_json),
            )
            result = CritiqueResult(**payload)
            return result
        except (OllamaError, ValidationError, ValueError) as exc:
            logger.warning("Critique failed: %s", exc)
            # If critique fails, treat the draft as acceptable to avoid infinite retry
            return CritiqueResult(acceptable=True)

    # ------------------------------------------------------------------
    # Private: revision
    # ------------------------------------------------------------------

    def _revise(
        self,
        raw_input: str,
        report: YTBReport,
        issues: list[str],
        model_name: str,
        preset_name: str,
        stream_callback=None,
    ) -> YTBReport | None:
        report_json = report.model_dump_json(indent=2)
        try:
            accumulated = ""
            for accumulated in self.client.stream_json_text(
                model_name=model_name,
                system_prompt=build_revision_system_prompt(preset_name),
                user_prompt=build_revision_user_prompt(raw_input, report_json, issues),
            ):
                if stream_callback:
                    stream_callback(accumulated)
            if not accumulated:
                return None
            payload = self.client._coerce_json(accumulated)
            revised = YTBReport(**payload)
            revised.preset_name = preset_name
            return revised
        except (OllamaError, ValidationError, ValueError) as exc:
            logger.warning("Revision failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Private: inline correction application
    # ------------------------------------------------------------------

    def _apply_corrections(self, report: YTBReport, corrections: list[FieldCorrection]) -> int:
        """Apply field-level corrections directly to a report's entries in-place.

        Returns the number of corrections successfully applied.
        """
        applied = 0
        for correction in corrections:
            idx = correction.entry_index
            if idx < 0 or idx >= len(report.entries):
                logger.debug("Correction index %d out of range (entries: %d)", idx, len(report.entries))
                continue
            entry = report.entries[idx]
            field = correction.field
            value = correction.corrected_value
            try:
                if field == "yesterday" and isinstance(value, str) and value.strip():
                    entry.yesterday = value.strip()
                    applied += 1
                elif field == "today" and isinstance(value, str) and value.strip():
                    entry.today = value.strip()
                    applied += 1
                elif field == "blockers" and isinstance(value, str) and value.strip():
                    entry.blockers = value.strip()
                    applied += 1
                elif field == "completed" and isinstance(value, bool):
                    entry.completed = value
                    applied += 1
            except Exception as exc:
                logger.debug("Failed to apply correction %s: %s", correction, exc)
        return applied

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _emit(callback, message: str) -> None:
        if callback:
            callback(message)
