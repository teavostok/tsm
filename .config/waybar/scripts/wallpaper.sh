#!/bin/bash

WALL_DIR="$HOME/walls"
CURRENT="$HOME/wallpaper.jpg"

[ ! -d "$WALL_DIR" ] && mkdir -p "$WALL_DIR"

if [ "$1" = "--next" ]; then
  mapfile -t walls < <(find "$WALL_DIR" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) 2>/dev/null)
  [ ${#walls[@]} -eq 0 ] && notify-send "No wallpapers in ~/walls/" && exit 1
  current_name=$(basename "$(readlink -f "$CURRENT" 2>/dev/null || echo "$CURRENT")")
  for i in "${!walls[@]}"; do
    if [[ "${walls[$i]}" == *"$current_name" ]]; then
      next=$(( (i + 1) % ${#walls[@]} ))
      selected="${walls[$next]}"
      break
    fi
  done
  selected="${selected:-${walls[0]}}"
elif [ "$1" = "--random" ]; then
  selected=$(find "$WALL_DIR" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) 2>/dev/null | shuf -n1)
  [ -z "$selected" ] && notify-send "No wallpapers in ~/walls/" && exit 1
elif [ -n "$1" ]; then
  selected="$1"
else
  echo "Usage: wallpaper.sh --next | --random | /path/to/image"
  exit 1
fi

ln -sf "$selected" "$CURRENT"
awww img "$selected"
hyprctl hyprpaper wallpaper ",$selected" 2>/dev/null || true
notify-send "Wallpaper" "$(basename "$selected")"
