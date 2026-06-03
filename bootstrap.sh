#!/bin/bash
set -e

DOTDIR="$(cd "$(dirname "$0")" && pwd)"
MODE="${1:-install}"

echo "  teavostok1's dotfiles"

link() {
  src="$DOTDIR/$1"
  dst="$HOME/$2"
  mkdir -p "$(dirname "$dst")"
  if [ -e "$dst" ] && [ ! -L "$dst" ]; then
    mv "$dst" "${dst}.bak"
    echo "    backed up $2 → ${2}.bak"
  fi
  ln -sfn "$src" "$dst"
  echo "    linked $1 → $2"
}

installed() {
  pacman -Q "$1" &>/dev/null
}

try_install() {
  local pkg="$1"
  local desc="$2"
  if installed "$pkg"; then
    echo "    $pkg ✓"
  else
    echo ""
    read -r -p "  install $pkg? ($desc) [y/N] " ans
    if [[ "$ans" =~ ^[yY] ]]; then
      yay -S --noconfirm "$pkg" 2>/dev/null || sudo pacman -S --noconfirm "$pkg" 2>/dev/null || echo "    could not install $pkg (install manually)"
    fi
  fi
}

install_extras() {
  echo ""
  echo "  optional extras"

  try_install "python-pillow"    "album art color extraction for mpris-glow"
  try_install "playerctl"        "media player control (mpris in waybar)"
  try_install "grim"             "screenshot tool (Super+Shift+S)"
  try_install "slurp"            "region selection for grim"
  try_install "ttf-jetbrains-mono" "nerd font for waybar icons"
  try_install "brightnessctl"    "keyboard backlight control"

  echo ""
}

install() {
  echo ""
  echo "  linking configs..."
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

  echo ""
  echo "  setting up mpd..."
  touch "$HOME/.config/mpd/database" "$HOME/.config/mpd/state" "$HOME/.config/mpd/log"
  mkdir -p "$HOME/.config/mpd/playlists" "$HOME/Music"

  install_extras

  echo ""
  echo "  done — reload your compositor to apply changes."
  echo "  add wallpapers to ~/walls/ and press Super+W to cycle."
  echo "  add music to ~/Music/ and start ncmpcpp to play."
}

clean() {
  echo ""
  echo "  removing old configs..."

  for cfg in bashrc .config/hypr .config/waybar .config/swaync .config/kitty \
             .config/rofi .config/eww .config/wlogout .config/btop .config/cava \
             .config/mpv .config/mpd .config/ncmpcpp .config/gtk-3.0 \
             .config/fontconfig; do
    dst="$HOME/$cfg"
    if [ -L "$dst" ]; then
      rm "$dst"
      echo "    removed symlink $cfg"
    elif [ -e "$dst" ]; then
      bak="${dst}.bak"
      if [ -e "$bak" ]; then
        rm -rf "$dst"
        echo "    removed $cfg (backup exists at ${cfg}.bak)"
      else
        mv "$dst" "$bak"
        echo "    backed up $cfg → ${cfg}.bak"
      fi
    fi
  done

  echo "  old configs cleared."
  echo ""
  install
}

case "$MODE" in
  install)
    install
    ;;
  clean)
    clean
    ;;
  *)
    echo "usage: ./bootstrap.sh [install|clean]"
    echo "  install  — symlink dotfiles + ask about optional packages"
    echo "  clean    — remove old configs then install"
    exit 1
    ;;
esac
