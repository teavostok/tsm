#!/usr/bin/env python3
import os, sys, subprocess, gi
gi.require_version('Gtk', '3.0')
gi.require_version('GtkSource', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, GtkSource, Gdk, GLib

CSS = """
window { background: #1c1c1e; }
paned { background: #1c1c1e; }
paned separator { background: rgba(255,255,255,0.06); min-width: 1px; }
notebook {
  background: #1c1c1e; border: none;
}
notebook header {
  background: #1c1c1e; border: none;
}
notebook tab {
  background: rgba(255,255,255,0.04);
  border: none; padding: 6px 16px;
  font-size: 12px; color: rgba(255,255,255,0.5);
}
notebook tab:checked {
  background: rgba(255,255,255,0.08);
  color: rgba(255,255,255,0.9);
}
notebook tab button {
  padding: 0; min-width: 18px; min-height: 18px;
  color: rgba(255,255,255,0.3);
}
notebook tab button:hover { color: rgba(255,255,255,0.8); }
scrollbar { background: transparent; }
scrollbar slider {
  background: rgba(255,255,255,0.1); border-radius: 4px;
  min-width: 6px;
}
scrollbar slider:hover { background: rgba(255,255,255,0.2); }
treeview {
  background: #1c1c1e; color: rgba(255,255,255,0.75);
  font-size: 12px;
}
treeview:selected {
  background: #007aff; color: white;
}
treeview.view { border: none; }
textview {
  background: #1c1c1e;
  color: rgba(255,255,255,0.85);
  font-family: "JetBrainsMono Nerd Font", "monospace";
  font-size: 13px;
}
entry {
  background: rgba(255,255,255,0.06);
  color: rgba(255,255,255,0.8);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 6px; padding: 4px 8px;
}
menubar {
  background: #1c1c1e; color: rgba(255,255,255,0.7);
  border: none; padding: 2px 0;
}
menubar > menuitem { padding: 4px 12px; }
menubar > menuitem:hover { background: rgba(255,255,255,0.08); }
menu {
  background: #2c2c2e; border: 1px solid rgba(255,255,255,0.1);
  border-radius: 8px; padding: 4px;
}
menuitem {
  padding: 6px 24px; color: rgba(255,255,255,0.8);
  border-radius: 4px;
}
menuitem:hover { background: #007aff; color: white; }
toolbar {
  background: rgba(255,255,255,0.03);
  border: none; border-bottom: 1px solid rgba(255,255,255,0.06);
  padding: 4px;
}
toolbar button {
  background: transparent; border: none;
  color: rgba(255,255,255,0.6); border-radius: 6px;
  padding: 4px 12px; font-size: 12px;
}
toolbar button:hover { background: rgba(255,255,255,0.08); color: white; }
"""


def load_css():
    prov = Gtk.CssProvider()
    prov.load_from_data(CSS.encode())
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), prov,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )


LANG_MAP = {
    ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp",
    ".py": "python",
    ".rs": "rust",
    ".go": "go",
    ".js": "javascript", ".ts": "typescript",
    ".html": "html", ".css": "css",
    ".json": "json", ".xml": "xml",
    ".sh": "sh", ".bash": "sh",
    ".md": "markdown",
    ".lua": "lua",
    ".java": "java",
}


def detect_lang(path):
    _, ext = os.path.splitext(path)
    return LANG_MAP.get(ext.lower())


EXT_FILTER = set(LANG_MAP.keys()) | {
    ".txt", ".cfg", ".conf", ".ini", ".yml", ".yaml", ".toml",
    ". Makefile", ".CMakeLists.txt",
}


class Editor:
    def __init__(self):
        load_css()
        self._files = {}
        self._root = None

        self.win = Gtk.Window.new(Gtk.WindowType.TOPLEVEL)
        self.win.set_title("ide")
        self.win.set_default_size(1100, 720)
        self.win.connect("destroy", Gtk.main_quit)
        self.win.set_icon_name("accessories-text-editor")

        self.lang_mgr = GtkSource.LanguageManager.get_default()
        self.style_mgr = GtkSource.StyleSchemeManager.get_default()

        vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.win.add(vb)

        menubar = self._build_menubar()
        vb.pack_start(menubar, False, False, 0)

        toolbar = self._build_toolbar()
        vb.pack_start(toolbar, False, False, 0)

        hp = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        vb.pack_start(hp, True, True, 0)

        self.tree = Gtk.TreeView()
        self.tree.set_headers_visible(False)
        self.tree.set_size_request(220, -1)
        self.store = Gtk.TreeStore(str, str)
        self.tree.set_model(self.store)
        renderer = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn("", renderer, text=0)
        self.tree.append_column(col)
        self.tree.connect("row-activated", self._on_tree_open)
        self.tree_selection = self.tree.get_selection()

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.add(self.tree)
        hp.pack1(sw, False, True)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        hp.pack2(right, True, True)

        self.notebook = Gtk.Notebook()
        self.notebook.set_scrollable(True)
        self.notebook.connect("switch-page", self._on_tab_switch)
        self.notebook.connect("page-removed", self._on_tab_removed)
        right.pack_start(self.notebook, True, True, 0)

        self.output_tv = Gtk.TextView()
        self.output_tv.set_editable(False)
        self.output_tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.output_buf = self.output_tv.get_buffer()
        self.output_buf.create_tag("red", foreground="#ff3b30")
        self.output_buf.create_tag("green", foreground="#30d158")
        self.output_buf.create_tag("white", foreground="rgba(255,255,255,0.8)")

        out_sw = Gtk.ScrolledWindow()
        out_sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        out_sw.set_size_request(-1, 180)
        out_sw.add(self.output_tv)

        out_frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        out_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        out_header.set_size_request(-1, 28)
        lbl = Gtk.Label(label="Output")
        lbl.set_xalign(0)
        lbl.set_margin_start(10)
        out_header.pack_start(lbl, True, True, 0)
        clear_btn = Gtk.Button(label="Clear")
        clear_btn.set_relief(Gtk.ReliefStyle.NONE)
        clear_btn.connect("clicked", lambda _: self.output_buf.set_text(""))
        out_header.pack_end(clear_btn, False, False, 0)

        self.term_revealer = Gtk.Revealer()
        self.term_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        self.term_revealer.set_transition_duration(200)
        out_frame.pack_start(out_header, False, False, 0)
        out_frame.pack_start(out_sw, True, True, 0)
        self.term_revealer.add(out_frame)
        right.pack_end(self.term_revealer, False, False, 0)

        self.win.show_all()
        self.term_revealer.set_reveal_child(False)

    def _build_menubar(self):
        bar = Gtk.MenuBar()

        fm = Gtk.Menu()
        fi = Gtk.MenuItem(label="File")
        fi.set_submenu(fm)

        items = [
            ("Open Folder", self._open_folder),
            ("Open File", self._open_file),
            (None, None),
            ("Save", self._save_file),
            ("Save As", self._save_as),
            (None, None),
            ("Close Tab", self._close_tab),
            ("Quit", Gtk.main_quit),
        ]
        for label, cb in items:
            if label is None:
                fm.append(Gtk.SeparatorMenuItem())
            else:
                mi = Gtk.MenuItem(label=label)
                mi.connect("activate", cb)
                fm.append(mi)
        bar.append(fi)

        em = Gtk.Menu()
        ei = Gtk.MenuItem(label="Edit")
        ei.set_submenu(em)
        for label, cb in [("Undo", self._undo), ("Redo", self._redo),
                          (None, None), ("Cut", self._cut),
                          ("Copy", self._copy), ("Paste", self._paste)]:
            if label is None:
                em.append(Gtk.SeparatorMenuItem())
            else:
                mi = Gtk.MenuItem(label=label)
                mi.connect("activate", cb)
                em.append(mi)
        bar.append(ei)

        bm = Gtk.Menu()
        bi = Gtk.MenuItem(label="Build")
        bi.set_submenu(bm)
        for label, cb in [("Compile", self._build_c), ("Compile & Run", self._build_run_c),
                          (None, None), ("Run Python", self._run_py)]:
            if label is None:
                bm.append(Gtk.SeparatorMenuItem())
            else:
                mi = Gtk.MenuItem(label=label)
                mi.connect("activate", cb)
                bm.append(mi)
        bar.append(bi)

        return bar

    def _build_toolbar(self):
        tb = Gtk.Toolbar()
        tb.set_style(Gtk.ToolbarStyle.ICONS)
        for label, icon, cb in [
            ("Open", "document-open", self._open_file),
            ("Save", "document-save", self._save_file),
            (None, None, None),
            ("Build", "media-playback-start", self._build_c),
            ("Run", "media-skip-forward", self._build_run_c),
        ]:
            if label is None:
                tb.insert(Gtk.SeparatorToolItem(), -1)
            else:
                btn = Gtk.ToolButton()
                btn.set_label(label)
                btn.set_icon_name(icon)
                btn.connect("clicked", cb)
                tb.insert(btn, -1)
        return tb

    def _current_view(self):
        n = self.notebook.get_nth_page(self.notebook.get_current_page())
        if n:
            return n.get_child()
        return None

    def _current_path(self):
        n = self.notebook.get_nth_page(self.notebook.get_current_page())
        if n:
            return self._files.get(id(n))
        return None

    def _open_file_dialog(self, folder=False):
        d = Gtk.FileChooserDialog(
            title="Open Folder" if folder else "Open File",
            parent=self.win,
            action=Gtk.FileChooserAction.SELECT_FOLDER if folder else Gtk.FileChooserAction.OPEN,
        )
        d.add_button("Cancel", Gtk.ResponseType.CANCEL)
        d.add_button("Open", Gtk.ResponseType.ACCEPT)
        if folder:
            filt = Gtk.FileFilter()
            filt.set_name("All Files")
            filt.add_pattern("*")
            d.add_filter(filt)
        r = d.run()
        path = d.get_filename() if r == Gtk.ResponseType.ACCEPT else None
        d.destroy()
        return path

    def _open_folder(self, *args):
        path = self._open_file_dialog(folder=True)
        if path:
            self._root = path
            self._populate_tree(path)

    def _open_file(self, *_path):
        path = _path[0] if _path else None
        if path is None or not isinstance(path, str):
            path = self._open_file_dialog()
        if not path:
            return
        self._open_in_tab(path)
        self._scroll_to_file(path)

    def _populate_tree(self, root):
        self.store.clear()
        self._root = root
        self._add_tree_node(None, root)

    def _add_tree_node(self, parent, path):
        try:
            entries = sorted(os.listdir(path))
        except PermissionError:
            return
        dirs = [e for e in entries if os.path.isdir(os.path.join(path, e))]
        files = [e for e in entries if os.path.isfile(os.path.join(path, e))]
        for d in dirs:
            if d.startswith("."):
                continue
            full = os.path.join(path, d)
            node = self.store.append(parent, [d + "/", full])
            self._add_tree_node(node, full)

        fext = EXT_FILTER
        for f in files:
            if f.startswith("."):
                continue
            _, ext = os.path.splitext(f)
            if ext.lower() not in fext:
                continue
            full = os.path.join(path, f)
            self.store.append(parent, [f, full])

    def _on_tree_open(self, tree, path, col):
        it = self.store.get_iter(path)
        fp = self.store.get_value(it, 1)
        if os.path.isdir(fp):
            if tree.row_expanded(path):
                tree.collapse_row(path)
            else:
                tree.expand_row(path, False)
        else:
            self._open_file(fp)

    def _scroll_to_file(self, path):
        def find(parent):
            it = self.store.iter_children(parent)
            while it:
                if self.store.get_value(it, 1) == path:
                    p = self.store.get_path(it)
                    self.tree.scroll_to_cell(p, None, True, 0.3, 0)
                    self.tree_selection.select_path(p)
                    return True
                if self.store.iter_has_child(it):
                    if find(it):
                        return True
                it = self.store.iter_next(it)
            return False
        find(None)

    def _open_in_tab(self, path):
        for i in range(self.notebook.get_n_pages()):
            p = self.notebook.get_nth_page(i)
            if self._files.get(id(p)) == path:
                self.notebook.set_current_page(i)
                return

        try:
            with open(path) as f:
                text = f.read()
        except (OSError, UnicodeDecodeError):
            return

        buf = GtkSource.Buffer()
        lang_id = detect_lang(path)
        if lang_id:
            lang = self.lang_mgr.get_language(lang_id)
            if lang:
                buf.set_language(lang)

        scheme = self.style_mgr.get_scheme("oblivion")
        if scheme:
            buf.set_style_scheme(scheme)
        buf.set_highlight_syntax(True)
        buf.set_text(text)
        buf.set_modified(False)
        buf.connect("modified-changed", self._on_modified, path)

        view = GtkSource.View.new_with_buffer(buf)
        view.set_show_line_numbers(True)
        view.set_tab_width(4)
        view.set_insert_spaces_instead_of_tabs(True)
        view.set_auto_indent(True)
        view.set_highlight_current_line(True)
        view.set_monospace(True)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.add(view)

        name = os.path.basename(path)
        label = Gtk.Label(label=name)
        label.set_margin_start(4)
        label.set_margin_end(4)
        label.show()

        close_btn = Gtk.Button(label="✕")
        close_btn.set_relief(Gtk.ReliefStyle.NONE)
        close_btn.set_focus_on_click(False)
        close_btn.connect("clicked", self._close_tab_by_page, sw)

        hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        hb.pack_start(label, True, True, 0)
        hb.pack_start(close_btn, False, False, 0)
        hb.show_all()

        n = self.notebook.append_page(sw, hb)
        self.notebook.set_current_page(n - 1)
        self.notebook.set_tab_reorderable(sw, True)
        self._files[id(sw)] = path

    def _on_modified(self, buf, path):
        for i in range(self.notebook.get_n_pages()):
            p = self.notebook.get_nth_page(i)
            if self._files.get(id(p)) == path:
                hb = self.notebook.get_tab_label(p)
                if hb:
                    lbl = hb.get_children()[0]
                    if isinstance(lbl, Gtk.Label):
                        name = os.path.basename(path)
                        lbl.set_text(f"● {name}" if buf.get_modified() else name)
                break

    def _on_tab_switch(self, nb, page, idx):
        pass

    def _on_tab_removed(self, nb, page, idx):
        self._files.pop(id(page), None)
        if nb.get_n_pages() == 0:
            self.term_revealer.set_reveal_child(False)

    def _close_tab(self, *_):
        n = self.notebook.get_current_page()
        if n >= 0:
            p = self.notebook.get_nth_page(n)
            self.notebook.remove_page(n)

    def _close_tab_by_page(self, btn, page):
        for i in range(self.notebook.get_n_pages()):
            if self.notebook.get_nth_page(i) == page:
                self.notebook.remove_page(i)
                break

    def _save_file(self, *_):
        path = self._current_path()
        if not path:
            return self._save_as()
        view = self._current_view()
        if not view:
            return
        buf = view.get_buffer()
        start, end = buf.get_bounds()
        text = buf.get_text(start, end, False)
        try:
            with open(path, "w") as f:
                f.write(text)
            buf.set_modified(False)
        except OSError as e:
            self._log(f"Save failed: {e}", "red")

    def _save_as(self, *_):
        path = self._current_path()
        d = Gtk.FileChooserDialog(
            title="Save As", parent=self.win,
            action=Gtk.FileChooserAction.SAVE,
        )
        d.add_button("Cancel", Gtk.ResponseType.CANCEL)
        d.add_button("Save", Gtk.ResponseType.ACCEPT)
        if path:
            d.set_filename(path)
        r = d.run()
        fp = d.get_filename() if r == Gtk.ResponseType.ACCEPT else None
        d.destroy()
        if fp:
            n = self.notebook.get_nth_page(self.notebook.get_current_page())
            self._files[id(n)] = fp
            self._save_file()

    def _undo(self, *_): self._edit_action("undo")
    def _redo(self, *_): self._edit_action("redo")
    def _cut(self, *_): self._edit_action("cut")
    def _copy(self, *_): self._edit_action("copy")
    def _paste(self, *_): self._edit_action("paste")

    def _edit_action(self, action):
        v = self._current_view()
        if not v:
            return
        buf = v.get_buffer() if hasattr(v, 'get_buffer') else None
        if not buf:
            return
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        if action == "undo":
            if buf.can_undo():
                buf.undo()
        elif action == "redo":
            if buf.can_redo():
                buf.redo()
        elif action == "cut":
            buf.cut_clipboard(clipboard, v.get_editable())
        elif action == "copy":
            buf.copy_clipboard(clipboard)
        elif action == "paste":
            buf.paste_clipboard(clipboard, None, v.get_editable())

    def _build_c(self, *_):
        path = self._current_path()
        if not path:
            return
        if path.endswith(".c"):
            cmd = ["gcc", "-Wall", "-Wextra", "-o", path[:-2], path]
        elif path.endswith((".cpp", ".cc", ".cxx")):
            cmd = ["g++", "-Wall", "-Wextra", "-o", path[:path.rfind(".")], path]
        else:
            self._log("Not a C/C++ file", "red")
            return
        self._run_cmd(cmd, f"Building {os.path.basename(path)}...")

    def _build_run_c(self, *_):
        path = self._current_path()
        if not path:
            return
        stem = path[:path.rfind(".")]
        exe = stem
        if path.endswith(".c"):
            cmd = ["gcc", "-Wall", "-Wextra", "-o", exe, path]
        elif path.endswith((".cpp", ".cc", ".cxx")):
            cmd = ["g++", "-Wall", "-Wextra", "-o", exe, path]
        else:
            self._log("Not a C/C++ file", "red")
            return
        self._run_cmd(cmd, f"Building and running {os.path.basename(path)}...", run_exe=exe)

    def _run_py(self, *_):
        path = self._current_path()
        if not path:
            return
        if not path.endswith(".py"):
            self._log("Not a Python file", "red")
            return
        self._run_cmd(["python3", path], f"Running {os.path.basename(path)}...")

    def _run_cmd(self, cmd, label, run_exe=None):
        self.term_revealer.set_reveal_child(True)
        self.output_buf.set_text("")
        self._log(f"> {' '.join(cmd)}\n", "green")
        self._flush()

        def run():
            try:
                p = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, cwd=os.path.dirname(self._current_path() or os.getcwd()),
                )
                for line in p.stdout:
                    GLib.idle_add(self._log, line, "white")
                p.wait()
                if p.returncode == 0:
                    GLib.idle_add(self._log, f"\n✓ Done (exit {p.returncode})\n", "green")
                    if run_exe and os.access(run_exe, os.X_OK):
                        GLib.idle_add(self._run_exe, run_exe)
                else:
                    GLib.idle_add(self._log, f"\n✗ Failed (exit {p.returncode})\n", "red")
            except FileNotFoundError as e:
                GLib.idle_add(self._log, f"Error: {e}\n", "red")

        import threading
        t = threading.Thread(target=run, daemon=True)
        t.start()

    def _run_exe(self, exe):
        self._log(f"\n> {exe}\n", "green")
        cmd = [os.path.abspath(exe)]
        p = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, cwd=os.path.dirname(exe),
        )
        for line in p.stdout:
            self._log(line, "white")
        p.wait()
        self._log(f"\n✓ Exit {p.returncode}\n", "green")

    def _log(self, text, tag="white"):
        end = self.output_buf.get_end_iter()
        self.output_buf.insert_with_tags(end, text, self.output_buf.get_tag_table().lookup(tag))

    def _flush(self):
        while Gtk.events_pending():
            Gtk.main_iteration()


if __name__ == "__main__":
    Editor()
    Gtk.main()
