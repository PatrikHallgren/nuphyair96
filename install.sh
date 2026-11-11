#!/bin/sh
# Install the Air96 theme-set hook, and optionally the bar plugin link.
# The hook calls this checkout's CLI. The bar plugin is not required.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
CLI="$ROOT/air96_cli.py"
HOOK_SOURCE="$ROOT/hooks/theme-set.d/50-air96-sync"
HOOK_DIR="$HOME/.config/omarchy/hooks/theme-set.d"
HOOK_PATH="$HOOK_DIR/50-air96-sync"
PLUGIN_DIR="$HOME/.config/omarchy/plugins"
PLUGIN_LINK="$PLUGIN_DIR/local.nuphy-air96"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
PATH_FILE="$CONFIG_HOME/omarchy-nuphy-air96/cli-path"

usage() {
  cat <<EOF
Usage: ./install.sh [--no-plugin | --plugin] 
       ./install.sh --uninstall

Installs ~/.config/omarchy/hooks/theme-set.d/50-air96-sync so Omarchy runs
\`python3 $CLI sync\` after every theme change. The bar plugin is not required.

  --no-plugin   Hook only. Theme follow works from the CLI.
  --plugin      Also link this checkout to ~/.config/omarchy/plugins/local.nuphy-air96
  --uninstall   Remove the hook, the recorded CLI path, and a plugin symlink
                this script created. Config and a real plugin directory stay.

Default is the hook and the plugin link. Enable the bar with:
  omarchy plugin enable local.nuphy-air96
EOF
}

die() {
  echo "$1" >&2
  exit 1
}

same_path() {
  [ "$(readlink -f "$1")" = "$(readlink -f "$2")" ]
}

install_hook() {
  [ -f "$CLI" ] || die "air96_cli.py is not next to install.sh"
  [ -f "$HOOK_SOURCE" ] || die "Theme hook source is missing: $HOOK_SOURCE"
  mkdir -p "$HOOK_DIR" "$(dirname "$PATH_FILE")"
  printf '%s\n' "$CLI" > "$PATH_FILE.tmp"
  mv "$PATH_FILE.tmp" "$PATH_FILE"
  ln -sfn "$HOOK_SOURCE" "$HOOK_PATH"
  echo "Theme hook: $HOOK_PATH"
  echo "CLI:        $CLI"
  echo "Follow must be on (\`python3 air96_cli.py apply --follow on\`) or sync does nothing."
}

install_plugin() {
  if [ -e "$PLUGIN_LINK" ] && [ ! -L "$PLUGIN_LINK" ]; then
    if same_path "$PLUGIN_LINK" "$ROOT"; then
      echo "Bar plugin is already this checkout: $PLUGIN_LINK"
    else
      echo "Bar plugin already installed at $PLUGIN_LINK (left in place)."
    fi
    echo "Enable it with: omarchy plugin enable local.nuphy-air96"
    return 0
  fi
  mkdir -p "$PLUGIN_DIR"
  ln -sfn "$ROOT" "$PLUGIN_LINK"
  echo "Bar plugin link: $PLUGIN_LINK"
  echo "Enable it with: omarchy plugin enable local.nuphy-air96"
  echo "Then restart the shell. The icon target is: omarchy-shell air96 toggle"
}

uninstall() {
  if [ -e "$HOOK_PATH" ] || [ -L "$HOOK_PATH" ]; then
    if grep -q AIR96_HOOK_MARKER "$HOOK_PATH" 2>/dev/null; then
      rm -f "$HOOK_PATH"
      echo "Removed $HOOK_PATH"
      rmdir "$HOOK_DIR" 2>/dev/null || true
    else
      echo "Left $HOOK_PATH in place (it is not the Air96 hook)."
    fi
  else
    echo "No Air96 theme hook at $HOOK_PATH"
  fi
  if [ -f "$PATH_FILE" ]; then
    rm -f "$PATH_FILE"
    echo "Removed $PATH_FILE"
  fi
  if [ -L "$PLUGIN_LINK" ] && same_path "$PLUGIN_LINK" "$ROOT"; then
    rm -f "$PLUGIN_LINK"
    echo "Removed plugin link $PLUGIN_LINK"
  elif [ -d "$PLUGIN_LINK" ]; then
    echo "Left the bar plugin directory in place: $PLUGIN_LINK"
    echo "Disable it with: omarchy plugin disable local.nuphy-air96"
    echo "Remove it with:  omarchy plugin remove local.nuphy-air96 --yes"
  fi
  echo "Kept ~/.config/omarchy-nuphy-air96/config.json if it exists."
}

mode="install"
plugin=1
while [ $# -gt 0 ]; do
  case "$1" in
    --uninstall) mode="uninstall" ;;
    --no-plugin) plugin=0 ;;
    --plugin) plugin=1 ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown argument: $1" ;;
  esac
  shift
done

if [ "$mode" = "uninstall" ]; then
  uninstall
else
  install_hook
  if [ "$plugin" -eq 1 ]; then
    install_plugin
  else
    echo "Bar plugin was not linked. Add it later with: ./install.sh --plugin"
    echo "Or: omarchy plugin add https://github.com/PatrikHallgren/nuphyair96 --enable --yes"
  fi
fi
