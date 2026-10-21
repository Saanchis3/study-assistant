from app.services.quality_checks import CardDraft, find_flags, source_looks_garbled


def codes(flags, card_id):
    return [f.code for f in flags.get(card_id, [])]


def test_same_section_duplicate_is_a_warning():
    drafts = [
        CardDraft(1, "What does 'a' mean?", "same text", chunk_id=1),
        CardDraft(2, "What does 'b' mean?", "same text", chunk_id=1),
    ]
    flags = find_flags(drafts)
    assert flags[1][0].code == "shared_answer"
    assert flags[1][0].severity == "warning"


def test_cross_section_duplicate_is_only_info():
    drafts = [
        CardDraft(1, "What does 'a' mean?", "same text", chunk_id=1),
        CardDraft(2, "What does 'b' mean?", "same text", chunk_id=2),
    ]
    flags = find_flags(drafts)
    assert flags[1][0].severity == "info"


def test_repeated_question_is_flagged():
    drafts = [
        CardDraft(1, "What does 'a' mean?", "same text", chunk_id=1),
        CardDraft(2, "What does 'a' mean?", "same text", chunk_id=2),
    ]
    assert codes(find_flags(drafts), 1) == ["repeated_question"]


def test_unsupported_quote_is_flagged():
    d = CardDraft(1, "What is X?", "an answer here ok",
                  source_text="some other text", source_quote="made up quote")
    assert "quote_not_found" in codes(find_flags([d]), 1)


def test_copied_answer_is_not_weak_support():
    d = CardDraft(1, "What is X?", "alpha bravo charlie delta",
                  source_text="X alpha bravo charlie delta", source_quote="X alpha")
    assert "weak_support" not in codes(find_flags([d]), 1)


def test_unrelated_answer_is_weak_support():
    d = CardDraft(1, "What is X?", "completely unrelated words appear here",
                  source_text="X is a sort of cell structure", source_quote="")
    assert "weak_support" in codes(find_flags([d]), 1)


def test_edited_answer_skips_weak_support():
    d = CardDraft(1, "What is X?", "completely unrelated words appear here",
                  source_text="X is a sort of cell structure", edited=True)
    assert "weak_support" not in codes(find_flags([d]), 1)


def test_empty_answer_is_flagged():
    d = CardDraft(1, "What is X?", "   ", source_text="X is something")
    assert "empty_answer" in codes(find_flags([d]), 1)


def test_one_word_per_line_is_garbled():
    assert source_looks_garbled("\n".join(["word"] * 30))
    assert not source_looks_garbled("A normal sentence with several words.\n" * 30)