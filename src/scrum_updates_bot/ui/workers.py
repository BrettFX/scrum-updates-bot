from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from scrum_updates_bot.core.models import YTBReport
from scrum_updates_bot.services.generator import YTBGeneratorService


class ReportWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, generator: YTBGeneratorService, raw_input: str, model_name: str, preset_name: str) -> None:
        super().__init__()
        self.generator = generator
        self.raw_input = raw_input
        self.model_name = model_name
        self.preset_name = preset_name

    def run(self) -> None:
        try:
            report: YTBReport = self.generator.generate_report(
                raw_input=self.raw_input,
                model_name=self.model_name,
                preset_name=self.preset_name,
                progress_callback=self.progress.emit,
            )
            self.succeeded.emit(report)
        except Exception as exc:
            self.failed.emit(str(exc))