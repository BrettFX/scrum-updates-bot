from scrum_updates_bot.core.fallbacks import fallback_generate
from scrum_updates_bot.core.models import NormalizedStory, NormalizedStoryCollection, StoryReference


def sample_normalized() -> NormalizedStoryCollection:
    return NormalizedStoryCollection(
        stories=[
            NormalizedStory(
                story=StoryReference(
                    title="Implement Configurable Guided Mode for Cloud Cost Estimator Chat Interface",
                    ticket_id="FCSCCE-8872",
                    ticket_url="https://jira.faa.gov/browse/FCSCCE-8872",
                    status="in_progress",
                ),
                yesterday_notes="Transitioned guided mode to a fully chat-based interface following the FCS checklist.",
                today_notes="Focus on refining the feature by fixing minor bugs and enhancing the user experience.",
                blockers="None",
            )
        ]
    )


def test_leadership_preset_differs_from_standard() -> None:
    standard = fallback_generate(sample_normalized(), "Standard YTB")
    leadership = fallback_generate(sample_normalized(), "Leadership Update")

    assert leadership.entries[0].yesterday != standard.entries[0].yesterday
    assert leadership.entries[0].today != standard.entries[0].today
    assert leadership.entries[0].yesterday.startswith("Advanced")
    assert leadership.entries[0].today.startswith("Continuing")


def test_concise_preset_shortens_output() -> None:
    standard = fallback_generate(sample_normalized(), "Standard YTB")
    concise = fallback_generate(sample_normalized(), "Concise Standup")

    assert concise.entries[0].yesterday != standard.entries[0].yesterday
    assert len(concise.entries[0].today.split()) <= len(standard.entries[0].today.split())