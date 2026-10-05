import sys
from pathlib import Path

from app.services.parsing import parse_file, ParsingError

path = Path(sys.argv[1])

try:
    pages = parse_file(path)
except ParsingError as e:
    print("ERROR:", e)
    sys.exit(1)

print(f"Found {len(pages)} page(s)\n")

for page in pages[:3]:
    print(f"--- Page {page.page_number} ({len(page.text)} characters) ---")
    print(page.text[:500])
    print()