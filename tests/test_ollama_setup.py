from unittest.mock import patch

from scrum_updates_bot.services import ollama_setup


def test_windows_install_command_text() -> None:
    with patch.object(ollama_setup.sys, "platform", "win32"):
        assert ollama_setup.ollama_install_command_text() == "irm https://ollama.com/install.ps1 | iex"


def test_linux_install_command_text() -> None:
    with patch.object(ollama_setup.sys, "platform", "linux"):
        assert ollama_setup.ollama_install_command_text() == "curl -fsSL https://ollama.com/install.sh | sh"


def test_is_ollama_cli_installed_uses_path_lookup() -> None:
    with patch.object(ollama_setup.shutil, "which", return_value="/usr/bin/ollama"):
        assert ollama_setup.is_ollama_cli_installed() is True