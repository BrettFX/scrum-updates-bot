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


def _first_sentence(text: str) -> str:
    """Return the first complete sentence; avoids mid-thought word truncation."""
    cleaned = _normalize_text(text)
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return _ensure_sentence(parts[0]) if parts else _ensure_sentence(cleaned)


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
        concise_yesterday = yesterday if yesterday == "None (Complete)" else _first_sentence(yesterday)
        concise_today = today if today == "None (Complete)" else _first_sentence(today)
        concise_blockers = blockers if blockers == "None" else _first_sentence(blockers)
        return concise_yesterday, concise_today, concise_blockers

    return _ensure_sentence(yesterday) if yesterday != "None (Complete)" else yesterday, _ensure_sentence(today) if today != "None (Complete)" else today, blockers or "None"


_FUTURE_MARKERS = re.compile(
    r"\b(going to|will be|will |plan to|planning to|intend to|want to|"
    r"today i|this morning|focus for today|continue with|next step|working on next|"
    r"scheduled to|aiming to|hoping to)\b",
    re.IGNORECASE,
)

_BLOCKER_MARKERS = re.compile(
    r"\b(blocked by|waiting for|waiting on|need to find out|needs to be assigned|"
    r"unclear who|no owner|haven't heard|no response from|"
    r"pending (?:approval|review|response|sign.off)|"
    r"need to (?:identify|determine|figure out|find out)|"
    r"have not heard|not yet assigned|responsible (?:party|person) (?:is |has )?not)\b",
    re.IGNORECASE,
)


def _strip_filler_openers(text: str) -> str:
    """Remove leading first-person pronouns and connector words from a sentence."""
    return re.sub(
        r"^(I\s+(also\s+|additionally\s+)?|also[,\s]+|additionally[,\s]+|furthermore[,\s]+|moreover[,\s]+)",
        "",
        text.strip(),
        flags=re.IGNORECASE,
    ).strip()


def _compress_to_one_sentence(phrases: list[str]) -> str:
    """Compress a list of action phrases into one clean professional sentence."""
    if not phrases:
        return ""
    cleaned = []
    for phrase in phrases:
        phrase = _strip_filler_openers(phrase).rstrip(".!?,;:").strip()
        if phrase:
            cleaned.append(phrase[0].upper() + phrase[1:])
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return _ensure_sentence(cleaned[0])
    if len(cleaned) == 2:
        second = cleaned[1][0].lower() + cleaned[1][1:]
        return _ensure_sentence(f"{cleaned[0]} and {second}")
    head = cleaned[0]
    mid = ", ".join(c[0].lower() + c[1:] for c in cleaned[1:-1])
    last = cleaned[-1][0].lower() + cleaned[-1][1:]
    return _ensure_sentence(f"{head}, {mid}, and {last}")


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
        status = "done" if re.search(r"(?:^|\s)(?:done|complete)\.?$", lowered) else "in_progress"
        cleaned_body = " ".join(body.split())

        yesterday = None
        today = None
        blockers = "None"

        if status == "done":
            yesterday = "Completed the story work."
            today = "No further work planned."
        elif cleaned_body:
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned_body) if s.strip()]
            past_sentences = [s for s in sentences if not _FUTURE_MARKERS.search(s) and not _BLOCKER_MARKERS.search(s)]
            planned_sentences = [s for s in sentences if _FUTURE_MARKERS.search(s)]
            blocker_sentences = [s for s in sentences if _BLOCKER_MARKERS.search(s)]
            yesterday = _compress_to_one_sentence(past_sentences) if past_sentences else _compress_to_one_sentence(sentences[:1])
            today = _compress_to_one_sentence(planned_sentences) if planned_sentences else f"Will continue advancing {title}."
            if blocker_sentences:
                blockers = _compress_to_one_sentence(blocker_sentences)
        else:
            yesterday = f"Made progress on {title}."
            today = f"Will continue advancing {title}."

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
        yesterday = item.yesterday_notes or ("Completed the story work." if completed else "Worked on the story yesterday.")
        today = item.today_notes or ("No further work planned." if completed else "Will continue the planned work.")
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