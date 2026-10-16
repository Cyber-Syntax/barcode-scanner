"""Barcode decoding. Deliberately free of any GUI imports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from pyzbar import pyzbar
from pyzbar.pyzbar import ZBarSymbol

SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp")

# 1D symbologies only (QR/PDF417 deliberately excluded).
_SYMBOLS = [
    ZBarSymbol.EAN13,
    ZBarSymbol.EAN8,
    ZBarSymbol.UPCA,
    ZBarSymbol.UPCE,
    ZBarSymbol.CODE128,
    ZBarSymbol.CODE39,
    ZBarSymbol.CODE93,
    ZBarSymbol.I25,
    ZBarSymbol.CODABAR,
    ZBarSymbol.DATABAR,
    ZBarSymbol.DATABAR_EXP,
]

_DISPLAY_NAMES = {
    "EAN13": "EAN-13",
    "EAN8": "EAN-8",
    "UPCA": "UPC-A",
    "UPCE": "UPC-E",
    "CODE128": "Code 128",
    "CODE39": "Code 39",
    "CODE93": "Code 93",
    "I25": "ITF",
    "CODABAR": "Codabar",
    "DATABAR": "DataBar",
    "DATABAR_EXP": "DataBar Expanded",
}

# ZBar can miss barcodes on large images; retry at other scales if needed.
_SCALES = (1.0, 0.5, 0.33, 2.0)


class ImageLoadError(Exception):
    """Raised when a file cannot be opened as a supported image."""


@dataclass(frozen=True)
class BarcodeResult:
    symbology: str  # display name, e.g. "EAN-13"
    value: str
    rect: tuple[int, int, int, int]  # left, top, width, height (original px)


def load_image(path: str | Path) -> Image.Image:
    path = Path(path)
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ImageLoadError(
            f"Unsupported file type '{path.suffix}'. "
            f"Use one of: {', '.join(SUPPORTED_EXTENSIONS)}."
        )
    try:
        with Image.open(path) as img:
            img.load()
            img = ImageOps.exif_transpose(img)  # honor phone-camera rotation
            return img.convert("RGB")
    except FileNotFoundError:
        raise ImageLoadError(f"File not found: {path.name}") from None
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ImageLoadError(
            f"Could not open '{path.name}' as an image ({exc})."
        ) from exc


def _decode_value(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def decode_barcodes(image: Image.Image) -> list[BarcodeResult]:
    """Decode all 1D barcodes in `image`.

    Pass 1 (native scale) keeps every detection, including repeated identical
    values at different positions. Later passes (other scales) only add
    (symbology, value) pairs not already found.
    """
    gray = image.convert("L")
    results: list[BarcodeResult] = []
    seen: set[tuple[str, str]] = set()

    for i, scale in enumerate(_SCALES):
        if scale == 2.0 and max(gray.size) > 1000:
            continue  # upscaling big images is pointless and slow
        if scale == 1.0:
            candidate = gray
        else:
            size = (max(1, int(gray.width * scale)), max(1, int(gray.height * scale)))
            candidate = gray.resize(size, Image.Resampling.LANCZOS)

        for d in pyzbar.decode(candidate, symbols=_SYMBOLS):
            sym = _DISPLAY_NAMES.get(d.type, d.type)
            value = _decode_value(d.data)
            key = (sym, value)
            if i == 0:
                is_new = True
            else:
                is_new = key not in seen
            if not is_new:
                continue
            seen.add(key)
            r = d.rect
            rect = tuple(int(v / scale) for v in (r.left, r.top, r.width, r.height))
            results.append(BarcodeResult(sym, value, rect))  # type: ignore[arg-type]

    results.sort(key=lambda r: (r.rect[1], r.rect[0]))  # top-to-bottom, left-to-right
    return results
