#!/bin/bash

pos="window { location: north east; anchor: north east; y-offset: 32; x-offset: -12; padding: 0; width: 260; }"
compact="entry { enabled: false; } prompt { enabled: false; } listview { spacing: 2px; scrollbar: true; } element { padding: 2px 6px; } element-text { margin: 0 2px; }"

data=$(nmcli -t -f ACTIVE,SSID,SECURITY dev wifi list --rescan no 2>/dev/null)

active=$(echo "$data" | grep "^yes" | head -1)
if [ -n "$active" ]; then
  active_ssid=$(echo "$active" | awk -F: '{print $2}')
  status_header="     $active_ssid\n────────────────────────────────────────"
else
  status_header="     Disconnected\n────────────────────────────────────────"
fi

available=$(echo "$data" | awk -F: '
  !seen[$2]++ && $2 != "" {
    if ($3 == "") $3 = "Open"
    printf "%-34.34s  %s\n", $2, $3
  }')

choice=$(echo -e "$status_header\n$available" | rofi -dmenu -i -theme-str "listview { font: \"SF Pro Text 13\"; } $pos $compact" 2>/dev/null)

if [ -n "$choice" ] && ! echo "$choice" | grep -Eq "(Disconnected|────────────────────)"; then
  ssid=$(echo "$choice" | sed 's/  \+.*//')
  if [ -z "$ssid" ]; then
    exit
  fi
  result=$(nmcli dev wifi connect "$ssid" 2>&1)
  if echo "$result" | grep -qi "password\|secrets\|key"; then
    pass=$(rofi -dmenu -p "Password for $ssid" -password 2>/dev/null)
    if [ -n "$pass" ]; then
      nmcli dev wifi connect "$ssid" password "$pass"
    fi
  fi
fi
