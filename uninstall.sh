#!/bin/bash
set -e

DOTDIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "  uninstalling teavostok1's dotfiles"
echo ""

restore() {
  src="$DOTDIR/$1"
  dst="$HOME/$2"
  if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
    rm "$dst"
    echo "    removed symlink $2"
    bak="${dst}.bak"
    if [ -e "$bak" ]; then
      mv "$bak" "$dst"
      echo "    restored original $2 from backup"
    fi
  fi
}

restore ".bashrc"                ".bashrc"
restore ".config/hypr"           ".config/hypr"
restore ".config/waybar"         ".config/waybar"
restore ".config/swaync"         ".config/swaync"
restore ".config/kitty"          ".config/kitty"
restore ".config/rofi"           ".config/rofi"
restore ".config/eww"            ".config/eww"
restore ".config/wlogout"        ".config/wlogout"
restore ".config/btop"           ".config/btop"
restore ".config/cava"           ".config/cava"
restore ".config/mpv"            ".config/mpv"
restore ".config/mpd"            ".config/mpd"
restore ".config/ncmpcpp"        ".config/ncmpcpp"
restore ".config/gtk-3.0"        ".config/gtk-3.0"
restore ".config/fontconfig"     ".config/fontconfig"

echo ""
echo "  dotfiles unlinked. originals restored where backups existed."
echo "  the cloned repo is still at $DOTDIR — remove it with:"
echo "    rm -rf $DOTDIR"
