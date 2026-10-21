
import re
from dataclasses import dataclass, field

import pymupdf


GROUP_RE = re.compile(r"^Group\s*(\d+)$")


@dataclass
class VocabEntry:
    term: str
    definition: str
    page: int


@dataclass
class VocabGroup:
    number: int
    entries: list[VocabEntry] = field(default_factory=list)


def _is_bold(span) -> bool:
    font_name = span["font"].lower()

    return (
        bool(span["flags"] & 16)
        or any(
            word in font_name
            for word in ("bold", "black", "heavy")
        )
    )


def parse_vocab_pdf(path: str) -> list[VocabGroup]:
    groups: list[VocabGroup] = []
    current_group = None
    current_entry = None
    saw_bold_headword = False

    with pymupdf.open(path) as doc:
        if doc.needs_pass:
            raise ValueError("The PDF is password-protected.")

        for page_no, page in enumerate(doc, start=1):
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                for line in block.get("lines", []):
                    spans = [
                        span
                        for span in line["spans"]
                        if span["text"].strip()
                    ]

                    if not spans:
                        continue

                    text = " ".join(
                        span["text"].strip()
                        for span in spans
                    )

                    all_bold = all(
                        _is_bold(span) for span in spans
                    )

                    # Detect group headings.
                    match = GROUP_RE.fullmatch(text)

                    if match and all_bold:
                        current_group = VocabGroup(
                            number=int(match.group(1))
                        )
                        groups.append(current_group)
                        current_entry = None
                        continue

                    # Ignore text before the first group.
                    if current_group is None:
                        continue

                    if all_bold:
                        # A bold line starts a new vocabulary word.
                        current_entry = VocabEntry(
                            term=text,
                            definition="",
                            page=page_no,
                        )
                        current_group.entries.append(current_entry)
                        saw_bold_headword = True

                    elif current_entry is not None:
                        # Append definition text, including
                        # definitions continuing onto another line.
                        current_entry.definition = (
                            current_entry.definition + " " + text
                        ).strip()

    if not saw_bold_headword:
        raise ValueError(
            "No bold headwords found. "
            "Check the PDF formatting."
        )

    # Remove entries without definitions.
    for group in groups:
        group.entries = [
            entry
            for entry in group.entries
            if entry.term.strip() and entry.definition.strip()
        ]

    # Return only groups that contain valid entries.
    return [
        group for group in groups
        if group.entries
    ]
