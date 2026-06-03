# teavostok1's dotfiles

| component | tool |
|---|---|
| compositor | Hyprland |
| bar | Waybar |
| notifications | SwayNC |
| launcher | Rofi |
| lockscreen | Hyprlock |
| terminal | Kitty |
| shell | bash |
| music widget | Zen MPRIS Host + mpris-glow |
| music player | MPD + ncmpcpp |

## install

```bash
git clone https://github.com/teavostok1/dotfiles ~/dotfiles
cd ~/dotfiles
chmod +x bootstrap.sh && ./bootstrap.sh
```

To remove your existing configs first (replaces with clean symlinks):

```bash
./bootstrap.sh clean
```

## uninstall

```bash
cd ~/dotfiles
chmod +x uninstall.sh && ./uninstall.sh
```

This removes symlinks and restores any `.bak` backups.

## keybinds

| key | action |
|---|---|
| Super + W | cycle wallpaper |
| Super + Shift + L | lock screen |
| Super + P | power menu (wlogout) |
| Super + Space | app launcher (rofi) |

## structure

```
.config/
├── hypr/           # compositor, lockscreen, idle
├── waybar/         # bar + scripts
├── swaync/         # notification center
├── kitty/          # terminal
├── rofi/           # launcher menus
├── eww/            # widgets
├── wlogout/        # power menu
├── btop/           # system monitor
├── cava/           # audio visualizer
├── mpv/            # media player
├── mpd/            # music daemon
├── ncmpcpp/        # music client
├── gtk-3.0/        # GTK settings
└── fontconfig/     # font config
```
