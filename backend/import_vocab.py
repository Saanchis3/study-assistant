
import sys
from collections import defaultdict
from pathlib import Path

from app.db import Base, SessionLocal, engine
from app.models import Card, Chunk, Document
from app.services.quality_checks import flag_document
from app.services.vocab_parser import parse_vocab_pdf


def main():
    if len(sys.argv) < 2:
        print("Usage: python import_vocab.py PDF_PATH [--apply]")
        return

    path = Path(sys.argv[1])

    if not path.is_file():
        print(f"Error: PDF not found: {path}")
        return

    try:
        groups = parse_vocab_pdf(str(path))
    except Exception as error:
        print(
            f"Error parsing PDF: {type(error).__name__}: {error}"
        )
        return

    # Remove empty groups.
    groups = [group for group in groups if group.entries]
    total = sum(len(group.entries) for group in groups)

    # Find duplicate definitions for manual review.
    seen = defaultdict(list)

    for group in groups:
        for entry in group.entries:
            definition = entry.definition.strip().casefold()

            if definition:
                seen[definition].append(
                    (group.number, entry.term)
                )

    for definition, owners in seen.items():
        if len(owners) > 1:
            print(
                "DUPLICATE DEFINITION:",
                owners,
                "->",
                definition,
            )

    print(f"\n{len(groups)} groups, {total} entries.")

    # Preview mode: do not write to the database.
    if "--apply" not in sys.argv:
        print("Preview only. Nothing was saved.")
        return

    # Create tables if necessary.
    Base.metadata.create_all(engine)
    db = SessionLocal()

    try:
        # Prevent importing the same filename twice.
        existing = (
            db.query(Document)
            .filter(Document.filename == path.name)
            .first()
        )

        if existing:
            print(
                f"Error: '{path.name}' is already imported as "
                f"document {existing.id}. Delete it first if you "
                "want to re-import."
            )
            return

        # Create the document record.
        document = Document(
            filename=path.name,
            status="done",
            total_chunks=len(groups),
            processed_chunks=len(groups),
        )
        db.add(document)
        db.flush()

        # Create one chunk per vocabulary group.
        for index, group in enumerate(groups):
            chunk = Chunk(
                document_id=document.id,
                chunk_index=index,
                text="\n".join(
                    f"{entry.term} {entry.definition}"
                    for entry in group.entries
                ),
                page_start=min(
                    entry.page for entry in group.entries
                ),
                page_end=max(
                    entry.page for entry in group.entries
                ),
                char_start=0,
                char_end=0,
            )
            db.add(chunk)
            db.flush()

            # Create one flashcard per vocabulary entry.
            for entry in group.entries:
                card = Card(
                    chunk_id=chunk.id,
                    question=f"What does '{entry.term}' mean?",
                    answer=entry.definition,
                    card_type="definition",
                    source_quote=f"{entry.term} {entry.definition}",
                    prompt_version="rules-v1",
                )
                db.add(card)

                db.commit()
        print(f"Successfully saved document {document.id}")

        # Run quality checks on the new cards (writes only the flags column)
        flagged = flag_document(db, document.id)
        print(f"{flagged} card(s) flagged for review.")

    except Exception as error:
        db.rollback()
        print(
            f"Error saving vocabulary: "
            f"{type(error).__name__}: {error}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()
