"""Shared helpers: configuration, validation, filename safety, temp storage."""

from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
import time
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

TEMPLATE_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
SPREADSHEET_EXTENSIONS = {".xlsx", ".csv"}

# Magic byte signatures used to confirm a file really is what its name claims.
_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    ".pdf": (b"%PDF-",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".xlsx": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
}

# Messages from the specification's error table.
MSG_NO_TEMPLATE = "Please upload a certificate template."
MSG_BAD_TEMPLATE = "Unsupported template format. Please upload PDF, PNG, JPG, or JPEG."
MSG_NO_NAMES = "Please enter at least one name."
MSG_EMPTY_SHEET = "No valid names were found in the uploaded file."
MSG_BAD_SHEET = (
    "Unable to read the uploaded Excel file. Please check the file and try again."
)
MSG_GENERATION_FAILED = (
    "Something went wrong while generating the certificates. Please try again."
)
MSG_TEMPLATE_TOO_LARGE = "The certificate template is too large."
MSG_OUTPUT_TOO_LARGE = (
    "This request would produce too much data to download at once. "
    "Please use fewer names, a smaller template, or choose the merged PDF option."
)
MSG_SHEET_TOO_LARGE = "The uploaded Excel/CSV file is too large."
MSG_TOO_MANY_NAMES = "Too many names in one request."
MSG_BAD_FILE = "The uploaded file appears to be corrupted or is not a valid file."
MSG_BAD_REQUEST = "The request was not valid. Please check the form and try again."


class AppError(Exception):
    """An error that is safe to show to the user verbatim."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("Ignoring non-integer value for %s: %r", name, raw)
        return default
    return value if value > 0 else default


DEFAULT_CORS_ORIGINS: tuple[str, ...] = (
    "https://certificate-generator-three-theta.vercel.app",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
)


@dataclass(frozen=True)
class Settings:
    max_template_bytes: int
    max_spreadsheet_bytes: int
    max_names: int
    max_name_length: int
    max_total_output_bytes: int
    preview_dpi: int
    preview_max_pixels: int
    temp_root: Path
    temp_ttl_seconds: int
    cors_origins: tuple[str, ...]
    cors_origin_regex: str | None
    api_key: str | None
    rate_limit_generation: str | None


def load_settings() -> Settings:
    origins = list(DEFAULT_CORS_ORIGINS)
    origins_env = os.getenv("CORS_ORIGINS", "").strip()
    if origins_env == "*":
        logger.warning(
            "CORS_ORIGINS=* is ignored: credentials require an explicit "
            "allowlist. Use CORS_ORIGIN_REGEX for dynamic hosts."
        )
    elif origins_env:
        for origin in origins_env.split(","):
            cleaned = origin.strip()
            if cleaned and cleaned not in origins:
                origins.append(cleaned)
    cors_origin_regex = os.getenv("CORS_ORIGIN_REGEX", "").strip() or None
    api_key = os.getenv("API_KEY", "").strip() or None
    rate_limit_generation = os.getenv("RATE_LIMIT_GENERATION", "").strip() or None
    return Settings(
        max_template_bytes=_env_int("MAX_TEMPLATE_SIZE_MB", 25) * 1024 * 1024,
        max_spreadsheet_bytes=_env_int("MAX_SPREADSHEET_SIZE_MB", 10) * 1024 * 1024,
        max_names=_env_int("MAX_NAMES", 2000),
        max_name_length=_env_int("MAX_NAME_LENGTH", 120),
        max_total_output_bytes=_env_int("MAX_TOTAL_OUTPUT_MB", 1024) * 1024 * 1024,
        preview_dpi=_env_int("PREVIEW_DPI", 110),
        preview_max_pixels=_env_int("PREVIEW_MAX_PIXELS", 1600),
        temp_root=Path(
            os.getenv(
                "TEMP_ROOT",
                str(Path(__file__).resolve().parents[2] / "temporary"),
            )
        ),
        temp_ttl_seconds=_env_int("TEMP_TTL_SECONDS", 6 * 60 * 60),
        cors_origins=tuple(origins),
        cors_origin_regex=cors_origin_regex,
        api_key=api_key,
        rate_limit_generation=rate_limit_generation,
    )



settings = load_settings()


def extension_of(filename: str | None) -> str:
    if not filename or "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[1].strip().lower()


def validate_upload(
    filename: str | None,
    data: bytes,
    *,
    allowed: set[str],
    max_bytes: int,
    too_large_message: str,
    unsupported_message: str,
) -> str:
    """Validate size, extension and file signature. Returns the extension."""
    ext = extension_of(filename)
    if ext not in allowed:
        raise AppError(unsupported_message)
    if not data:
        raise AppError(MSG_BAD_FILE)
    if len(data) > max_bytes:
        raise AppError(too_large_message, status_code=413)
    signatures = _SIGNATURES.get(ext)
    if not signatures:
        return ext
    for signature in signatures:
        if data.startswith(signature):
            return ext
    raise AppError(MSG_BAD_FILE)


def validate_template_upload(filename: str | None, data: bytes) -> str:
    return validate_upload(
        filename,
        data,
        allowed=TEMPLATE_EXTENSIONS,
        max_bytes=settings.max_template_bytes,
        too_large_message=MSG_TEMPLATE_TOO_LARGE,
        unsupported_message=MSG_BAD_TEMPLATE,
    )


def validate_spreadsheet_upload(filename: str | None, data: bytes) -> str:
    ext = validate_upload(
        filename,
        data,
        allowed=SPREADSHEET_EXTENSIONS,
        max_bytes=settings.max_spreadsheet_bytes,
        too_large_message=MSG_SHEET_TOO_LARGE,
        unsupported_message=(
            "Unsupported file format. Please upload an .xlsx or .csv file."
        ),
    )
    return ext


def clean_name(value: object, max_length: int | None = None) -> str:
    """Normalise a single name coming from a spreadsheet or a text area."""
    limit = max_length or settings.max_name_length
    if value is None:
        return ""
    text = str(value)
    # Drop characters pandas uses for missing values.
    if text.strip().lower() in {"nan", "none", "null", "nat"}:
        return ""
    text = text.replace("\xa0", " ")
    text = " ".join(text.split())
    text = unicodedata.normalize("NFC", text)
    if len(text) > limit:
        text = text[:limit].rstrip()
    return text


def dedupe_names(names: list[str]) -> list[str]:
    """Remove repeats while preserving order (duplicates are not an error)."""
    seen: set[str] = set()
    result: list[str] = []
    for name in names:
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(name)
    return result


def parse_name_payload(raw: str) -> list[str]:
    """Accept a JSON array, or plain newline separated text."""
    import json

    text = (raw or "").strip()
    if not text:
        return []
    values: list[object] = []
    if text[0] in "[\"":
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            raise AppError(MSG_NO_NAMES) from None
        if isinstance(decoded, list):
            values = decoded
        elif isinstance(decoded, str):
            values = decoded.splitlines()
        else:
            raise AppError(MSG_NO_NAMES)
    else:
        values = text.splitlines()
    names = [clean_name(value) for value in values]
    return [name for name in names if name]


def enforce_name_limit(names: list[str]) -> list[str]:
    if len(names) > settings.max_names:
        raise AppError(MSG_TOO_MANY_NAMES, status_code=413)
    return names


_FILENAME_ALLOWED = set(" _.-")
_REPEATED_SEPARATORS = re.compile(r"[ _.\-]{2,}")


def safe_filename(name: str) -> str:
    """Turn a user supplied name into a safe file name stem (never a path).

    Letters and digits of any script are kept; everything else (including path
    separators) is dropped.
    """
    kept = [char for char in name if char.isalnum() or char in _FILENAME_ALLOWED]
    stem = _REPEATED_SEPARATORS.sub("_", "".join(kept)).strip(" ._-")
    if not stem:
        stem = "unnamed"
    return stem[:80].rstrip(" ._-") or "unnamed"


def certificate_filename(name: str, extension: str = ".pdf") -> str:
    return f"certificate_{safe_filename(name).replace(' ', '_')}{extension}"


def unique_path(directory: Path, filename: str) -> Path:
    """Return a path inside ``directory`` that does not exist yet."""
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem, ext = os.path.splitext(filename)
    for index in range(2, 10_000):
        candidate = directory / f"{stem}_{index}{ext}"
        if not candidate.exists():
            return candidate
    raise AppError(MSG_GENERATION_FAILED, status_code=500)


@contextmanager
def request_workspace() -> Iterator[Path]:
    """Per-request scratch directory. Always removed, success or failure."""
    workspace = create_workspace()
    try:
        yield workspace
    finally:
        shutil.rmtree(workspace, ignore_errors=True)



def create_workspace() -> Path:
    """Create a per-request scratch directory (caller removes it when done)."""
    root = settings.temp_root
    try:
        root.mkdir(parents=True, exist_ok=True)
        workspace = Path(tempfile.mkdtemp(prefix="req-", dir=root))
    except OSError:
        logger.exception("Could not create a temporary workspace")
        raise AppError(MSG_GENERATION_FAILED, status_code=500) from None
    (workspace / "output").mkdir(exist_ok=True)
    return workspace


def purge_stale_temp_files(now: float | None = None) -> int:
    """Delete leftover workspaces (for example after an unclean shutdown)."""
    root = settings.temp_root
    if not root.exists():
        return 0
    cutoff = (now or time.time()) - settings.temp_ttl_seconds
    removed = 0
    for entry in root.glob("req-*"):
        try:
            if entry.stat().st_mtime < cutoff:
                shutil.rmtree(entry, ignore_errors=True)
                removed += 1
        except OSError:
            continue
    return removed
