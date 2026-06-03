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


def sh(args):
    return subprocess.run(args, capture_output=True, text=True).stdout.strip()


def get_vol():
    r = sh(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"])
    parts = r.split(None, 2)
    vol = float(parts[1]) * 100 if len(parts) > 1 else 50
    return vol, "MUTED" in r


def set_vol(v):
    sh(["wpctl", "set-volume", "-l", "1.5", "@DEFAULT_AUDIO_SINK@", str(v / 100.0)])


def get_screen_w():
    try:
        out = sh(["hyprctl", "monitors"])
        for line in out.splitlines():
            if "@" in line and " at " in line:
                return int(line.split(None, 1)[0].split("x")[0])
    except (ValueError, IndexError):
        pass
    return 1920


def hypr_move(addr, x, y):
    sh(["hyprctl", "dispatch", "movewindowpixel", f"exact {x} {y},address:{addr}"])


class VolumeWindow:
    def __init__(self):
        self._timer_id = None
        self._close_timer = None
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
        self.win.set_accept_focus(True)
        self.win.connect("key-press-event", self._on_key)
        self.win.connect("focus-in-event", self._on_focus_in)
        self.win.connect("focus-out-event", self._on_focus_out)

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

        sw = get_screen_w()
        self._target_x = sw - 318
        self._target_y = 36

        self.win.show_all()
        self.win.get_window().set_opacity(0)
        self._retries = 0
        GLib.timeout_add(10, self._reposition)

    def _reposition(self):
        clients = json.loads(sh(["hyprctl", "clients", "-j"]))
        for c in clients:
            if c.get("title") == "volume-slider":
                addr = c.get("address", "")
                if addr:
                    hypr_move(addr, self._target_x, self._target_y)
                    gdk_win = self.win.get_window()
                    if gdk_win:
                        gdk_win.set_opacity(1)
                return False
        self._retries += 1
        if self._retries < 10:
            GLib.timeout_add(100, self._reposition)
        return False

    def _on_focus_in(self, *_):
        if self._close_timer is not None:
            GLib.source_remove(self._close_timer)
            self._close_timer = None
        return False

    def _on_focus_out(self, *_):
        if self._close_timer is None:
            self._close_timer = GLib.timeout_add(500, self._close)
        return False

    def _on_change(self, scale):
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
        self._timer_id = GLib.timeout_add(150, self._commit, scale.get_value())

    def _commit(self, v):
        self._timer_id = None
        set_vol(round(v))
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
