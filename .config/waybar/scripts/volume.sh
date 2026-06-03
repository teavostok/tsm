#!/bin/bash

bar_h="window { location: north east; anchor: north east; y-offset: 44; x-offset: -12; }"

get_vol() {
  wpctl get-volume @DEFAULT_AUDIO_SINK@ | awk '{print $2 * 100}' | cut -d. -f1
}

is_muted() {
  wpctl get-volume @DEFAULT_AUDIO_SINK@ | grep -q MUTED
}

set_vol() {
  wpctl set-volume -l 1.5 @DEFAULT_AUDIO_SINK@ "$1%"
}

toggle_mute() {
  wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle
}

vol=$(get_vol)
muted="false"
if is_muted; then
  muted="true"
fi

if [ "$muted" = "true" ]; then
  status=" Muted"
else
  bars=$((vol / 10))
  bar=""
  for i in $(seq 1 $bars); do bar="${bar}█"; done
  for i in $(seq $bars 9); do bar="${bar}░"; done
  status=" $bar ${vol}%"
fi

choice=$(echo -e "$status\n 25%\n 50%\n 75%\n 100%\n +5%\n -5%\n Toggle mute" | rofi -dmenu -p "Volume" -l 9 -theme-str "$bar_h" 2>/dev/null)

case "$choice" in
  " 25%") set_vol 25 ;;
  " 50%") set_vol 50 ;;
  " 75%") set_vol 75 ;;
  " 100%") set_vol 100 ;;
  " +5%") new=$((vol + 5)); [ "$new" -gt 150 ] && new=150; set_vol "$new" ;;
  " -5%") new=$((vol - 5)); [ "$new" -lt 0 ] && new=0; set_vol "$new" ;;
  " Toggle mute") toggle_mute ;;
esac
