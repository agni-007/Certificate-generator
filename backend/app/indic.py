"""Complex-script (Indic) text rendering for certificates.

PyMuPDF's ``insert_text`` cannot shape complex scripts, so conjuncts and vowel
signs come out broken. ``Page.insert_htmlbox`` is HarfBuzz based and does shape
correctly. This module selects a bundled OFL Noto font per script and lays the
name out at the same anchor/alignment used by the standard-font path.

Fonts live in ``app/fonts`` and are licensed under the SIL Open Font License
(see ``app/fonts/OFL.txt``).
"""

from __future__ import annotations

import html
import logging
from functools import lru_cache
from pathlib import Path

import pymupdf

logger = logging.getLogger(__name__)

FONT_DIR = Path(__file__).resolve().parent / "fonts"

# script -> (font file name, CSS family name)
SCRIPT_FONTS: dict[str, tuple[str, str]] = {
    "devanagari": ("NotoSansDevanagari-Regular.ttf", "CertDevanagari"),
    "malayalam": ("NotoSansMalayalam-Regular.ttf", "CertMalayalam"),
    "tamil": ("NotoSansTamil-Regular.ttf", "CertTamil"),
}
LATIN_FONT = ("NotoSans-Regular.ttf", "CertLatin")

# Unicode blocks per script (including common extended ranges).
_SCRIPT_RANGES: dict[str, tuple[tuple[int, int], ...]] = {
    "devanagari": ((0x0900, 0x097F), (0xA8E0, 0xA8FF), (0x1CD0, 0x1CFF)),
    "malayalam": ((0x0D00, 0x0D7F),),
    "tamil": ((0x0B80, 0x0BFF),),
}


def detect_script(text: str) -> str | None:
    """Return the first supported Indic script found in ``text``, if any."""
    for char in text:
        codepoint = ord(char)
        for script, ranges in _SCRIPT_RANGES.items():
            if any(low <= codepoint <= high for low, high in ranges):
                return script
    return None


def bundled_font(script: str | None) -> tuple[str, str] | None:
    """Return ``(file_name, css_family)`` for a bundled script font."""
    if not script:
        return None
    entry = SCRIPT_FONTS.get(script)
    if not entry:
        return None
    file_name, family = entry
    if not (FONT_DIR / file_name).is_file():
        logger.warning("Bundled font missing for script %r: %s", script, file_name)
        return None
    return file_name, family


@lru_cache(maxsize=1)
def font_archive() -> pymupdf.Archive:
    return pymupdf.Archive(str(FONT_DIR))


def _css(samples: list[tuple[str, str]], *, font_size: float, color: str, alignment: str) -> str:
    faces = "\n".join(
        f"@font-face {{ font-family: {family}; src: url({file_name}); }}"
        for file_name, family in samples
    )
    families = ", ".join(family for _file_name, family in samples)
    return (
        f"{faces}\n"
        "* { margin: 0; padding: 0; }\n"
        f"body {{ font-family: {families}; font-size: {font_size}px;"
        f" color: {color}; }}\n"
        f"div {{ text-align: {alignment}; }}\n"
    )


def insert_shaped_text(
    page: pymupdf.Page,
    text: str,
    *,
    font_size: float,
    anchor_x: float,
    anchor_y: float,
    alignment: str,
    color: str,
) -> None:
    """Draw ``text`` on ``page`` using a HarfBuzz shaped HTML box."""
    script = detect_script(text)
    script_font = bundled_font(script)
    samples = ([script_font] if script_font else []) + [LATIN_FONT]

    box_width = page.rect.width
    if alignment == "right":
        left = anchor_x - box_width
    elif alignment == "center":
        left = anchor_x - (box_width / 2)
    else:
        left = anchor_x
    top = anchor_y - (font_size * 0.6)
    rect = pymupdf.Rect(left, top, left + box_width, top + (font_size * 2.0))

    css = _css(samples, font_size=font_size, color=color, alignment=alignment)
    markup = f"<div>{html.escape(text)}</div>"
    page.insert_htmlbox(rect, markup, css=css, archive=font_archive())


def rgb_from_floats(color: tuple[float, float, float]) -> str:
    red, green, blue = (max(0, min(255, round(channel * 255))) for channel in color)
    return f"rgb({red}, {green}, {blue})"
