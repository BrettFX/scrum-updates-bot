#!/usr/bin/env bash
set -euo pipefail

missing=0
for lib in \
  libxkbcommon-x11.so.0 \
  libxcb-cursor.so.0 \
  libxcb-xkb.so.1 \
  libxcb-render-util.so.0 \
  libxcb-keysyms.so.1 \
  libxcb-util.so.1 \
  libxcb-icccm.so.4 \
  libxcb-image.so.0
do
  if ! ldconfig -p | grep -q "$lib"; then
    echo "Missing: $lib"
    missing=1
  fi
done

if ldconfig -p | grep -q 'libtiff.so.5'; then
  :
elif ldconfig -p | grep -q 'libtiff.so.6'; then
  :
else
  echo "Missing: libtiff.so.5 or libtiff.so.6"
  missing=1
fi

if [[ $missing -eq 0 ]]; then
  echo "Linux Qt runtime dependencies look available."
else
  echo "Install the missing Qt runtime libraries before running the packaged app."
  exit 1
fi