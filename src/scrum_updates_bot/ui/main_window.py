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
        self.splitter.setHandleWidth(10)

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
            QMainWindow {
                background: #eff4f8;
                color: #16202a;
                font-family: 'Segoe UI', 'Noto Sans', sans-serif;
            }
            QToolBar {
                background: #fbfdff;
                border: 1px solid #d5e1ea;
                border-radius: 14px;
                spacing: 8px;
                padding: 10px;
            }
            QToolButton, QPushButton {
                background: #edf3f7;
                border: 1px solid #c5d3df;
                border-radius: 10px;
                padding: 8px 14px;
            }
            QToolButton#presetButton {
                background: #ffffff;
                font-weight: 600;
                text-align: left;
                padding-right: 18px;
            }
            QPushButton[panelButton="true"] {
                background: #f8fbfd;
                padding: 7px 12px;
            }
            QPushButton#primaryButton {
                background: #0f766e;
                color: #ffffff;
                border: 1px solid #0f766e;
                font-weight: 600;
            }
            QPushButton:hover, QToolButton:hover {
                background: #dfeaf5;
            }
            QPushButton#primaryButton:hover {
                background: #115e59;
            }
            QLineEdit, QPlainTextEdit, QTextEdit, QTextBrowser, QComboBox {
                background: #ffffff;
                border: 1px solid #cfd9e3;
                border-radius: 12px;
                padding: 8px;
                selection-background-color: #cfe8e5;
            }
            QMenu {
                background: #ffffff;
                border: 1px solid #cfd9e3;
                padding: 6px;
            }
            QMenu::item {
                padding: 8px 14px;
                border-radius: 8px;
            }
            QMenu::item:selected {
                background: #d7ebe7;
                color: #16202a;
            }
            QFrame#panel, QFrame {
                background: #ffffff;
                border: 1px solid #dbe4ee;
                border-radius: 18px;
            }
            QLabel#appTitle {
                font-size: 26px;
                font-weight: 700;
            }
            QLabel#appSubtitle {
                color: #52606d;
                font-size: 13px;
            }
            QLabel#sectionTitle {
                font-size: 15px;
                font-weight: 700;
            }
            QLabel#sectionSubtitle {
                color: #607282;
                font-size: 12px;
            }
            QLabel#loadingLabel {
                color: #0f766e;
                font-size: 12px;
                font-weight: 600;
            }
            QProgressBar {
                background: #e4edf4;
                border: 1px solid #d4e0ea;
                border-radius: 8px;
                min-height: 12px;
                max-height: 12px;
            }
            QProgressBar::chunk {
                background: #0f766e;
                border-radius: 8px;
            }
            QStatusBar {
                background: #ffffff;
                border-top: 1px solid #dbe4ee;
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