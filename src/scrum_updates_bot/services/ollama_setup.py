from __future__ import annotations

import shutil
import subprocess
import sys


WINDOWS_INSTALL_COMMAND = [
    "powershell.exe",
    "-ExecutionPolicy",
    "Bypass",
    "-NoProfile",
    "-Command",
    "irm https://ollama.com/install.ps1 | iex",
]

LINUX_INSTALL_COMMAND = [
    "bash",
    "-lc",
    "curl -fsSL https://ollama.com/install.sh | sh",
]


def is_ollama_cli_installed() -> bool:
    return shutil.which("ollama") is not None


def get_ollama_install_command() -> list[str]:
    if sys.platform.startswith("win"):
        return WINDOWS_INSTALL_COMMAND.copy()
    if sys.platform.startswith("linux"):
        return LINUX_INSTALL_COMMAND.copy()
    raise RuntimeError(f"Automatic Ollama install is not supported on platform '{sys.platform}'.")


def ollama_install_command_text() -> str:
    if sys.platform.startswith("win"):
        return "irm https://ollama.com/install.ps1 | iex"
    if sys.platform.startswith("linux"):
        return "curl -fsSL https://ollama.com/install.sh | sh"
    return "Visit https://ollama.com/download"


def ollama_install_instructions() -> str:
    command = ollama_install_command_text()
    return (
        "Ollama does not appear to be installed.\n\n"
        "Install it with:\n"
        f"  {command}\n\n"
        "Then start Ollama and pull a model such as llama3.2:3b."
    )


def launch_ollama_install() -> subprocess.Popen[bytes]:
    return subprocess.Popen(get_ollama_install_command())