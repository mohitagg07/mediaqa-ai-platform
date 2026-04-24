import fitz  # PyMuPDF
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_path: str) -> Optional[str]:
    """
    Extract full text from a PDF file using PyMuPDF.
    Returns concatenated text from all pages.
    """
    try:
        doc = fitz.open(file_path)
        text_parts = []

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text("text")
            if text.strip():
                text_parts.append(f"[Page {page_num + 1}]\n{text.strip()}")

        doc.close()
        full_text = "\n\n".join(text_parts)
        logger.info(f"Extracted {len(full_text)} chars from PDF: {file_path}")
        return full_text if full_text.strip() else None

    except Exception as e:
        logger.error(f"PDF extraction failed for {file_path}: {e}")
        raise RuntimeError(f"Failed to extract PDF text: {str(e)}")


def extract_metadata_from_pdf(file_path: str) -> dict:
    """Extract metadata from a PDF file."""
    try:
        doc = fitz.open(file_path)
        meta = doc.metadata or {}
        page_count = len(doc)
        doc.close()
        return {
            "title": meta.get("title", ""),
            "author": meta.get("author", ""),
            "page_count": page_count,
        }
    except Exception as e:
        logger.error(f"PDF metadata extraction failed: {e}")
        return {}
