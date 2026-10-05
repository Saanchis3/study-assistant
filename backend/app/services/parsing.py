from dataclasses import dataclass
from pathlib import Path
from docx import Document
from pypdf import PdfReader
class ParsingError(Exception):
    """Raised when a file can't be read, with a message safe to show the user."""
@dataclass
class PageText:
    page_number: int
    text: str
def parse_pdf(path: Path) -> list[PageText]:
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            raise ParsingError("This PDF is password-protected.")
        pages = []
        for number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(PageText(page_number=number, text=text))
    except ParsingError:
        raise
    except Exception as e:
        raise ParsingError(f"Could not read this PDF: {e}")
    if not pages:
        raise ParsingError(
            "No text found. This looks like a scanned PDF (images only). "
            "Try a version with selectable text."
        )

    return pages


def parse_docx(path: Path) -> list[PageText]:
    try:
        doc = Document(str(path))
    except Exception as e:
        raise ParsingError(f"Could not read this Word file: {e}")

    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

    if not paragraphs:
        raise ParsingError("This Word file has no text.")

    # Word files don't have fixed pages, so treat the whole file as page 1
    return [PageText(page_number=1, text="\n\n".join(paragraphs))]


def parse_txt(path: Path) -> list[PageText]:
    text = path.read_text(encoding="utf-8", errors="replace").strip()

    if not text:
        raise ParsingError("This text file is empty.")

    return [PageText(page_number=1, text=text)]


def parse_file(path: Path) -> list[PageText]:
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return parse_pdf(path)

    if suffix == ".docx":
        return parse_docx(path)

    if suffix in (".txt", ".md"):
        return parse_txt(path)

    raise ParsingError(f"Unsupported file type: {suffix}")    
            