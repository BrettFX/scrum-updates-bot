from __future__ import annotations

from typing import NamedTuple

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from scrum_updates_bot.services.ollama import OllamaClient, OllamaError
from scrum_updates_bot.ui.workers import ModelPullWorker


# ---------------------------------------------------------------------------
# Curated marketplace catalogue
# ---------------------------------------------------------------------------

class _MarketplaceEntry(NamedTuple):
    name: str
    description: str
    size_hint: str
    tags: list[str]


MARKETPLACE_MODELS: list[_MarketplaceEntry] = [
    # ── Tiny / ultra-light ──────────────────────────────────────────────────
    _MarketplaceEntry("llama3.2:1b",             "Meta Llama 3.2 · 1 B — ultra-lightweight",                  "~0.8 GB",  ["tiny"]),
    _MarketplaceEntry("gemma3:1b",               "Google Gemma 3 · 1 B — compact on-device model",            "~0.8 GB",  ["tiny"]),
    _MarketplaceEntry("qwen2.5:0.5b-instruct",   "Alibaba Qwen 2.5 · 0.5 B Instruct — minimal footprint",     "~0.4 GB",  ["tiny"]),

    # ── Small (2–4 GB) ──────────────────────────────────────────────────────
    _MarketplaceEntry("llama3.2:3b",             "Meta Llama 3.2 · 3 B — efficient everyday tasks",           "~2.0 GB",  ["small", "recommended"]),
    _MarketplaceEntry("phi3.5:3.8b",             "Microsoft Phi-3.5 · 3.8 B — strong for size",               "~2.2 GB",  ["small"]),
    _MarketplaceEntry("qwen2.5:3b-instruct",     "Alibaba Qwen 2.5 · 3 B Instruct — multilingual & coding",   "~2.0 GB",  ["small"]),
    _MarketplaceEntry("gemma3:4b",               "Google Gemma 3 · 4 B — solid mid-small model",              "~3.3 GB",  ["small"]),

    # ── Medium (4–10 GB) ────────────────────────────────────────────────────
    _MarketplaceEntry("llama3.1:8b",             "Meta Llama 3.1 · 8 B — strong general purpose",             "~4.7 GB",  ["medium", "recommended"]),
    _MarketplaceEntry("mistral:7b-instruct",     "Mistral 7B Instruct v0.3 — versatile & fast",               "~4.1 GB",  ["medium"]),
    _MarketplaceEntry("qwen2.5:7b-instruct",     "Alibaba Qwen 2.5 · 7 B Instruct — excellent reasoning",     "~4.7 GB",  ["medium", "recommended"]),
    _MarketplaceEntry("gemma3:9b",               "Google Gemma 3 · 9 B — excellent mid-range",                "~5.8 GB",  ["medium"]),
    _MarketplaceEntry("mistral-nemo:12b",        "Mistral NeMo · 12 B — great reasoning & context",           "~7.1 GB",  ["medium"]),
    _MarketplaceEntry("phi4:14b",                "Microsoft Phi-4 · 14 B — strong instruction following",     "~8.9 GB",  ["medium"]),
    _MarketplaceEntry("qwen2.5:14b-instruct",    "Alibaba Qwen 2.5 · 14 B Instruct — near GPT-3.5 quality",  "~9.0 GB",  ["medium"]),
    _MarketplaceEntry("deepseek-r1:7b",          "DeepSeek R1 · 7 B — chain-of-thought reasoning model",      "~4.7 GB",  ["medium", "reasoning"]),
    _MarketplaceEntry("deepseek-r1:14b",         "DeepSeek R1 · 14 B — stronger reasoning",                   "~9.0 GB",  ["medium", "reasoning"]),

    # ── Large (10 GB+) ──────────────────────────────────────────────────────
    _MarketplaceEntry("qwen2.5:32b-instruct",    "Alibaba Qwen 2.5 · 32 B Instruct — near GPT-4 quality",    "~20 GB",   ["large"]),
    _MarketplaceEntry("gemma3:27b",              "Google Gemma 3 · 27 B — high quality open model",           "~17 GB",   ["large"]),
    _MarketplaceEntry("llama3.1:70b",            "Meta Llama 3.1 · 70 B — frontier open-weight model",        "~40 GB",   ["large"]),
    _MarketplaceEntry("mixtral:8x7b-instruct",   "Mistral Mixtral MoE · 8×7 B — very capable mixture",        "~26 GB",   ["large"]),
    _MarketplaceEntry("deepseek-r1:32b",         "DeepSeek R1 · 32 B — high quality reasoning",               "~20 GB",   ["large", "reasoning"]),
    _MarketplaceEntry("phi4:14b-instruct",       "Microsoft Phi-4 · 14 B Instruct — excellent quality",       "~8.9 GB",  ["large"]),

    # ── Embedding ────────────────────────────────────────────────────────────
    _MarketplaceEntry("nomic-embed-text:latest", "Nomic Embed Text — fast embedding model",                   "~0.3 GB",  ["embedding"]),
    _MarketplaceEntry("mxbai-embed-large:latest","mxbai-embed-large — high-quality embeddings",               "~0.7 GB",  ["embedding"]),
]

_TAG_COLORS = {
    "recommended": "#0d9488",
    "reasoning":   "#7c3aed",
    "embedding":   "#0369a1",
    "tiny":        "#64748b",
    "small":       "#475569",
    "medium":      "#334155",
    "large":       "#1e293b",
}

_STYLESHEET = """
QWidget {
    background-color: #f1f5f9;
    color: #0f172a;
    font-family: 'Inter', 'Segoe UI', 'Ubuntu', 'Noto Sans', sans-serif;
    font-size: 14px;
}
QFrame#panel {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
}
QFrame { border: none; background: transparent; }
QLabel { background: transparent; border: none; }
QLabel#sectionTitle { font-size: 15px; font-weight: 700; color: #0f172a; }
QLabel#sectionSubtitle { color: #94a3b8; font-size: 13px; }
QLabel#statusLabel { color: #64748b; font-size: 13px; }
QLabel#pullStatusLabel { color: #0d9488; font-size: 13px; font-weight: 600; }
QListWidget {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 4px;
    font-size: 13px;
    outline: none;
}
QListWidget::item { padding: 8px 10px; border-radius: 6px; color: #1e293b; }
QListWidget::item:selected { background-color: #ccfbf1; color: #0f172a; }
QListWidget::item:hover:!selected { background-color: #f8fafc; }
QLineEdit {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 14px;
}
QLineEdit:focus { border-color: #0d9488; }
QPushButton {
    background-color: #f1f5f9;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
}
QPushButton:hover { background-color: #e2e8f0; border-color: #94a3b8; }
QPushButton:pressed { background-color: #cbd5e1; }
QPushButton:disabled { color: #94a3b8; border-color: #e2e8f0; }
QPushButton#primaryButton {
    background-color: #0d9488;
    color: #ffffff;
    border: 1px solid #0f766e;
    font-weight: 700;
    font-size: 14px;
    padding: 9px 20px;
    border-radius: 8px;
}
QPushButton#primaryButton:hover { background-color: #0f766e; }
QPushButton#primaryButton:disabled { background-color: #99d6d1; border-color: #99d6d1; }
QPushButton#dangerButton {
    background-color: #fef2f2;
    color: #dc2626;
    border: 1px solid #fecaca;
    font-weight: 600;
}
QPushButton#dangerButton:hover { background-color: #fee2e2; border-color: #f87171; }
QProgressBar {
    background-color: #e2e8f0;
    border: none;
    border-radius: 4px;
    min-height: 8px;
    max-height: 8px;
}
QProgressBar::chunk { background-color: #0d9488; border-radius: 4px; }
QSplitter::handle:horizontal { background-color: #e2e8f0; width: 1px; }
QSplitter::handle:horizontal:hover { background-color: #0d9488; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 4px 2px 4px 0; }
QScrollBar::handle:vertical { background-color: #cbd5e1; border-radius: 4px; min-height: 32px; }
QScrollBar::handle:vertical:hover { background-color: #94a3b8; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; background: none; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
"""


def _fmt_bytes(n: int) -> str:
    if n <= 0:
        return ""
    if n >= 1_073_741_824:
        return f"{n / 1_073_741_824:.1f} GB"
    if n >= 1_048_576:
        return f"{n / 1_048_576:.0f} MB"
    return f"{n / 1024:.0f} KB"


class ModelManagerDialog(QDialog):
    """Dedicated dialog for browsing, pulling, and deleting Ollama models."""

    def __init__(self, client: OllamaClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.client = client
        self._pull_worker: ModelPullWorker | None = None
        self._installed_names: set[str] = set()

        self.setWindowTitle("Manage Models")
        self.resize(960, 620)
        self.setStyleSheet(_STYLESHEET)

        self._build_ui()
        self._load_installed()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(6)
        splitter.addWidget(self._build_installed_panel())
        splitter.addWidget(self._build_marketplace_panel())
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        root.addWidget(splitter, 1)

        root.addWidget(self._build_progress_panel())

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.close)
        root.addWidget(buttons)

    def _build_installed_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addLayout(self._header("Installed Models", "Models downloaded locally in Ollama."))

        self.installed_list = QListWidget()
        self.installed_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.installed_list.itemSelectionChanged.connect(self._on_installed_selection_changed)
        layout.addWidget(self.installed_list, 1)

        row = QHBoxLayout()
        self.installed_status = QLabel("")
        self.installed_status.setObjectName("statusLabel")
        row.addWidget(self.installed_status, 1)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._load_installed)
        row.addWidget(self.refresh_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setObjectName("dangerButton")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._delete_selected)
        row.addWidget(self.delete_btn)

        layout.addLayout(row)
        return panel

    def _build_marketplace_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addLayout(self._header("Marketplace", "Popular Ollama models. Click a row then Pull to download."))

        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter models…")
        self.search_input.textChanged.connect(self._filter_marketplace)
        search_row.addWidget(self.search_input, 1)

        clear_btn = QPushButton("✕")
        clear_btn.setFixedWidth(36)
        clear_btn.clicked.connect(lambda: self.search_input.clear())
        search_row.addWidget(clear_btn)
        layout.addLayout(search_row)

        self.marketplace_list = QListWidget()
        self.marketplace_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.marketplace_list.itemSelectionChanged.connect(self._on_marketplace_selection_changed)
        layout.addWidget(self.marketplace_list, 1)

        row = QHBoxLayout()
        self.marketplace_status = QLabel("")
        self.marketplace_status.setObjectName("statusLabel")
        row.addWidget(self.marketplace_status, 1)

        self.pull_btn = QPushButton("Pull Model")
        self.pull_btn.setObjectName("primaryButton")
        self.pull_btn.setEnabled(False)
        self.pull_btn.clicked.connect(self._pull_selected)
        row.addWidget(self.pull_btn)

        layout.addLayout(row)
        self._populate_marketplace()
        return panel

    def _build_progress_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        header_row = QHBoxLayout()
        self.pull_status_label = QLabel("No active download.")
        self.pull_status_label.setObjectName("pullStatusLabel")
        header_row.addWidget(self.pull_status_label, 1)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_pull)
        header_row.addWidget(self.cancel_btn)
        layout.addLayout(header_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.progress_bytes_label = QLabel("")
        self.progress_bytes_label.setObjectName("statusLabel")
        layout.addWidget(self.progress_bytes_label)

        return panel

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _header(title: str, subtitle: str) -> QHBoxLayout:
        row = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(2)
        t = QLabel(title)
        t.setObjectName("sectionTitle")
        s = QLabel(subtitle)
        s.setObjectName("sectionSubtitle")
        col.addWidget(t)
        col.addWidget(s)
        row.addLayout(col)
        row.addStretch(1)
        return row

    # ------------------------------------------------------------------
    # Installed models panel
    # ------------------------------------------------------------------

    def _load_installed(self) -> None:
        self.installed_list.clear()
        self._installed_names.clear()
        try:
            models = self.client.list_models_detail()
        except OllamaError as exc:
            self.installed_status.setText(f"Error: {exc}")
            return

        for m in sorted(models, key=lambda x: x.get("name", "")):
            name = m.get("name", "")
            if not name:
                continue
            self._installed_names.add(name)
            size_str = _fmt_bytes(m.get("size", 0))
            family = (m.get("details") or {}).get("family", "")
            params = (m.get("details") or {}).get("parameter_size", "")
            detail = "  ·  ".join(filter(None, [family, params, size_str]))
            item = QListWidgetItem(f"{name}\n  {detail}" if detail else name)
            item.setData(Qt.UserRole, name)
            self.installed_list.addItem(item)

        count = len(models)
        self.installed_status.setText(f"{count} model{'s' if count != 1 else ''} installed")
        self.delete_btn.setEnabled(False)
        # Refresh marketplace indicators
        self._populate_marketplace(filter_text=self.search_input.text())

    def _on_installed_selection_changed(self) -> None:
        self.delete_btn.setEnabled(bool(self.installed_list.selectedItems()))

    def _delete_selected(self) -> None:
        items = self.installed_list.selectedItems()
        if not items:
            return
        model_name = items[0].data(Qt.UserRole)
        reply = QMessageBox.question(
            self,
            "Delete model",
            f"Permanently delete <b>{model_name}</b> from Ollama?<br><br>"
            "The model files will be removed. You can re-download it later.",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            self.client.delete_model(model_name)
            self.installed_status.setText(f"Deleted {model_name}.")
            self._load_installed()
        except OllamaError as exc:
            QMessageBox.critical(self, "Delete failed", str(exc))

    # ------------------------------------------------------------------
    # Marketplace panel
    # ------------------------------------------------------------------

    def _populate_marketplace(self, filter_text: str = "") -> None:
        needle = filter_text.strip().lower()
        self.marketplace_list.clear()
        for entry in MARKETPLACE_MODELS:
            if needle and needle not in entry.name.lower() and needle not in entry.description.lower() and not any(needle in t for t in entry.tags):
                continue
            installed = entry.name in self._installed_names
            indicator = " ✓ installed" if installed else ""
            tags_str = "  ".join(f"[{t}]" for t in entry.tags) if entry.tags else ""
            text = f"{entry.name}{indicator}\n  {entry.description}  ·  {entry.size_hint}  {tags_str}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, entry.name)
            if installed:
                item.setForeground(Qt.gray)
            self.marketplace_list.addItem(item)

    def _filter_marketplace(self, text: str) -> None:
        self._populate_marketplace(filter_text=text)

    def _on_marketplace_selection_changed(self) -> None:
        has_sel = bool(self.marketplace_list.selectedItems())
        is_pulling = self._pull_worker is not None and self._pull_worker.isRunning()
        self.pull_btn.setEnabled(has_sel and not is_pulling)

    # ------------------------------------------------------------------
    # Pull workflow
    # ------------------------------------------------------------------

    def _pull_selected(self) -> None:
        items = self.marketplace_list.selectedItems()
        if not items:
            return
        model_name = items[0].data(Qt.UserRole)
        self._start_pull(model_name)

    def _start_pull(self, model_name: str) -> None:
        if self._pull_worker is not None and self._pull_worker.isRunning():
            return

        self.pull_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.progress_bytes_label.setText("")
        self.pull_status_label.setText(f"Pulling {model_name}…")

        self._pull_worker = ModelPullWorker(self.client, model_name)
        self._pull_worker.progress.connect(self._on_pull_progress)
        self._pull_worker.succeeded.connect(self._on_pull_succeeded)
        self._pull_worker.failed.connect(self._on_pull_failed)
        self._pull_worker.start()

    def _on_pull_progress(self, status: str, completed: int, total: int) -> None:
        self.pull_status_label.setText(status or "Working…")
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(completed)
            self.progress_bytes_label.setText(f"{_fmt_bytes(completed)} / {_fmt_bytes(total)}")
        else:
            self.progress_bar.setRange(0, 0)
            self.progress_bytes_label.setText("")

    def _on_pull_succeeded(self) -> None:
        self.pull_status_label.setText("Download complete.")
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        self.progress_bytes_label.setText("")
        self.cancel_btn.setEnabled(False)
        self._pull_worker = None
        self._load_installed()
        # Re-enable pull button if something is selected
        self._on_marketplace_selection_changed()

    def _on_pull_failed(self, message: str) -> None:
        self.pull_status_label.setText(f"Failed: {message}")
        self.progress_bar.setVisible(False)
        self.progress_bytes_label.setText("")
        self.cancel_btn.setEnabled(False)
        self._pull_worker = None
        self._on_marketplace_selection_changed()

    def _cancel_pull(self) -> None:
        if self._pull_worker is not None and self._pull_worker.isRunning():
            self._pull_worker.requestInterruption()
            self.pull_status_label.setText("Cancelling…")
            self.cancel_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._pull_worker is not None and self._pull_worker.isRunning():
            self._pull_worker.requestInterruption()
            self._pull_worker.wait(3000)
        super().closeEvent(event)
