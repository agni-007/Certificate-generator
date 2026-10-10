"""Certificate generation: template loading, text placement, PDF output, ZIP.

The PyMuPDF approach is inherited from the original ``script.py``: open the
template once, copy it per name with ``insert_pdf`` and draw the name with
``insert_text``. What changed is that everything (template, names, position,
font, colour, alignment) is supplied per request instead of hard coded.
"""

from __future__ import annotations

import io
import logging
import zipfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Sequence

import pymupdf
from PIL import Image, UnidentifiedImageError

from .utils import (
    AppError,
    IMAGE_EXTENSIONS,
    MSG_BAD_FILE,
    MSG_BAD_TEMPLATE,
    MSG_GENERATION_FAILED,
    MSG_NO_TEMPLATE,
    certificate_filename,
    extension_of,
    settings,
    unique_path,
)

logger = logging.getLogger(__name__)

# The 14 standard PDF fonts. No font files needed, so no extra dependency.
FONTS: dict[str, str] = {
    "times": "Times-Roman",
    "times-italic": "Times-Italic",
    "times-bold": "Times-Bold",
    "times-bolditalic": "Times-BoldItalic",
    "helvetica": "Helvetica",
    "helvetica-bold": "Helvetica-Bold",
    "helvetica-oblique": "Helvetica-Oblique",
    "helvetica-boldoblique": "Helvetica-BoldOblique",
    "courier": "Courier",
    "courier-bold": "Courier-Bold",
    "courier-oblique": "Courier-Oblique",
    "courier-boldoblique": "Courier-BoldOblique",
}
DEFAULT_FONT = "times-italic"

ALIGNMENTS = {"left", "center", "right"}
DEFAULT_ALIGNMENT = "center"

# Fallback TrueType fonts, used only when a name cannot be encoded with the
# standard fonts (for example Devanagari, Tamil or Chinese characters).
_FALLBACK_FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "C:/Windows/Fonts/arial.ttf",
)
_fallback_font_cache: str | None | bool = False

# A4 in PostScript points, used to keep image templates at a sane page size.
A4_WIDTH = 595.28
A4_HEIGHT = 841.89
DEFAULT_IMAGE_DPI = 300.0
MIN_IMAGE_DPI = 72.0
MAX_IMAGE_DPI = 600.0

# Image templates are downscaled/recompressed once so a single template is not
# copied at full resolution into every generated PDF.
MAX_IMAGE_DIMENSION = 3508  # long side cap, roughly A4 at 300 DPI
IMAGE_RECOMPRESS_QUALITY = 80
IMAGE_KEEP_ORIGINAL_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class TextStyle:
    x: float  # percentage 0-100, the alignment anchor
    y: float  # percentage 0-100, vertical centre of the text line
    font: str
    font_size: float
    color: tuple[float, float, float]
    alignment: str


def normalize_color(value: str | None) -> tuple[float, float, float]:
    """Accept ``#fff``, ``#ffffff`` or ``rgb(255, 255, 255)``."""
    text = (value or "").strip().lower()
    if text.startswith("rgb"):
        parts = text[text.find("(") + 1 : text.rfind(")")].split(",")
        if len(parts) == 3:
            try:
                return tuple(max(0.0, min(1.0, float(p) / 255)) for p in parts)  # type: ignore[return-value]
            except ValueError:
                pass
        raise AppError("Invalid text colour. Please choose a colour.")
    text = text.lstrip("#")
    if len(text) == 3:
        text = "".join(char * 2 for char in text)
    if len(text) != 6:
        raise AppError("Invalid text colour. Please choose a colour.")
    try:
        channels = [int(text[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    except ValueError:
        raise AppError("Invalid text colour. Please choose a colour.") from None
    return (channels[0], channels[1], channels[2])


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def build_style(
    x: float,
    y: float,
    font: str,
    font_size: float,
    color: str | None,
    alignment: str,
) -> TextStyle:
    font_key = (font or DEFAULT_FONT).strip().lower()
    if font_key not in FONTS:
        raise AppError("Unsupported font. Please choose one of the listed fonts.")
    align_key = (alignment or DEFAULT_ALIGNMENT).strip().lower()
    if align_key not in ALIGNMENTS:
        raise AppError("Unsupported alignment. Use left, center or right.")
    try:
        size = float(font_size)
    except (TypeError, ValueError):
        raise AppError("Invalid font size.") from None
    return TextStyle(
        x=_clamp(float(x), 0.0, 100.0),
        y=_clamp(float(y), 0.0, 100.0),
        font=font_key,
        font_size=_clamp(size, 6.0, 200.0),
        color=normalize_color(color),
        alignment=align_key,
    )


@lru_cache(maxsize=4)
def _unicode_font(fontfile: str) -> pymupdf.Font:
    return pymupdf.Font(fontfile=fontfile)


def fallback_font_file() -> str | None:
    """Path of a Unicode capable TTF, or ``None`` when none is installed."""
    global _fallback_font_cache
    if _fallback_font_cache is False:
        for path in _FALLBACK_FONTS:
            if Path(path).is_file():
                _fallback_font_cache = path
                break
        else:
            logger.warning("No Unicode fallback font found on this system.")
            _fallback_font_cache = None
    return _fallback_font_cache  # type: ignore[return-value]


def _image_dpi(image: Image.Image) -> float:
    info = image.info.get("dpi")
    if isinstance(info, (tuple, list)) and info:
        try:
            candidate = float(info[0])
        except (TypeError, ValueError):
            candidate = 0.0
        if candidate > 0:
            return _clamp(candidate, MIN_IMAGE_DPI, MAX_IMAGE_DPI)
    return DEFAULT_IMAGE_DPI


def _should_recompress(image: Image.Image, original_bytes: int) -> bool:
    """True when an image template is large enough to be worth shrinking."""
    return (
        max(image.size) > MAX_IMAGE_DIMENSION
        or original_bytes > IMAGE_KEEP_ORIGINAL_BYTES
    )


def image_to_pdf(data: bytes) -> pymupdf.Document:
    """Convert a PNG/JPG/JPEG into a one page PDF, keeping its aspect ratio.

    Large image templates are downscaled (long side capped at
    ``MAX_IMAGE_DIMENSION``) and recompressed once here, so the resulting PDF
    stays small and every generated certificate shares the same compact copy.
    """
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError, ValueError):
        raise AppError(MSG_BAD_FILE) from None

    with image:
        if image.mode in {"RGBA", "LA", "P", "PA"}:
            background = Image.new("RGB", image.size, (255, 255, 255))
            converted = image.convert("RGBA")
            background.paste(converted, mask=converted.split()[-1])
            image = background
        elif image.mode != "RGB":
            image = image.convert("RGB")

        dpi = _image_dpi(image)
        width_px, height_px = image.size
        # Shrink (never enlarge) the page so it fits inside A4.
        page_width = width_px * 72.0 / dpi
        page_height = height_px * 72.0 / dpi
        fit = min(1.0, A4_WIDTH / page_width, A4_HEIGHT / page_height)
        if fit < 1.0:
            dpi = dpi / fit

        save_kwargs: dict[str, object] = {}
        if _should_recompress(image, len(data)):
            scale = min(1.0, MAX_IMAGE_DIMENSION / max(width_px, height_px))
            if scale < 1.0:
                new_size = (
                    max(1, round(width_px * scale)),
                    max(1, round(height_px * scale)),
                )
                image = image.resize(new_size, Image.LANCZOS)
                # Keep the physical page size the same after downscaling.
                dpi = dpi * scale
            save_kwargs["quality"] = IMAGE_RECOMPRESS_QUALITY

        buffer = io.BytesIO()
        image.save(buffer, format="PDF", resolution=dpi, **save_kwargs)
        buffer.seek(0)

    return pymupdf.open(stream=buffer.read(), filetype="pdf")


def load_template(data: bytes, filename: str) -> pymupdf.Document:
    """Open a PDF template, or turn an image template into a PDF page."""
    if not data:
        raise AppError(MSG_NO_TEMPLATE)
    extension = extension_of(filename)
    if extension not in {".pdf", *IMAGE_EXTENSIONS}:
        raise AppError(MSG_BAD_TEMPLATE)

    try:
        if extension in IMAGE_EXTENSIONS:
            return image_to_pdf(data)
        document = pymupdf.open(stream=data, filetype="pdf")
    except AppError:
        raise
    except Exception as error:  # noqa: BLE001 - corrupt upload
        logger.warning("Could not open template %r: %s", filename, error)
        raise AppError(MSG_BAD_FILE) from None

    if document.page_count < 1:
        document.close()
        raise AppError(MSG_BAD_FILE)
    return document


def _text_width(
    text: str, style: TextStyle, fontname: str, fontfile: str | None
) -> float:
    try:
        if fontfile:
            return _unicode_font(fontfile).text_length(
                text, fontsize=style.font_size
            )
        return pymupdf.get_text_length(text, fontname=fontname, fontsize=style.font_size)
    except Exception:  # noqa: BLE001 - fall back to an average width estimate
        logger.warning("Could not measure text, using an estimate for %r", fontname)
        return len(text) * style.font_size * 0.5


def _write_name(
    page: pymupdf.Page,
    name: str,
    style: TextStyle,
    *,
    fontfile: str | None = None,
) -> None:
    """Draw one name at the configured normalised position."""
    fontname = FONTS[style.font]
    width = _text_width(name, style, fontname, fontfile)
    anchor_x = page.rect.width * (style.x / 100.0)
    if style.alignment == "center":
        start_x = anchor_x - (width / 2)
    elif style.alignment == "right":
        start_x = anchor_x - width
    else:
        start_x = anchor_x
    # The stored Y is the vertical centre of the line; the baseline sits
    # roughly one third of a font size below it (same as the original script).
    center_y = page.rect.height * (style.y / 100.0)
    baseline_y = center_y + (style.font_size / 3)

    insert_kwargs = {
        "fontsize": style.font_size,
        "fontname": fontname,
        "color": style.color,
        "render_mode": 0,
    }
    if fontfile:
        insert_kwargs["fontfile"] = fontfile
    try:
        page.insert_text(
            (max(0.0, start_x), max(0.0, baseline_y)), name, **insert_kwargs
        )
    except Exception as error:  # noqa: BLE001
        logger.warning("Could not render name %r: %s", name, error)
        raise AppError(MSG_GENERATION_FAILED, status_code=500) from None


def _needs_unicode_font(name: str) -> bool:
    try:
        name.encode("latin-1")
    except UnicodeEncodeError:
        return True
    return False


def render_certificate(
    template: pymupdf.Document, name: str, style: TextStyle
) -> bytes:
    """Return the bytes of one personalised certificate."""
    document = pymupdf.open()
    try:
        document.insert_pdf(template)
        page = document[0]
        fontfile = None
        if _needs_unicode_font(name):
            fontfile = fallback_font_file()
            if fontfile is None:
                raise AppError(
                    "This name uses characters that cannot be rendered on this "
                    "server. Please use a Latin or English name.",
                    status_code=400,
                )
        _write_name(page, name, style, fontfile=fontfile)
        data = document.tobytes(garbage=0, deflate=True)
    finally:
        document.close()
    return data


def generate_pdfs(
    template: pymupdf.Document,
    names: Sequence[str],
    style: TextStyle,
    output_dir: Path,
) -> list[Path]:
    """Write one PDF per name into ``output_dir``."""
    written: list[Path] = []
    for name in names:
        try:
            data = render_certificate(template, name, style)
        except AppError:
            raise
        except Exception as error:  # noqa: BLE001
            logger.exception("Generation failed for %r: %s", name, error)
            raise AppError(MSG_GENERATION_FAILED, status_code=500) from None
        path = unique_path(output_dir, certificate_filename(name))
        path.write_bytes(data)
        written.append(path)
    return written


def generate_merged_pdf(
    template: pymupdf.Document,
    names: Sequence[str],
    style: TextStyle,
    output_path: Path,
) -> Path:
    """Write every certificate into one multi-page PDF.

    The template is imported once per name but identical objects (notably the
    background image) are stored only once thanks to ``garbage=4`` dedup, so a
    50-name run produces roughly one template + 50 text layers instead of 50
    full copies.
    """
    if not names:
        raise AppError(MSG_GENERATION_FAILED, status_code=500)
    document = pymupdf.open()
    try:
        for name in names:
            try:
                document.insert_pdf(template)
                page = document[-1]
                fontfile = None
                if _needs_unicode_font(name):
                    fontfile = fallback_font_file()
                    if fontfile is None:
                        raise AppError(
                            "This name uses characters that cannot be rendered on "
                            "this server. Please use a Latin or English name.",
                            status_code=400,
                        )
                _write_name(page, name, style, fontfile=fontfile)
            except AppError:
                raise
            except Exception as error:  # noqa: BLE001
                logger.exception("Generation failed for %r: %s", name, error)
                raise AppError(MSG_GENERATION_FAILED, status_code=500) from None
        data = document.tobytes(garbage=4, deflate=True)
    finally:
        document.close()
    output_path.write_bytes(data)
    return output_path


def estimate_output_bytes(template_bytes: int, name_count: int) -> int:
    """Rough pre-flight size estimate: one template copy per name."""
    return max(0, int(template_bytes)) * max(0, int(name_count))


def build_zip(files: Sequence[Path], zip_path: Path) -> Path:
    """Package the generated PDFs into ``certificates/certificates.zip``."""
    if not files:
        raise AppError(MSG_GENERATION_FAILED, status_code=500)
    try:
        with zipfile.ZipFile(
            zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
        ) as archive:
            for path in files:
                archive.write(path, arcname=f"certificates/{path.name}")
    except OSError as error:
        logger.exception("Could not create ZIP: %s", error)
        raise AppError(MSG_GENERATION_FAILED, status_code=500) from None
    return zip_path


def _rasterise(document: pymupdf.Document) -> tuple[bytes, float, float]:
    """Rasterise page 1 to PNG. Returns (png_bytes, page_width_pt, page_height_pt)."""
    page = document[0]
    target_dpi = settings.preview_dpi
    width_pt = page.rect.width
    height_pt = page.rect.height
    if width_pt > 0 and (width_pt * target_dpi / 72.0) > settings.preview_max_pixels:
        target_dpi = settings.preview_max_pixels * 72.0 / width_pt
    scale = target_dpi / 72.0
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
    return pixmap.tobytes("png"), width_pt, height_pt


def render_preview_png(document: pymupdf.Document) -> bytes:
    """Rasterise page 1 of the template exactly as it will be printed."""
    try:
        png, _, _ = _rasterise(document)
        return png
    except AppError:
        raise
    except Exception as error:  # noqa: BLE001
        logger.warning("Could not render preview: %s", error)
        raise AppError(MSG_BAD_FILE) from None


def render_certificate_png(template: pymupdf.Document, name: str, style: TextStyle) -> tuple[bytes, float, float]:
    """Generate one personalised certificate and return it as a PNG.

    This is the pixel-exact equivalent of what the user will get in the downloaded
    PDF — rendered at the same DPI used for the blank template preview so the
    browser can display both at the same canvas size.
    """
    try:
        cert_bytes = render_certificate(template, name, style)
        cert_doc = pymupdf.open(stream=cert_bytes, filetype="pdf")
        try:
            png, width_pt, height_pt = _rasterise(cert_doc)
        finally:
            cert_doc.close()
        return png, width_pt, height_pt
    except AppError:
        raise
    except Exception as error:  # noqa: BLE001
        logger.warning("Could not render certificate preview: %s", error)
        raise AppError(MSG_GENERATION_FAILED, status_code=500) from None
