"""End-to-end API tests covering the full matrix from the specification."""

from __future__ import annotations

import io
import json
import zipfile

import pandas as pd
import pymupdf
import pytest

from app.utils import settings
from conftest import NAMES, make_csv, make_xlsx
from app.generator import FONTS


def generate(client, template_file, names=NAMES, **overrides):
    fields = {
        "names": json.dumps(names) if isinstance(names, list) else names,
        "x": "50",
        "y": "52",
        "font": "times-italic",
        "fontSize": "37",
        "color": "#ffffff",
        "alignment": "center",
    }
    fields.update({key: str(value) for key, value in overrides.items()})
    return client.post(
        "/api/generate", data=fields, files={"template": template_file}
    )


def read_zip(response) -> tuple[list[str], dict[str, str]]:
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = archive.namelist()
        assert archive.testzip() is None
        contents = {name: archive.read(name) for name in names}
    return names, contents


def text_of(pdf_bytes: bytes) -> str:
    document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        return "".join(page.get_text() for page in document)
    finally:
        document.close()


class TestHealth:
    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_options(self, client):
        body = client.get("/api/options").json()
        assert body["defaultFont"] in FONTS
        assert body["defaultAlignment"] == "center"
        assert set(body["alignments"]) == {"left", "center", "right"}


class TestNameExtraction:
    def test_xlsx_with_name_column(self, client):
        response = client.post(
            "/api/names",
            files={"file": ("names.xlsx", make_xlsx(NAMES), "application/vnd.ms-excel")},
        )
        assert response.status_code == 200
        assert response.json()["names"] == NAMES

    def test_xlsx_case_insensitive_column(self, client):
        response = client.post(
            "/api/names",
            files={"file": ("n.xlsx", make_xlsx(NAMES, "NAME"), "application/vnd.ms-excel")},
        )
        assert response.json()["names"] == NAMES

    def test_xlsx_without_name_column_uses_first(self, client):
        response = client.post(
            "/api/names",
            files={"file": ("n.xlsx", make_xlsx(NAMES, "Participant"), "application/vnd.ms-excel")},
        )
        assert response.json()["names"] == NAMES

    def test_csv(self, client):
        response = client.post(
            "/api/names", files={"file": ("n.csv", make_csv(NAMES), "text/csv")}
        )
        assert response.json()["names"] == NAMES

    def test_excel_ignores_blank_rows_and_trims(self, client):
        buffer = io.BytesIO()
        pd.DataFrame({"Name": ["  Agnivesh S  ", "", None, "Rahul Kumar", "  "]}).to_excel(
            buffer, index=False
        )
        response = client.post(
            "/api/names", files={"file": ("n.xlsx", buffer.getvalue(), "x")}
        )
        assert response.json()["names"] == ["Agnivesh S", "Rahul Kumar"]

    def test_duplicate_names_are_removed(self, client):
        response = client.post(
            "/api/names", files={"file": ("n.csv", make_csv(["A", "A", "B"]), "text/csv")}
        )
        assert response.json()["names"] == ["A", "B"]

    def test_empty_excel_message(self, client):
        buffer = io.BytesIO()
        pd.DataFrame({"Name": []}).to_excel(buffer, index=False)
        response = client.post(
            "/api/names", files={"file": ("n.xlsx", buffer.getvalue(), "x")}
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "No valid names were found in the uploaded file."

    def test_invalid_excel_message(self, client):
        # A real workbook signature with broken content inside.
        response = client.post(
            "/api/names", files={"file": ("bad.xlsx", b"PK\x03\x04 not a workbook", "x")}
        )
        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Unable to read the uploaded Excel file. Please check the file and try again."
        )

    def test_not_a_workbook_at_all(self, client):
        response = client.post(
            "/api/names", files={"file": ("bad.xlsx", b"this is not a workbook", "x")}
        )
        assert response.status_code == 400
        assert response.json()["detail"] == (
            "The uploaded file appears to be corrupted or is not a valid file."
        )

    def test_unsupported_spreadsheet_extension(self, client):
        response = client.post(
            "/api/names", files={"file": ("bad.docx", b"whatever", "x")}
        )
        assert response.status_code == 400

    def test_no_file(self, client):
        response = client.post("/api/names", files={})
        assert response.status_code == 400
        assert "upload" in response.json()["detail"].lower()


class TestPreview:
    @pytest.mark.parametrize("kind", ["pdf", "png", "jpg"])
    def test_preview_returns_png(self, client, templates, kind):
        response = client.post("/api/preview", files={"template": templates[kind]})
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content.startswith(b"\x89PNG")

    @pytest.mark.parametrize("kind", ["pdf", "png", "jpg"])
    def test_preview_reports_page_size_in_points(self, client, templates, kind):
        response = client.post("/api/preview", files={"template": templates[kind]})
        assert response.status_code == 200
        width = float(response.headers["x-page-width"])
        height = float(response.headers["x-page-height"])
        assert width > 0
        assert height > 0
        # The PNG must match the reported page box.
        pixmap = pymupdf.Pixmap(io.BytesIO(response.content))
        assert pixmap.width / pixmap.height == pytest.approx(width / height, rel=0.02)

    @pytest.mark.parametrize(
        "filename", ["t.png", "t.jpg", "t.jpeg"], ids=["png", "jpg", "jpeg"]
    )
    def test_preview_preserves_aspect_ratio(
        self, client, png_template, jpg_template, filename
    ):
        data = jpg_template if filename != "t.png" else png_template
        response = client.post(
            "/api/preview",
            files={"template": (filename, data, "image/" + filename[2:])},
        )
        assert response.status_code == 200
        pixmap = pymupdf.Pixmap(io.BytesIO(response.content))
        document = _as_pdf_document(data)
        page = document[0]
        assert pixmap.width / pixmap.height == pytest.approx(
            page.rect.width / page.rect.height, rel=0.02
        )
        document.close()

    def test_preview_rejects_bad_format(self, client):
        response = client.post(
            "/api/preview", files={"template": ("t.gif", b"GIF89a", "image/gif")}
        )
        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Unsupported template format. Please upload PDF, PNG, JPG, or JPEG."
        )

    def test_preview_rejects_corrupt_pdf(self, client):
        response = client.post(
            "/api/preview", files={"template": ("t.pdf", b"%PDF-1.4 broken", "application/pdf")}
        )
        assert response.status_code == 400

    def test_preview_requires_template(self, client):
        response = client.post("/api/preview", files={})
        assert response.json()["detail"] == "Please upload a certificate template."


def _as_pdf_document(image_bytes: bytes):
    from app.generator import image_to_pdf

    return image_to_pdf(image_bytes)


class TestGeneration:
    @pytest.mark.parametrize("kind", ["pdf", "png", "jpg"])
    @pytest.mark.parametrize(
        "names_source", ["manual", "xlsx", "csv"], ids=["manual", "xlsx", "csv"]
    )
    def test_full_matrix(self, client, templates, kind, names_source):
        names = NAMES
        if names_source == "xlsx":
            extracted = client.post(
                "/api/names", files={"file": ("n.xlsx", make_xlsx(NAMES), "x")}
            ).json()["names"]
            names = extracted
        elif names_source == "csv":
            names = client.post(
                "/api/names", files={"file": ("n.csv", make_csv(NAMES), "text/csv")}
            ).json()["names"]

        response = generate(client, templates[kind], names=names)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        assert "certificates.zip" in response.headers["content-disposition"]

        entries, contents = read_zip(response)
        assert len(entries) == len(NAMES)
        assert all(entry.startswith("certificates/certificate_") for entry in entries)
        assert sorted(entries) == sorted(
            [
                "certificates/certificate_Ananya_Menon.pdf",
                "certificates/certificate_Agnivesh_S.pdf",
                "certificates/certificate_Arjun_Raj.pdf",
                "certificates/certificate_Rahul_Kumar.pdf",
            ]
        )
        # every PDF must contain exactly one of the requested names
        for entry, pdf_bytes in contents.items():
            text = text_of(pdf_bytes)
            if kind == "pdf":
                assert "CERTIFICATE" in text  # real text from the template
            matched = [name for name in NAMES if name in text]
            assert len(matched) == 1, f"{entry} contains {matched}"


    def test_newline_separated_names_accepted(self, client, templates):
        response = generate(client, templates["pdf"], names="\n".join(NAMES))
        entries, _ = read_zip(response)
        assert len(entries) == len(NAMES)

    def test_alignment_and_position(self, client, templates):
        response = generate(
            client,
            templates["pdf"],
            names=["Rahul Kumar"],
            x=20,
            y=30,
            alignment="left",
            color="#ff0000",
            fontSize=48,
        )
        _, contents = read_zip(response)
        document = pymupdf.open(stream=next(iter(contents.values())), filetype="pdf")
        page = document[0]
        rect = page.search_for("Rahul Kumar")[0]
        assert rect.x0 == pytest.approx(page.rect.width * 0.20, abs=6)
        spans = [
            span
            for block in page.get_text("dict")["blocks"]
            for line in block.get("lines", [])
            for span in line["spans"]
        ]
        name_spans = [span for span in spans if "Rahul Kumar" in span["text"]]
        assert name_spans, spans
        assert name_spans[0]["color"] & 0xFFFFFF == 0xFF0000
        assert name_spans[0]["size"] == pytest.approx(48, abs=0.6)
        # The baseline is the vertical centre of the line plus one third of a
        # font size, matching the original script.
        expected_baseline = page.rect.height * 0.30 + (48 / 3)
        assert name_spans[0]["origin"][1] == pytest.approx(expected_baseline, abs=0.6)
        document.close()

    def test_right_alignment(self, client, templates):
        response = generate(
            client, templates["pdf"], names=["Rahul Kumar"], x=80, alignment="right"
        )
        _, contents = read_zip(response)
        document = pymupdf.open(stream=next(iter(contents.values())), filetype="pdf")
        page = document[0]
        rect = page.search_for("Rahul Kumar")[0]
        assert rect.x1 == pytest.approx(page.rect.width * 0.80, abs=6)
        document.close()

    @pytest.mark.parametrize("font", sorted(FONTS))
    def test_every_font_renders(self, client, templates, font):
        response = generate(client, templates["pdf"], names=["Agnivesh S"], font=font)
        _, contents = read_zip(response)
        assert "Agnivesh S" in text_of(next(iter(contents.values())))

    def test_preserves_template_page_size(self, client, templates):
        response = generate(client, templates["pdf"], names=["Agnivesh S"])
        _, contents = read_zip(response)
        document = pymupdf.open(stream=next(iter(contents.values())), filetype="pdf")
        assert document.page_count == 1
        assert document[0].rect.width == pytest.approx(595.28, abs=1)
        assert document[0].rect.height == pytest.approx(841.89, abs=1)
        document.close()

    def test_image_template_page_is_not_stretched(self, client, templates):
        response = generate(client, templates["png"], names=["Agnivesh S"])
        _, contents = read_zip(response)
        document = pymupdf.open(stream=next(iter(contents.values())), filetype="pdf")
        page = document[0]
        assert page.rect.width / page.rect.height == pytest.approx(1754 / 2480, rel=0.01)
        assert page.rect.width <= 595.3 and page.rect.height <= 842.0
        document.close()

    def test_special_characters_and_long_names(self, client, templates):
        names = [
            "Ananya Menon",
            "Dr. Rajesh K. Sharma (Jr.)",
            "José Álvarez",
            "A" * settings.max_name_length,
            "Name/With\\Backslash",
            "  spaced  out  ",
        ]
        response = generate(client, templates["pdf"], names=names)
        entries, contents = read_zip(response)
        assert len(entries) == len(names)
        assert all(not entry.startswith("certificates/..") for entry in entries)
        assert "José Álvarez" in text_of(
            contents["certificates/certificate_José_Álvarez.pdf"]
        )

    def test_duplicate_names_get_unique_files(self, client, templates):
        response = client.post(
            "/api/generate",
            data={"names": json.dumps(["A", "A"]), "x": 50, "y": 50},
            files={"template": templates["pdf"]},
        )
        entries, _ = read_zip(response)
        assert len(entries) == 2
        assert len(set(entries)) == 2

    def test_bulk_500_names(self, client, templates):
        names = [f"Participant {index:04d}" for index in range(500)]
        response = generate(client, templates["pdf"], names=names)
        assert response.status_code == 200
        entries, _ = read_zip(response)
        assert len(entries) == 500


class TestGenerationErrors:
    def test_no_template(self, client):
        response = client.post("/api/generate", data={"names": json.dumps(NAMES)})
        assert response.status_code == 400
        assert response.json()["detail"] == "Please upload a certificate template."

    def test_no_names(self, client, templates):
        response = generate(client, templates["pdf"], names=[])
        assert response.status_code == 400
        assert response.json()["detail"] == "Please enter at least one name."

    def test_blank_names_only(self, client, templates):
        response = generate(client, templates["pdf"], names=["  ", "", "\n\n"])
        assert response.json()["detail"] == "Please enter at least one name."

    def test_unsupported_template(self, client):
        response = generate(
            client, ("t.gif", b"GIF89a" + b"\x00" * 32, "image/gif"), names=NAMES
        )
        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Unsupported template format. Please upload PDF, PNG, JPG, or JPEG."
        )

    def test_renamed_but_wrong_content(self, client):
        response = generate(client, ("t.pdf", b"not a pdf at all", "application/pdf"))
        assert response.status_code == 400

    def test_too_many_names(self, client, templates):
        names = [f"Name {index}" for index in range(settings.max_names + 1)]
        response = generate(client, templates["pdf"], names=names)
        assert response.status_code == 413
        assert response.json()["detail"] == "Too many names in one request."

    def test_oversized_template(self, client, templates):
        filename, data, content_type = templates["pdf"]
        padded = data + b"\n%" + b"0" * (settings.max_template_bytes + 10)
        response = generate(client, (filename, padded, content_type))
        assert response.status_code == 413

    def test_invalid_font(self, client, templates):
        response = generate(client, templates["pdf"], names=NAMES, font="comic-sans")
        assert response.status_code == 400
        assert "font" in response.json()["detail"].lower()

    def test_invalid_color(self, client, templates):
        response = generate(client, templates["pdf"], names=NAMES, color="not-a-color")
        assert response.status_code == 400

    def test_invalid_alignment(self, client, templates):
        response = generate(client, templates["pdf"], names=NAMES, alignment="justify")
        assert response.status_code == 400

    def test_no_stack_traces_leak(self, client):
        response = generate(client, ("t.pdf", b"%PDF-1.4 broken", "application/pdf"))
        assert "Traceback" not in response.text
        assert "pymupdf" not in response.text.lower()


class TestTempFiles:
    def test_temporary_files_are_cleaned(self, client, templates):
        before = set(settings.temp_root.glob("req-*")) if settings.temp_root.exists() else set()
        response = generate(client, templates["pdf"])
        assert response.status_code == 200
        after = set(settings.temp_root.glob("req-*")) if settings.temp_root.exists() else set()
        assert after == before
