"""Shared fixtures: sample templates and name files built on the fly."""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd
import pymupdf
import pytest
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402

NAMES = ["Agnivesh S", "Rahul Kumar", "Ananya Menon", "Arjun Raj"]


def make_pdf_template(width: float = 595.28, height: float = 841.89) -> bytes:
    """A4 page with a border, a title and a line where the name goes."""
    document = pymupdf.open()
    page = document.new_page(width=width, height=height)
    page.draw_rect(
        pymupdf.Rect(20, 20, width - 20, height - 20),
        color=(0.2, 0.2, 0.6),
        width=3,
    )
    page.insert_text((width / 2 - 90, 150), "CERTIFICATE", fontsize=36, fontname="Times-Bold")
    page.insert_text(
        (width / 2 - 120, 220),
        "This certificate is proudly presented to",
        fontsize=14,
        fontname="Times-Roman",
    )
    page.insert_text((width / 2 - 100, height - 90), "Authorised Signatory", fontsize=12)
    data = document.tobytes()
    document.close()
    return data


def make_image_template(fmt: str = "PNG", size: tuple[int, int] = (1754, 2480)) -> bytes:
    image = Image.new("RGB", size, (18, 42, 86))
    draw = ImageDraw.Draw(image)
    draw.rectangle([20, 20, size[0] - 20, size[1] - 20], outline=(240, 210, 120), width=12)
    draw.text((size[0] // 2 - 220, 250), "CERTIFICATE", fill=(255, 255, 255))
    buffer = io.BytesIO()
    image.save(buffer, format=fmt, dpi=(300, 300))
    return buffer.getvalue()


def make_xlsx(names: list[str], column: str = "Name") -> bytes:
    buffer = io.BytesIO()
    pd.DataFrame({column: names}).to_excel(buffer, index=False)
    return buffer.getvalue()


def make_csv(names: list[str], column: str = "Name") -> bytes:
    return ("\n".join([column, *names])).encode("utf-8")


@pytest.fixture(scope="session")
def pdf_template() -> bytes:
    return make_pdf_template()


@pytest.fixture(scope="session")
def png_template() -> bytes:
    return make_image_template("PNG")


@pytest.fixture(scope="session")
def jpg_template() -> bytes:
    return make_image_template("JPEG")


@pytest.fixture(scope="session")
def big_jpg_template() -> bytes:
    """A noisy JPEG large enough that copies would dominate the output."""
    import numpy as np

    rng = np.random.default_rng(2024)
    array = rng.integers(0, 256, (1600, 1200, 3), dtype=np.uint8)
    image = Image.fromarray(array, "RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=80, dpi=(300, 300))
    return buffer.getvalue()


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def templates(pdf_template: bytes, png_template: bytes, jpg_template: bytes) -> dict:
    return {
        "pdf": ("certificate.pdf", pdf_template, "application/pdf"),
        "png": ("certificate.png", png_template, "image/png"),
        "jpg": ("certificate.jpg", jpg_template, "image/jpeg"),
    }
