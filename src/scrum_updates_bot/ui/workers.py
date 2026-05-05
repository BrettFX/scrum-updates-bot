from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from scrum_updates_bot.core.models import YTBReport
from scrum_updates_bot.services.generator import YTBGeneratorService
from scrum_updates_bot.services.ollama import OllamaClient, OllamaError


class ModelPullWorker(QThread):
    """Background thread that streams an Ollama model pull with progress signals."""

    progress = Signal(str, object, object)  # status_msg, bytes_completed, bytes_total
    succeeded = Signal()
    failed = Signal(str)

    def __init__(self, client: OllamaClient, model_name: str) -> None:
        super().__init__()
        self.client = client
        self.model_name = model_name

    def run(self) -> None:
        try:
            for status, completed, total in self.client.pull_model_stream(self.model_name):
                if self.isInterruptionRequested():
                    self.failed.emit("Cancelled.")
                    return
                self.progress.emit(status, completed, total)
            self.succeeded.emit()
        except OllamaError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc))


class ReportWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)
    progress = Signal(str)
    streamed = Signal(str)

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
                stream_callback=self.streamed.emit,
            )
            self.succeeded.emit(report)
        except Exception as exc:
            self.failed.emit(str(exc))