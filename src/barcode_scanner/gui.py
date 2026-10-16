from __future__ import annotations

import queue
import threading
import tkinter as tk
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

COPIED_FEEDBACK_MS = 1500
ERROR_FG = "#b00020"
OK_FG = "#1b6e2d"
FONT_SIZE = 24
PREFERRED_FONT_FAMILIES = (
    "Segoe UI",
    "DejaVu Sans",
    "Liberation Sans",
    "Arial",
)


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

        self._build_ui()

    # ---------- UI construction ----------
    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        self.import_btn = ttk.Button(
            top, text="Import Image", command=self._on_import
        )
        self.import_btn.pack(side="left")
        self.status = ttk.Label(top, text="Import an image to begin.")
        self.status.pack(side="left", padx=12)

        paned = ttk.PanedWindow(self, orient="vertical")
        paned.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        preview_frame = ttk.LabelFrame(paned, text="Preview")
        self.preview_label = ttk.Label(preview_frame, anchor="center")
        self.preview_label.pack(fill="both", expand=True)
        preview_frame.bind("<Configure>", self._on_preview_resize)
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

    def _on_wheel(self, event: tk.Event) -> None:
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    # ---------- Preview ----------
    def _on_preview_resize(self, _event: tk.Event) -> None:
        if self._resize_after:
            self.after_cancel(self._resize_after)
        self._resize_after = self.after(60, self._render_preview)

    def _render_preview(self) -> None:
        self._resize_after = None
        if self._preview_src is None:
            return
        w = max(self.preview_label.winfo_width(), 50)
        h = max(self.preview_label.winfo_height(), 50)
        fitted = ImageOps.contain(
            self._preview_src, (w, h), Image.Resampling.LANCZOS
        )
        self._preview_tk = ImageTk.PhotoImage(fitted)  # keep a reference
        self.preview_label.configure(image=self._preview_tk)

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

    # ---------- Import flow ----------
    def _on_import(self) -> None:
        if self._busy:
            return
        pattern = " ".join(f"*{ext}" for ext in SUPPORTED_EXTENSIONS)
        path = filedialog.askopenfilename(
            title="Select a barcode image",
            filetypes=[("Images", pattern), ("All files", "*.*")],
        )
        if not path:
            return

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
    try:  # crisp rendering on high-DPI displays
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    App().mainloop()
