from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from scrum_updates_bot.core.models import DraftDocument
from scrum_updates_bot.storage.settings import get_app_data_dir


def _slugify(name: str) -> str:
    value = "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")
    return value or "draft"


class DraftStore:
    def __init__(self, base_dir: Path | None = None) -> None:
        root = base_dir or get_app_data_dir()
        self.root_dir = root
        self.drafts_dir = root / "drafts"
        self.drafts_dir.mkdir(parents=True, exist_ok=True)
        self.session_path = root / "session.json"

    def draft_path(self, name: str) -> Path:
        return self.drafts_dir / f"{_slugify(name)}.json"

    def save(self, draft: DraftDocument) -> Path:
        draft.updated_at = datetime.now(UTC)
        path = self.draft_path(draft.name)
        path.write_text(draft.model_dump_json(indent=2), encoding="utf-8")
        return path

    def load(self, path: Path) -> DraftDocument:
        data = json.loads(path.read_text(encoding="utf-8"))
        return DraftDocument(**data)

    def list_drafts(self) -> list[Path]:
        return sorted(self.drafts_dir.glob("*.json"))

    def save_session(self, draft: DraftDocument) -> Path:
        draft.updated_at = datetime.now(UTC)
        self.session_path.write_text(draft.model_dump_json(indent=2), encoding="utf-8")
        return self.session_path

    def load_session(self) -> DraftDocument | None:
        if not self.session_path.exists():
            return None
        data = json.loads(self.session_path.read_text(encoding="utf-8"))
        return DraftDocument(**data)