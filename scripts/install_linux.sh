#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || true)}"
PACKAGE_NAME="scrum-updates-bot"
SETUP_ONLY=false
BUILD_ONLY=false
BUILD_DEB=false
INSTALL_OLLAMA=false
SKIP_OLLAMA_CHECK=false

for arg in "$@"; do
  case "$arg" in
    --setup-only)
      SETUP_ONLY=true
      ;;
    --build-only)
      BUILD_ONLY=true
      ;;
    --deb)
      BUILD_DEB=true
      ;;
    --install-ollama)
      INSTALL_OLLAMA=true
      ;;
    --skip-ollama-check)
      SKIP_OLLAMA_CHECK=true
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      echo "Usage: $0 [--setup-only | --build-only | --deb | --install-ollama | --skip-ollama-check]" >&2
      exit 1
      ;;
  esac
done

if [[ "$SETUP_ONLY" == true && "$BUILD_ONLY" == true ]]; then
  echo "Choose either --setup-only or --build-only, not both." >&2
  exit 1
fi

if [[ "$SETUP_ONLY" == true && "$BUILD_DEB" == true ]]; then
  echo "The --deb option requires a build. Remove --setup-only and try again." >&2
  exit 1
fi

setup_environment() {
  if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
    echo "Python 3 interpreter not found. Set PYTHON_BIN or install python3." >&2
    exit 1
  fi

  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi

  "$VENV_DIR/bin/python" -m pip install --upgrade pip
  "$VENV_DIR/bin/python" -m pip install -e "$ROOT_DIR[build]"
}

install_ollama() {
  if command -v ollama >/dev/null 2>&1; then
    echo "Ollama is already installed."
    return
  fi

  if ! command -v curl >/dev/null 2>&1; then
    echo "curl is required to install Ollama automatically on Linux." >&2
    echo "Install curl and then run: curl -fsSL https://ollama.com/install.sh | sh" >&2
    exit 1
  fi

  echo "Installing Ollama..."
  bash -lc 'curl -fsSL https://ollama.com/install.sh | sh'

  if ! command -v ollama >/dev/null 2>&1; then
    echo "Ollama installation finished but the 'ollama' command is still not available on PATH." >&2
    echo "You may need to open a new shell session before running it." >&2
  fi
}

ensure_ollama() {
  if [[ "$SKIP_OLLAMA_CHECK" == true || "$BUILD_ONLY" == true || "$BUILD_DEB" == true || -n "${CI:-}" ]]; then
    return
  fi

  if command -v ollama >/dev/null 2>&1; then
    echo "Ollama installation verified."
    return
  fi

  echo "Ollama was not found on this system."

  if [[ "$INSTALL_OLLAMA" == true ]]; then
    install_ollama
    return
  fi

  if [[ -t 0 ]]; then
    read -r -p "Install Ollama now? [y/N] " reply
    if [[ "$reply" =~ ^[Yy]$ ]]; then
      install_ollama
      return
    fi
  fi

  cat <<'EOF'
Install Ollama later with:

  curl -fsSL https://ollama.com/install.sh | sh
  ollama serve
  ollama pull llama3.2:3b
EOF
}

build_bundle() {
  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    echo "Missing virtual environment. Run $ROOT_DIR/scripts/install_linux.sh first." >&2
    exit 1
  fi

  cd "$ROOT_DIR"
  "$VENV_DIR/bin/python" -m PyInstaller --noconfirm --clean --onedir --paths src --name "$PACKAGE_NAME" src/scrum_updates_bot/main.py

  local bundle_path="$ROOT_DIR/dist/$PACKAGE_NAME/$PACKAGE_NAME"
  if [[ ! -x "$bundle_path" ]]; then
    echo "Build completed without producing the expected executable: $bundle_path" >&2
    exit 1
  fi

  echo "Linux build complete: $bundle_path"
}

build_deb_package() {
  if ! command -v dpkg-deb >/dev/null 2>&1; then
    echo "dpkg-deb is required to build a .deb package." >&2
    exit 1
  fi

  local version
  version="$(awk -F ' = ' '/^version = / {gsub(/"/, "", $2); print $2}' "$ROOT_DIR/pyproject.toml")"
  local arch="amd64"
  local stage_dir="$ROOT_DIR/build/deb/${PACKAGE_NAME}_${version}_${arch}"
  local app_dir="$stage_dir/opt/$PACKAGE_NAME"
  local bin_dir="$stage_dir/usr/bin"
  local desktop_dir="$stage_dir/usr/share/applications"
  local debian_dir="$stage_dir/DEBIAN"

  rm -rf "$stage_dir"
  mkdir -p "$app_dir" "$bin_dir" "$desktop_dir" "$debian_dir"

  cp -R "$ROOT_DIR/dist/$PACKAGE_NAME/." "$app_dir/"

  cat > "$bin_dir/$PACKAGE_NAME" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exec /opt/scrum-updates-bot/scrum-updates-bot "$@"
EOF
  chmod 755 "$bin_dir/$PACKAGE_NAME"

  install -m 644 "$ROOT_DIR/packaging/linux/assets/scrum-updates-bot.desktop" "$desktop_dir/scrum-updates-bot.desktop"
  install -m 755 "$ROOT_DIR/packaging/linux/debian/postinst" "$debian_dir/postinst"

  cat > "$debian_dir/control" <<EOF
Package: $PACKAGE_NAME
Version: $version
Section: utils
Priority: optional
Architecture: $arch
Maintainer: Brian Allen
Depends: libxkbcommon-x11-0, libxcb-cursor0, libxcb-xkb1, libxcb-render-util0, libxcb-keysyms1, libxcb-util1, libxcb-icccm4, libxcb-image0, libtiff5 | libtiff6
Description: Desktop chatbot for generating YTB scrum updates with local LLMs.
 Scrum Updates Bot turns messy or structured scrum notes into polished Yesterday,
 Today, Blockers updates for Teams and Outlook using a local Ollama model.
EOF

  chmod 644 "$debian_dir/control"
  dpkg-deb --build "$stage_dir"

  echo "Debian package complete: ${stage_dir}.deb"
}

if [[ "$BUILD_ONLY" != true ]]; then
  setup_environment
  ensure_ollama
fi

if [[ "$SETUP_ONLY" != true ]]; then
  build_bundle
fi

if [[ "$BUILD_DEB" == true ]]; then
  build_deb_package
fi

if [[ "$SETUP_ONLY" == true ]]; then
  echo "Linux environment is ready."
  echo "Run the app with: $ROOT_DIR/scripts/run_linux.sh"
elif [[ "$BUILD_DEB" == true ]]; then
  echo "Run the packaged app with: $ROOT_DIR/dist/$PACKAGE_NAME/$PACKAGE_NAME"
else
  echo "Run the packaged app with: $ROOT_DIR/dist/$PACKAGE_NAME/$PACKAGE_NAME"
fi