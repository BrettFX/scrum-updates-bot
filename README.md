# Scrum Updates Bot

Scrum Updates Bot is a cross-platform desktop application for turning messy or structured scrum notes into polished YTB status updates for Teams and Outlook.

## V1 scope

- PySide6 desktop UI for Windows and Linux
- Ollama-backed local LLM generation
- Structured and freeform note handling
- Rich-text YTB preview with bold labels and hyperlinks
- Copy to clipboard as both HTML and plain text
- Autosaved session restore plus named drafts
- Export to `.txt`, `.md`, and `.html`
- Template presets for different YTB tones
- Structured-note fast path for low-latency formatting
- Streaming progress updates during freeform generation

## Current experience

- Structured story-block input is formatted deterministically for speed and preset consistency.
- Freeform notes use Ollama with live progress updates in the loading area.
- The last session is restored automatically, including notes, generated output, selected model, selected preset, and activity history.
- Presets currently include `Standard YTB`, `Leadership Update`, and `Concise Standup`.
- Full story titles can be copied/exported as hyperlinks when ticket URLs are available.

## Architecture

- `src/scrum_updates_bot/core`: domain models, prompts, rendering, fallback parsing
- `src/scrum_updates_bot/services`: Ollama integration and generation orchestration
- `src/scrum_updates_bot/storage`: settings and draft persistence
- `src/scrum_updates_bot/ui`: PySide6 desktop interface and worker threads

## Prerequisites

1. Python 3.11+
2. Ollama installed locally
3. At least one local Ollama model pulled, for example `llama3.2:3b`

## Setup

```bash
./scripts/bootstrap_linux.sh
```

This project uses a repo-local `.venv` on Linux. That avoids conflicts with an active Anaconda shell such as `data-science`, because the scripts call `.venv/bin/python` directly instead of relying on the shell's current `python`.

## Run

```bash
./scripts/run_linux.sh
```

This launcher uses the repo-local `.venv` directly, so it is safe even when an Anaconda environment such as `data-science` is active in the shell.

If you want to test the packaged binary after building, run:

```bash
./dist/scrum-updates-bot/scrum-updates-bot
```

## Ollama quick start

```bash
ollama serve
ollama pull llama3.2:3b
```

The app will also let you refresh the local model list and trigger model pulls from the UI.

## Windows direction

The next packaging target is a Windows executable and installer built natively on Windows from the same codebase. The current repository already includes a PyInstaller starter script for that workflow in `scripts/build_windows.ps1`.

## Packaging direction

The repository includes PyInstaller starter scripts for Windows and Linux packaging. Builds should be produced natively on each target OS and use the repo-local virtual environment rather than the active conda environment.

For Linux, the recommended first-class installer target is Ubuntu and Debian via `.deb`. That gives the cleanest dependency story because `apt` can install the required Qt/XCB libraries automatically.

### Linux build

```bash
./scripts/build_linux.sh
```

### Debian and Ubuntu package

```bash
./scripts/build_deb.sh
```

This produces a `.deb` installer that places the app under `/opt/scrum-updates-bot`, installs a launcher at `/usr/bin/scrum-updates-bot`, and declares the required shared-library dependencies.

If the packaged app fails to launch on Linux with Qt or XCB plugin errors, install the common runtime libraries first:

```bash
sudo apt install libxkbcommon-x11-0 libxcb-cursor0 libxcb-xkb1 libxcb-render-util0 libxcb-keysyms1 libxcb-util1 libxcb-icccm4 libxcb-image0 libtiff5
```

On newer Ubuntu releases, `libtiff5` may be replaced by `libtiff6`.

### Windows build

Use `scripts/build_windows.ps1` from a Windows PowerShell session after creating a local `.venv` and installing `.[dev,build]` into it.

See [docs/PACKAGING.md](docs/PACKAGING.md) for the distro support strategy and installer rationale.

## Future enhancements

- Stage-based progress updates such as `Parsing notes`, `Drafting response`, and `Formatting final output`
- A true spinner-style loading indicator instead of the current indeterminate progress bar
- Streaming live draft preview while the final structured result is still being assembled
- Continued UI refinement for a more polished desktop-app feel

## Testing

```bash
pytest
```