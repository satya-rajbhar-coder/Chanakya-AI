import io
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from docling.chunking import HybridChunker
from langchain_docling import DoclingLoader
from langchain_docling.loader import ExportType
from pypdf import PdfReader

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}
logger = logging.getLogger(__name__)


class UnsupportedFileError(ValueError):
    pass


class EmptyDocumentError(ValueError):
    pass


@dataclass(frozen=True)
class PageText:
    page: int | None
    text: str
    element_type: str = "text"
    metadata: dict[str, Any] | None = None


def _clean(text: str) -> str:
    return text.replace("\x00", "").replace("\r\n", "\n").strip()


def _read_pdf_docling(filename: str, data: bytes) -> list[PageText]:
    temp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".pdf",
            delete=False,
        ) as temp_file:
            temp_file.write(data)
            temp_path = temp_file.name

        # Heading-aware, token-aware chunking
        chunker = HybridChunker(
            max_tokens=512,
            merge_peers=True,
        )

        loader = DoclingLoader(
            file_path=temp_path,
            export_type=ExportType.DOC_CHUNKS,
            chunker=chunker,
        )

        documents = loader.load()

        elements: list[PageText] = []

        for document in documents:
            text = _clean(document.page_content)
            if not text:
                continue

            metadata = document.metadata or {}
            dl_meta = metadata.get("dl_meta", {}) or {}

            headings = dl_meta.get("headings") or []
            captions = dl_meta.get("captions") or []

            # Extract page number when available
            page_number: int | None = None
            doc_items = dl_meta.get("doc_items", [])
            for item in doc_items:
                provenance = item.get("prov", [])
                if provenance:
                    page_number = provenance[0].get("page_no")
                    if page_number is not None:
                        break

            # Identify tables
            element_type = (
                "table"
                if any(
                    item.get("label") == "table"
                    for item in doc_items
                )
                else "text"
            )

            elements.append(
                PageText(
                    page=page_number,
                    text=text,
                    element_type=element_type,
                    metadata={
                        "headings": headings,
                        "captions": captions,
                        "source": filename,
                        "element_type": element_type,
                    },
                )
            )

        return elements

    except Exception as exc:
        raise UnsupportedFileError(
            f"Could not read PDF with Docling: {filename}"
        ) from exc
    finally:
        if temp_path:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except OSError:
                logger.debug("Could not delete temp file %s", temp_path)


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
