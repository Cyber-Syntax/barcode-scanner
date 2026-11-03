# ruff: noqa: D100, D103, INP001

import pytest
from PIL import Image

from barcode_scanner.capture import ScreenCaptureError, capture_screen_region
from barcode_scanner.gui import MIN_WINDOW_SIZE


def test_capture_screen_region_returns_selected_pixels():
    screen = Image.new("RGB", (100, 80), "white")
    screen.putpixel((25, 30), (255, 0, 0))

    captured = capture_screen_region(
        (20, 25, 60, 60),
        grabber=lambda: screen,
    )

    assert captured.size == (40, 35)
    assert captured.getpixel((5, 5)) == (255, 0, 0)


def test_capture_screen_region_returns_none_when_cancelled():
    assert (
        capture_screen_region(
            None, grabber=lambda: Image.new("RGB", (1, 1))
        )
        is None
    )


def test_capture_screen_region_reports_capture_failure():
    def failing_grabber():
        raise OSError("screen unavailable")

    with pytest.raises(ScreenCaptureError, match="Ekran görüntüsü alınamadı"):
        capture_screen_region((0, 0, 10, 10), grabber=failing_grabber)


def test_capture_screen_region_rejects_empty_selection():
    with pytest.raises(ScreenCaptureError, match="Sıfır pikselden büyük"):
        capture_screen_region(
            (10, 10, 10, 20),
            grabber=lambda: Image.new("RGB", (20, 20)),
        )


def test_minimum_window_size_is_cross_platform_baseline():
    assert MIN_WINDOW_SIZE == (640, 480)
