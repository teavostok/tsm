#!/bin/bash
set -e

DOTDIR="$(cd "$(dirname "$0")" && pwd)"

echo "  bootstrapping dotfiles..."

link() {
  src="$DOTDIR/$1"
  dst="$HOME/$2"
  mkdir -p "$(dirname "$dst")"
  if [ -e "$dst" ] && [ ! -L "$dst" ]; then
    mv "$dst" "${dst}.bak"
    echo "    backed up $dst → ${dst}.bak"
  fi
  ln -sfn "$src" "$dst"
  echo "    linked $1 → $dst"
}

link ".bashrc"                ".bashrc"
link ".config/hypr"           ".config/hypr"
link ".config/waybar"         ".config/waybar"
link ".config/swaync"         ".config/swaync"
link ".config/kitty"          ".config/kitty"
link ".config/rofi"           ".config/rofi"
link ".config/eww"            ".config/eww"
link ".config/wlogout"        ".config/wlogout"
link ".config/btop"           ".config/btop"
link ".config/cava"           ".config/cava"
link ".config/mpv"            ".config/mpv"
link ".config/mpd"            ".config/mpd"
link ".config/ncmpcpp"        ".config/ncmpcpp"
link ".config/gtk-3.0"        ".config/gtk-3.0"
link ".config/fontconfig"     ".config/fontconfig"

echo "  done — reload your compositor to apply changes."
