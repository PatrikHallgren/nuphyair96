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
  --plugin      Link this checkout to ~/.config/omarchy/plugins/local.nuphy-air96,
                restart the bar worker, and turn per-key push on.
  --uninstall   Remove the hook, the recorded CLI path, and a plugin symlink
                this script created. Config and a plugin backup stay.

A plugin directory Omarchy copied is moved aside and replaced with a link to
this checkout, so git pull updates the bar. Default is the hook and that link.
Enable the bar with:
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

restart_worker() {
  found=0
  for dir in /proc/[0-9]*; do
    [ -r "$dir/cmdline" ] || continue
    cmd=$(tr '\0' ' ' < "$dir/cmdline" 2>/dev/null || true)
    case "$cmd" in
      *air96_worker.py*)
        pid=${dir#/proc/}
        if kill "$pid" 2>/dev/null; then
          echo "Stopped bar worker pid $pid so it reloads this checkout."
          found=1
        fi
        ;;
    esac
  done
  if [ "$found" -eq 0 ]; then
    echo "No air96_worker.py is running. Enable the plugin, then restart the shell if the bar is not up."
  else
    echo "The bar starts the worker again in a few seconds from $PLUGIN_LINK."
  fi
}

install_plugin() {
  mkdir -p "$PLUGIN_DIR"
  if [ -L "$PLUGIN_LINK" ] || [ ! -e "$PLUGIN_LINK" ]; then
    ln -sfn "$ROOT" "$PLUGIN_LINK"
    echo "Bar plugin link: $PLUGIN_LINK -> $ROOT"
  elif same_path "$PLUGIN_LINK" "$ROOT"; then
    echo "Bar plugin is this checkout: $PLUGIN_LINK"
  else
    backup="${PLUGIN_LINK}.previous"
    rm -rf "$backup"
    mv "$PLUGIN_LINK" "$backup"
    ln -sfn "$ROOT" "$PLUGIN_LINK"
    echo "Replaced the separate plugin copy with a link to this checkout."
    echo "Previous copy: $backup"
    echo "git pull in this checkout is what the bar runs. A second clone is not used."
  fi
  echo "Enable it with: omarchy plugin enable local.nuphy-air96"
  echo "The icon target is: omarchy-shell air96 toggle"
  restart_worker
  python3 "$CLI" push on
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
