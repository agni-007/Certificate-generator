"""Complex-script (Indic) rendering tests.

Correct shaping is verified against Pillow's Raqm/HarfBuzz layout engine: the
HTML-box render must match the shaped reference far better than the unshaped
("basic") reference, proving conjuncts and vowel signs are joined.
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pymupdf
import pytest
from PIL import Image, ImageDraw, ImageFont, features

from app.generator import build_style, render_certificate
from app.indic import (
    FONT_DIR,
    SCRIPT_FONTS,
    bundled_font,
    detect_script,
    font_archive,
    rgb_from_floats,
)

SAMPLES = {
    "malayalam": ("നന്ദി", "NotoSansMalayalam-Regular.ttf"),
    "tamil": ("க்ஷ", "NotoSansTamil-Regular.ttf"),
    "hindi": ("हिन्दी", "NotoSansDevanagari-Regular.ttf"),
}

_RAQM = features.check("raqm")


def _blank_template(width: float = 595.28, height: float = 841.89) -> pymupdf.Document:
    document = pymupdf.open()
    document.new_page(width=width, height=height)
    return document


def _certificate_png(name: str, size: float) -> np.ndarray:
    template = _blank_template()
    style = build_style(50, 50, "times-italic", size, "#000000", "center")
    try:
        data = render_certificate(template, name, style)
    finally:
        template.close()
    document = pymupdf.open(stream=data, filetype="pdf")
    try:
        pixmap = document[0].get_pixmap(dpi=72, alpha=False)
        image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    finally:
        document.close()
    return _ink_mask(image)


def _ink_mask(image: Image.Image) -> np.ndarray:
    return np.array(image.convert("L")) < 200


def _bbox(mask: np.ndarray):
    ys, xs = np.where(mask)
    if not len(xs):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def _iou(first: np.ndarray, second: np.ndarray) -> float:
    a = _bbox(first)
    b = _bbox(second)
    if a is None or b is None:
        return 0.0
    crop_a = first[a[1] : a[3] + 1, a[0] : a[2] + 1]
    crop_b = second[b[1] : b[3] + 1, b[0] : b[2] + 1]
    resized = (
        np.array(
            Image.fromarray((crop_b * 255).astype(np.uint8)).resize(
                (crop_a.shape[1], crop_a.shape[0])
            )
        )
        > 128
    )
    union = (resized | crop_a).sum()
    return float((resized & crop_a).sum() / union) if union else 0.0


def _pillow_reference(font_path: Path, text: str, size: int, layout) -> np.ndarray:
    font = ImageFont.truetype(str(font_path), size, layout_engine=layout)
    image = Image.new("L", (size * len(text) + 200, size * 3), 255)
    ImageDraw.Draw(image).text((80, 80), text, font=font, fill=0)
    return _ink_mask(image)


class TestScriptDetection:
    def test_detects_indic_scripts(self):
        assert detect_script("മലയാളം") == "malayalam"
        assert detect_script("தமிழ்") == "tamil"
        assert detect_script("हिन्दी") == "devanagari"

    def test_latin_and_mixed(self):
        assert detect_script("Agnivesh S") is None
        assert detect_script("രാജു Raju") == "malayalam"

    @pytest.mark.parametrize("script", sorted(SCRIPT_FONTS))
    def test_fonts_are_bundled(self, script):
        assert bundled_font(script) is not None

    def test_ofl_licence_is_bundled(self):
        licence = (FONT_DIR / "OFL.txt").read_text(encoding="utf-8")
        assert "SIL OPEN FONT LICENSE" in licence

    def test_rgb_from_floats(self):
        assert rgb_from_floats((0.0, 0.0, 0.0)) == "rgb(0, 0, 0)"
        assert rgb_from_floats((1.0, 1.0, 1.0)) == "rgb(255, 255, 255)"

    def test_archive_lists_fonts(self):
        assert font_archive().has_entry("NotoSansMalayalam-Regular.ttf")


class TestIndicRendering:
    @pytest.mark.parametrize("script", sorted(SAMPLES))
    def test_indic_name_inserts_bundled_font(self, script):
        text, _font = SAMPLES[script]
        template = _blank_template()
        style = build_style(50, 50, "times-italic", 48, "#000000", "center")
        try:
            data = render_certificate(template, text, style)
        finally:
            template.close()
        document = pymupdf.open(stream=data, filetype="pdf")
        try:
            fonts = {entry[3] for entry in document.get_page_fonts(0)}
        finally:
            document.close()
        assert any("Noto Sans" in name for name in fonts), fonts

    @pytest.mark.skipif(not _RAQM, reason="Pillow was not built with Raqm")
    @pytest.mark.parametrize("script", sorted(SAMPLES))
    def test_shaping_matches_harfbuzz_reference(self, script):
        text, font_name = SAMPLES[script]
        size = 54
        actual = _certificate_png(text, size)
        font_path = FONT_DIR / font_name
        shaped = _pillow_reference(
            font_path, text, size, ImageFont.Layout.RAQM
        )
        unshaped = _pillow_reference(
            font_path, text, size, ImageFont.Layout.BASIC
        )
        shaped_score = _iou(actual, shaped)
        unshaped_score = _iou(actual, unshaped)
        assert shaped_score > 0.75, (script, shaped_score, unshaped_score)
        assert shaped_score > unshaped_score + 0.2, (script, shaped_score, unshaped_score)

    def test_latin_output_uses_standard_fonts(self):
        template = _blank_template()
        style = build_style(50, 50, "times-italic", 37, "#000000", "center")
        try:
            data = render_certificate(template, "Agnivesh S", style)
        finally:
            template.close()
        document = pymupdf.open(stream=data, filetype="pdf")
        try:
            text = document[0].get_text()
            fonts = {entry[3] for entry in document.get_page_fonts(0)}
        finally:
            document.close()
        assert "Agnivesh S" in text
        assert "Times-Italic" in fonts


class TestIndicThroughApi:
    def test_generate_indic_names(self, client, pdf_template):
        import json

        names = ["നന്ദി", "தமிழ்", "हिन्दी"]
        response = client.post(
            "/api/generate",
            data={"names": json.dumps(names), "x": "50", "y": "50", "font": "times-italic"},
            files={"template": ("c.pdf", pdf_template, "application/pdf")},
        )
        assert response.status_code == 200, response.text
        import zipfile

        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            assert archive.testzip() is None
            assert len(archive.namelist()) == len(names)
