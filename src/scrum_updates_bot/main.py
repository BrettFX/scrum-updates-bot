from __future__ import annotations

import ctypes
import logging
import os
import sys
import traceback
from pathlib import Path

from scrum_updates_bot.storage.settings import get_app_data_dir


def _get_startup_log_path() -> Path:
    log_dir = get_app_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "startup.log"


def _configure_logging() -> Path:
    log_path = _get_startup_log_path()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
        force=True,
    )
    return log_path


def _show_fatal_error(message: str) -> None:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(0, message, "Scrum Updates Bot failed to start", 0x10)
        return

    print(message, file=sys.stderr)


def main() -> int:
    log_path = _configure_logging()
    logging.info("Application startup initiated")

    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        from scrum_updates_bot.ui.main_window import MainWindow

        app = QApplication([])
        app.setApplicationName("Scrum Updates Bot")
        app.setOrganizationName("Brian Allen")

        def handle_exception(exc_type, exc_value, exc_traceback) -> None:
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return

            error_text = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
            logging.critical("Unhandled exception during app execution\n%s", error_text)
            QMessageBox.critical(
                None,
                "Scrum Updates Bot failed to start",
                "Scrum Updates Bot encountered a fatal error.\n\n"
                f"Details were written to:\n{log_path}\n\n"
                f"{exc_value}",
            )

        sys.excepthook = handle_exception

        window = MainWindow()
        logging.info("Main window created successfully")
        window.show()
        logging.info("Main window shown")
        return app.exec()
    except Exception as exc:  # pragma: no cover - startup fatal path
        error_text = traceback.format_exc()
        logging.critical("Application failed to start\n%s", error_text)
        _show_fatal_error(
            "Scrum Updates Bot failed to start.\n\n"
            f"Details were written to:\n{log_path}\n\n"
            f"{exc}"
        )
        return 1