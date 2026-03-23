from __future__ import annotations

import json

from scrum_updates_bot.core.models import NormalizedStoryCollection


PRESET_GUIDANCE = {
    "Standard YTB": (
        "Write concisely in professional third-person voice. "
        "Each Yesterday and Today must be one sentence that captures the key outcome or goal, "
        "not a list of individual steps."
    ),
    "Leadership Update": (
        "Use executive-friendly, outcome-focused language with no implementation detail. "
        "Write in third person. Yesterday begins with 'Advanced'; Today begins with 'Continuing'. "
        "One sentence per field."
    ),
    "Concise Standup": (
        "Keep each field to one short sentence suitable for a fast standup readout. "
        "Write in third person. Capture only the essential action and outcome."
    ),
}


def build_normalization_system_prompt() -> str:
    return (
        "You normalize scrum notes into structured JSON. "
        "Infer stories, ticket IDs, URLs, completion state, yesterday work, today plans, and blockers. "
        "Distill each note to its core outcome — summarize in your own words and do not copy the raw input verbatim. "
        "If a story is clearly complete, mark status as done and use concise completed-state phrasing. "
        "Return only valid JSON matching the requested schema."
    )


def build_normalization_user_prompt(raw_input: str) -> str:
    schema = {
        "stories": [
            {
                "story": {
                    "title": "Full story title",
                    "ticket_id": "ABC-1234",
                    "ticket_url": "https://jira.example/browse/ABC-1234",
                    "status": "in_progress"
                },
                "source_summary": "What the user wrote about this story.",
                "yesterday_notes": "What was worked on yesterday.",
                "today_notes": "What is planned today.",
                "blockers": "Any blockers or None"
            }
        ]
    }
    return (
        "Normalize the following scrum notes into the JSON schema below. "
        "Support either structured examples or messy freeform notes. "
        "When information is missing, infer cautiously and use null only if truly unknown.\n\n"
        f"JSON schema example:\n{json.dumps(schema, indent=2)}\n\n"
        f"Raw input:\n{raw_input.strip()}"
    )


def build_generation_system_prompt(preset_name: str) -> str:
    guidance = PRESET_GUIDANCE.get(preset_name, PRESET_GUIDANCE["Standard YTB"])
    return (
        "You generate polished Yesterday, Today, Blockers status updates from structured scrum data. "
        "Synthesize multiple actions into one cohesive sentence per field — do not list every step or copy source text verbatim. "
        "Use professional third-person voice with no personal pronouns or names. "
        f"{guidance} "
        "Return only valid JSON matching the requested schema."
    )


def build_direct_generation_system_prompt(preset_name: str) -> str:
    guidance = PRESET_GUIDANCE.get(preset_name, PRESET_GUIDANCE["Standard YTB"])
    return (
        "You generate polished Yesterday, Today, Blockers status updates directly from raw scrum notes. "
        "The input may be structured or messy. Infer story titles, ticket IDs, URLs, completion state, yesterday work, today plans, and blockers. "
        "Synthesize multiple actions into one cohesive sentence per field — do not list every step or copy input text verbatim. "
        "Use professional third-person voice with no personal pronouns or names. "
        "If a story is complete, use None (Complete) for Yesterday and Today. "
        f"{guidance} "
        "Return only valid JSON matching the requested schema."
    )


def build_generation_user_prompt(normalized: NormalizedStoryCollection) -> str:
    schema = {
        "entries": [
            {
                "story_title": "Story title",
                "ticket_id": "ABC-1234",
                "ticket_url": "https://jira.example/browse/ABC-1234",
                "yesterday": "One sentence",
                "today": "One or two sentences",
                "blockers": "None",
                "completed": False,
            }
        ]
    }
    return (
        "Turn the normalized stories into a polished YTB report. "
        "For each entry write one concise sentence for Yesterday (what was accomplished) and one for Today (what is planned). "
        "Synthesize the key outcome in your own words — do not echo or closely paraphrase the source_summary. "
        "Preserve ticket metadata and mark completed stories as None (Complete) where appropriate.\n\n"
        f"Target schema:\n{json.dumps(schema, indent=2)}\n\n"
        f"Normalized stories:\n{normalized.model_dump_json(indent=2)}"
    )


def build_direct_generation_user_prompt(raw_input: str) -> str:
    schema = {
        "entries": [
            {
                "story_title": "Story title",
                "ticket_id": "ABC-1234",
                "ticket_url": "https://jira.example/browse/ABC-1234",
                "yesterday": "One sentence",
                "today": "One or two sentences",
                "blockers": "None",
                "completed": False,
            }
        ]
    }
    return (
        "Turn the following scrum notes into a polished YTB report. "
        "For each story write one concise sentence for Yesterday and one for Today, "
        "synthesizing the key outcome in your own words — do not copy the notes verbatim. "
        "Handle both clean structured and messy freeform input.\n\n"
        f"Target schema:\n{json.dumps(schema, indent=2)}\n\n"
        f"Raw input:\n{raw_input.strip()}"
    )