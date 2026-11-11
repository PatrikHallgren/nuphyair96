#!/bin/sh
# Build the Omarchy keymap against a pinned ablasik/nuphy-qmk checkout.
# The QMK tree is not vendored. Output is firmware/.build/*.bin.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
PIN=6101403bd61ffed5b9c1642d45bb742c263a815b
SRC=${AIR96_QMK_SRC:-$ROOT/.build/nuphy-qmk}

mkdir -p "$ROOT/.build"
if [ ! -d "$SRC/.git" ]; then
    git init -q "$SRC"
    git -C "$SRC" remote add origin https://github.com/ablasik/nuphy-qmk.git
fi
if [ "$(git -C "$SRC" rev-parse HEAD 2>/dev/null || true)" != "$PIN" ]; then
    git -C "$SRC" fetch --depth 1 origin "$PIN"
    git -C "$SRC" checkout --detach FETCH_HEAD
fi
git -C "$SRC" submodule update --init --recursive --depth 1

rm -rf "$SRC/keyboards/nuphy/air96_v2/ansi/keymaps/omarchy"
cp -a "$ROOT/keymaps/omarchy" "$SRC/keyboards/nuphy/air96_v2/ansi/keymaps/omarchy"

# `make` asks the QMK CLI to resolve the keyboard before arm-none-eabi-gcc runs.
if ! command -v qmk >/dev/null 2>&1; then
    echo "qmk was not found. Install it with: python3 -m pip install --user qmk" >&2
    echo "and put \"\$HOME/.local/bin\" on PATH. gcc-arm-none-eabi is also required." >&2
    exit 1
fi
# The checkout is pinned and shallow. Skip the CLI's submodule sync.
export SKIP_GIT=yes

python3 - "$SRC/keyboards/nuphy/air96_v2/ansi/keyboard.json" <<'PY'
import json
import sys
path = sys.argv[1]
with open(path, encoding="utf-8") as handle:
    data = json.load(handle)
data["usb"]["pid"] = "0x3266"
with open(path, "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2)
    handle.write("\n")
PY

JOBS=${AIR96_JOBS:-$(nproc)}
make -C "$SRC" -j"$JOBS" nuphy/air96_v2/ansi:omarchy
bin=$(find "$SRC" -name 'nuphy_air96_v2_ansi_omarchy.bin' -print -quit)
test -n "$bin"
cp "$bin" "$ROOT/.build/nuphy_air96_v2_ansi_omarchy.bin"
echo "built $ROOT/.build/nuphy_air96_v2_ansi_omarchy.bin"
