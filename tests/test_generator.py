import json

from scrum_updates_bot.services.generator import YTBGeneratorService


class FakeOllamaClient:
    def __init__(self) -> None:
        self.calls = 0

    def generate_json(self, model_name: str, system_prompt: str, user_prompt: str):
        self.calls += 1
        return {
            "entries": [
                {
                    "story_title": "Generated via LLM",
                    "ticket_id": "ABC-1",
                    "ticket_url": "https://example.com/ABC-1",
                    "yesterday": "Did work.",
                    "today": "More work.",
                    "blockers": "None",
                    "completed": False,
                }
            ]
        }

    def stream_json_text(self, model_name: str, system_prompt: str, user_prompt: str):
        self.calls += 1
        yield '{"entries": ['
        yield '{"entries": [{"story_title": "Generated via LLM", "ticket_id": "ABC-1", "ticket_url": "https://example.com/ABC-1", '
        yield '{"entries": [{"story_title": "Generated via LLM", "ticket_id": "ABC-1", "ticket_url": "https://example.com/ABC-1", "yesterday": "Did work.", "today": "More work.", "blockers": "None", "completed": false}]}'

    def _coerce_json(self, raw: str):
        return json.loads(raw)


STRUCTURED_INPUT = '''Story title is "Implement Configurable Guided Mode for Cloud Cost Estimator Chat Interface (FCSCCE-8872)"
https://jira.faa.gov/browse/FCSCCE-8872

Got rid of guided mode forms and is now completely chat based and sticks to the FCS checklist (configurable). Will continue working on refining today.
'''


def test_structured_input_uses_preset_specific_fast_path_without_llm() -> None:
    client = FakeOllamaClient()
    service = YTBGeneratorService(client)

    standard = service.generate_report(STRUCTURED_INPUT, "llama3.2:3b", "Standard YTB")
    leadership = service.generate_report(STRUCTURED_INPUT, "llama3.2:3b", "Leadership Update")

    assert client.calls == 0
    assert standard.entries[0].yesterday != leadership.entries[0].yesterday


def test_repeat_request_is_served_from_cache() -> None:
    client = FakeOllamaClient()
    service = YTBGeneratorService(client)

    raw_input = "Freeform notes without explicit story structure"
    first = service.generate_report(raw_input, "llama3.2:3b", "Standard YTB")
    second = service.generate_report(raw_input, "llama3.2:3b", "Standard YTB")

    assert client.calls == 1
    assert first.entries[0].story_title == second.entries[0].story_title