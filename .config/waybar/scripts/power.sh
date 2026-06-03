#!/bin/bash

pos="window { location: north east; anchor: north east; y-offset: 26; x-offset: -12; padding: 0; width: 180; }"
compact="entry { enabled: false; } prompt { enabled: false; } listview { spacing: 4px; } element { padding: 3px 4px; } element-text { margin: 0 2px; }"

align() { printf "%-5s : %s\n" "$1" "$2"; }
options="$(align  Lock)\n$(align  Suspend)\n$(align  Hibernate)\n$(align  Logout)\n$(align  Restart)\n$(align  Shutdown)"

selected=$(echo -e "$options" | rofi -dmenu -l 6 -theme-str "listview { font: \"SF Pro Text 13\"; } $pos $compact" 2>/dev/null)

confirm() {
    choice=$(echo -e "$(align  No)\n$(align  Yes)" | rofi -dmenu -l 2 -theme-str "listview { font: \"SF Pro Text 13\"; } $pos $compact" 2>/dev/null)
    [[ "$choice" == "$(align  No)" ]]
}

selected=$(echo "$selected" | sed 's/^.*: //')

case "$selected" in
    "Lock") hyprlock ;;
    "Suspend") systemctl suspend ;;
    "Hibernate") systemctl hibernate ;;
    "Logout") confirm "Logout" && hyprctl dispatch exit ;;
    "Restart") confirm "Restart" && systemctl reboot ;;
    "Shutdown") confirm "Shutdown" && systemctl poweroff ;;
esac
