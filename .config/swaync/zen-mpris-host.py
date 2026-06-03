#!/usr/bin/env python3
"""
zen-mpris-host.py — Native messaging host for Zen MPRIS Helper.

Listens on stdin for track data from the extension, exposes a real
MPRIS D-Bus service with album art, and triggers mpris-glow colors.
"""
import sys
import struct
import json
import os
import threading
import urllib.request

from pydbus import SessionBus
from gi.repository import GLib, Gio

BUS_NAME = "org.mpris.MediaPlayer2.zen-bridge"
OBJECT_PATH = "/org/mpris/MediaPlayer2"
ART_PATH = "/tmp/zen-album-art.png"

# D-Bus MPRIS service


class MprisBridge:
    __dbus_xml__ = """
    <node>
      <interface name="org.freedesktop.DBus.Properties">
        <method name="Get">
          <arg type="s" direction="in" name="interface"/>
          <arg type="s" direction="in" name="property"/>
          <arg type="v" direction="out" name="value"/>
        </method>
        <method name="GetAll">
          <arg type="s" direction="in" name="interface"/>
          <arg type="a{sv}" direction="out" name="properties"/>
        </method>
      </interface>
      <interface name="org.mpris.MediaPlayer2">
        <property name="Identity" type="s" access="read"/>
        <property name="DesktopEntry" type="s" access="read"/>
        <property name="CanRaise" type="b" access="read"/>
        <property name="CanQuit" type="b" access="read"/>
      </interface>
      <interface name="org.mpris.MediaPlayer2.Player">
        <property name="PlaybackStatus" type="s" access="read"/>
        <property name="Metadata" type="a{sv}" access="read"/>
        <property name="CanControl" type="b" access="read"/>
        <property name="CanPlay" type="b" access="read"/>
        <property name="CanPause" type="b" access="read"/>
        <property name="CanGoNext" type="b" access="read"/>
        <property name="CanGoPrevious" type="b" access="read"/>
        <property name="CanSeek" type="b" access="read"/>
        <method name="PlayPause"/>
        <method name="Next"/>
        <method name="Previous"/>
        <method name="Play"/>
        <method name="Pause"/>
        <method name="Stop"/>
      </interface>
    </node>
    """

    def __init__(self):
        self._meta = self._idle_meta()

    @staticmethod
    def _idle_meta():
        return {
            "mpris:trackid": "/zen/bridge/idle",
            "xesam:title": "Not Playing",
            "mpris:artUrl": "",
            "mpris:length": 0,
        }

    def _v(self, val):
        if isinstance(val, str):
            return GLib.Variant("s", val)
        if isinstance(val, bool):
            return GLib.Variant("b", val)
        if isinstance(val, int):
            return GLib.Variant("x", val)
        if isinstance(val, list):
            return GLib.Variant("as", val)
        if isinstance(val, dict):
            d = {}
            for k, v in val.items():
                d[k] = self._v(v)
            return GLib.Variant("a{sv}", d)
        return GLib.Variant("s", str(val))

    def Get(self, iface, prop):
        try:
            return self._v(getattr(self, prop))
        except AttributeError:
            return self._v("")

    def GetAll(self, iface):
        if iface == "org.mpris.MediaPlayer2":
            props = {k: getattr(self, k) for k in
                     ("Identity", "DesktopEntry", "CanRaise", "CanQuit")}
            return {k: self._v(v) for k, v in props.items()}
        if iface == "org.mpris.MediaPlayer2.Player":
            props = {k: getattr(self, k) for k in
                     ("PlaybackStatus", "Metadata", "CanControl", "CanPlay",
                      "CanPause", "CanGoNext", "CanGoPrevious", "CanSeek")}
            return {k: self._v(v) for k, v in props.items()}
        return {}

    @property
    def Identity(self):
        return "Zen Music"

    @property
    def DesktopEntry(self):
        return "firefox"

    @property
    def CanRaise(self):
        return False

    @property
    def CanQuit(self):
        return False

    @property
    def PlaybackStatus(self):
        return "Playing"

    @property
    def Metadata(self):
        return self._meta

    @property
    def CanControl(self):
        return True

    @property
    def CanPlay(self):
        return True

    @property
    def CanPause(self):
        return True

    @property
    def CanGoNext(self):
        return True

    @property
    def CanGoPrevious(self):
        return True

    @property
    def CanSeek(self):
        return False

    def PlayPause(self): pass
    def Next(self): pass
    def Previous(self): pass
    def Play(self): pass
    def Pause(self): pass
    def Stop(self): pass

    def update_metadata(self, title, artist, art_url):
        self._meta = {
            "mpris:trackid": f"/zen/bridge/{abs(hash(title + artist))}",
            "xesam:title": title,
            "xesam:artist": [artist] if artist else [],
            "mpris:artUrl": art_url,
            "mpris:length": 0,
        }


# Globals

bridge = None
dbus_conn = None
_name_owner = None
_reg_obj = None  # keep ref to prevent GC unregistering the object
stdin_buf = b""


# Native messaging: buffered stdin reader (GLib IO watch)

def on_stdin_data(fd, condition):
    global stdin_buf
    if condition & GLib.IO_HUP:
        loop.quit()
        return False

    chunk = os.read(fd, 4096)
    if not chunk:
        loop.quit()
        return False

    stdin_buf += chunk
    while parse_message():
        pass
    return True


def parse_message():
    global stdin_buf
    if len(stdin_buf) < 4:
        return False
    length = struct.unpack("@I", stdin_buf[:4])[0]
    if len(stdin_buf) < 4 + length:
        return False
    payload = stdin_buf[4:4 + length]
    stdin_buf = stdin_buf[4 + length:]
    try:
        msg = json.loads(payload)
        handle_message(msg)
    except json.JSONDecodeError:
        pass
    return True


# Art download and glow trigger

def download_art(url):
    try:
        req = urllib.request.Request(url,
                                     headers={"User-Agent": "Zen-MPRIS/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            with open(ART_PATH, "wb") as f:
                f.write(resp.read())
        return ART_PATH
    except Exception:
        return None


def trigger_glow(art_path):
    GLib.spawn_async(
        ["python3", "/home/teavostok1/.config/swaync/mpris-glow.py",
         "--image", art_path],
        flags=GLib.SpawnFlags.SEARCH_PATH
        | GLib.SpawnFlags.STDOUT_TO_DEV_NULL
        | GLib.SpawnFlags.STDERR_TO_DEV_NULL,
        child_setup=lambda: None,
    )


def emit_properties_changed(changed):
    """Emit org.freedesktop.DBus.Properties.PropertiesChanged signal."""
    dbus_conn.emit_signal(
        None,
        OBJECT_PATH,
        "org.freedesktop.DBus.Properties",
        "PropertiesChanged",
        GLib.Variant("(sa{sv}as)", (
            "org.mpris.MediaPlayer2.Player",
            changed,
            [],
        )),
    )


# Message handler

def handle_message(msg):
    title = msg.get("title", "Unknown Track")
    artist = msg.get("artist", "")
    art_url = msg.get("artUrl", "")

    # 1. Update D-Bus metadata (uses HTTPS artUrl for now)
    bridge.update_metadata(title, artist, art_url)

    # 2. Emit PropertiesChanged so swaync sees the update immediately
    emit_properties_changed({
        "Metadata": bridge._v(bridge._meta),
        "PlaybackStatus": bridge._v("Playing"),
    })

    # 3. Download art off the main loop, then update metadata with file:// URI
    if art_url:
        threading.Thread(
            target=_download_and_update,
            args=(title, artist, art_url),
            daemon=True,
        ).start()

    sys.stderr.write(f"  ♫ {artist} — {title}\n")
    sys.stderr.flush()


def _download_and_update(title, artist, art_url):
    art_path = download_art(art_url)
    if not art_path:
        return
    # Update metadata with local file:// URI on the main loop
    def _update():
        bridge.update_metadata(title, artist, f"file://{art_path}")
        emit_properties_changed({
            "Metadata": bridge._v(bridge._meta),
            "PlaybackStatus": bridge._v("Playing"),
        })
        trigger_glow(art_path)
        return False
    GLib.idle_add(_update)


# Main

def main():
    global bridge, dbus_conn, _name_owner, _reg_obj, loop

    bus = SessionBus()
    try:
        _name_owner = bus.request_name(BUS_NAME)
    except Exception:
        pass
    dbus_conn = bus.con
    bridge = MprisBridge()
    _reg_obj = bus.register_object(OBJECT_PATH, bridge, MprisBridge.__dbus_xml__)
    sys.stderr.write("zen-mpris  •  ready\n")
    sys.stderr.flush()

    GLib.io_add_watch(0, GLib.IO_IN | GLib.IO_HUP, on_stdin_data)

    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
