
from app.services.chunking import chunk_pages, MAX_WORDS
from app.services.parsing import PageText


def test_empty_input_gives_no_chunks():
    assert chunk_pages([]) == []


def test_short_text_is_one_chunk():
    pages = [PageText(1, "Photosynthesis makes sugar from light.")]
    chunks = chunk_pages(pages)
    assert len(chunks) == 1
    assert chunks[0].page_start == 1


def test_one_giant_paragraph_with_sentences_is_split():
    text = "This is a sentence with several words. " * 300
    chunks = chunk_pages([PageText(1, text)])
    assert len(chunks) > 1
    assert all(len(c.text.split()) <= MAX_WORDS + 50 for c in chunks)


def test_giant_text_without_punctuation_is_split():
    chunks = chunk_pages([PageText(1, "word " * 2000)])
    assert len(chunks) > 1


def test_headings_and_paragraphs_stay_in_order():
    text = "Chapter 1\n\n" + ("Cells are small. " * 30) + "\n\nChapter 2\n\n" + (
        "DNA stores information. " * 30
    )
    chunks = chunk_pages([PageText(1, text)])
    combined = "\n\n".join(c.text for c in chunks)
    assert combined.index("Chapter 1") < combined.index("Chapter 2")


def test_page_numbers_are_tracked():
    pages = [
        PageText(1, "Alpha " * 450),
        PageText(2, "Beta " * 450),
        PageText(3, "Gamma " * 450),
    ]
    chunks = chunk_pages(pages)
    assert chunks[0].page_start == 1
    assert chunks[-1].page_end == 3
