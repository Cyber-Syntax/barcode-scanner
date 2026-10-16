from __future__ import annotations

import json
import logging
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from tkinter import font as tkfont

from PIL import Image, ImageOps, ImageTk

from .decoder import (
    SUPPORTED_EXTENSIONS,
    BarcodeResult,
    ImageLoadError,
    decode_barcodes,
    load_image,
)

log = logging.getLogger(__name__)

COPIED_FEEDBACK_MS = 1500
ERROR_FG = "#b00020"
OK_FG = "#1b6e2d"
FONT_SIZE = 24
ZOOM_STEP = 0.25
MIN_ZOOM = 0.25
MAX_ZOOM = 4.0
MOUSE_WHEEL_UP = 4
PREFERRED_FONT_FAMILIES = (
    "Segoe UI",
    "DejaVu Sans",
    "Liberation Sans",
    "Arial",
)
APP_CONFIG_NAME = "barcode-scanner"
LAST_IMPORT_DIR_KEY = "last_import_dir"


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        style = ttk.Style(self)
        available_fonts = set(tkfont.families(self))
        font_family = next(
            (
                family
                for family in PREFERRED_FONT_FAMILIES
                if family in available_fonts
            ),
            tkfont.nametofont("TkDefaultFont").actual()["family"],
        )
        ui_font = (font_family, FONT_SIZE)
        heading_font = (font_family, FONT_SIZE, "bold")
        self._heading_font = heading_font

        for name in (
            "TkDefaultFont",
            "TkTextFont",
            "TkMenuFont",
            "TkHeadingFont",
            "TkCaptionFont",
            "TkSmallCaptionFont",
            "TkIconFont",
            "TkTooltipFont",
        ):
            try:
                font = tkfont.nametofont(name)
                font.configure(family=font_family, size=FONT_SIZE)
            except tk.TclError:
                pass

        style.configure(".", font=ui_font)
        style.configure("TButton", font=ui_font, padding=(16, 10))
        style.configure("TEntry", font=ui_font)
        style.configure("TLabel", font=ui_font)
        style.configure("TLabelframe.Label", font=heading_font)

        self.title("Barcode Scanner")
        self.geometry("1200x900")
        self.minsize(900, 700)

        self._queue: queue.Queue = queue.Queue()
        self._value_vars: list[tk.StringVar] = []
        self._job = 0  # token to discard stale worker results
        self._busy = False
        self._preview_src: Image.Image | None = None
        self._preview_tk: ImageTk.PhotoImage | None = None
        self._resize_after: str | None = None
        self._zoom = 1.0
        self._zoom_label: ttk.Label | None = None
        self._last_import_dir = self._load_last_import_dir()

        self._build_ui()

    # ---------- UI construction ----------
    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        self.import_btn = ttk.Button(
            top, text="Import Image", command=self._on_import
        )
        self.import_btn.pack(side="left")
        self.image_name = ttk.Label(top, text="No image selected", anchor="w")
        self.image_name.pack(side="left", padx=(16, 0), fill="x", expand=True)
        self.status = ttk.Label(top, text="Import an image to begin.")
        self.status.pack(side="left", padx=12)

        paned = ttk.PanedWindow(self, orient="vertical")
        paned.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        preview_frame = ttk.LabelFrame(paned, text="Preview")
        self._build_preview(preview_frame)
        paned.add(preview_frame, weight=3)

        results_frame = ttk.LabelFrame(paned, text="Detected barcodes")
        self.canvas = tk.Canvas(results_frame, highlightthickness=0)
        vsb = ttk.Scrollbar(
            results_frame, orient="vertical", command=self.canvas.yview
        )
        self.canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.results = ttk.Frame(self.canvas)
        self._win = self.canvas.create_window(
            (0, 0), window=self.results, anchor="nw"
        )
        self.results.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            ),
        )
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfigure(self._win, width=e.width),
        )
        self.canvas.bind(
            "<Enter>",
            lambda e: self.canvas.bind_all("<MouseWheel>", self._on_wheel),
        )
        self.canvas.bind(
            "<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>")
        )
        paned.add(results_frame, weight=2)

    def _build_preview(self, preview_frame: ttk.LabelFrame) -> None:
        preview_controls = ttk.Frame(preview_frame)
        preview_controls.pack(fill="x", padx=6, pady=(4, 0))
        ttk.Button(
            preview_controls, text="-", width=3, command=self._zoom_out
        ).pack(side="left")
        ttk.Button(
            preview_controls, text="100%", command=self._reset_zoom
        ).pack(side="left", padx=4)
        ttk.Button(
            preview_controls, text="+", width=3, command=self._zoom_in
        ).pack(side="left")
        self._zoom_label = ttk.Label(preview_controls, text="Fit")
        self._zoom_label.pack(side="left", padx=8)

        preview_body = ttk.Frame(preview_frame)
        preview_body.pack(fill="both", expand=True, pady=(4, 0))
        preview_xscroll = ttk.Scrollbar(preview_body, orient="horizontal")
        preview_yscroll = ttk.Scrollbar(preview_body, orient="vertical")
        self.preview_canvas = tk.Canvas(
            preview_body,
            highlightthickness=0,
            xscrollcommand=preview_xscroll.set,
            yscrollcommand=preview_yscroll.set,
        )
        preview_xscroll.configure(command=self.preview_canvas.xview)
        preview_yscroll.configure(command=self.preview_canvas.yview)
        preview_xscroll.pack(side="bottom", fill="x")
        preview_yscroll.pack(side="right", fill="y")
        self.preview_canvas.pack(side="left", fill="both", expand=True)
        self._preview_item = self.preview_canvas.create_image(
            0, 0, anchor="center"
        )
        self.preview_canvas.bind("<Configure>", self._on_preview_resize)
        self.preview_canvas.bind("<MouseWheel>", self._on_preview_wheel)
        self.preview_canvas.bind("<Button-4>", self._on_preview_wheel)
        self.preview_canvas.bind("<Button-5>", self._on_preview_wheel)
        self.preview_canvas.bind("<ButtonPress-1>", self._start_preview_pan)
        self.preview_canvas.bind("<B1-Motion>", self._pan_preview)
        preview_frame.bind("<Configure>", self._on_preview_resize)

    def _on_wheel(self, event: tk.Event) -> None:
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    # ---------- Preview ----------
    def _on_preview_resize(self, _event: tk.Event) -> None:
        if self._resize_after:
            self.after_cancel(self._resize_after)
        self._resize_after = self.after(60, self._render_preview)

    def _on_preview_wheel(self, event: tk.Event) -> str:
        if getattr(event, "num", None) == MOUSE_WHEEL_UP or event.delta > 0:
            self._zoom_in()
        else:
            self._zoom_out()
        return "break"

    def _start_preview_pan(self, event: tk.Event) -> None:
        self.preview_canvas.scan_mark(event.x, event.y)

    def _pan_preview(self, event: tk.Event) -> None:
        self.preview_canvas.scan_dragto(event.x, event.y, gain=1)

    def _set_zoom(self, zoom: float) -> None:
        self._zoom = min(MAX_ZOOM, max(MIN_ZOOM, zoom))
        self._render_preview()

    def _zoom_in(self) -> None:
        self._set_zoom(self._zoom + ZOOM_STEP)

    def _zoom_out(self) -> None:
        self._set_zoom(self._zoom - ZOOM_STEP)

    def _reset_zoom(self) -> None:
        self._set_zoom(1.0)

    def _render_preview(self) -> None:
        self._resize_after = None
        if self._preview_src is None:
            return
        w = max(self.preview_canvas.winfo_width(), 50)
        h = max(self.preview_canvas.winfo_height(), 50)
        fitted = ImageOps.contain(
            self._preview_src, (w, h), Image.Resampling.LANCZOS
        )
        if self._zoom != 1.0:
            fitted = fitted.resize(
                (
                    max(1, round(fitted.width * self._zoom)),
                    max(1, round(fitted.height * self._zoom)),
                ),
                Image.Resampling.LANCZOS,
            )
        self._preview_tk = ImageTk.PhotoImage(fitted)
        self.preview_canvas.itemconfigure(
            self._preview_item, image=self._preview_tk
        )
        center_x = max(w, fitted.width) / 2
        center_y = max(h, fitted.height) / 2
        self.preview_canvas.coords(self._preview_item, center_x, center_y)
        self.preview_canvas.configure(
            scrollregion=(
                0,
                0,
                max(w, fitted.width),
                max(h, fitted.height),
            )
        )
        if self._zoom_label is not None:
            self._zoom_label.configure(
                text="Fit" if self._zoom == 1.0 else f"{self._zoom:.0%}"
            )

    # ---------- State helpers ----------
    def _set_status(self, text: str, color: str | None = None) -> None:
        self.status.configure(text=text, foreground=color or "")

    def _clear_results(self) -> None:
        self._value_vars.clear()
        for child in self.results.winfo_children():
            child.destroy()

    def _show_message(self, text: str, color: str | None = None) -> None:
        self._clear_results()
        ttk.Label(
            self.results, text=text, foreground=color or "", padding=12
        ).pack(anchor="w")

    def _config_path(self) -> Path:
        if os.name == "nt":
            config_root = Path(
                os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")
            )
        else:
            config_root = Path(
                os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
            )
        return config_root / APP_CONFIG_NAME / "settings.json"

    def _load_last_import_dir(self) -> Path:
        fallback = Path.home()
        try:
            config = json.loads(self._config_path().read_text())
            saved_dir = Path(config[LAST_IMPORT_DIR_KEY])
            return saved_dir if saved_dir.is_dir() else fallback
        except (OSError, KeyError, TypeError, ValueError):
            return fallback

    def _initial_dir(self) -> str:
        directory = self._last_import_dir
        try:
            if not directory.is_dir():
                directory = Path.home()
        except OSError:
            directory = Path.home()
        return os.path.normpath(str(directory))

    def _save_last_import_dir(self, directory: Path) -> None:
        try:
            config_path = self._config_path()
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(
                json.dumps({LAST_IMPORT_DIR_KEY: str(directory)})
            )
        except OSError:
            log.warning("Could not save settings", exc_info=True)

    # ---------- Import flow ----------
    def _on_import(self) -> None:
        if self._busy:
            return
        pattern = " ".join(f"*{ext}" for ext in SUPPORTED_EXTENSIONS)
        path = filedialog.askopenfilename(
            title="Select a barcode image",
            filetypes=[("Images", pattern), ("All files", "*.*")],
            initialdir=self._initial_dir(),
            parent=self,
        )
        if not path:
            return

        self._last_import_dir = Path(path).parent
        self._save_last_import_dir(self._last_import_dir)
        self.image_name.configure(text=Path(path).name)
        self._job += 1
        self._busy = True
        self.import_btn.state(["disabled"])
        self._set_status("Reading barcodes…")
        self._show_message("Working…")
        threading.Thread(
            target=self._work, args=(self._job, path), daemon=True
        ).start()
        self.after(50, self._poll)

    def _work(self, token: int, path: str) -> None:
        try:
            img = load_image(path)
            found = decode_barcodes(img)
            self._queue.put((token, "ok", (img, found)))
        except ImageLoadError as exc:
            self._queue.put((token, "error", str(exc)))
        except Exception as exc:  # never let a worker crash silently
            self._queue.put(
                (token, "error", f"Unexpected error while decoding: {exc}")
            )

    def _poll(self) -> None:
        try:
            token, kind, payload = self._queue.get_nowait()
        except queue.Empty:
            self.after(50, self._poll)
            return

        if token != self._job:
            self.after(50, self._poll)
            return

        self._busy = False
        self.import_btn.state(["!disabled"])
        if kind == "ok":
            img, found = payload
            self._preview_src = img
            self._render_preview()
            self._show_results(found)
        else:
            self._set_status("Error", ERROR_FG)
            self._show_message(payload, ERROR_FG)

    # ---------- Results ----------
    def _show_results(self, found: list[BarcodeResult]) -> None:
        self._clear_results()
        if not found:
            self._set_status("No barcodes detected.", ERROR_FG)
            self._show_message("No barcodes detected. Try another image.")
            return

        self._set_status(f"Found {len(found)} barcode(s).", OK_FG)
        self.results.columnconfigure(1, weight=1)
        for col, title in enumerate(
            ("Barcode type", "Decoded value", "Action")
        ):
            ttk.Label(self.results, text=title, font=self._heading_font).grid(
                row=0, column=col, sticky="w", padx=6, pady=(4, 2)
            )
        for i, res in enumerate(found, start=1):
            ttk.Label(self.results, text=res.symbology, width=16).grid(
                row=i, column=0, sticky="w", padx=6, pady=3
            )
            # Readonly Entry: text is selectable, long values don't wrap oddly.
            var = tk.StringVar(value=res.value)
            self._value_vars.append(var)
            ttk.Entry(self.results, textvariable=var, state="readonly").grid(
                row=i, column=1, sticky="ew", padx=6, pady=3
            )
            btn = ttk.Button(self.results, text="Copy", width=10)
            btn.configure(command=lambda v=res.value, b=btn: self._copy(v, b))
            btn.grid(row=i, column=2, padx=6, pady=3)

    def _copy(self, value: str, btn: ttk.Button) -> None:
        self.clipboard_clear()
        self.clipboard_append(value)
        self.update()  # flush so the data is committed to the Windows clipboard
        btn.configure(text="Copied!")
        self.after(
            COPIED_FEEDBACK_MS,
            lambda: btn.winfo_exists() and btn.configure(text="Copy"),
        )


def main() -> None:
    if os.name == "nt":
        try:
            import ctypes

            try:
                ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
            except Exception:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            log.warning("Could not set DPI awareness", exc_info=True)
    App().mainloop()
