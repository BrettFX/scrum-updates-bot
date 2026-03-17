# Packaging Strategy

## Recommendation

For Linux, support Ubuntu and Debian first with a `.deb` package. That is the most pragmatic starting point because `apt` can install the Qt/XCB shared-library dependencies automatically.

For Windows, build the executable and installer natively on Windows.

The repo now exposes one primary installer entrypoint per platform:

1. `./scripts/install_linux.sh`
2. `.\scripts\install_windows.ps1`

For end users, the preferred distribution path is GitHub Releases rather than local source builds.

For developers working from Linux, the preferred Windows packaging path is GitHub-hosted Windows runners rather than local cross-compilation.

## Windows plan

The Windows packaging flow is:

1. Create a local `.venv` and install dependencies with `.\scripts\install_windows.ps1`.
2. Build the PyInstaller GUI executable in the same step.
3. Optionally wrap the PyInstaller output in an Inno Setup installer with `.\scripts\install_windows.ps1 -WithInstaller`.

The primary runnable artifact is `dist\scrum-updates-bot\scrum-updates-bot.exe`.

For local Windows source builds, Python 3.12 is the supported target. Python 3.13 local builds have shown PySide6 DLL import failures.

The installer path is optional but recommended for distributing the app to end users because it adds shortcuts and a clean install directory.

The repo also includes a GitHub Actions workflow that builds and publishes release artifacts:

1. Windows Inno Setup installer `.exe`
2. Windows portable `.zip`
3. Linux `.deb`
4. Linux portable `.tar.gz`

## Linux to Windows builds

PyInstaller does not provide a reliable native Linux-to-Windows cross-compile path for this app. You can sometimes force it with Wine plus a Windows Python environment, but that is brittle and becomes harder to support than a native Windows build.

The practical approach is:

1. Export a source bundle from Linux with `./scripts/export_windows_bundle.sh`.
2. Extract it into a normal Windows folder.
3. Run `.\scripts\install_windows.ps1` there.

If you want to stay on Linux end to end, use `./scripts/build_remote_packages.sh` with a GitHub token. That script dispatches the GitHub Actions packaging workflow, waits for completion, and downloads the Windows and Linux artifact zip files locally.

Push your current branch before triggering the workflow, because remote builds run the code already on GitHub.

Recommended token permissions:

1. Fine-grained PAT: repository access to this repo with `Actions: Read and write`, `Contents: Read and write`, and `Metadata: Read`.
2. Classic PAT: `repo` and `workflow` scopes.

## Current Windows runtime issue

If a locally built Windows executable fails during `PySide6.QtWidgets` import, the most likely causes are an incomplete PySide6 bundle or a Windows-specific runtime mismatch in the local build environment.

The packaging spec now explicitly collects PySide6 and `shiboken6` binaries, data files, and hidden imports to reduce that risk. Release builds should be produced on GitHub's Windows runners with Python 3.12 for better repeatability.

## Why not every Linux distro first

Linux desktop packaging is fragmented. A single package format does not cover Ubuntu, Debian, Fedora, RHEL, Arch, and others equally well.

The least risky rollout is:

1. Primary Linux target: `.deb` for Ubuntu and Debian.
2. Secondary Linux target later: AppImage for a broader distro reach.
3. Optional later targets if needed: `.rpm` for Fedora/RHEL.

## V1 Linux package plan

- Build the app with PyInstaller in `onedir` mode.
- Package the bundle into a `.deb` that installs into `/opt/scrum-updates-bot`.
- Add a wrapper binary in `/usr/bin/scrum-updates-bot`.
- Install a desktop entry so the app appears in desktop launchers.
- Declare the required Qt/XCB runtime libraries in the Debian package dependencies.
- Do not hard-depend on an `ollama` Debian package, because users may install Ollama through different channels. Instead, check for it during install and print guidance.

## Dependency strategy

For Debian and Ubuntu, let the package manager install the Linux shared libraries. This is easier and more reliable than trying to bundle those libraries manually.

For the local LLM runtime:

- Keep Ollama as an external prerequisite.
- Detect it in the app and in post-install messaging.
- Provide setup instructions instead of trying to package Ollama into the application.

## Non-Debian Linux

For non-Debian distros, the best next step is usually an AppImage or a tarball plus distro-specific dependency instructions. That gives broader reach without committing to distro-specific installers immediately.