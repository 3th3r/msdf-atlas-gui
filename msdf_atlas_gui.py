"""Simple graphical interface for msdf-atlas-gen.

Builds the command line(s) from the fields, displays them, then runs them.
Standard library only (Tkinter / ttk).
"""

import json
import os
import queue
import struct
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# Base of every relative path: the folder containing this script.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")

TYPES = ["hardmask", "softmask", "sdf", "psdf", "msdf", "mtsdf"]
PRESETS = ["256", "512", "1024", "2048", "4096"]
GRID_COLUMNS = 6

# (short name, label, abbreviation, items). An item is a codepoint or an inclusive (first, last) range.
# Default order: frequency of use for a European user.
CHARSETS = [
    ("ascii", "Basic Latin", "asc", [(0x20, 0x7E)]),
    ("latin1", "Latin-1", "lt1", [(0xA0, 0xFF)]),
    ("punct", "General Punct.", "pun", [(0x2000, 0x206F)]),
    ("currency", "Currency", "cur", [(0x20A0, 0x20BF)]),
    ("latinExtA", "Latin Ext-A", "lxa", [(0x100, 0x17F)]),
    ("latinExtB", "Latin Ext-B", "lxb", [(0x180, 0x24F)]),
    ("greek", "Greek", "grk", [(0x370, 0x3FF)]),
    ("cyrillic", "Cyrillic", "cyr", [(0x400, 0x4FF)]),
    ("letterlike", "Letterlike", "let", [(0x2100, 0x214F)]),
    ("supsub", "Super/Subscripts", "sup", [(0x2070, 0x209F)]),
    ("numforms", "Number Forms", "num", [(0x2150, 0x218F)]),
    ("arrows", "Arrows", "arr", [(0x2190, 0x21FF)]),
    ("math", "Math Operators", "mth", [(0x2200, 0x22FF)]),
    ("shapes", "Geometric Shapes", "shp", [(0x25A0, 0x25FF)]),
    ("cyrillicSup", "Cyrillic Sup.", "cys", [(0x500, 0x52F)]),
    ("vietnamese", "Vietnamese", "vie", [
        (0x41, 0x5A), (0x61, 0x7A),
        (0xC0, 0xC3), (0xC8, 0xCA), 0xCC, 0xCD, (0xD2, 0xD5), 0xD9, 0xDA, 0xDD,
        (0xE0, 0xE3), (0xE8, 0xEA), 0xEC, 0xED, (0xF2, 0xF5), 0xF9, 0xFA, 0xFD,
        0x102, 0x103, 0x110, 0x111, 0x128, 0x129, 0x168, 0x169,
        0x1A0, 0x1A1, 0x1AF, 0x1B0,
        (0x1EA0, 0x1EF9),
        0x20AB,
    ]),
    ("combining", "Combining marks", "cmb", [(0x300, 0x36F)]),
]
DEFAULT_ORDER = [name for name, _, _, _ in CHARSETS]
LABELS = {name: label for name, label, _, _ in CHARSETS}
ABBRS = {name: abbr for name, _, abbr, _ in CHARSETS}


def _item_spec(item):
    return f"[0x{item[0]:X}, 0x{item[1]:X}]" if isinstance(item, tuple) else f"0x{item:X}"


def _item_codepoints(item):
    return range(item[0], item[1] + 1) if isinstance(item, tuple) else (item,)


SPECS = {name: ", ".join(_item_spec(i) for i in items) for name, _, _, items in CHARSETS}
CODEPOINTS = {name: frozenset(cp for i in items for cp in _item_codepoints(i)) for name, _, _, items in CHARSETS}

# Whitespace / invisible codepoints, used to detect empty glyphs in CFF fonts (approximation).
WHITESPACE = frozenset([0x20, 0xA0, *range(0x2000, 0x2010), 0x2028, 0x2029, 0x202F, 0x205F, *range(0x2060, 0x2065)])

PATH_KEYS = ("exe", "font", "image_dir", "image_path", "csv_path", "json_path")

DEFAULTS = {
    "exe": "",
    "font": "",
    "type": "psdf",
    "charsets": ["ascii"],
    "size": "64",
    "uniform": True,
    "cell_x": "96",
    "cell_y": "96",
    "pxrange": "8",
    "dim_x": "4096",
    "dim_y": "4096",
    "square": True,
    "image_auto": True,
    "image_dir": "output",
    "image_path": "",
    "csv": False,
    "csv_auto": True,
    "csv_path": "",
    "json": False,
    "json_auto": True,
    "json_path": "",
    "charset_order": DEFAULT_ORDER,
    "charset_atlas": {},
    "atlas_mode": "auto",
}


# ------------------------------------------------------------------ Paths

def to_abs(path):
    """Absolute path; a relative path is resolved from BASE_DIR."""
    return os.path.normpath(os.path.join(BASE_DIR, path))


def numbered(path, index, count):
    """Adds _<index> before the extension when there are several atlases."""
    if count <= 1:
        return path
    root, ext = os.path.splitext(path)
    return f"{root}_{index}{ext}"


# --------------------------------------------------------------- Settings

def load_settings():
    settings = {k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v)
                for k, v in DEFAULTS.items()}
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            settings.update({k: v for k, v in data.items() if k in DEFAULTS})
    except (OSError, ValueError):
        pass
    for key in PATH_KEYS:
        if isinstance(settings[key], str) and settings[key] and not os.path.isabs(settings[key]):
            settings[key] = to_abs(settings[key])
    # Unknown charset names are ignored, missing ones are appended (atlas 1).
    settings["charsets"] = [n for n in settings["charsets"] if n in LABELS]
    order = [n for n in settings["charset_order"] if n in LABELS]
    settings["charset_order"] = list(dict.fromkeys(order + DEFAULT_ORDER))
    atlas = settings["charset_atlas"] if isinstance(settings["charset_atlas"], dict) else {}
    settings["charset_atlas"] = {n: v for n, v in atlas.items() if n in LABELS and isinstance(v, int) and v >= 1}
    if settings["atlas_mode"] not in ("auto", "manual"):
        settings["atlas_mode"] = "auto"
    return settings


def save_settings(settings):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


# ------------------------------------------------------------------- Font

def _parse_cmap(data, offset):
    """Unicode codepoint -> glyph index, from cmap subtables of format 4 and 12."""
    result = {}
    count = struct.unpack_from(">H", data, offset + 2)[0]
    for i in range(count):
        platform, encoding, sub = struct.unpack_from(">HHI", data, offset + 4 + 8 * i)
        if not (platform == 0 or (platform == 3 and encoding in (1, 10))):
            continue
        so = offset + sub
        fmt = struct.unpack_from(">H", data, so)[0]
        if fmt == 4:
            seg_x2 = struct.unpack_from(">H", data, so + 6)[0]
            ends = so + 14
            starts = ends + seg_x2 + 2
            deltas = starts + seg_x2
            range_offsets = deltas + seg_x2
            for s in range(seg_x2 // 2):
                end = struct.unpack_from(">H", data, ends + 2 * s)[0]
                start = struct.unpack_from(">H", data, starts + 2 * s)[0]
                delta = struct.unpack_from(">H", data, deltas + 2 * s)[0]
                ro = struct.unpack_from(">H", data, range_offsets + 2 * s)[0]
                for c in range(start, end + 1):
                    if c == 0xFFFF:
                        continue
                    if ro == 0:
                        g = (c + delta) & 0xFFFF
                    else:
                        g = struct.unpack_from(">H", data, range_offsets + 2 * s + ro + 2 * (c - start))[0]
                        if g:
                            g = (g + delta) & 0xFFFF
                    if g:
                        result[c] = g
        elif fmt == 12:
            groups = struct.unpack_from(">I", data, so + 12)[0]
            for gi in range(groups):
                start, end, first = struct.unpack_from(">III", data, so + 16 + 12 * gi)
                for c in range(start, end + 1):
                    g = first + c - start
                    if g:
                        result[c] = g
    return result


def read_font_glyphs(path):
    """Returns (codepoints with a non-empty glyph, exact) or None if the font cannot be read."""
    try:
        with open(path, "rb") as f:
            data = f.read()
        base = struct.unpack_from(">I", data, 12)[0] if data[:4] == b"ttcf" else 0
        num_tables = struct.unpack_from(">H", data, base + 4)[0]
        tables = {}
        for i in range(num_tables):
            tag, _, offset, length = struct.unpack_from(">4sIII", data, base + 12 + 16 * i)
            tables[tag] = offset
        cmap = _parse_cmap(data, tables[b"cmap"])
        if b"glyf" in tables and b"loca" in tables:
            long_loca = struct.unpack_from(">h", data, tables[b"head"] + 50)[0]
            num_glyphs = struct.unpack_from(">H", data, tables[b"maxp"] + 4)[0]
            if long_loca:
                loca = struct.unpack_from(f">{num_glyphs + 1}I", data, tables[b"loca"])
            else:
                loca = [x * 2 for x in struct.unpack_from(f">{num_glyphs + 1}H", data, tables[b"loca"])]
            # Empty glyph = loca entry of length 0.
            return frozenset(c for c, g in cmap.items() if g < num_glyphs and loca[g + 1] > loca[g]), True
        return frozenset(c for c in cmap if c not in WHITESPACE), False
    except (OSError, struct.error, KeyError, IndexError):
        return None


class App:
    def __init__(self, root):
        self.root = root
        self.settings = load_settings()
        self.process = None
        self.closing = False
        self.log_queue = queue.Queue()
        self.font_key = None
        self.font_glyphs = None
        self.font_exact = False
        self.glyph_cache = {}
        self.pages = []
        self.layout_errors = []
        self.outputs = []

        root.title("msdf-atlas-gen GUI")
        root.minsize(760, 0)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        s = self.settings
        self.exe = tk.StringVar(value=s["exe"])
        self.font = tk.StringVar(value=s["font"])
        self.type = tk.StringVar(value=s["type"] if s["type"] in TYPES else DEFAULTS["type"])
        self.order = s["charset_order"]
        self.charset_atlas = s["charset_atlas"]
        self.atlas_mode = s["atlas_mode"]
        self.charset_vars = {name: tk.BooleanVar(value=name in s["charsets"]) for name in DEFAULT_ORDER}
        self.size = tk.StringVar(value=s["size"])
        self.uniform = tk.BooleanVar(value=s["uniform"])
        self.cell_x = tk.StringVar(value=s["cell_x"])
        self.cell_y = tk.StringVar(value=s["cell_y"])
        self.pxrange = tk.StringVar(value=s["pxrange"])
        self.dim_x = tk.StringVar(value=s["dim_x"])
        self.dim_y = tk.StringVar(value=s["dim_y"])
        self.square = tk.BooleanVar(value=s["square"])
        self.preset = tk.StringVar()
        self.image_auto = tk.BooleanVar(value=s["image_auto"])
        self.image_dir = s["image_dir"]
        self.image_path = tk.StringVar(value=s["image_path"])
        self.csv = tk.BooleanVar(value=s["csv"])
        self.csv_auto = tk.BooleanVar(value=s["csv_auto"])
        self.csv_path = tk.StringVar(value=s["csv_path"])
        self.json = tk.BooleanVar(value=s["json"])
        self.json_auto = tk.BooleanVar(value=s["json_auto"])
        self.json_path = tk.StringVar(value=s["json_path"])
        self.prev_auto = {"image": self.image_auto.get(), "csv": self.csv_auto.get(), "json": self.json_auto.get()}

        self.build_ui()

        for var in (self.exe, self.font, self.type, self.size, self.uniform, self.cell_x, self.cell_y,
                    self.pxrange, self.dim_x, self.dim_y, self.square, self.image_auto, self.image_path,
                    self.csv, self.csv_auto, self.csv_path, self.json, self.json_auto, self.json_path,
                    *self.charset_vars.values()):
            var.trace_add("write", lambda *_: self.refresh())
        self.refresh()
        self.poll_log()

    # ------------------------------------------------------------------ UI

    def build_ui(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)
        main.columnconfigure(1, weight=1)
        row = 0

        def label(text, sticky="w"):
            ttk.Label(main, text=text).grid(row=row, column=0, sticky=sticky, padx=(0, 8), pady=3)

        label("msdf-atlas-gen executable")
        ttk.Entry(main, textvariable=self.exe).grid(row=row, column=1, sticky="ew", pady=3)
        ttk.Button(main, text="Browse…", command=self.browse_exe).grid(row=row, column=2, padx=(6, 0), sticky="w")
        row += 1

        label("Font")
        ttk.Entry(main, textvariable=self.font).grid(row=row, column=1, sticky="ew", pady=3)
        ttk.Button(main, text="Browse…", command=self.browse_font).grid(row=row, column=2, padx=(6, 0), sticky="w")
        row += 1

        label("Type")
        ttk.Combobox(main, textvariable=self.type, values=TYPES, state="readonly", width=12).grid(
            row=row, column=1, sticky="w", pady=3)
        row += 1

        label("Charsets", sticky="nw")
        self.charset_frame = ttk.Frame(main)
        self.charset_frame.grid(row=row, column=1, sticky="w", pady=3)
        self.rebuild_charset_grid()
        csb = ttk.Frame(main)
        csb.grid(row=row, column=2, padx=(6, 0), sticky="nw", pady=3)
        ttk.Button(csb, text="All", command=lambda: self.set_all_charsets(True)).pack(fill="x")
        ttk.Button(csb, text="None", command=lambda: self.set_all_charsets(False)).pack(fill="x", pady=2)
        ttk.Button(csb, text="Order…", command=lambda: OrderDialog(self)).pack(fill="x")
        row += 1

        label("Glyph size (px/em)")
        ttk.Entry(main, textvariable=self.size, width=8).grid(row=row, column=1, sticky="w", pady=3)
        row += 1

        label("Uniform cells")
        uf = ttk.Frame(main)
        uf.grid(row=row, column=1, sticky="w", pady=3)
        ttk.Checkbutton(uf, text="Enable", variable=self.uniform).pack(side="left", padx=(0, 8))
        ttk.Label(uf, text="X").pack(side="left")
        self.cell_x_entry = ttk.Entry(uf, textvariable=self.cell_x, width=6)
        self.cell_x_entry.pack(side="left", padx=(2, 8))
        ttk.Label(uf, text="Y").pack(side="left")
        self.cell_y_entry = ttk.Entry(uf, textvariable=self.cell_y, width=6)
        self.cell_y_entry.pack(side="left", padx=(2, 0))
        row += 1

        label("SDF range (px)")
        ttk.Entry(main, textvariable=self.pxrange, width=8).grid(row=row, column=1, sticky="w", pady=3)
        row += 1

        label("Atlas dimensions")
        df = ttk.Frame(main)
        df.grid(row=row, column=1, sticky="w", pady=3)
        ttk.Label(df, text="X").pack(side="left")
        ttk.Entry(df, textvariable=self.dim_x, width=6).pack(side="left", padx=(2, 8))
        self.dim_y_label = ttk.Label(df, text="Y")
        self.dim_y_label.pack(side="left")
        self.dim_y_entry = ttk.Entry(df, textvariable=self.dim_y, width=6)
        self.dim_y_entry.pack(side="left", padx=(2, 8))
        ttk.Checkbutton(df, text="Square", variable=self.square).pack(side="left", padx=(0, 12))
        ttk.Label(df, text="Preset").pack(side="left")
        preset = ttk.Combobox(df, textvariable=self.preset, values=PRESETS, state="readonly", width=6)
        preset.pack(side="left", padx=(4, 0))
        preset.bind("<<ComboboxSelected>>", self.apply_preset)
        row += 1

        self.info = ttk.Label(main, text="", wraplength=700, justify="left")
        self.info.grid(row=row, column=0, columnspan=3, sticky="w", pady=(6, 3))
        row += 1

        ttk.Separator(main).grid(row=row, column=0, columnspan=3, sticky="ew", pady=6)
        row += 1

        label("Image output (.png)")
        self.image_entry = ttk.Entry(main, textvariable=self.image_path)
        self.image_entry.grid(row=row, column=1, sticky="ew", pady=3)
        imf = ttk.Frame(main)
        imf.grid(row=row, column=2, padx=(6, 0), sticky="w")
        ttk.Button(imf, text="Browse…", command=self.browse_image).pack(side="left")
        ttk.Checkbutton(imf, text="Auto name", variable=self.image_auto).pack(side="left", padx=(6, 0))
        row += 1

        self.csv_entry, row = self.build_side_output(main, row, "CSV", self.csv, self.csv_auto, self.csv_path,
                                                     lambda: self.browse_side(self.csv_path, ".csv"))
        self.json_entry, row = self.build_side_output(main, row, "JSON", self.json, self.json_auto, self.json_path,
                                                      lambda: self.browse_side(self.json_path, ".json"))

        ttk.Separator(main).grid(row=row, column=0, columnspan=3, sticky="ew", pady=6)
        row += 1

        label("Command", sticky="nw")
        cmdf = ttk.Frame(main)
        cmdf.grid(row=row, column=1, columnspan=2, sticky="ew", pady=3)
        cmdf.columnconfigure(0, weight=1)
        self.preview = tk.Text(cmdf, height=4, wrap="char", font=("Consolas", 9))
        self.preview.grid(row=0, column=0, sticky="ew")
        # Read-only but selectable: only keys that modify the text are blocked.
        self.preview.bind("<Key>", self.preview_key)
        self.preview.bind("<<Paste>>", lambda e: "break")
        self.preview.bind("<<Cut>>", lambda e: "break")
        ttk.Button(cmdf, text="Copy", command=self.copy_command).grid(row=0, column=1, padx=(6, 0), sticky="n")
        row += 1

        bf = ttk.Frame(main)
        bf.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(6, 3))
        self.generate_btn = ttk.Button(bf, text="Generate", command=self.generate)
        self.generate_btn.pack(side="right")
        self.status = ttk.Label(bf, text="")
        self.status.pack(side="left")
        row += 1

        main.rowconfigure(row, weight=1)
        logf = ttk.Frame(main)
        logf.grid(row=row, column=0, columnspan=3, sticky="nsew")
        logf.columnconfigure(0, weight=1)
        logf.rowconfigure(0, weight=1)
        self.log = tk.Text(logf, height=12, wrap="word", font=("Consolas", 9), state="disabled")
        self.log.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(logf, orient="vertical", command=self.log.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=sb.set)
        self.log.tag_configure("error", foreground="#c00000")
        self.log.tag_configure("info", foreground="#606060")

    def build_side_output(self, parent, row, name, enabled, auto, path, browse):
        cb = ttk.Checkbutton(parent, text=name, variable=enabled)
        cb.grid(row=row, column=0, sticky="w", pady=3)
        entry = ttk.Entry(parent, textvariable=path)
        entry.grid(row=row, column=1, sticky="ew", pady=3)
        f = ttk.Frame(parent)
        f.grid(row=row, column=2, padx=(6, 0), sticky="w")
        btn = ttk.Button(f, text="Browse…", command=browse)
        btn.pack(side="left")
        auto_cb = ttk.Checkbutton(f, text="Auto name", variable=auto)
        auto_cb.pack(side="left", padx=(6, 0))
        entry.side_widgets = (btn, auto_cb)
        return entry, row + 1

    def rebuild_charset_grid(self):
        for child in self.charset_frame.winfo_children():
            child.destroy()
        for i, name in enumerate(self.order):
            ttk.Checkbutton(self.charset_frame, text=LABELS[name], variable=self.charset_vars[name]).grid(
                row=i // GRID_COLUMNS, column=i % GRID_COLUMNS, sticky="w", padx=(0, 10))

    def set_all_charsets(self, value):
        for var in self.charset_vars.values():
            var.set(value)

    def apply_preset(self, _event=None):
        value = self.preset.get()
        self.square.set(True)
        self.dim_x.set(value)
        self.dim_y.set(value)

    # -------------------------------------------------------------- Browse

    def browse_exe(self):
        exe = self.exe.get().strip()
        path = filedialog.askopenfilename(title="msdf-atlas-gen.exe",
                                          initialdir=os.path.dirname(to_abs(exe)) if exe else BASE_DIR,
                                          filetypes=[("Executable", "*.exe"), ("All files", "*.*")])
        if path:
            self.exe.set(os.path.normpath(path))

    def browse_font(self):
        font = self.font.get().strip()
        path = filedialog.askopenfilename(title="Font",
                                          initialdir=os.path.dirname(to_abs(font)) if font else BASE_DIR,
                                          filetypes=[("Fonts", "*.ttf *.otf"), ("All files", "*.*")])
        if path:
            self.font.set(os.path.normpath(path))

    def browse_image(self):
        initial = to_abs(os.path.dirname(self.image_path.get()) or self.image_dir or ".")
        if self.image_auto.get():
            path = filedialog.askdirectory(title="Output folder", initialdir=initial)
            if path:
                self.image_dir = os.path.normpath(path)
                self.refresh()
        else:
            path = filedialog.asksaveasfilename(title="Image output", initialdir=initial, defaultextension=".png",
                                                filetypes=[("PNG", "*.png")])
            if path:
                self.image_path.set(os.path.normpath(path))

    def browse_side(self, var, ext):
        initial = to_abs(os.path.dirname(var.get()) or self.image_dir or ".")
        path = filedialog.asksaveasfilename(initialdir=initial, defaultextension=ext,
                                            filetypes=[(ext[1:].upper(), "*" + ext)])
        if path:
            var.set(os.path.normpath(path))

    # ------------------------------------------------------ Glyph counting

    def selected_charsets(self):
        return [name for name in self.order if self.charset_vars[name].get()]

    def update_font(self):
        font = self.font.get().strip()
        key = to_abs(font) if font else ""
        if key == self.font_key:
            return
        self.font_key = key
        self.glyph_cache = {}
        result = read_font_glyphs(key) if key and os.path.isfile(key) else None
        self.font_glyphs, self.font_exact = result if result else (None, False)

    def charset_glyphs(self, name):
        """Glyphs that take a cell: codepoints present in the font, minus empty glyphs."""
        if name not in self.glyph_cache:
            cps = CODEPOINTS[name]
            self.glyph_cache[name] = cps if self.font_glyphs is None else cps & self.font_glyphs
        return self.glyph_cache[name]

    def glyph_count(self, names):
        glyphs = set()
        for name in names:
            glyphs |= self.charset_glyphs(name)
        return len(glyphs)

    def capacity(self):
        if not self.uniform.get():
            return None
        try:
            cx, cy = int(self.cell_x.get()), int(self.cell_y.get())
            dx = int(self.dim_x.get())
            dy = dx if self.square.get() else int(self.dim_y.get())
            if min(cx, cy, dx, dy) <= 0:
                return None
        except ValueError:
            return None
        return (dx // cx) * (dy // cy)

    def auto_pages(self, names):
        """Fills atlas 1 in order, then atlas 2, etc. A charset is never split."""
        cap = self.capacity()
        if cap is None:
            return [list(names)] if names else []
        pages, current, current_glyphs = [], [], set()
        for name in names:
            merged = current_glyphs | self.charset_glyphs(name)
            if current and len(merged) > cap:
                pages.append(current)
                current, current_glyphs = [name], set(self.charset_glyphs(name))
            else:
                current.append(name)
                current_glyphs = merged
        if current:
            pages.append(current)
        return pages

    def compute_layout(self):
        selected = self.selected_charsets()
        if self.atlas_mode == "auto":
            pages = self.auto_pages(selected)
            for index, names in enumerate(pages, 1):
                for name in names:
                    self.charset_atlas[name] = index
        else:
            numbers = sorted({self.charset_atlas.get(n, 1) for n in selected})
            pages = [[n for n in selected if self.charset_atlas.get(n, 1) == number] for number in numbers]
        cap = self.capacity()
        errors = []
        if cap is not None:
            for name in selected:
                count = len(self.charset_glyphs(name))
                if count > cap:
                    errors.append(f"{LABELS[name]} alone exceeds the atlas capacity ({count} / {cap}): "
                                  "increase the dimensions or reduce the cells.")
            for index, names in enumerate(pages, 1):
                count = self.glyph_count(names)
                if count > cap and len(names) > 1:
                    errors.append(f"Atlas {index} exceeds its capacity ({count} / {cap}).")
        self.pages = pages
        self.layout_errors = errors

    def apply_layout(self, pages, unselected, mode):
        """Called by the order dialog when it is validated."""
        self.order = [n for names in pages for n in names] + list(unselected)
        for index, names in enumerate(pages, 1):
            for name in names:
                self.charset_atlas[name] = index
        self.atlas_mode = mode
        self.rebuild_charset_grid()
        self.refresh()

    # ------------------------------------------------------------- Refresh

    def refresh(self):
        if getattr(self, "_refreshing", False):
            return
        self._refreshing = True
        try:
            self.update_font()
            self.compute_layout()
            self.update_outputs()
            self.update_states()
            self.update_info()
            self.update_preview()
        finally:
            self._refreshing = False

    def auto_base_name(self, names, single):
        font_name = os.path.splitext(os.path.basename(self.font.get().strip()))[0] or "atlas"
        if single and len(names) == len(DEFAULT_ORDER):
            return font_name + "_all"
        return font_name + "_" + "-".join(ABBRS[n] for n in names) if names else font_name

    def update_outputs(self):
        pages = self.pages or [[]]
        count = len(pages)
        # When "Auto name" is unticked, the displayed name of atlas 1 loses its "_1" suffix.
        for key, auto_var, path_var in (("image", self.image_auto, self.image_path),
                                        ("csv", self.csv_auto, self.csv_path),
                                        ("json", self.json_auto, self.json_path)):
            if self.prev_auto[key] and not auto_var.get() and count > 1:
                root, ext = os.path.splitext(path_var.get())
                if root.endswith("_1"):
                    path_var.set(root[:-2] + ext)
            self.prev_auto[key] = auto_var.get()
        if not self.image_auto.get() and os.path.dirname(self.image_path.get()):
            self.image_dir = os.path.dirname(self.image_path.get())

        outputs = []
        for index, names in enumerate(pages, 1):
            if self.image_auto.get():
                name = self.auto_base_name(names, count == 1)
                image = os.path.join(self.image_dir, numbered(name, index, count) + ".png")
            else:
                image = numbered(self.image_path.get().strip(), index, count)
            stem = os.path.splitext(image)[0]
            csv = stem + ".csv" if self.csv_auto.get() else numbered(self.csv_path.get().strip(), index, count)
            js = stem + ".json" if self.json_auto.get() else numbered(self.json_path.get().strip(), index, count)
            outputs.append((names, image, csv, js))
        self.outputs = outputs

        # Auto-named fields display the paths of atlas 1.
        if self.image_auto.get():
            self.image_path.set(outputs[0][1])
        if self.csv_auto.get():
            self.csv_path.set(outputs[0][2])
        if self.json_auto.get():
            self.json_path.set(outputs[0][3])

    def update_states(self):
        def set_state(widget, enabled, readonly=False):
            if not enabled:
                widget.state(["disabled"])
            else:
                widget.state(["!disabled"])
                widget.state(["readonly"] if readonly else ["!readonly"])

        set_state(self.cell_x_entry, self.uniform.get())
        set_state(self.cell_y_entry, self.uniform.get())
        set_state(self.dim_y_entry, not self.square.get())
        set_state(self.dim_y_label, not self.square.get())
        set_state(self.image_entry, True, readonly=self.image_auto.get())
        for entry, enabled, auto in ((self.csv_entry, self.csv, self.csv_auto),
                                     (self.json_entry, self.json, self.json_auto)):
            set_state(entry, enabled.get(), readonly=auto.get())
            for w in entry.side_widgets:
                set_state(w, enabled.get())

        x = self.dim_x.get().strip()
        y = x if self.square.get() else self.dim_y.get().strip()
        self.preset.set(x if x == y and x in PRESETS else "")

    def update_info(self):
        selected = self.selected_charsets()
        cap = self.capacity()
        cap_text = str(cap) if cap is not None else "n/a"
        if self.font_glyphs is None:
            source = " (codepoints, font not read)"
        elif not self.font_exact:
            source = " (approx., CFF font)"
        else:
            source = ""
        parts = [f"Glyphs: {self.glyph_count(selected)}{source}", f"Atlases: {len(self.pages)}"]
        parts += [f"Atlas {i}: {self.glyph_count(names)} / {cap_text}" for i, names in enumerate(self.pages, 1)]
        text = "  ·  ".join(parts)
        if self.layout_errors:
            text += "\n" + "\n".join(self.layout_errors)
        self.info.configure(text=text, foreground="#c00000" if self.layout_errors else "")

    def exe_for_command(self):
        exe = self.exe.get().strip() or "msdf-atlas-gen.exe"
        return exe if os.path.dirname(exe) else ".\\" + exe

    def build_commands(self):
        common = ["-type", self.type.get()]
        tail = ["-size", self.size.get().strip()]
        if self.uniform.get():
            tail += ["-uniformgrid", "-uniformcell", self.cell_x.get().strip(), self.cell_y.get().strip()]
        tail += ["-pxrange", self.pxrange.get().strip()]
        dim_x = self.dim_x.get().strip()
        dim_y = dim_x if self.square.get() else self.dim_y.get().strip()
        tail += ["-dimensions", dim_x, dim_y]
        commands = []
        for names, image, csv, js in self.outputs:
            cmd = [self.exe_for_command(), "-font", self.font.get().strip()] + common
            if names:
                cmd += ["-chars", ", ".join(SPECS[n] for n in names)]
            cmd += tail + ["-imageout", image]
            if self.csv.get():
                cmd += ["-csv", csv]
            if self.json.get():
                cmd += ["-json", js]
            commands.append(cmd)
        return commands

    def command_text(self):
        return "\n".join(subprocess.list2cmdline(cmd) for cmd in self.build_commands())

    def update_preview(self):
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", self.command_text())

    def preview_key(self, event):
        ctrl = event.state & 0x4
        if ctrl and event.keysym.lower() in ("c", "a", "insert"):
            if event.keysym.lower() == "a":
                self.preview.tag_add("sel", "1.0", "end-1c")
                return "break"
            return None
        if event.keysym in ("Left", "Right", "Up", "Down", "Home", "End", "Prior", "Next"):
            return None
        return "break"

    def copy_command(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.command_text())
        self.status.configure(text="Command copied.")

    # ---------------------------------------------------------- Validation

    def validate(self):
        errors = []
        exe = self.exe.get().strip()
        if not exe or not os.path.isfile(to_abs(exe)):
            errors.append("msdf-atlas-gen executable not found.")
        font = self.font.get().strip()
        if not font or not os.path.isfile(to_abs(font)):
            errors.append("Font not found.")
        if not self.selected_charsets():
            errors.append("Select at least one charset.")

        def positive(value, name, integer):
            try:
                n = int(value) if integer else float(value)
                if n <= 0:
                    raise ValueError
            except ValueError:
                errors.append(f"{name}: positive {'integer' if integer else 'number'} expected.")

        positive(self.size.get().strip(), "Glyph size", False)
        positive(self.pxrange.get().strip(), "SDF range", False)
        if self.uniform.get():
            positive(self.cell_x.get().strip(), "Cell X", True)
            positive(self.cell_y.get().strip(), "Cell Y", True)
        positive(self.dim_x.get().strip(), "Dimension X", True)
        if not self.square.get():
            positive(self.dim_y.get().strip(), "Dimension Y", True)
        errors += self.layout_errors

        for _, image, csv, js in self.outputs:
            outputs = [("Image output", image)]
            if self.csv.get():
                outputs.append(("CSV", csv))
            if self.json.get():
                outputs.append(("JSON", js))
            for name, path in outputs:
                folder = os.path.dirname(path)
                if not os.path.basename(path):
                    errors.append(f"{name}: empty path.")
                elif not os.path.isdir(to_abs(folder or ".")):
                    errors.append(f"{name}: folder does not exist ({folder}).")
        return list(dict.fromkeys(errors))

    # ----------------------------------------------------------- Execution

    def generate(self):
        if self.process is not None:
            return
        errors = self.validate()
        if errors:
            messagebox.showerror("Invalid parameters", "\n".join(errors))
            return
        self.save()
        self.log_clear()
        self.generate_btn.state(["disabled"])
        self.status.configure(text="Generating…")
        threading.Thread(target=self.run, args=(self.build_commands(),), daemon=True).start()

    def run(self, commands):
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        # Relative paths are resolved by msdf-atlas-gen from BASE_DIR; the exe itself is passed absolute.
        executable = to_abs(self.exe.get().strip())
        for index, cmd in enumerate(commands, 1):
            if self.closing:
                return
            if len(commands) > 1:
                self.log_queue.put(("text", f"Atlas {index}/{len(commands)}\n", "info"))
            self.log_queue.put(("text", "> " + subprocess.list2cmdline(cmd) + "\n", "info"))
            try:
                self.process = subprocess.Popen(cmd, executable=executable, cwd=BASE_DIR,
                                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                                stdin=subprocess.DEVNULL, creationflags=flags)
                err_thread = threading.Thread(target=self.pump, args=(self.process.stderr, "error"), daemon=True)
                err_thread.start()
                self.pump(self.process.stdout, None)
                err_thread.join()
                code = self.process.wait()
            except OSError as e:
                self.log_queue.put(("text", f"Failed to start: {e}\n", "error"))
                code = None
            if code != 0:
                self.log_queue.put(("done", code))
                return
        self.log_queue.put(("done", 0))

    def pump(self, stream, tag):
        for raw in iter(stream.readline, b""):
            self.log_queue.put(("text", raw.decode("utf-8", errors="replace").replace("\r\n", "\n"), tag))
        stream.close()

    def poll_log(self):
        try:
            while True:
                item = self.log_queue.get_nowait()
                if item[0] == "text":
                    self.log_write(item[1], item[2])
                else:
                    code = item[1]
                    self.process = None
                    self.generate_btn.state(["!disabled"])
                    if code == 0:
                        self.status.configure(text="Done.")
                        self.log_write("Done (exit code 0).\n", "info")
                    else:
                        self.status.configure(text="Failed.")
                        self.log_write(f"Failed (exit code {code}).\n", "error")
        except queue.Empty:
            pass
        self.root.after(50, self.poll_log)

    def log_clear(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def log_write(self, text, tag=None):
        self.log.configure(state="normal")
        self.log.insert("end", text, tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    # ------------------------------------------------------------ Settings

    def save(self):
        save_settings({
            "exe": self.exe.get(),
            "font": self.font.get(),
            "type": self.type.get(),
            "charsets": self.selected_charsets(),
            "size": self.size.get(),
            "uniform": self.uniform.get(),
            "cell_x": self.cell_x.get(),
            "cell_y": self.cell_y.get(),
            "pxrange": self.pxrange.get(),
            "dim_x": self.dim_x.get(),
            "dim_y": self.dim_y.get(),
            "square": self.square.get(),
            "image_auto": self.image_auto.get(),
            "image_dir": self.image_dir,
            "image_path": self.image_path.get(),
            "csv": self.csv.get(),
            "csv_auto": self.csv_auto.get(),
            "csv_path": self.csv_path.get(),
            "json": self.json.get(),
            "json_auto": self.json_auto.get(),
            "json_path": self.json_path.get(),
            "charset_order": self.order,
            "charset_atlas": self.charset_atlas,
            "atlas_mode": self.atlas_mode,
        })

    def on_close(self):
        self.save()
        self.closing = True
        if self.process is not None:
            try:
                self.process.kill()
            except OSError:
                pass
        self.root.destroy()


class OrderDialog:
    """Charset order and distribution across atlases."""

    UNSELECTED = "unselected"

    def __init__(self, app):
        self.app = app
        self.mode = app.atlas_mode
        self.section_counter = 0
        self.drag = None

        top = self.top = tk.Toplevel(app.root)
        top.title("Charset order")
        top.transient(app.root)
        top.grab_set()
        top.columnconfigure(0, weight=1)
        top.rowconfigure(0, weight=1)

        tree = self.tree = ttk.Treeview(top, columns=("num", "abbr", "chars", "glyphs"),
                                        show="tree headings", selectmode="browse", height=24)
        tree.heading("#0", text="Charset")
        tree.heading("num", text="#")
        tree.heading("abbr", text="Abbr.")
        tree.heading("chars", text="Chars")
        tree.heading("glyphs", text="Glyphs")
        tree.column("#0", width=260)
        tree.column("num", width=40, anchor="e")
        tree.column("abbr", width=60, anchor="center")
        tree.column("chars", width=60, anchor="e")
        tree.column("glyphs", width=60, anchor="e")
        tree.tag_configure("header", font=("Segoe UI", 9, "bold"))
        tree.tag_configure("over", foreground="#c00000")
        tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=10)
        sb = ttk.Scrollbar(top, orient="vertical", command=tree.yview)
        sb.grid(row=0, column=1, sticky="ns", pady=10)
        tree.configure(yscrollcommand=sb.set)
        tree.bind("<ButtonPress-1>", self.drag_start)
        tree.bind("<B1-Motion>", self.drag_motion)
        tree.bind("<ButtonRelease-1>", self.drag_end)

        side = ttk.Frame(top)
        side.grid(row=0, column=2, sticky="n", padx=10, pady=10)
        for text, command in (("Move up", self.move_up), ("Move down", self.move_down),
                              ("New atlas", self.new_atlas), ("Auto split", self.auto_split),
                              ("Reset to default", self.reset)):
            ttk.Button(side, text=text, command=command).pack(fill="x", pady=2)

        bottom = ttk.Frame(top)
        bottom.grid(row=1, column=0, columnspan=3, sticky="ew", padx=10, pady=(0, 10))
        self.mode_label = ttk.Label(bottom, text="")
        self.mode_label.pack(side="left")
        ttk.Button(bottom, text="Cancel", command=top.destroy).pack(side="right")
        ttk.Button(bottom, text="OK", command=self.ok).pack(side="right", padx=(0, 6))

        selected = set(app.selected_charsets())
        self.build(app.pages, [n for n in app.order if n not in selected])

    # ---------------------------------------------------------------- Tree

    def build(self, pages, unselected, select=None):
        tree = self.tree
        tree.delete(*tree.get_children())
        for names in pages:
            section = self.add_section()
            for name in names:
                tree.insert(section, "end", iid=name, text=LABELS[name])
        tree.insert("", "end", iid=self.UNSELECTED, text="Not selected", open=True, tags=("header",))
        for name in unselected:
            tree.insert(self.UNSELECTED, "end", iid=name, text=LABELS[name])
        if select:
            tree.selection_set(select)
            tree.see(select)
        self.update_counts()

    def add_section(self, index="end"):
        self.section_counter += 1
        return self.tree.insert("", index, iid=f"atlas{self.section_counter}", open=True, tags=("header",))

    def sections(self):
        return [s for s in self.tree.get_children() if s != self.UNSELECTED]

    def state(self):
        pages = [list(self.tree.get_children(s)) for s in self.sections()]
        return pages, list(self.tree.get_children(self.UNSELECTED))

    def update_counts(self):
        tree, app = self.tree, self.app
        cap = app.capacity()
        cap_text = str(cap) if cap is not None else "n/a"
        number = 1
        for index, section in enumerate(self.sections(), 1):
            names = tree.get_children(section)
            count = app.glyph_count(names)
            over = cap is not None and count > cap
            tree.item(section, text=f"Atlas {index} — {count} / {cap_text} glyphs",
                      tags=("header", "over") if over else ("header",))
            for name in names:
                number = self.update_row(name, number, cap)
        for name in tree.get_children(self.UNSELECTED):
            number = self.update_row(name, number, None)
        self.mode_label.configure(text=f"Mode: {self.mode}")

    def update_row(self, name, number, cap):
        glyphs = len(self.app.charset_glyphs(name))
        self.tree.item(name, values=(number, ABBRS[name], len(CODEPOINTS[name]), glyphs),
                       tags=("over",) if cap is not None and glyphs > cap else ())
        return number + 1

    def relayout(self, select=None):
        """Auto mode: redistributes the selected charsets following the displayed order."""
        pages, unselected = self.state()
        self.build(self.app.auto_pages([n for names in pages for n in names]), unselected, select)

    def after_move(self, item, section_changed):
        if section_changed:
            self.mode = "manual"
        if self.mode == "auto":
            self.relayout(item)
        else:
            self.update_counts()

    # ------------------------------------------------------------- Buttons

    def selected_charset(self):
        selection = self.tree.selection()
        return selection[0] if selection and selection[0] in LABELS else None

    def move_up(self):
        item = self.selected_charset()
        if not item:
            return
        parent, index = self.tree.parent(item), self.tree.index(item)
        if index > 0:
            self.tree.move(item, parent, index - 1)
            self.after_move(item, False)
        elif parent != self.UNSELECTED:
            sections = self.sections()
            position = sections.index(parent)
            if position > 0:
                self.tree.move(item, sections[position - 1], "end")
                self.after_move(item, True)
        self.tree.see(item)

    def move_down(self):
        item = self.selected_charset()
        if not item:
            return
        parent, index = self.tree.parent(item), self.tree.index(item)
        if index < len(self.tree.get_children(parent)) - 1:
            self.tree.move(item, parent, index + 1)
            self.after_move(item, False)
        elif parent != self.UNSELECTED:
            sections = self.sections()
            position = sections.index(parent)
            if position < len(sections) - 1:
                self.tree.move(item, sections[position + 1], 0)
                self.after_move(item, True)
        self.tree.see(item)

    def new_atlas(self):
        self.add_section(self.tree.index(self.UNSELECTED))
        self.update_counts()

    def auto_split(self):
        self.mode = "auto"
        self.relayout(self.selected_charset())

    def reset(self):
        self.mode = "auto"
        pages, _ = self.state()
        selected = {n for names in pages for n in names}
        self.build(self.app.auto_pages([n for n in DEFAULT_ORDER if n in selected]),
                   [n for n in DEFAULT_ORDER if n not in selected], self.selected_charset())

    def ok(self):
        pages, unselected = self.state()
        self.app.apply_layout([p for p in pages if p], unselected, self.mode)
        self.top.destroy()

    # --------------------------------------------------------- Drag & drop

    def drag_start(self, event):
        row = self.tree.identify_row(event.y)
        self.drag = row if row in LABELS else None
        self.drag_from = self.tree.parent(row) if self.drag else None
        self.drag_moved = False

    def drag_motion(self, event):
        if not self.drag:
            return
        target = self.tree.identify_row(event.y)
        if not target or target == self.drag:
            return
        if target in LABELS:
            parent, index = self.tree.parent(target), self.tree.index(target)
        else:
            # Dropping on a section header puts the charset at the end of that section.
            parent, index = target, "end"
        # Unselected charsets stay in their own section.
        if (parent == self.UNSELECTED) != (self.drag_from == self.UNSELECTED):
            return
        self.tree.move(self.drag, parent, index)
        self.drag_moved = True
        self.update_counts()

    def drag_end(self, _event):
        if self.drag and self.drag_moved:
            self.tree.selection_set(self.drag)
            self.after_move(self.drag, self.tree.parent(self.drag) != self.drag_from)
        self.drag = None


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
