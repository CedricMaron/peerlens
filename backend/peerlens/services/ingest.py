"""Turning uploaded files into plain text the model can read.

The original file is always kept on disk untouched; extraction only produces a
readable rendering alongside it. Extraction never summarises or interprets --
that is the analysis step's job, and conflating them would lose information.
"""

from __future__ import annotations

import csv
import io
import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from ..config import UPLOAD_DIR

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".tex", ".csv", ".json"}

# Long documents are truncated only when handed to the model, never on disk.
MAX_CSV_ROWS = 400
MAX_TEXT_CHARS = 200_000


@dataclass
class ExtractionOutcome:
    text: str
    note: str


def is_supported(filename: str) -> bool:
    return Path(filename).suffix.lower() in SUPPORTED_EXTENSIONS


def store_upload(data: bytes, filename: str) -> Path:
    """Persist the original bytes under a collision-free name."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix.lower()
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]", "_", Path(filename).stem)[:80] or "upload"
    target = UPLOAD_DIR / f"{safe_stem}-{uuid.uuid4().hex[:8]}{suffix}"
    target.write_bytes(data)
    return target


def extract_text(data: bytes, filename: str) -> ExtractionOutcome:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(data)
    if suffix == ".csv":
        return _extract_csv(data)
    if suffix == ".json":
        return _extract_json(data)
    if suffix in (".txt", ".md", ".tex"):
        return _extract_plain(data, suffix)
    return ExtractionOutcome(
        text="",
        note=f"Unsupported file type '{suffix}'. The original file is stored but "
        "its content was not extracted.",
    )


def _decode(data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _truncate(text: str) -> tuple[str, str]:
    if len(text) <= MAX_TEXT_CHARS:
        return text, ""
    return (
        text[:MAX_TEXT_CHARS],
        f"Content truncated to {MAX_TEXT_CHARS:,} characters for analysis "
        f"(original is {len(text):,} characters and is preserved in full on disk).",
    )


def _extract_plain(data: bytes, suffix: str) -> ExtractionOutcome:
    text, note = _truncate(_decode(data))
    kind = {".txt": "Plain text", ".md": "Markdown", ".tex": "LaTeX"}[suffix]
    return ExtractionOutcome(text=text, note=note or f"{kind} read directly.")


def _extract_pdf(data: bytes) -> ExtractionOutcome:
    try:
        from pypdf import PdfReader
    except ImportError:  # pragma: no cover - dependency is declared
        return ExtractionOutcome(
            text="", note="PDF support requires the 'pypdf' package."
        )
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001 - malformed PDFs are user input
        return ExtractionOutcome(text="", note=f"Could not read PDF: {exc}")

    pages: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            content = page.extract_text() or ""
        except Exception:  # noqa: BLE001 - skip unreadable pages, keep the rest
            content = ""
        if content.strip():
            pages.append(f"--- page {index} ---\n{content.strip()}")

    if not pages:
        return ExtractionOutcome(
            text="",
            note=f"No extractable text in this PDF ({len(reader.pages)} pages). It is "
            "likely a scanned document; PeerLens does not perform OCR. Consider "
            "pasting the relevant text directly.",
        )

    text, truncation = _truncate("\n\n".join(pages))
    note = f"Extracted text from {len(pages)} of {len(reader.pages)} PDF pages."
    return ExtractionOutcome(text=text, note=f"{note} {truncation}".strip())


def _extract_csv(data: bytes) -> ExtractionOutcome:
    raw = _decode(data)
    try:
        dialect = csv.Sniffer().sniff(raw[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(raw), dialect))
    if not rows:
        return ExtractionOutcome(text="", note="CSV file is empty.")

    header, *body = rows
    shown = body[:MAX_CSV_ROWS]
    lines = [
        f"Tabular data: {len(body)} data rows, {len(header)} columns.",
        f"Columns: {', '.join(str(c) for c in header)}",
        "",
        "\t".join(str(c) for c in header),
    ]
    lines.extend("\t".join(str(cell) for cell in row) for row in shown)

    note = f"CSV parsed: {len(body)} rows x {len(header)} columns."
    if len(body) > len(shown):
        omitted = len(body) - len(shown)
        lines.append(f"... {omitted} further rows not shown ...")
        note += f" First {len(shown)} rows included for analysis."
    return ExtractionOutcome(text="\n".join(lines), note=note)


def _extract_json(data: bytes) -> ExtractionOutcome:
    raw = _decode(data)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        text, _ = _truncate(raw)
        return ExtractionOutcome(text=text, note=f"Invalid JSON ({exc}); stored as raw text.")
    pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
    text, truncation = _truncate(pretty)
    shape = type(parsed).__name__
    size = f", {len(parsed)} top-level entries" if isinstance(parsed, (list, dict)) else ""
    return ExtractionOutcome(
        text=text, note=f"JSON parsed ({shape}{size}). {truncation}".strip()
    )
