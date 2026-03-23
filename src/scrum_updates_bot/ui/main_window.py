from __future__ import annotations

from pathlib import Path
from time import perf_counter

from PySide6.QtCore import QMimeData, Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QComboBox,
    QPlainTextEdit,
    QProgressBar,
    QSizePolicy,
    QTextBrowser,
    QTextEdit,
    QSplitter,
    QStatusBar,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from scrum_updates_bot.core.models import AppSettings, DraftDocument, PromptTemplateDocument, YTBReport
from scrum_updates_bot.core.prompts import PRESET_GUIDANCE
from scrum_updates_bot.core.rendering import render_report_html, render_report_markdown, render_report_text
from scrum_updates_bot.services.generator import YTBGeneratorService
from scrum_updates_bot.services.ollama import OllamaClient, OllamaError
from scrum_updates_bot.services.ollama_setup import is_ollama_cli_installed, ollama_install_instructions
from scrum_updates_bot.storage.drafts import DraftStore
from scrum_updates_bot.storage.prompt_templates import PromptTemplateStore
from scrum_updates_bot.storage.settings import SettingsStore
from scrum_updates_bot.ui.workers import ReportWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings_store = SettingsStore()
        self.settings = self.settings_store.load()
        self.draft_store = DraftStore()
        self.template_store = PromptTemplateStore()
        self.ollama_client = OllamaClient(self.settings.ollama_base_url)
        self.generator = YTBGeneratorService(self.ollama_client)
        self.current_report: YTBReport | None = None
        self.current_worker: ReportWorker | None = None
        self.selected_preset = self.settings.selected_preset
        self._restoring_session = False
        self._ollama_prompt_shown = False
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(700)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.timeout.connect(self._save_session_state)

        self.setWindowTitle("Scrum Updates Bot")
        self.resize(self.settings.window_width, self.settings.window_height)

        self._build_ui()
        self._apply_theme()
        self._wire_autosave()
        self._load_initial_state()

    def _build_ui(self) -> None:
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        check_action = QAction("Check Ollama", self)
        check_action.triggered.connect(self.check_ollama_status)
        toolbar.addAction(check_action)

        refresh_action = QAction("Refresh Models", self)
        refresh_action.triggered.connect(self.refresh_models)
        toolbar.addAction(refresh_action)

        save_action = QAction("Save Draft", self)
        save_action.triggered.connect(self.save_draft)
        toolbar.addAction(save_action)

        load_action = QAction("Load Draft", self)
        load_action.triggered.connect(self.load_draft)
        toolbar.addAction(load_action)

        save_template_action = QAction("Save Prompt Template", self)
        save_template_action.triggered.connect(self.save_prompt_template)
        toolbar.addAction(save_template_action)

        load_template_action = QAction("Load Prompt Template", self)
        load_template_action.triggered.connect(self.load_prompt_template)
        toolbar.addAction(load_template_action)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        header = QFrame()
        header.setObjectName("appHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(4)
        title = QLabel("Scrum Updates Bot")
        title.setObjectName("appTitle")
        subtitle = QLabel("Turn work notes into clean YTB updates with local Ollama models.")
        subtitle.setObjectName("appSubtitle")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        layout.addWidget(header)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        controls.addWidget(QLabel("Model"))

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setMinimumWidth(220)
        controls.addWidget(self.model_combo)

        self.pull_model_input = QLineEdit()
        self.pull_model_input.setPlaceholderText("Model to pull, for example llama3.2:3b")
        controls.addWidget(self.pull_model_input)

        pull_button = QPushButton("Pull Model")
        pull_button.clicked.connect(self.pull_model)
        controls.addWidget(pull_button)

        controls.addWidget(QLabel("Preset"))
        self.preset_button = QToolButton()
        self.preset_button.setObjectName("presetButton")
        self.preset_button.setPopupMode(QToolButton.InstantPopup)
        self.preset_button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.preset_button.setMinimumWidth(190)
        controls.addWidget(self.preset_button)

        self.generate_button = QPushButton("Generate Standard YTB")
        self.generate_button.setObjectName("primaryButton")
        self.generate_button.clicked.connect(self.generate_report)
        controls.addWidget(self.generate_button)

        layout.addLayout(controls)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(6)

        left_panel = QFrame()
        left_panel.setObjectName("panel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)
        left_layout.addLayout(self._build_panel_header("Assistant Activity", "Track model status and generation events.", [("Clear Activity", self.clear_activity)]))
        self.chat_history = QTextBrowser()
        self.chat_history.setOpenExternalLinks(True)
        left_layout.addWidget(self.chat_history, 1)
        left_layout.addLayout(self._build_panel_header("Raw Scrum Notes", "Paste structured stories or rough notes for cleanup.", []))
        self.raw_input = QPlainTextEdit()
        self.raw_input.setPlaceholderText("Paste raw scrum notes, structured story blocks, or freeform work notes here.")
        left_layout.addWidget(self.raw_input, 2)

        right_panel = QFrame()
        right_panel.setObjectName("panel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(12)
        right_layout.addLayout(
            self._build_panel_header(
                "Editable YTB Output",
                "Review the generated update before sharing it in Teams or Outlook.",
                [
                    ("Copy Output", self.copy_output),
                    ("Export", self.export_output),
                    ("Clear Output", self.clear_output),
                ],
            )
        )
        self.output_loading_row = QHBoxLayout()
        self.output_loading_row.setSpacing(10)
        self.output_loading_label = QLabel("Generating response...")
        self.output_loading_label.setObjectName("loadingLabel")
        self.output_loading_indicator = QProgressBar()
        self.output_loading_indicator.setRange(0, 0)
        self.output_loading_indicator.setTextVisible(False)
        self.output_loading_indicator.setFixedWidth(180)
        self.output_loading_row.addWidget(self.output_loading_label)
        self.output_loading_row.addWidget(self.output_loading_indicator)
        self.output_loading_row.addStretch(1)
        self.output_loading_label.hide()
        self.output_loading_indicator.hide()
        right_layout.addLayout(self.output_loading_row)
        self.output_editor = QTextEdit()
        self.output_editor.setAcceptRichText(True)
        self.output_editor.setPlaceholderText("Generated YTB output will appear here.")
        right_layout.addWidget(self.output_editor, 1)

        self.splitter.addWidget(left_panel)
        self.splitter.addWidget(right_panel)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        layout.addWidget(self.splitter, 1)

        self.setCentralWidget(central)

        status = QStatusBar()
        self.setStatusBar(status)

    def _build_panel_header(self, title_text: str, subtitle_text: str, actions: list[tuple[str, object]]) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title = QLabel(title_text)
        title.setObjectName("sectionTitle")
        subtitle = QLabel(subtitle_text)
        subtitle.setObjectName("sectionSubtitle")
        text_col.addWidget(title)
        text_col.addWidget(subtitle)
        row.addLayout(text_col)
        row.addStretch(1)

        for label, handler in actions:
            button = QPushButton(label)
            button.setProperty("panelButton", True)
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            button.clicked.connect(handler)
            row.addWidget(button)

        return row

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            /* === Base === */
            QWidget {
                background-color: #f1f5f9;
                color: #0f172a;
                font-family: 'Inter', 'Segoe UI', 'Ubuntu', 'Noto Sans', sans-serif;
                font-size: 14px;
            }

            /* === Toolbar — dark header bar === */
            QToolBar {
                background-color: #1e293b;
                border: none;
                border-bottom: 2px solid #0f172a;
                spacing: 4px;
                padding: 8px 14px;
            }
            QToolBar QToolButton {
                color: #cbd5e1;
                background: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 6px 13px;
                font-size: 13px;
                font-weight: 500;
            }
            QToolBar QToolButton:hover {
                background-color: #334155;
                color: #f8fafc;
                border-color: #475569;
            }
            QToolBar QToolButton:pressed {
                background-color: #0f172a;
            }

            /* === App header title block === */
            QFrame#appHeader {
                background: transparent;
                border: none;
            }

            /* === Panels / Cards === */
            QFrame#panel {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 16px;
            }
            QFrame {
                border: none;
                background: transparent;
            }

            /* === Buttons === */
            QPushButton {
                background-color: #f1f5f9;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
                border-color: #94a3b8;
            }
            QPushButton:pressed {
                background-color: #cbd5e1;
            }
            QPushButton:disabled {
                color: #94a3b8;
                border-color: #e2e8f0;
            }

            QPushButton#primaryButton {
                background-color: #0d9488;
                color: #ffffff;
                border: 1px solid #0f766e;
                font-weight: 700;
                font-size: 15px;
                padding: 10px 22px;
                border-radius: 8px;
            }
            QPushButton#primaryButton:hover {
                background-color: #0f766e;
                border-color: #115e59;
            }
            QPushButton#primaryButton:pressed {
                background-color: #115e59;
            }
            QPushButton#primaryButton:disabled {
                background-color: #99d6d1;
                border-color: #99d6d1;
                color: #ffffff;
            }

            QPushButton[panelButton="true"] {
                background-color: #f8fafc;
                color: #475569;
                border: 1px solid #e2e8f0;
                padding: 6px 14px;
                font-size: 13px;
                font-weight: 500;
                border-radius: 7px;
            }
            QPushButton[panelButton="true"]:hover {
                background-color: #f1f5f9;
                color: #0f172a;
                border-color: #94a3b8;
            }

            /* === Preset dropdown (lives in controls row, not toolbar) === */
            QToolButton#presetButton {
                background-color: #ffffff;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                font-weight: 600;
                font-size: 14px;
                padding: 8px 14px;
                text-align: left;
                min-width: 190px;
            }
            QToolButton#presetButton:hover {
                background-color: #f1f5f9;
                border-color: #94a3b8;
            }
            QToolButton#presetButton::menu-indicator {
                width: 12px;
                subcontrol-origin: padding;
                subcontrol-position: right center;
                right: 8px;
            }

            /* === Inputs === */
            QLineEdit, QPlainTextEdit, QTextEdit, QTextBrowser, QComboBox {
                background-color: #ffffff;
                color: #0f172a;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 10px 12px;
                font-size: 14px;
                selection-background-color: #ccfbf1;
                selection-color: #0f172a;
            }
            QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
                border-color: #0d9488;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 4px;
                selection-background-color: #ccfbf1;
                selection-color: #0f172a;
                font-size: 14px;
            }

            /* === Menus === */
            QMenu {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                padding: 6px;
                font-size: 14px;
            }
            QMenu::item {
                padding: 9px 16px;
                border-radius: 6px;
                color: #1e293b;
            }
            QMenu::item:selected {
                background-color: #ccfbf1;
                color: #0f172a;
            }
            QMenu::separator {
                height: 1px;
                background: #e2e8f0;
                margin: 4px 8px;
            }

            /* === Labels === */
            QLabel {
                color: #0f172a;
                font-size: 14px;
                background: transparent;
                border: none;
            }
            QLabel#appTitle {
                font-size: 22px;
                font-weight: 700;
                color: #0f172a;
            }
            QLabel#appSubtitle {
                color: #64748b;
                font-size: 14px;
            }
            QLabel#sectionTitle {
                font-size: 16px;
                font-weight: 700;
                color: #0f172a;
            }
            QLabel#sectionSubtitle {
                color: #94a3b8;
                font-size: 13px;
            }
            QLabel#loadingLabel {
                color: #0d9488;
                font-size: 13px;
                font-weight: 600;
            }

            /* === Progress bar === */
            QProgressBar {
                background-color: #e2e8f0;
                border: none;
                border-radius: 4px;
                min-height: 6px;
                max-height: 6px;
            }
            QProgressBar::chunk {
                background-color: #0d9488;
                border-radius: 4px;
            }

            /* === Status bar === */
            QStatusBar {
                background-color: #ffffff;
                color: #64748b;
                font-size: 13px;
                border-top: 1px solid #e2e8f0;
                padding: 2px 12px;
            }
            QStatusBar::item {
                border: none;
            }

            /* === Scrollbars === */
            QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 4px 2px 4px 0;
            }
            QScrollBar::handle:vertical {
                background-color: #cbd5e1;
                border-radius: 4px;
                min-height: 32px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #94a3b8;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            QScrollBar:horizontal {
                background: transparent;
                height: 8px;
                margin: 0 4px;
            }
            QScrollBar::handle:horizontal {
                background-color: #cbd5e1;
                border-radius: 4px;
                min-width: 32px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #94a3b8;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0;
                background: none;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }

            /* === Splitter === */
            QSplitter::handle:horizontal {
                background-color: #e2e8f0;
                width: 1px;
            }
            QSplitter::handle:horizontal:hover {
                background-color: #0d9488;
            }
            """
        )

    def _wire_autosave(self) -> None:
        self.raw_input.textChanged.connect(self.schedule_session_save)
        self.output_editor.textChanged.connect(self.schedule_session_save)
        self.model_combo.currentTextChanged.connect(self.schedule_session_save)

    def schedule_session_save(self) -> None:
        if self._restoring_session:
            return
        self.autosave_timer.start()

    def _rebuild_preset_menu(self) -> None:
        menu = QMenu(self)
        for preset_name in PRESET_GUIDANCE:
            action = QAction(preset_name, self)
            action.setCheckable(True)
            action.setChecked(preset_name == self.selected_preset)
            action.triggered.connect(lambda checked=False, name=preset_name: self._select_preset(name))
            menu.addAction(action)
        self.preset_button.setMenu(menu)
        self._update_generate_button_label()

    def _select_preset(self, preset_name: str) -> None:
        self.selected_preset = preset_name
        self._rebuild_preset_menu()
        self.statusBar().showMessage(f"Preset selected: {self.selected_preset}", 3000)
        self.schedule_session_save()

    def _update_generate_button_label(self) -> None:
        preset = self.selected_preset.strip() or "YTB"
        self.preset_button.setText(preset)
        self.generate_button.setText(f"Generate {preset}")

    def _load_initial_state(self) -> None:
        self.model_combo.addItem(self.settings.model_name)
        self.model_combo.setCurrentText(self.settings.model_name)
        if self.settings.selected_preset in PRESET_GUIDANCE:
            self.selected_preset = self.settings.selected_preset
        self._rebuild_preset_menu()
        self.check_ollama_status()
        self._show_ollama_setup_prompt_if_needed()
        self.refresh_models(silent=True)
        self.splitter.setSizes([self.settings.splitter_left_width, self.settings.splitter_right_width])
        restored = self._restore_session_state()
        if not restored:
            self.append_activity("Ready. Paste notes, choose a model, and generate a YTB update.")

    def append_activity(self, message: str) -> None:
        self.chat_history.append(message)
        self.statusBar().showMessage(message, 5000)
        self.schedule_session_save()

    def check_ollama_status(self) -> None:
        available = self.ollama_client.is_available()
        if available:
            self.append_activity("Ollama is reachable.")
        else:
            self.append_activity("Ollama is not reachable. Start Ollama or update the configured base URL.")

    def _show_ollama_setup_prompt_if_needed(self) -> None:
        if self._ollama_prompt_shown or self.ollama_client.is_available():
            return

        self._ollama_prompt_shown = True
        if is_ollama_cli_installed():
            QMessageBox.information(
                self,
                "Start Ollama",
                "Ollama appears to be installed but is not reachable.\n\n"
                "Start the Ollama service, then click 'Check Ollama' or 'Refresh Models'.",
            )
            return

        QMessageBox.warning(self, "Install Ollama", ollama_install_instructions())

    def refresh_models(self, silent: bool = False) -> None:
        try:
            current = self.model_combo.currentText().strip()
            models = self.ollama_client.list_models()
            self.model_combo.clear()
            if not models:
                self.model_combo.addItem(current or self.settings.model_name)
            else:
                self.model_combo.addItems(models)
                if current and current not in models:
                    self.model_combo.addItem(current)
                self.model_combo.setCurrentText(current or self.settings.model_name)
            if not silent:
                self.append_activity("Refreshed local Ollama model list.")
        except OllamaError as exc:
            if not silent:
                self.append_activity(str(exc))

    def pull_model(self) -> None:
        model_name = self.pull_model_input.text().strip() or self.model_combo.currentText().strip()
        if not model_name:
            QMessageBox.warning(self, "Model required", "Enter a model name to pull from Ollama.")
            return
        try:
            self.append_activity(f"Pulling model {model_name}...")
            self.ollama_client.pull_model(model_name)
            self.refresh_models(silent=True)
            self.model_combo.setCurrentText(model_name)
            self.append_activity(f"Model pull completed for {model_name}.")
        except OllamaError as exc:
            QMessageBox.critical(self, "Model pull failed", str(exc))

    def generate_report(self) -> None:
        raw_input = self.raw_input.toPlainText().strip()
        if not raw_input:
            QMessageBox.warning(self, "Input required", "Paste scrum notes before generating a report.")
            return
        if self.current_worker is not None and self.current_worker.isRunning():
            return
        model_name = self.model_combo.currentText().strip()
        preset_name = self.selected_preset.strip()
        self.append_activity(f"Generating YTB update with {model_name} using the {preset_name} preset.")
        self._generation_started_at = perf_counter()
        self._set_generating_state(True)
        self.current_worker = ReportWorker(self.generator, raw_input, model_name, preset_name)
        self.current_worker.progress.connect(self.on_generation_progress)
        self.current_worker.succeeded.connect(self.on_report_ready)
        self.current_worker.failed.connect(self.on_report_failed)
        self.current_worker.start()

    def on_generation_progress(self, message: str) -> None:
        self.output_loading_label.setText(message)
        self.statusBar().showMessage(message, 0)

    def on_report_ready(self, report: YTBReport) -> None:
        self._set_generating_state(False)
        self.current_report = report
        html = render_report_html(report)
        self.output_editor.setHtml(html)
        elapsed = getattr(self, "_generation_started_at", None)
        if elapsed is not None:
            duration = perf_counter() - elapsed
            self.append_activity(f"Generated {len(report.entries)} YTB item(s) in {duration:.1f}s.")
        else:
            self.append_activity(f"Generated {len(report.entries)} YTB item(s).")
        self._persist_ui_settings()
        self._save_session_state()
        self.current_worker = None

    def on_report_failed(self, message: str) -> None:
        self._set_generating_state(False)
        QMessageBox.critical(self, "Generation failed", message)
        self.append_activity(f"Generation failed: {message}")
        self.current_worker = None

    def _set_generating_state(self, is_generating: bool) -> None:
        self.output_editor.setDisabled(is_generating)
        self.output_loading_label.setVisible(is_generating)
        self.output_loading_indicator.setVisible(is_generating)
        self.generate_button.setDisabled(is_generating)
        self.preset_button.setDisabled(is_generating)
        if is_generating:
            self.current_report = None
            self.output_editor.clear()
            self.output_loading_label.setText("Generating response...")
            self.statusBar().showMessage("Generating YTB response...", 0)
        else:
            self.generate_button.setEnabled(True)
            self.preset_button.setEnabled(True)
            self._update_generate_button_label()

    def copy_output(self) -> None:
        html = self.output_editor.toHtml()
        text = self.output_editor.toPlainText()
        if not text.strip():
            QMessageBox.information(self, "Nothing to copy", "Generate or edit a report before copying.")
            return
        mime_data = QMimeData()
        mime_data.setHtml(html)
        mime_data.setText(text)
        clipboard = self.app_clipboard()
        clipboard.setMimeData(mime_data)
        self.append_activity("Copied YTB output to the clipboard as HTML and plain text.")

    def clear_activity(self) -> None:
        if not self.chat_history.toPlainText().strip():
            return
        self.chat_history.clear()
        self.statusBar().showMessage("Assistant activity cleared.", 3000)
        self.schedule_session_save()

    def clear_output(self) -> None:
        if not self.output_editor.toPlainText().strip() and self.current_report is None:
            return
        self.output_editor.clear()
        self.current_report = None
        self.statusBar().showMessage("YTB output cleared.", 3000)
        self.schedule_session_save()

    def app_clipboard(self):
        from PySide6.QtWidgets import QApplication

        return QApplication.clipboard()

    def export_output(self) -> None:
        html = self.output_editor.toHtml()
        text = self.output_editor.toPlainText()
        if not text.strip():
            QMessageBox.information(self, "Nothing to export", "Generate or edit a report before exporting.")
            return
        target, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export YTB Update",
            str(Path.home() / "ytb-update.html"),
            "HTML Files (*.html);;Markdown Files (*.md);;Text Files (*.txt)",
        )
        if not target:
            return
        path = Path(target)
        if selected_filter.startswith("Markdown"):
            content = render_report_markdown(self.current_report) if self.current_report else text
        elif selected_filter.startswith("Text"):
            content = render_report_text(self.current_report) if self.current_report else text
        else:
            content = html
        path.write_text(content, encoding="utf-8")
        self.append_activity(f"Exported output to {path}.")

    def save_draft(self) -> None:
        name, accepted = QInputDialog.getText(
            self,
            "Save draft",
            "Draft name:",
            text=self.settings.last_draft_name or "daily-ytb",
        )
        if not accepted or not name.strip():
            return
        report_html = self.output_editor.toHtml()
        report_text = self.output_editor.toPlainText()
        draft = DraftDocument(
            name=name.strip(),
            raw_input=self.raw_input.toPlainText(),
            output_html=report_html,
            output_text=report_text,
            activity_log=self._activity_log(),
            report=self.current_report,
            preset_name=self.selected_preset,
            model_name=self.model_combo.currentText().strip() or None,
        )
        path = self.draft_store.save(draft)
        self.settings.last_draft_name = name.strip()
        self._persist_ui_settings()
        self.append_activity(f"Saved draft to {path}.")

    def save_prompt_template(self) -> None:
        content = self.raw_input.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "No prompt text", "Enter prompt text before saving a template.")
            return
        name, accepted = QInputDialog.getText(
            self,
            "Save prompt template",
            "Template name:",
            text="Prompt Template",
        )
        if not accepted or not name.strip():
            return
        template = PromptTemplateDocument(name=name.strip(), content=content)
        path = self.template_store.save(template)
        self.append_activity(f"Saved prompt template to {path}.")

    def load_prompt_template(self) -> None:
        templates = [self.template_store.load(path) for path in self.template_store.list_templates()]
        if not templates:
            QMessageBox.information(self, "No templates", "No saved prompt templates were found.")
            return
        names = [template.name for template in templates]
        selected_name, accepted = QInputDialog.getItem(
            self,
            "Load prompt template",
            "Choose a template:",
            names,
            editable=False,
        )
        if not accepted or not selected_name:
            return
        selected_template = next(template for template in templates if template.name == selected_name)
        self.raw_input.setPlainText(selected_template.content)
        self.append_activity(f"Loaded prompt template {selected_template.name} into the input field.")

    def load_draft(self) -> None:
        drafts = self.draft_store.list_drafts()
        if not drafts:
            QMessageBox.information(self, "No drafts", "No saved drafts were found.")
            return
        target, _ = QFileDialog.getOpenFileName(
            self,
            "Load draft",
            str(self.draft_store.drafts_dir),
            "Draft Files (*.json)",
        )
        if not target:
            return
        draft = self.draft_store.load(Path(target))
        self.raw_input.setPlainText(draft.raw_input)
        self.output_editor.setHtml(draft.output_html or draft.output_text)
        self.current_report = draft.report
        self.chat_history.setHtml("<br/>".join(draft.activity_log))
        self.model_combo.setCurrentText(draft.model_name or self.model_combo.currentText())
        if draft.preset_name in PRESET_GUIDANCE:
            self.selected_preset = draft.preset_name
            self._rebuild_preset_menu()
        self.append_activity(f"Loaded draft {draft.name}.")

    def _persist_ui_settings(self) -> None:
        self.settings.model_name = self.model_combo.currentText().strip() or self.settings.model_name
        self.settings.selected_preset = self.selected_preset.strip() or self.settings.selected_preset
        self.settings.window_width = self.width()
        self.settings.window_height = self.height()
        sizes = self.splitter.sizes()
        if len(sizes) == 2:
            self.settings.splitter_left_width = sizes[0]
            self.settings.splitter_right_width = sizes[1]
        self.settings_store.save(self.settings)

    def _activity_log(self) -> list[str]:
        return [line for line in self.chat_history.toPlainText().splitlines() if line.strip()]

    def _save_session_state(self) -> None:
        if self._restoring_session:
            return
        draft = DraftDocument(
            name="Last Session",
            raw_input=self.raw_input.toPlainText(),
            output_html=self.output_editor.toHtml(),
            output_text=self.output_editor.toPlainText(),
            activity_log=self._activity_log(),
            report=self.current_report,
            preset_name=self.selected_preset,
            model_name=self.model_combo.currentText().strip() or None,
        )
        self.draft_store.save_session(draft)
        self._persist_ui_settings()

    def _restore_session_state(self) -> bool:
        session = self.draft_store.load_session()
        if session is None:
            return False
        self._restoring_session = True
        try:
            self.raw_input.setPlainText(session.raw_input)
            self.output_editor.setHtml(session.output_html or session.output_text)
            self.current_report = session.report
            self.chat_history.setPlainText("\n".join(session.activity_log))
            if session.model_name:
                self.model_combo.setCurrentText(session.model_name)
            if session.preset_name in PRESET_GUIDANCE:
                self.selected_preset = session.preset_name
                self._rebuild_preset_menu()
        finally:
            self._restoring_session = False
        if session.raw_input or session.output_text or session.activity_log:
            self.statusBar().showMessage("Restored your previous session.", 5000)
            return True
        return False

    def closeEvent(self, event) -> None:
        self._save_session_state()
        self._persist_ui_settings()
        super().closeEvent(event)