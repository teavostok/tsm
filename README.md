# teavostok1's dotfiles

| component | tool |
|---|---|
| compositor | Hyprland |
| bar | Waybar |
| notifications | SwayNC |
| launcher | Rofi |
| terminal | Kitty |
| shell | bash |
| music widget | Zen MPRIS Host + mpris-glow |

## install

```bash
git clone https://github.com/teavostok1/dotfiles ~/dotfiles
cd ~/dotfiles
chmod +x bootstrap.sh && ./bootstrap.sh
```

Then reload Hyprland: `hyprctl reload`

## structure

```
.config/
├── hypr/           # compositor config
├── waybar/         # bar + scripts
├── swaync/         # notification center
├── kitty/          # terminal
├── rofi/           # launcher menus
├── eww/            # widgets
├── btop/           # system monitor
├── cava/           # audio visualizer
├── mpv/            # media player
├── gtk-3.0/        # GTK settings
└── fontconfig/     # font config
```
