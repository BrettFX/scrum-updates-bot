from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class StoryReference(BaseModel):
    title: str = Field(..., min_length=1)
    ticket_id: str | None = None
    ticket_url: str | None = None
    status: Literal["todo", "in_progress", "done", "unknown"] = "unknown"


class NormalizedStory(BaseModel):
    story: StoryReference
    source_summary: str = ""
    yesterday_notes: str | None = None
    today_notes: str | None = None
    blockers: str | None = None


class NormalizedStoryCollection(BaseModel):
    stories: list[NormalizedStory] = Field(default_factory=list)


class YTBEntry(BaseModel):
    story_title: str = Field(..., min_length=1)
    ticket_id: str | None = None
    ticket_url: str | None = None
    yesterday: str = Field(..., min_length=1)
    today: str = Field(..., min_length=1)
    blockers: str = Field(..., min_length=1)
    completed: bool = False


class YTBReport(BaseModel):
    entries: list[YTBEntry] = Field(default_factory=list)
    preset_name: str = "Standard YTB"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class FieldCorrection(BaseModel):
    """A targeted correction produced by the critique step."""

    entry_index: int
    field: Literal["yesterday", "today", "blockers", "completed"]
    corrected_value: Any  # str for text fields, bool for completed
    reason: str = ""


class CritiqueResult(BaseModel):
    """Structured output from the ReAct critique step."""

    acceptable: bool = False
    issues: list[str] = Field(default_factory=list)
    corrections: list[FieldCorrection] = Field(default_factory=list)


class DraftDocument(BaseModel):
    name: str = Field(..., min_length=1)
    raw_input: str = ""
    output_html: str = ""
    output_text: str = ""
    activity_log: list[str] = Field(default_factory=list)
    report: YTBReport | None = None
    preset_name: str = "Standard YTB"
    model_name: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PromptTemplateDocument(BaseModel):
    name: str = Field(..., min_length=1)
    content: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AppSettings(BaseModel):
    ollama_base_url: str = "http://127.0.0.1:11434"
    model_name: str = "qwen2.5:7b-instruct"
    selected_preset: str = "Standard YTB"
    last_draft_name: str | None = None
    window_width: int = 1440
    window_height: int = 920
    splitter_left_width: int = 560
    splitter_right_width: int = 760