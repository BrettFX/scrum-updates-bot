# Packaging Strategy

## Recommendation

For Linux, support Ubuntu and Debian first with a `.deb` package. That is the most pragmatic starting point because `apt` can install the Qt/XCB shared-library dependencies automatically.

For Windows, build a native installer separately on Windows.

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