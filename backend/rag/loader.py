import io
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from langchain_docling import DoclingLoader
from langchain_docling.loader import ExportType
from pypdf import PdfReader

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}
MAX_TEXT_BLOCK_CHARS = 3000


class UnsupportedFileError(ValueError):
    pass


class EmptyDocumentError(ValueError):
    pass


@dataclass(frozen=True)
class PageText:
    page: int | None
    text: str
    element_type: str = "text"
    metadata: dict[str, str | int] | None = None


def _clean(text: str) -> str:
    return text.replace("\x00", "").replace("\r\n", "\n").strip()


def _is_table(block: str) -> bool:
    lines = [l for l in block.splitlines() if l.strip()]
    return len(lines) >= 2 and "|" in lines[0] and "|" in lines[1]


def _detect_element_type(text: str) -> str:
    stripped = text.strip()
    if _is_table(stripped):
        return "table"
    if stripped.startswith("#"):
        return "heading"
    if stripped.startswith(("-", "*")):
        return "list"
    return "text"


def _markdown_to_elements(markdown: str, base_metadata: dict) -> list[PageText]:
    """Split a whole-document markdown string into tables and text groups."""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", markdown) if b.strip()]
    elements: list[PageText] = []
    buffer: list[str] = []
    size = 0

    def flush() -> None:
        nonlocal buffer, size
        if buffer:
            elements.append(
                PageText(
                    page=None,
                    text="\n\n".join(buffer),
                    element_type="text",
                    metadata=base_metadata,
                )
            )
        buffer, size = [], 0

    for block in blocks:
        if _is_table(block):
            flush()
            elements.append(
                PageText(
                    page=None,
                    text=block,
                    element_type="table",
                    metadata=base_metadata,
                )
            )
            continue
        if size + len(block) > MAX_TEXT_BLOCK_CHARS:
            flush()
        buffer.append(block)
        size += len(block)
    flush()
    return elements


def _read_pdf_docling(filename: str, data: bytes) -> list[PageText]:
    temp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_file.write(data)
            temp_path = temp_file.name

        loader = DoclingLoader(file_path=temp_path, export_type=ExportType.MARKDOWN)
        documents = loader.load()

        pages: list[PageText] = []
        for document in documents:
            text = _clean(document.page_content)
            if not text:
                continue
            metadata = {
                str(k): v
                for k, v in (document.metadata or {}).items()
                if isinstance(v, (str, int)) and str(k) != "source"
            }
            pages.extend(_markdown_to_elements(text, metadata))
        return pages

    except Exception as exc:
        raise UnsupportedFileError(
            f"Could not read PDF with Docling: {filename}"
        ) from exc
    finally:
        if temp_path:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except Exception:
                pass


def _read_pdf_pypdf(data: bytes) -> list[PageText]:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise UnsupportedFileError("This PDF is password protected")

        pages: list[PageText] = []
        for number, page in enumerate(reader.pages, start=1):
            text = _clean(page.extract_text() or "")
            if text:
                pages.append(
                    PageText(page=number, text=text, element_type="text", metadata={})
                )
        return pages
    except UnsupportedFileError:
        raise
    except Exception as exc:
        raise UnsupportedFileError("Could not read this PDF") from exc


def _read_pdf(filename: str, data: bytes) -> list[PageText]:
    try:
        pages = _read_pdf_docling(filename, data)
        if pages:
            return pages
    except UnsupportedFileError:
        pass
    return _read_pdf_pypdf(data)


def _read_text(data: bytes) -> list[PageText]:
    text = _clean(data.decode("utf-8", errors="replace"))
    if not text:
        return []
    return [PageText(page=None, text=text, element_type="text", metadata={})]


def extract_pages(filename: str, data: bytes) -> list[PageText]:
    extension = Path(filename).suffix.lower()
    if extension == ".pdf":
        pages = _read_pdf(filename, data)
    elif extension in {".txt", ".md"}:
        pages = _read_text(data)
    else:
        raise UnsupportedFileError(f"Unsupported file type: {extension or 'unknown'}")

    if not pages:
        raise EmptyDocumentError(
            "No text could be extracted. This may be a scanned/image-only PDF and may require OCR."
        )
    return pages
