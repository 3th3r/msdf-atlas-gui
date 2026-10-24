"""Simple graphical interface for msdf-atlas-gen.

Builds the command line from the fields, displays it, then runs it.
Standard library only (Tkinter / ttk).
"""

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(SCRIPT_DIR, "settings.json")

TYPES = ["hardmask", "softmask", "sdf", "psdf", "msdf", "mtsdf"]

# (short name, label, -chars ranges)
CHARSETS = [
    ("upper", "Uppercase", "[0x41, 0x5A]"),
    ("lower", "Lowercase", "[0x61, 0x7A]"),
    ("digits", "Digits", "[0x30, 0x39]"),
    ("punct", "Punctuation", "[0x20, 0x2F], [0x3A, 0x40], [0x5B, 0x60], [0x7B, 0x7E]"),
    ("latin1", "Latin-1", "[0xA0, 0xFF], 0x20AC"),
    ("latinExtA", "Latin Ext-A", "[0x100, 0x17F]"),
    ("greek", "Greek", "[0x370, 0x3FF]"),
    ("cyrillic", "Cyrillic", "[0x400, 0x4FF]"),
]
ASCII_GROUP = ("upper", "lower", "digits", "punct")

DEFAULTS = {
    "exe": "",
    "font": "",
    "type": "msdf",
    "charsets": ["upper", "lower", "digits", "punct"],
    "size": "32",
    "uniform": False,
    "cell_x": "32",
    "cell_y": "32",
    "pxrange": "2",
    "dim_x": "512",
    "dim_y": "512",
    "square": True,
    "image_auto": True,
    "image_dir": "",
    "image_path": "",
    "csv": False,
    "csv_auto": True,
    "csv_path": "",
    "json": False,
    "json_auto": True,
    "json_path": "",
}


def load_settings():
    settings = dict(DEFAULTS)
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            settings.update({k: v for k, v in data.items() if k in DEFAULTS})
    except (OSError, ValueError):
        pass
    return settings


def save_settings(settings):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


def auto_base_name(font_path, charsets):
    """<FontName>_<charsets>, with upper/lower/digits/punct grouped as "ascii"."""
    font_name = os.path.splitext(os.path.basename(font_path))[0] or "atlas"
    names = [name for name, _, _ in CHARSETS if name in charsets]
    if all(name in names for name in ASCII_GROUP):
        names = ["ascii"] + [n for n in names if n not in ASCII_GROUP]
    return font_name + "_" + "-".join(names) if names else font_name


class App:
    def __init__(self, root):
        self.root = root
        self.settings = load_settings()
        self.process = None
        self.log_queue = queue.Queue()

        root.title("msdf-atlas-gen GUI")
        root.minsize(720, 0)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        s = self.settings
        self.exe = tk.StringVar(value=s["exe"])
        self.font = tk.StringVar(value=s["font"])
        self.type = tk.StringVar(value=s["type"] if s["type"] in TYPES else "msdf")
        self.charset_vars = {name: tk.BooleanVar(value=name in s["charsets"]) for name, _, _ in CHARSETS}
        self.size = tk.StringVar(value=s["size"])
        self.uniform = tk.BooleanVar(value=s["uniform"])
        self.cell_x = tk.StringVar(value=s["cell_x"])
        self.cell_y = tk.StringVar(value=s["cell_y"])
        self.pxrange = tk.StringVar(value=s["pxrange"])
        self.dim_x = tk.StringVar(value=s["dim_x"])
        self.dim_y = tk.StringVar(value=s["dim_y"])
        self.square = tk.BooleanVar(value=s["square"])
        self.image_auto = tk.BooleanVar(value=s["image_auto"])
        self.image_dir = s["image_dir"]
        self.image_path = tk.StringVar(value=s["image_path"])
        self.csv = tk.BooleanVar(value=s["csv"])
        self.csv_auto = tk.BooleanVar(value=s["csv_auto"])
        self.csv_path = tk.StringVar(value=s["csv_path"])
        self.json = tk.BooleanVar(value=s["json"])
        self.json_auto = tk.BooleanVar(value=s["json_auto"])
        self.json_path = tk.StringVar(value=s["json_path"])

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

        def label(text):
            ttk.Label(main, text=text).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)

        label("msdf-atlas-gen executable")
        ttk.Entry(main, textvariable=self.exe).grid(row=row, column=1, sticky="ew", pady=3)
        ttk.Button(main, text="Browse…", command=self.browse_exe).grid(row=row, column=2, padx=(6, 0))
        row += 1

        label("Font")
        ttk.Entry(main, textvariable=self.font).grid(row=row, column=1, sticky="ew", pady=3)
        ttk.Button(main, text="Browse…", command=self.browse_font).grid(row=row, column=2, padx=(6, 0))
        row += 1

        label("Type")
        ttk.Combobox(main, textvariable=self.type, values=TYPES, state="readonly", width=12).grid(
            row=row, column=1, sticky="w", pady=3)
        row += 1

        label("Charsets")
        cs = ttk.Frame(main)
        cs.grid(row=row, column=1, columnspan=2, sticky="w", pady=3)
        for name, text, _ in CHARSETS:
            ttk.Checkbutton(cs, text=text, variable=self.charset_vars[name]).pack(side="left", padx=(0, 8))
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
        ttk.Checkbutton(df, text="Square", variable=self.square).pack(side="left")
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

        label("Command")
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

    # -------------------------------------------------------------- Browse

    def browse_exe(self):
        path = filedialog.askopenfilename(title="msdf-atlas-gen.exe",
                                          filetypes=[("Executable", "*.exe"), ("All files", "*.*")])
        if path:
            self.exe.set(os.path.normpath(path))

    def browse_font(self):
        initial = os.path.dirname(self.font.get()) or None
        path = filedialog.askopenfilename(title="Font", initialdir=initial,
                                          filetypes=[("Fonts", "*.ttf *.otf"), ("All files", "*.*")])
        if path:
            self.font.set(os.path.normpath(path))

    def browse_image(self):
        initial = os.path.dirname(self.image_path.get()) or self.image_dir or None
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
        initial = os.path.dirname(var.get()) or self.image_dir or None
        path = filedialog.asksaveasfilename(initialdir=initial, defaultextension=ext,
                                            filetypes=[(ext[1:].upper(), "*" + ext)])
        if path:
            var.set(os.path.normpath(path))

    # ------------------------------------------------------------- Refresh

    def selected_charsets(self):
        return [name for name, _, _ in CHARSETS if self.charset_vars[name].get()]

    def refresh(self):
        if getattr(self, "_refreshing", False):
            return
        self._refreshing = True
        try:
            self.update_auto_names()
            self.update_states()
            self.update_preview()
        finally:
            self._refreshing = False

    def update_auto_names(self):
        base = auto_base_name(self.font.get(), self.selected_charsets())
        if self.image_auto.get():
            folder = self.image_dir or os.path.dirname(self.image_path.get())
            self.image_path.set(os.path.join(folder, base + ".png") if folder else base + ".png")
        else:
            current = self.image_path.get()
            if os.path.dirname(current):
                self.image_dir = os.path.dirname(current)
        image_base = os.path.splitext(self.image_path.get())[0]
        if self.csv_auto.get():
            self.csv_path.set(image_base + ".csv")
        if self.json_auto.get():
            self.json_path.set(image_base + ".json")

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

    def build_command(self):
        cmd = [self.exe.get().strip() or "msdf-atlas-gen.exe",
               "-font", self.font.get().strip(),
               "-type", self.type.get()]
        ranges = [r for name, _, r in CHARSETS if self.charset_vars[name].get()]
        if ranges:
            cmd += ["-chars", ", ".join(ranges)]
        cmd += ["-size", self.size.get().strip()]
        if self.uniform.get():
            cmd += ["-uniformgrid", "-uniformcell", self.cell_x.get().strip(), self.cell_y.get().strip()]
        cmd += ["-pxrange", self.pxrange.get().strip()]
        dim_x = self.dim_x.get().strip()
        dim_y = dim_x if self.square.get() else self.dim_y.get().strip()
        cmd += ["-dimensions", dim_x, dim_y]
        cmd += ["-imageout", self.image_path.get().strip()]
        if self.csv.get():
            cmd += ["-csv", self.csv_path.get().strip()]
        if self.json.get():
            cmd += ["-json", self.json_path.get().strip()]
        return cmd

    def update_preview(self):
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", subprocess.list2cmdline(self.build_command()))

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
        self.root.clipboard_append(subprocess.list2cmdline(self.build_command()))
        self.status.configure(text="Command copied.")

    # ---------------------------------------------------------- Validation

    def validate(self):
        errors = []
        exe = self.exe.get().strip()
        if not exe or not os.path.isfile(exe):
            errors.append("msdf-atlas-gen executable not found.")
        font = self.font.get().strip()
        if not font or not os.path.isfile(font):
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

        outputs = [("Image output", self.image_path.get().strip())]
        if self.csv.get():
            outputs.append(("CSV", self.csv_path.get().strip()))
        if self.json.get():
            outputs.append(("JSON", self.json_path.get().strip()))
        for name, path in outputs:
            if not path:
                errors.append(f"{name}: empty path.")
            elif not os.path.dirname(path):
                errors.append(f"{name}: choose an output folder.")
            elif not os.path.isdir(os.path.dirname(os.path.abspath(path))):
                errors.append(f"{name}: folder does not exist ({os.path.dirname(path) or '.'}).")
        return errors

    # ----------------------------------------------------------- Execution

    def generate(self):
        if self.process is not None:
            return
        errors = self.validate()
        if errors:
            messagebox.showerror("Invalid parameters", "\n".join(errors))
            return
        self.save()
        cmd = self.build_command()
        self.log_clear()
        self.log_write("> " + subprocess.list2cmdline(cmd) + "\n", "info")
        self.generate_btn.state(["disabled"])
        self.status.configure(text="Generating…")
        threading.Thread(target=self.run, args=(cmd,), daemon=True).start()

    def run(self, cmd):
        try:
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            stdin=subprocess.DEVNULL, creationflags=flags)
            err_thread = threading.Thread(target=self.pump, args=(self.process.stderr, "error"), daemon=True)
            err_thread.start()
            self.pump(self.process.stdout, None)
            err_thread.join()
            code = self.process.wait()
            self.log_queue.put(("done", code))
        except OSError as e:
            self.log_queue.put(("text", f"Failed to start: {e}\n", "error"))
            self.log_queue.put(("done", None))

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
        })

    def on_close(self):
        self.save()
        if self.process is not None:
            try:
                self.process.kill()
            except OSError:
                pass
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
