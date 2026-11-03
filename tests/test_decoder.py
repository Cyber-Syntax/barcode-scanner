import pytest
from barcode import EAN13, Code128
from barcode.writer import ImageWriter
from barcode_scanner.decoder import (
    BarcodeResult,
    ImageLoadError,
    decode_barcodes,
    first_code128,
    load_image,
    sort_results,
)
from PIL import Image


def _stack(*imgs: Image.Image) -> Image.Image:
    w = max(i.width for i in imgs)
    h = sum(i.height for i in imgs) + 40 * (len(imgs) + 1)
    canvas = Image.new("RGB", (w + 80, h), "white")
    y = 40
    for i in imgs:
        canvas.paste(i, (40, y))
        y += i.height + 40
    return canvas


def test_multiple_barcodes():
    a = EAN13("590123412345", writer=ImageWriter()).render()
    b = Code128("123456789012", writer=ImageWriter()).render()
    found = {(r.symbology, r.value) for r in decode_barcodes(_stack(a, b))}
    assert ("EAN-13", "5901234123457") in found
    assert ("Code 128", "123456789012") in found


def test_no_barcode():
    assert decode_barcodes(Image.new("RGB", (400, 300), "white")) == []


def test_invalid_file(tmp_path):
    p = tmp_path / "bad.png"
    p.write_text("not an image")
    with pytest.raises(ImageLoadError):
        load_image(p)


def test_unsupported_extension(tmp_path):
    p = tmp_path / "x.gif"
    p.write_bytes(b"GIF89a")
    with pytest.raises(ImageLoadError):
        load_image(p)


def test_visual_order_uses_decoder_order_for_position_ties():
    results = [
        BarcodeResult("Code 128", "tie-first", (10, 20, 5, 5)),
        BarcodeResult("Code 128", "lower", (5, 30, 5, 5)),
        BarcodeResult("Code 128", "tie-second", (10, 20, 5, 5)),
        BarcodeResult("EAN-13", "upper", (5, 10, 5, 5)),
    ]

    assert [r.value for r in sort_results(results)] == [
        "upper", "tie-first", "tie-second", "lower"
    ]


def test_first_code128_follows_visual_order_and_preserves_no_match_policy():
    results = [
        BarcodeResult("Code 128", "right", (80, 10, 5, 5)),
        BarcodeResult("EAN-13", "left", (10, 10, 5, 5)),
        BarcodeResult("Code 128", "top", (5, 5, 5, 5)),
    ]

    assert first_code128(results).value == "top"
    assert first_code128([results[1]]) is None
