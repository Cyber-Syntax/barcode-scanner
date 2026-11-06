# ruff: noqa: D100, D103, INP001

import tkinter as tk

from PIL import Image

from barcode_scanner import gui


class _FakeWindow:
    def __init__(self, _parent):
        self.geometry_value = None

    def overrideredirect(self, _value):
        pass

    def attributes(self, *_args):
        pass

    def geometry(self, value):
        self.geometry_value = value

    def bind(self, *_args):
        pass

    def focus_force(self):
        pass

    def destroy(self):
        pass


class _FakeCanvas:
    def __init__(self, *_args, **_kwargs):
        pass

    def pack(self, **_kwargs):
        pass

    def bind(self, *_args):
        pass

    def create_image(self, *_args, **_kwargs):
        pass


def test_screenshot_overlay_uses_tk_screen_size_for_dpi_scaled_windows(
    monkeypatch,
):
    app = object.__new__(gui.App)
    app._busy = False
    app._selection_window = None
    app._selection_image = None
    app._selection_canvas = None
    app._selection_tk = None
    app._selection_scale = (1.0, 1.0)
    app.winfo_screenwidth = lambda: 1920
    app.winfo_screenheight = lambda: 1080

    screen = Image.new("RGB", (2880, 1620))
    window = _FakeWindow(app)

    monkeypatch.setattr(gui, "grab_screen", lambda: screen)
    monkeypatch.setattr(tk, "Toplevel", lambda _app: window)
    monkeypatch.setattr(tk, "Canvas", _FakeCanvas)
    monkeypatch.setattr(gui.ImageTk, "PhotoImage", lambda _image: object())

    app._on_screenshot()

    assert window.geometry_value == "1920x1080+0+0"
    assert app._selection_scale == (1.5, 1.5)


def test_screenshot_selection_maps_tk_coordinates_to_capture_pixels(
    monkeypatch,
):
    app = object.__new__(gui.App)
    app._selection_start = (100, 200)
    app._selection_image = Image.new("RGB", (2880, 1620))
    app._selection_scale = (1.5, 1.5)
    app._selection_window = _FakeWindow(app)
    app._selection_canvas = None
    app._selection_tk = None
    app._busy = False
    app._selection_image_name = ""
    captured = []

    def fake_capture(region, *, grabber):
        captured.append(region)
        return Image.new("RGB", (1, 1))

    monkeypatch.setattr(gui, "capture_screen_region", fake_capture)
    monkeypatch.setattr(app, "_start_processing", lambda **_kwargs: None)

    event = type("Event", (), {"x": 400, "y": 600})()
    app._finish_selection(event)

    assert captured == [(150, 300, 600, 900)]
