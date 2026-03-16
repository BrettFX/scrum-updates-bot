from __future__ import annotations

import re

from scrum_updates_bot.core.models import NormalizedStory, NormalizedStoryCollection, StoryReference, YTBEntry, YTBReport


STORY_BLOCK_PATTERN = re.compile(
    r"Story title is\s+\"(?P<title>.+?)\"\s*(?P<url>https?://\S+)?\s*(?P<body>.*?)(?=(?:Story title is\s+\")|\Z)",
    re.DOTALL,
)

TICKET_PATTERN = re.compile(r"\(([A-Z][A-Z0-9]+-\d+)\)")


def _normalize_text(text: str) -> str:
    return " ".join(text.split()).strip()


def _ensure_sentence(text: str) -> str:
    cleaned = _normalize_text(text)
    if not cleaned:
        return cleaned
    if cleaned.endswith((".", "!", "?")):
        return cleaned
    return f"{cleaned}."


def _shorten_text(text: str, max_words: int) -> str:
    cleaned = _normalize_text(text)
    words = cleaned.split()
    if len(words) <= max_words:
        return _ensure_sentence(cleaned)
    shortened = " ".join(words[:max_words]).rstrip(",;:")
    return f"{shortened}..."


def _leadership_phrase(story_title: str, text: str, prefix: str) -> str:
    cleaned = _normalize_text(text)
    if not cleaned or cleaned == "None":
        return "None"
    if cleaned == "None (Complete)":
        return cleaned
    lowered = cleaned[0].lower() + cleaned[1:] if len(cleaned) > 1 else cleaned.lower()
    return _ensure_sentence(f"{prefix} {story_title} by {lowered.rstrip('.')}" )


def _apply_preset(yesterday: str, today: str, blockers: str, story_title: str, preset_name: str) -> tuple[str, str, str]:
    if preset_name == "Leadership Update":
        leadership_yesterday = yesterday if yesterday == "None (Complete)" else _leadership_phrase(story_title, yesterday, "Advanced")
        leadership_today = today if today == "None (Complete)" else _leadership_phrase(story_title, today, "Continuing")
        leadership_blockers = blockers if blockers == "None" else _ensure_sentence(_normalize_text(blockers))
        return leadership_yesterday, leadership_today, leadership_blockers

    if preset_name == "Concise Standup":
        concise_yesterday = yesterday if yesterday == "None (Complete)" else _shorten_text(yesterday, 9)
        concise_today = today if today == "None (Complete)" else _shorten_text(today, 10)
        concise_blockers = blockers if blockers == "None" else _shorten_text(blockers, 8)
        return concise_yesterday, concise_today, concise_blockers

    return _ensure_sentence(yesterday) if yesterday != "None (Complete)" else yesterday, _ensure_sentence(today) if today != "None (Complete)" else today, blockers or "None"


def has_structured_story_blocks(raw_input: str) -> bool:
    return bool(STORY_BLOCK_PATTERN.search(raw_input))


def fallback_normalize(raw_input: str) -> NormalizedStoryCollection:
    stories: list[NormalizedStory] = []
    for match in STORY_BLOCK_PATTERN.finditer(raw_input):
        title = match.group("title").strip()
        url = (match.group("url") or "").strip() or None
        body = (match.group("body") or "").strip()
        ticket_match = TICKET_PATTERN.search(title)
        ticket_id = ticket_match.group(1) if ticket_match else None
        lowered = body.lower()
        status = "done" if re.search(r"\bdone\b|\bcomplete\b", lowered) else "in_progress"
        cleaned_body = " ".join(body.split())

        yesterday = None
        today = None
        blockers = "None"

        if status == "done":
            yesterday = "None (Complete)"
            today = "None (Complete)"
        elif cleaned_body:
            sentences = re.split(r"(?<=[.!?])\s+", cleaned_body)
            if len(sentences) == 1:
                yesterday = sentences[0].strip()
                today = "Continue refining and advancing this story based on current progress."
            else:
                yesterday = sentences[0].strip()
                today = " ".join(sentence.strip() for sentence in sentences[1:] if sentence.strip()) or "Continue advancing this story today."
        else:
            yesterday = "Worked on the story based on current priorities."
            today = "Continue moving the story forward today."

        stories.append(
            NormalizedStory(
                story=StoryReference(
                    title=title,
                    ticket_id=ticket_id,
                    ticket_url=url,
                    status=status,
                ),
                source_summary=cleaned_body,
                yesterday_notes=yesterday,
                today_notes=today,
                blockers=blockers,
            )
        )

    if stories:
        return NormalizedStoryCollection(stories=stories)

    condensed = " ".join(raw_input.split())
    if not condensed:
        return NormalizedStoryCollection()

    return NormalizedStoryCollection(
        stories=[
            NormalizedStory(
                story=StoryReference(title="General Scrum Update", status="in_progress"),
                source_summary=condensed,
                yesterday_notes=condensed[:180],
                today_notes="Continue advancing the active work items described in the notes.",
                blockers="None",
            )
        ]
    )


def fallback_generate(normalized: NormalizedStoryCollection, preset_name: str) -> YTBReport:
    entries: list[YTBEntry] = []
    for item in normalized.stories:
        completed = item.story.status == "done"
        yesterday = item.yesterday_notes or ("None (Complete)" if completed else "Worked on the story yesterday.")
        today = item.today_notes or ("None (Complete)" if completed else "Continue the planned work for this story today.")
        blockers = item.blockers or "None"
        yesterday, today, blockers = _apply_preset(yesterday, today, blockers, item.story.title, preset_name)
        entries.append(
            YTBEntry(
                story_title=item.story.title,
                ticket_id=item.story.ticket_id,
                ticket_url=item.story.ticket_url,
                yesterday=yesterday,
                today=today,
                blockers=blockers,
                completed=completed,
            )
        )
    return YTBReport(entries=entries, preset_name=preset_name)