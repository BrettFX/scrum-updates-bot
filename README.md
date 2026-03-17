# Scrum Updates Bot

Scrum Updates Bot is a cross-platform desktop application for turning messy or structured scrum notes into polished YTB status updates for Teams and Outlook.

For end users, the target distribution model is GitHub Releases: download a Windows installer `.exe` or a Linux `.deb` package without building from source.

For developers working from Linux, the preferred Windows packaging path is to trigger the GitHub Actions Windows build from Linux and download the artifacts back locally.

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

1. Python 3.11+ in general, but Python 3.12 is the supported target for local Windows packaging
2. Ollama installed locally
3. At least one local Ollama model pulled, for example `llama3.2:3b`

## Quick start

Linux uses one script to set up the environment and build a runnable app bundle:

```bash
./scripts/install_linux.sh
```

That creates a repo-local `.venv`, installs the app, and builds the runnable binary at `dist/scrum-updates-bot/scrum-updates-bot`.

Windows also uses one script. Run it from a native Windows PowerShell session, not from WSL:

```powershell
.\scripts\install_windows.ps1
```

That creates `.venv`, installs the app, and builds the runnable executable at `dist\scrum-updates-bot\scrum-updates-bot.exe`.

For local Windows packaging, use Python 3.12 if possible. Python 3.13 builds have shown `PySide6.QtWidgets` DLL load failures in local packaging.

This local build flow is mainly for development. End users should use the packaged release artifacts instead of running PowerShell scripts.

This repo still uses a local `.venv` on both platforms, so it does not depend on your active Anaconda shell.

If PowerShell warns that the script came from another machine, run this once first from the extracted project folder:

```powershell
Unblock-File .\scripts\install_windows.ps1
```

If `py` is unavailable on your Windows machine, the installer script will also try a native `python` command on `PATH`. For local Windows packaging, install Python 3.12 first and verify one of these works:

```powershell
py -0p
python --version
```

If your source tree currently lives under WSL, export a Windows-ready `.zip` from Linux first and then extract it into a normal Windows folder such as `C:\Users\<you>\Downloads\scrum-updates-bot`:

```bash
./scripts/export_windows_bundle.sh
```

You can also pass a custom destination path for the `.zip` file.

If you want to avoid using a Windows machine during packaging, trigger the GitHub Actions packaging workflow from Linux instead:

```bash
export GITHUB_TOKEN=your_token_here
git push origin master
./scripts/build_remote_packages.sh
```

That runs the Windows and Linux package builds on GitHub-hosted runners and downloads the resulting artifact zip files into `output/github-actions-artifacts`.

For the token:

- Fine-grained PAT: grant repository access to this repo with `Actions: Read and write`, `Contents: Read and write`, and `Metadata: Read`.
- Classic PAT: grant `repo` and `workflow` scopes.

Remote builds always run the code already pushed to GitHub, not unpushed local commits.

## Run

```bash
./dist/scrum-updates-bot/scrum-updates-bot
```

If you want the editable development launcher instead of the packaged Linux build, use:

```bash
./scripts/run_linux.sh
```

On Windows, run the built executable with:

```powershell
.\dist\scrum-updates-bot\scrum-updates-bot.exe
```

If you want the editable development launcher on Windows instead, use:

```powershell
.\.venv\Scripts\python.exe -m scrum_updates_bot
```

## Ollama quick start

```bash
ollama serve
ollama pull llama3.2:3b
```

The app will also let you refresh the local model list and trigger model pulls from the UI.

## Windows direction

The Windows `.exe` should be built natively on Windows. PyInstaller does not reliably cross-compile a true Windows executable from Linux, so the pragmatic flow is still:

1. From Linux or WSL, export a Windows-ready bundle with `./scripts/export_windows_bundle.sh`.
2. Extract that bundle into a normal Windows folder.
3. Run `./scripts/install_windows.ps1` in Windows PowerShell using Python 3.12.

If you want to stay entirely on Linux, do not try to cross-compile locally. Use `./scripts/build_remote_packages.sh` to trigger the GitHub Actions Windows build and download the finished artifacts.

For non-technical users, the better path is a GitHub Release that includes:

1. A Windows GUI installer `.exe` produced by Inno Setup.
2. A Windows portable `.zip` for users who just want to unpack and run.
3. A Linux `.deb` package for Ubuntu and Debian users.
4. A Linux portable `.tar.gz` for manual unpack-and-run installs.

If a local Windows source build fails with a `PySide6.QtWidgets` DLL import error, stop using that local build and switch to a Release-built installer or GitHub Actions Windows artifact.

Recommended workflow from WSL:

1. Create a Windows source bundle with `./scripts/export_windows_bundle.sh`.
2. Move or extract that `.zip` into a normal Windows path such as `C:\Users\<you>\Downloads\scrum-updates-bot`.
3. Open that extracted folder in Windows PowerShell.
4. Run `./scripts/install_windows.ps1` there.

## Packaging direction

The repository includes a single installer entrypoint per platform:

- `./scripts/install_linux.sh`
- `.\scripts\install_windows.ps1`

For Linux, the recommended first-class installer target is Ubuntu and Debian via `.deb`. That gives the cleanest dependency story because `apt` can install the required Qt/XCB libraries automatically.

### Linux build

```bash
./scripts/install_linux.sh
```

### Debian and Ubuntu package

```bash
./scripts/install_linux.sh --deb
```

This produces a `.deb` installer that places the app under `/opt/scrum-updates-bot`, installs a launcher at `/usr/bin/scrum-updates-bot`, and declares the required shared-library dependencies.

If the packaged app fails to launch on Linux with Qt or XCB plugin errors, install the common runtime libraries first:

```bash
sudo apt install libxkbcommon-x11-0 libxcb-cursor0 libxcb-xkb1 libxcb-render-util0 libxcb-keysyms1 libxcb-util1 libxcb-icccm4 libxcb-image0 libtiff5
```

On newer Ubuntu releases, `libtiff5` may be replaced by `libtiff6`.

### Windows build

Build the Windows executable natively on Windows from PowerShell:

```powershell
.\scripts\install_windows.ps1
```

This produces the runnable executable at `dist\scrum-updates-bot\scrum-updates-bot.exe`.

Use Python 3.12 for this local build path.

To create a Windows installer, install Inno Setup 6 and run:

```powershell
.\scripts\install_windows.ps1 -WithInstaller
```

This produces an installer `.exe` under `output\windows-installer`.

## GitHub Releases

The repository now includes a GitHub Actions workflow at `.github/workflows/release-packages.yml` that can:

- build a Windows GUI installer `.exe`
- build a Windows portable `.zip`
- build a Linux `.deb`
- build a Linux portable `.tar.gz`
- attach those artifacts to a tagged GitHub Release

For iterative development from Linux, `./scripts/build_remote_packages.sh` can dispatch that workflow without creating a release.

To publish a release, push a tag such as `v0.1.0` to GitHub.

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