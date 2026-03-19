from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from scrum_updates_bot.core.models import PromptTemplateDocument
from scrum_updates_bot.storage.settings import get_app_data_dir

DEFAULT_PROMPT_TEMPLATE_NAME = "Story Update Template"
DEFAULT_PROMPT_TEMPLATE_CONTENT = (
    'Story title is "[STORY NAME HERE] ([JIRA TICKET ID HERE])"\n'
    "[JIRA TICKET URL HERE]\n\n"
    "[BRIEF UPDATE HERE]"
)


def _slugify(name: str) -> str:
    value = "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")
    return value or "template"


class PromptTemplateStore:
    def __init__(self, base_dir: Path | None = None) -> None:
        root = base_dir or get_app_data_dir()
        self.root_dir = root
        self.templates_dir = root / "prompt-templates"
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_default_template()

    def template_path(self, name: str) -> Path:
        return self.templates_dir / f"{_slugify(name)}.json"

    def save(self, template: PromptTemplateDocument) -> Path:
        template.updated_at = datetime.now(UTC)
        path = self.template_path(template.name)
        path.write_text(template.model_dump_json(indent=2), encoding="utf-8")
        return path

    def load(self, path: Path) -> PromptTemplateDocument:
        data = json.loads(path.read_text(encoding="utf-8"))
        return PromptTemplateDocument(**data)

    def list_templates(self) -> list[Path]:
        return sorted(self.templates_dir.glob("*.json"))

    def _ensure_default_template(self) -> None:
        default_path = self.template_path(DEFAULT_PROMPT_TEMPLATE_NAME)
        if default_path.exists():
            return
        self.save(
            PromptTemplateDocument(
                name=DEFAULT_PROMPT_TEMPLATE_NAME,
                content=DEFAULT_PROMPT_TEMPLATE_CONTENT,
            )
        )