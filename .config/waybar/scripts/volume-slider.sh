#!/bin/bash

get_vol() {
  wpctl get-volume @DEFAULT_AUDIO_SINK@ | awk '{print $2 * 100}' | cut -d. -f1
}

is_muted() {
  wpctl get-volume @DEFAULT_AUDIO_SINK@ | grep -q MUTED
}

vol=$(get_vol)
text=""
is_muted && text=""

# Kill any existing Volume yad window
hyprctl clients -j 2>/dev/null | python3 -c "
import sys,json
for c in json.load(sys.stdin):
    if c.get('title','').lower() == 'volume':
        print(c.get('pid',''))
" 2>/dev/null | while read -r pid; do
  [ -n "$pid" ] && kill "$pid" 2>/dev/null
done

# Pre-calculate position below cursor
read -r CX CY <<< "$(hyprctl cursorpos | tr ',' ' ')"
CX=${CX:-960}; CY=${CY:-540}
read -r SW SH <<< "$(hyprctl monitors | awk '/^[[:space:]]+[0-9]+x/{gsub(/@.*/,"",$1); split($1,a,"x"); print a[1],a[2]; exit}')"
SW=${SW:-1920}; SH=${SH:-1200}
PW=300
X=$((CX - PW / 2)); [ "$X" -lt 10 ] && X=10; [ "$((X + PW))" -gt "$SW" ] && X=$((SW - PW - 10))
Y=$((CY + 14))

# Launch yad in background
result_file="/tmp/waybar-volume-result"
> "$result_file"
yad --scale \
  --title="Volume" \
  --text="$text" \
  --value="$vol" \
  --min=0 --max=150 --step=5 \
  --no-buttons --width="$PW" --height=80 \
  --undecorated --skip-taskbar --on-top --close-on-unfocus \
  --borders=14 \
  --css="
    window {
      background: rgba(28,28,30,0.82);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 16px;
    }
    label {
      font-family: JetBrainsMono Nerd Font;
      font-size: 22px;
      color: rgba(255,255,255,0.92);
    }
    scale { min-height: 40px; }
    scale trough {
      min-height: 6px; border-radius: 3px;
      background: rgba(255,255,255,0.12);
    }
    scale highlight {
      border-radius: 3px; background: #007aff;
    }
    scale slider {
      min-height: 18px; min-width: 18px;
      border-radius: 9px; background: white;
      box-shadow: 0 2px 6px rgba(0,0,0,0.36);
    }
  " > "$result_file" &
YAD_PID=$!

# Position via hyprctl (only reliable way in Wayland)
for _ in 1 2 3 4 5; do
  ADDR=$(hyprctl clients -j 2>/dev/null | python3 -c "
import sys,json
for c in json.load(sys.stdin):
    if c.get('title','') == 'Volume':
        print(c.get('address',''))
        break
" 2>/dev/null)
  if [ -n "$ADDR" ]; then
    hyprctl dispatch movewindowpixel "exact ${X} ${Y},address:${ADDR}" 2>/dev/null
    break
  fi
  sleep 0.1
done

wait "$YAD_PID" 2>/dev/null

# Apply selected volume (take last line from yad output)
new_vol=$(tail -1 "$result_file" 2>/dev/null)
if [ -n "$new_vol" ]; then
  wpctl set-volume -l 1.5 @DEFAULT_AUDIO_SINK@ "${new_vol}%"
fi
