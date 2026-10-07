
import sys
from pathlib import Path

from app.services.parsing import parse_file, ParsingError
from app.services.chunking import chunk_pages

try:
    pages = parse_file(Path(sys.argv[1]))
except ParsingError as e:
    print("ERROR:", e)
    sys.exit(1)

chunks = chunk_pages(pages)
print(f"{len(pages)} page(s) -> {len(chunks)} chunk(s)\n")
for c in chunks:
    words = len(c.text.split())
    print(f"Chunk {c.chunk_index}: {words} words, pages {c.page_start}-{c.page_end}")
    print("   starts:", c.text[:80].replace("\n", " "))
    print("   ends:  ", c.text[-80:].replace("\n", " "))
