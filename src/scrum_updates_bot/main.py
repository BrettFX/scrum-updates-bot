from PySide6.QtWidgets import QApplication

from scrum_updates_bot.ui.main_window import MainWindow


def main() -> int:
    app = QApplication([])
    app.setApplicationName("Scrum Updates Bot")
    app.setOrganizationName("Brian Allen")
    window = MainWindow()
    window.show()
    return app.exec()