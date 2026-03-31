from __future__ import annotations

import json

from scrum_updates_bot.core.models import NormalizedStoryCollection


PRESET_GUIDANCE = {
    "Standard YTB": (
        "Write concisely in professional third-person voice. "
        "Yesterday must be past tense (e.g., 'Completed X', 'Implemented Y'). "
        "Today must be future tense (e.g., 'Will continue X', 'Will focus on Y'). "
        "Each field must be one sentence capturing the key outcome or goal, not a list of steps."
    ),
    "Leadership Update": (
        "Use executive-friendly, outcome-focused language with no implementation detail. "
        "Write in third person. Yesterday begins with 'Advanced'; Today begins with 'Will continue'. "
        "One sentence per field."
    ),
    "Concise Standup": (
        "Keep each field to one short sentence suitable for a fast standup readout. "
        "Write in third person. Yesterday is past tense; Today is future tense and starts with 'Will'. "
        "Capture only the essential action and outcome."
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
        "Yesterday must be past tense describing what was accomplished before today. "
        "Today must be future tense describing the specific planned work (e.g., 'Will finalize the API changes', 'Will begin integration testing'). "
        "Never write Today as 'Will continue advancing [story title]' — describe the actual work, not the ticket name. "
        "Events described as happening 'this morning' or 'today' belong in Today, not Yesterday. "
        "When notes mention uncertainty, missing owners, waiting on others, or needing to identify responsible parties, "
        "surface those as a specific Blockers sentence rather than leaving Blockers as None. "
        "CRITICAL: if the notes say 'Done', 'Complete', or the story status is done, set completed=true and use "
        "exactly the string 'None (Complete)' for both yesterday and today. Do NOT invent content for completed stories. "
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
        "Yesterday must be past tense describing what was accomplished before today. "
        "Today must be future tense describing the specific planned work (e.g., 'Will finalize the API changes', 'Will begin integration testing'). "
        "Never write Today as 'Will continue advancing [story title]' — describe the actual work, not the ticket name. "
        "Events described as happening 'this morning' or 'today' belong in Today, not Yesterday. "
        "When notes mention uncertainty, missing owners, waiting on others, or needing to identify responsible parties, "
        "surface those as a specific Blockers sentence rather than leaving Blockers as None. "
        "CRITICAL: if the notes say 'Done', 'Complete', or similar, set completed=true and use "
        "exactly the string 'None (Complete)' for both yesterday and today. Do NOT invent content for completed stories. "
        f"{guidance} "
        "Return only valid JSON matching the requested schema."
    )


_FEW_SHOT_EXAMPLES = """
EXAMPLES — these show the required OUTPUT FORMAT and style only.
WARNING: Do NOT copy or reuse any content from these examples in your output.
Base your output SOLELY on the input provided at the end of this prompt.

Example 1 (data pipeline, multi-step progress):
  source: "Spent the day tuning the ETL job for the customer churn dataset. Had to rewrite the
           deduplication step because it was producing duplicate rows downstream. Pipeline now
           runs end-to-end cleanly in staging. Will focus on scheduling and monitoring alerts today."
  → yesterday: "Refactored the ETL deduplication logic and validated the customer churn pipeline end-to-end in staging."
  → today:     "Will configure the pipeline schedule and set up monitoring alerts for production readiness."
  → blockers:  "None"
  → completed: false

Example 2 (no progress yesterday, this-morning event, missing owner):
  source: "No movement on this yesterday. Heard this morning that the security team needs to review
           the new IAM role changes before we can proceed. Still not sure who owns final approval."
  → yesterday: "No progress made."
  → today:     "Will follow up with the security team on the IAM role review and clarify approval ownership."
  → blockers:  "Final approver for IAM role changes has not yet been identified."
  → completed: false

Example 3 (bug fix, waiting on review):
  source: "Fixed the login timeout bug and deployed the fix to staging. Waiting for QA sign-off
           before it can go to production."
  → yesterday: "Resolved the login timeout bug and deployed the fix to the staging environment."
  → today:     "Will monitor staging and coordinate production release once QA approves."
  → blockers:  "Pending QA sign-off before production deployment."
  → completed: false

Example 4 (story is complete — note says 'Done' or 'Complete'):
  source: "Done."
  → yesterday: "None (Complete)"
  → today:     "None (Complete)"
  → blockers:  "None"
  → completed: true
  IMPORTANT: when a story is done/complete, BOTH yesterday AND today must be exactly the string
  "None (Complete)" and completed must be true. Do NOT invent or infer extra details.
"""


def build_generation_user_prompt(normalized: NormalizedStoryCollection) -> str:
    story_count = len(normalized.stories)
    schema = {
        "entries": [
            {
                "story_title": "Story title",
                "ticket_id": "ABC-1234",
                "ticket_url": "https://jira.example/browse/ABC-1234",
                "yesterday": "Completed the planned feature work.",
                "today": "Will continue refining and testing the implementation.",
                "blockers": "None",
                "completed": False,
            }
        ]
    }
    return (
        f"Turn ALL {story_count} normalized stories into a polished YTB report. "
        f"You MUST produce exactly {story_count} entries in the output — one entry per story, in the same order. "
        "For each entry write one concise past-tense sentence for Yesterday and one future-tense sentence for Today. "
        "Synthesize the key outcome in your own words — do not echo or closely paraphrase the source_summary. "
        "IMPORTANT: Base your output ONLY on the normalized stories below. "
        "Do NOT reuse or borrow any content from the examples above. "
        "Preserve ticket metadata and mark completed stories as None (Complete) where appropriate.\n\n"
        f"{_FEW_SHOT_EXAMPLES}\n"
        f"Target schema:\n{json.dumps(schema, indent=2)}\n\n"
        f"Normalized stories ({story_count} total):\n{normalized.model_dump_json(indent=2)}"
    )


def build_direct_generation_user_prompt(raw_input: str) -> str:
    schema = {
        "entries": [
            {
                "story_title": "Story title",
                "ticket_id": "ABC-1234",
                "ticket_url": "https://jira.example/browse/ABC-1234",
                "yesterday": "Completed the planned feature work.",
                "today": "Will continue refining and testing the implementation.",
                "blockers": "None",
                "completed": False,
            }
        ]
    }
    return (
        "Turn the following scrum notes into a polished YTB report. "
        "For each story write one concise past-tense sentence for Yesterday and one future-tense sentence for Today, "
        "synthesizing the key outcome in your own words — do not copy the notes verbatim. "
        "IMPORTANT: Base your output ONLY on the raw input below. "
        "Do NOT reuse or borrow any content from the examples above. "
        "Handle both clean structured and messy freeform input.\n\n"
        f"{_FEW_SHOT_EXAMPLES}\n"
        f"Target schema:\n{json.dumps(schema, indent=2)}\n\n"
        f"Raw input:\n{raw_input.strip()}"
    )