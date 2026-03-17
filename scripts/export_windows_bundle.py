from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


EXCLUDED_PARTS = {
    ".git",
    ".venv",
    ".pytest_cache",
    "build",
    "dist",
    "output",
    "__pycache__",
}

EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".pyd",
}


def should_include(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    return True


def build_archive_name(root: Path) -> str:
    version = "0.1.0"
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        for line in pyproject.read_text(encoding="utf-8").splitlines():
            if line.startswith("version = "):
                version = line.split("=", 1)[1].strip().strip('"')
                break
    return f"scrum-updates-bot-windows-src-{version}.zip"


def export_bundle(root: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_dir():
                continue
            if not should_include(path, root):
                continue
            archive.write(path, path.relative_to(root))
    return destination


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Export a Windows-ready source bundle from the current working tree.")
    parser.add_argument(
        "destination",
        nargs="?",
        default=str(root / "output" / "windows-bundle" / build_archive_name(root)),
        help="Path to the output .zip file.",
    )
    args = parser.parse_args()

    destination = Path(args.destination).expanduser().resolve()
    archive_path = export_bundle(root, destination)
    print(f"Created Windows source bundle: {archive_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())