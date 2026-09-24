"""Turns uploaded bytes into (page, text) pairs. PDF, TXT and Markdown."""
import io
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}


class UnsupportedFileError(ValueError):
    pass


class EmptyDocumentError(ValueError):
    pass


@dataclass(frozen=True)
class PageText:
    page: int | None
    text: str


def _clean(text: str) -> str:
    return text.replace("\x00", "").strip()


def _read_pdf(data: bytes) -> list[PageText]:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise UnsupportedFileError("This PDF is password protected")

        pages: list[PageText] = []
        for number, page in enumerate(reader.pages, start=1):
            text = _clean(page.extract_text() or "")
            if text:
                pages.append(PageText(number, text))
        return pages
    except UnsupportedFileError:
        raise
    except Exception as exc:
        raise UnsupportedFileError("Could not read this PDF") from exc


def _read_text(data: bytes) -> list[PageText]:
    text = _clean(data.decode("utf-8", errors="replace"))
    return [PageText(None, text)] if text else []


def extract_pages(filename: str, data: bytes) -> list[PageText]:
    extension = Path(filename).suffix.lower()

    if extension == ".pdf":
        pages = _read_pdf(data)
    elif extension in {".txt", ".md"}:
        pages = _read_text(data)
    else:
        raise UnsupportedFileError(f"Unsupported file type: {extension or 'unknown'}")

    if not pages:
        raise EmptyDocumentError(
            "No text could be extracted. Scanned/image-only PDFs need OCR, "
            "which is not supported yet."
        )
    return pages
