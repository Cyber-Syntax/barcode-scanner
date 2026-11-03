"""Screen-region capture adapter."""

# Turkish user-facing messages intentionally use locale-specific characters.
# ruff: noqa: RUF001

from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image, ImageGrab

if TYPE_CHECKING:
    from collections.abc import Callable

ScreenRegion = tuple[int, int, int, int]


class ScreenCaptureError(Exception):
    """Raised when the screen cannot be captured."""


def grab_screen() -> Image.Image:
    """Capture the full screen or raise a user-facing capture error."""
    try:
        return ImageGrab.grab()
    except (OSError, ValueError) as exc:
        message = f"Ekran görüntüsü alınamadı: {exc}"
        raise ScreenCaptureError(message) from exc


def capture_screen_region(
    region: ScreenRegion | None,
    *,
    grabber: Callable[[], Image.Image] = ImageGrab.grab,
) -> Image.Image | None:
    """Capture and crop a confirmed screen region.

    ``None`` represents user cancellation and is deliberately not an error.
    """
    if region is None:
        return None

    left, top, right, bottom = region
    if right <= left or bottom <= top:
        message = "Sıfır pikselden büyük bir alan seçin."
        raise ScreenCaptureError(message)

    try:
        screen = grabber()
        return screen.crop((left, top, right, bottom)).convert("RGB")
    except (OSError, ValueError) as exc:
        message = f"Ekran görüntüsü alınamadı: {exc}"
        raise ScreenCaptureError(message) from exc
