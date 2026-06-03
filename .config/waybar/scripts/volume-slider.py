#!/usr/bin/env python3
import subprocess, os, json, gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, GLib

PID_FILE = "/tmp/waybar-volume-slider.pid"

if os.path.exists(PID_FILE):
    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        os.kill(pid, 15)
        os.unlink(PID_FILE)
    except (ProcessLookupError, ValueError, OSError):
        pass
    else:
        raise SystemExit(0)

with open(PID_FILE, "w") as f:
    f.write(str(os.getpid()))

CSS = """
window {
  background: rgba(28, 28, 30, 0.82);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 16px;
}
box { background: transparent; }
label#icon {
  font-family: "JetBrainsMono Nerd Font";
  font-size: 22px;
  color: rgba(255, 255, 255, 0.92);
}
scale { min-height: 40px; }
scale trough {
  min-height: 6px; border-radius: 3px;
  background: rgba(255, 255, 255, 0.12);
}
scale highlight {
  border-radius: 3px; background: #007aff;
}
scale slider {
  min-height: 18px; min-width: 18px;
  border-radius: 9px; background: white;
  box-shadow: 0 2px 6px rgba(0,0,0,0.36);
}
"""


def hyprctl(args):
    return subprocess.run(args, capture_output=True, text=True).stdout.strip()


def get_vol():
    r = hyprctl(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"])
    out = r.split(None, 2)
    vol = float(out[1]) * 100 if len(out) > 1 else 50
    muted = "MUTED" in r
    return vol, muted


def set_vol(v):
    hyprctl(["wpctl", "set-volume", "-l", "1.5", "@DEFAULT_AUDIO_SINK@", f"{v}%"])


class VolumeWindow:
    def __init__(self):
        self._dirty = False
        vol, muted = get_vol()

        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(CSS.encode())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.win = Gtk.Window.new(Gtk.WindowType.TOPLEVEL)
        self.win.set_title("volume-slider")
        self.win.set_border_width(14)
        self.win.set_decorated(False)
        self.win.set_resizable(False)
        self.win.set_skip_taskbar_hint(True)
        self.win.set_keep_above(True)
        self.win.set_position(Gtk.WindowPosition.NONE)
        self.win.set_accept_focus(True)
        self.win.connect("key-press-event", self._on_key)
        self.win.connect("realize", self._on_realize)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_valign(Gtk.Align.CENTER)
        box.set_halign(Gtk.Align.CENTER)

        icon_label = Gtk.Label(label="" if muted else "")
        icon_label.set_name("icon")

        adj = Gtk.Adjustment(value=vol, lower=0, upper=150, step_increment=5)
        self.scale = Gtk.Scale(
            orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj
        )
        self.scale.set_draw_value(False)
        self.scale.set_size_request(220, -1)
        self.scale.connect("value-changed", self._on_change)

        box.pack_start(icon_label, False, False, 0)
        box.pack_start(self.scale, True, True, 0)
        self.win.add(box)
        self.win.set_size_request(300, -1)
        self.win.show_all()

    def _on_realize(self, *_):
        try:
            out = hyprctl(["hyprctl", "monitors"])
            for line in out.splitlines():
                line = line.strip()
                if "@" in line and " at " in line:
                    sw = int(line.split("x", 1)[0])
                    break
            else:
                sw = 1920
        except (ValueError, IndexError):
            sw = 1920

        pw = 300
        x = sw - pw - 18
        y = 36
        self.win.move(x, y)

        GLib.timeout_add(100, self._reposition, x, y)

    def _reposition(self, x, y):
        clients = json.loads(hyprctl(["hyprctl", "clients", "-j"]))
        for c in clients:
            if c.get("title") == "volume-slider":
                addr = c.get("address", "")
                if addr:
                    hyprctl(["hyprctl", "dispatch", "movewindowpixel",
                             f"exact {x} {y},address:{addr}"])
                break
        return False

    def _on_change(self, scale):
        if self._dirty:
            return
        self._dirty = True
        GLib.timeout_add(150, self._commit, scale.get_value())

    def _commit(self, v):
        set_vol(round(v))
        self._dirty = False
        return False

    def _on_key(self, _, event):
        k = event.get_keyval()[1]
        if k == Gdk.KEY_Escape:
            self._close()
        elif k in (Gdk.KEY_Up, Gdk.KEY_Right):
            adj = self.scale.get_adjustment()
            adj.set_value(min(adj.get_value() + 5, adj.get_upper()))
        elif k in (Gdk.KEY_Down, Gdk.KEY_Left):
            adj = self.scale.get_adjustment()
            adj.set_value(max(adj.get_value() - 5, adj.get_lower()))
        return True

    def _close(self):
        Gtk.main_quit()


if __name__ == "__main__":
    VolumeWindow()
    Gtk.main()
