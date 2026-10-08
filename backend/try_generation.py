import sys
from pathlib import Path

from app.services.parsing import parse_file, ParsingError
from app.services.chunking import chunk_pages
from app.services.card_generation import generate_cards, CardGenerationError


try:
    pages = parse_file(Path(sys.argv[1]))
except ParsingError as e:
    print("ERROR:", e)
    sys.exit(1)

chunks = chunk_pages(pages)

print(f"{len(pages)} page(s) -> {len(chunks)} chunk(s)\n")

for chunk in chunks[:2]:
    print(f"Generating cards for chunk {chunk.chunk_index}...")
    
    try:
        cards = generate_cards(chunk.text)

        for i, card in enumerate(cards, start=1):
            print(f"\nCard {i}")
            print("Question:", card.question)
            print("Answer:", card.answer)
            print("Type:", card.card_type)
            print("Source:", card.source_quote)

    except CardGenerationError as e:
        print("ERROR:", e)