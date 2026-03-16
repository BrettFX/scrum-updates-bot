from __future__ import annotations

import json
import os
from pathlib import Path

from scrum_updates_bot.core.models import AppSettings


def get_app_data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = base / "scrum-updates-bot"
    path.mkdir(parents=True, exist_ok=True)
    return path


class SettingsStore:
    def __init__(self, app_dir: Path | None = None) -> None:
        self.app_dir = app_dir or get_app_data_dir()
        self.path = self.app_dir / "settings.json"

    def load(self) -> AppSettings:
        if not self.path.exists():
            settings = AppSettings()
            self.save(settings)
            return settings
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return AppSettings(**data)
        except (json.JSONDecodeError, OSError, ValueError):
            settings = AppSettings()
            self.save(settings)
            return settings

    def save(self, settings: AppSettings) -> None:
        self.path.write_text(settings.model_dump_json(indent=2), encoding="utf-8")