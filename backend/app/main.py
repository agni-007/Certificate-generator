"""FastAPI application: template preview, name extraction, bulk generation."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from .generator import (
    ALIGNMENTS,
    DEFAULT_ALIGNMENT,
    DEFAULT_FONT,
    FONTS,
    build_style,
    build_zip,
    generate_pdfs,
    load_template,
    render_certificate_png,
    render_preview_png,
)
from .parser import extract_names_from_file
from .utils import (
    AppError,
    MSG_GENERATION_FAILED,
    MSG_NO_NAMES,
    MSG_BAD_REQUEST,
    MSG_NO_TEMPLATE,
    enforce_name_limit,
    parse_name_payload,
    purge_stale_temp_files,
    request_workspace,
    settings,
    validate_spreadsheet_upload,
    validate_template_upload,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("certificate_generator")

FONT_LABELS = {
    "times-italic": "Times Italic",
    "times": "Times Roman",
    "times-bold": "Times Bold",
    "times-bolditalic": "Times Bold Italic",
    "helvetica": "Helvetica",
    "helvetica-bold": "Helvetica Bold",
    "helvetica-oblique": "Helvetica Oblique",
    "helvetica-boldoblique": "Helvetica Bold Oblique",
    "courier": "Courier",
    "courier-bold": "Courier Bold",
    "courier-oblique": "Courier Oblique",
    "courier-boldoblique": "Courier Bold Oblique",
}


ZIP_FILENAME = "certificates.zip"
UPLOAD_CHUNK = 1024 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    removed = purge_stale_temp_files()
    if removed:
        logger.info("Removed %s stale temporary workspace(s)", removed)
    settings.temp_root.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="Certificate Generator API",
    version="1.0.0",
    description="Bulk personalised certificate generation from a template and a list of names.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Certificate-Count"],
)


@app.exception_handler(AppError)
async def app_error_handler(request, exc: AppError):  # noqa: ARG001
    return JSONResponse(
        status_code=exc.status_code, content={"detail": exc.message}
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    logger.info("Rejected malformed request: %s", exc.errors()[:3])
    return JSONResponse(status_code=400, content={"detail": MSG_BAD_REQUEST})


@app.exception_handler(Exception)
async def unhandled_error_handler(request, exc: Exception):  # noqa: ARG001
    # Technical detail stays in the logs; the user gets a friendly message.
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(status_code=500, content={"detail": MSG_GENERATION_FAILED})


async def read_upload(upload: UploadFile | None, max_bytes: int) -> bytes:
    if upload is None or not upload.filename:
        return b""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(UPLOAD_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise AppError("The uploaded file is too large.", status_code=413)
        chunks.append(chunk)
    await upload.close()
    return b"".join(chunks)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/options")
async def options() -> dict[str, object]:
    """Font / alignment choices and limits, so the UI never hard codes them."""
    return {
        "fonts": [{"value": key, "label": label} for key, label in FONT_LABELS.items()],
        "defaultFont": DEFAULT_FONT,
        "alignments": ["left", "center", "right"],
        "defaultAlignment": DEFAULT_ALIGNMENT,
        "maxNames": settings.max_names,
        "maxTemplateSizeMb": settings.max_template_bytes // (1024 * 1024),
        "maxSpreadsheetSizeMb": settings.max_spreadsheet_bytes // (1024 * 1024),
        "templateExtensions": [".pdf", ".png", ".jpg", ".jpeg"],
        "spreadsheetExtensions": [".xlsx", ".csv"],
    }


@app.post("/api/names")
async def extract_names(
    file: Annotated[UploadFile | None, File(description="An .xlsx or .csv file")] = None,
) -> dict[str, object]:
    if file is None:
        raise AppError("Please upload an Excel or CSV file.")
    data = await read_upload(file, settings.max_spreadsheet_bytes)
    if not data:
        raise AppError("Please upload an Excel or CSV file.")
    extension = validate_spreadsheet_upload(file.filename, data)
    names = extract_names_from_file(data, extension)
    logger.info("Extracted %s name(s) from %s", len(names), file.filename)
    return {"names": names, "count": len(names)}


@app.post("/api/preview")
async def preview(
    template: Annotated[
        UploadFile | None, File(description="A PDF, PNG, JPG or JPEG")
    ] = None,
) -> Response:
    """Render page 1 of the template to PNG so the UI can show it exactly."""
    if template is None:
        raise AppError(MSG_NO_TEMPLATE)
    data = await read_upload(template, settings.max_template_bytes)
    if not data:
        raise AppError(MSG_NO_TEMPLATE)
    extension = validate_template_upload(template.filename, data)
    document = load_template(data, template.filename)
    try:
        page = document[0]
        page_width = page.rect.width
        page_height = page.rect.height
        png = render_preview_png(document)
        logger.info(
            "Preview ready for %s (%s, %.0fx%.0f pt)",
            template.filename,
            extension,
            page_width,
            page_height,
        )
    finally:
        document.close()
    return Response(
        content=png,
        media_type="image/png",
        headers={
            "Cache-Control": "no-store",
            "X-Preview-Extension": extension,
            # Page box in PDF points, so the UI can scale point font sizes.
            "X-Page-Width": f"{page_width:.2f}",
            "X-Page-Height": f"{page_height:.2f}",
        },
    )

@app.post("/api/preview-certificate")
async def preview_certificate(
    template: Annotated[
        UploadFile | None, File(description="A PDF, PNG, JPG or JPEG")
    ] = None,
    name: Annotated[str, Form(description="Name to place on the certificate")] = "Sample Name",
    x: Annotated[float, Form()] = 50.0,
    y: Annotated[float, Form()] = 52.0,
    font: Annotated[str, Form()] = DEFAULT_FONT,
    fontSize: Annotated[float, Form()] = 37.0,
    color: Annotated[str, Form()] = "#ffffff",
    alignment: Annotated[str, Form()] = DEFAULT_ALIGNMENT,
) -> Response:
    """Render a single personalised certificate to PNG — pixel-exact preview."""
    if template is None:
        raise AppError(MSG_NO_TEMPLATE)
    data = await read_upload(template, settings.max_template_bytes)
    if not data:
        raise AppError(MSG_NO_TEMPLATE)
    validate_template_upload(template.filename, data)
    clean = (name or "Sample Name").strip() or "Sample Name"
    style = build_style(x, y, font, fontSize, color, alignment)
    document = load_template(data, template.filename)
    try:
        png, page_width, page_height = render_certificate_png(document, clean, style)
        logger.info("Certificate preview rendered for %r", clean)
    finally:
        document.close()
    return Response(
        content=png,
        media_type="image/png",
        headers={
            "Cache-Control": "no-store",
            "X-Page-Width": f"{page_width:.2f}",
            "X-Page-Height": f"{page_height:.2f}",
        },
    )


@app.post("/api/generate")
async def generate(
    template: Annotated[UploadFile | None, File(description="A PDF, PNG, JPG or JPEG")] = None,
    names: Annotated[str, Form(description="JSON array or newline separated text")] = "",
    x: Annotated[float, Form()] = 50.0,
    y: Annotated[float, Form()] = 52.0,
    font: Annotated[str, Form()] = DEFAULT_FONT,
    fontSize: Annotated[float, Form()] = 37.0,
    color: Annotated[str, Form()] = "#ffffff",
    alignment: Annotated[str, Form()] = DEFAULT_ALIGNMENT,
) -> Response:
    if not template or not template.filename:
        raise AppError(MSG_NO_TEMPLATE)

    name_list = enforce_name_limit(parse_name_payload(names))
    if not name_list:
        raise AppError(MSG_NO_NAMES)

    style = build_style(x, y, font, fontSize, color, alignment)

    data = await read_upload(template, settings.max_template_bytes)
    if not data:
        raise AppError(MSG_NO_TEMPLATE)
    validate_template_upload(template.filename, data)

    with request_workspace() as workspace:
        document = load_template(data, template.filename)
        try:
            files = generate_pdfs(document, name_list, style, workspace / "output")
        finally:
            document.close()
        zip_path = build_zip(files, workspace / "output" / ZIP_FILENAME)
        zip_bytes = zip_path.read_bytes()
        logger.info("Generated %s certificate(s) into a ZIP (%s bytes)", len(files), len(zip_bytes))

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{ZIP_FILENAME}"',
            "X-Certificate-Count": str(len(name_list)),
            "Cache-Control": "no-store",
        },
    )


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": "certificate-generator-api",
        "status": "ok",
        "docs": "/docs",
        "temporaryRoot": str(settings.temp_root),
        "tempExists": Path(settings.temp_root).is_dir(),
    }
