
import sys
from pathlib import Path

import pymupdf
from pypdf import PdfReader


def is_bold(span) -> bool:
    font_name = span["font"].lower()
    return (
        bool(span["flags"] & 16)
        or "bold" in font_name
        or "black" in font_name
        or "heavy" in font_name
    )


def main():
    if len(sys.argv) < 2:
        print("Usage: python try_pdf_methods.py PDF_PATH [PAGE_NUMBER]")
        return

    path = Path(sys.argv[1])

    try:
        page_no = int(sys.argv[2]) - 1 if len(sys.argv) > 2 else 0
    except ValueError:
        print("Error: Page number must be an integer.")
        return

    if not path.is_file():
        print(f"Error: PDF not found: {path}")
        return

    if page_no < 0:
        print("Error: Page number must be 1 or greater.")
        return

    try:
        reader = PdfReader(str(path))

        if reader.is_encrypted:
            print("Error: This PDF is password-protected.")
            return

        if page_no >= len(reader.pages):
            print(f"Error: PDF has only {len(reader.pages)} pages.")
            return

        print("===== pypdf (default) =====")
        print(reader.pages[page_no].extract_text() or "(No text found)")

        with pymupdf.open(str(path)) as doc:
            if doc.needs_pass:
                print("Error: This PDF is password-protected.")
                return

            page = doc[page_no]
            blocks = page.get_text("dict")["blocks"]

            print("\n===== PyMuPDF (plain) =====")
            print(page.get_text() or "(No text found)")

            print("\n===== PyMuPDF (bold words marked with **) =====")
            for block in blocks:
                for line in block.get("lines", []):
                    parts = []
                    for span in line["spans"]:
                        text = span["text"].strip()
                        if not text:
                            continue
                        parts.append(
                            f"**{text}**" if is_bold(span) else text
                        )
                    if parts:
                        print(" ".join(parts))

            print("\n===== Fonts used on this page =====")
            seen = {}

            for block in blocks:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        if not span["text"].strip():
                            continue

                        key = (
                            span["font"],
                            round(span["size"], 1),
                            span["flags"],
                            span["color"],
                        )
                        seen.setdefault(key, span["text"].strip())

            for (font, size, flags, color), example in seen.items():
                print(
                    f"font={font} size={size} flags={flags} "
                    f"color={color} e.g. '{example}'"
                )

    except Exception as e:
        print(
            f"Error: Could not read the PDF "
            f"({type(e).__name__}): {e}"
        )


if __name__ == "__main__":
    main()
