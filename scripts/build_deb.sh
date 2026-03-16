#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PKG_NAME="scrum-updates-bot"
VERSION="$(awk -F ' = ' '/^version = / {gsub(/"/, "", $2); print $2}' "$ROOT_DIR/pyproject.toml")"
ARCH="amd64"
STAGE_DIR="$ROOT_DIR/build/deb/${PKG_NAME}_${VERSION}_${ARCH}"
APP_DIR="$STAGE_DIR/opt/$PKG_NAME"
BIN_DIR="$STAGE_DIR/usr/bin"
DESKTOP_DIR="$STAGE_DIR/usr/share/applications"
DEBIAN_DIR="$STAGE_DIR/DEBIAN"

rm -rf "$STAGE_DIR"
mkdir -p "$APP_DIR" "$BIN_DIR" "$DESKTOP_DIR" "$DEBIAN_DIR"

"$ROOT_DIR/scripts/build_linux.sh"

cp -R "$ROOT_DIR/dist/$PKG_NAME/." "$APP_DIR/"

cat > "$BIN_DIR/$PKG_NAME" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exec /opt/scrum-updates-bot/scrum-updates-bot "$@"
EOF
chmod 755 "$BIN_DIR/$PKG_NAME"

install -m 644 "$ROOT_DIR/packaging/linux/assets/scrum-updates-bot.desktop" "$DESKTOP_DIR/scrum-updates-bot.desktop"
install -m 755 "$ROOT_DIR/packaging/linux/debian/postinst" "$DEBIAN_DIR/postinst"

cat > "$DEBIAN_DIR/control" <<EOF
Package: $PKG_NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Maintainer: Brian Allen
Depends: libxkbcommon-x11-0, libxcb-cursor0, libxcb-xkb1, libxcb-render-util0, libxcb-keysyms1, libxcb-util1, libxcb-icccm4, libxcb-image0, libtiff5 | libtiff6
Description: Desktop chatbot for generating YTB scrum updates with local LLMs.
 Scrum Updates Bot turns messy or structured scrum notes into polished Yesterday,
 Today, Blockers updates for Teams and Outlook using a local Ollama model.
EOF

chmod 644 "$DEBIAN_DIR/control"
dpkg-deb --build "$STAGE_DIR"

echo "Built Debian package: ${STAGE_DIR}.deb"