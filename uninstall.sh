#!/bin/bash

DOTDIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "  uninstalling teavostok1's dotfiles"
echo "  removing configs and restoring defaults"
echo ""

remove_link_or_dir() {
  local dst="$HOME/$2"
  if [ -L "$dst" ]; then
    rm "$dst"
    echo "    removed symlink $2"
  elif [ -e "$dst" ]; then
    rm -rf "$dst"
    echo "    removed $2"
  fi
  local bak="${dst}.bak"
  if [ -e "$bak" ]; then
    mv "$bak" "$dst"
    echo "    restored original $2 from backup"
  fi
}

remove_link_or_dir ".bashrc"             ".bashrc"
remove_link_or_dir ".config/hypr"        ".config/hypr"
remove_link_or_dir ".config/waybar"      ".config/waybar"
remove_link_or_dir ".config/swaync"      ".config/swaync"
remove_link_or_dir ".config/kitty"       ".config/kitty"
remove_link_or_dir ".config/rofi"        ".config/rofi"
remove_link_or_dir ".config/eww"         ".config/eww"
remove_link_or_dir ".config/wlogout"     ".config/wlogout"
remove_link_or_dir ".config/btop"        ".config/btop"
remove_link_or_dir ".config/cava"        ".config/cava"
remove_link_or_dir ".config/mpv"         ".config/mpv"
remove_link_or_dir ".config/mpd"         ".config/mpd"
remove_link_or_dir ".config/ncmpcpp"     ".config/ncmpcpp"
remove_link_or_dir ".config/gtk-3.0"     ".config/gtk-3.0"
remove_link_or_dir ".config/fontconfig"  ".config/fontconfig"

echo ""
echo "  killing running processes..."
pkill waybar 2>/dev/null && echo "    waybar stopped" || echo "    waybar not running"
pkill swaync 2>/dev/null && echo "    swaync stopped" || echo "    swaync not running"

echo ""
echo "  all dotfiles removed."
echo "  hyprland will start with its built-in defaults."
echo "  other programs will restart with defaults when you log in again."
echo ""
echo "  the cloned repo is still at $DOTDIR — remove it with:"
echo "    rm -rf $DOTDIR"
