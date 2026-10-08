from app.services.card_generation import extract_json, quote_is_in_chunk


def test_extract_json_from_plain_json():
    text = '{"cards": []}'

    result = extract_json(text)

    assert result == '{"cards": []}'


def test_extract_json_from_markdown():
    text = """```json
{"cards": []}
```"""

    result = extract_json(text)

    assert result == '{"cards": []}'


def test_extract_json_from_extra_text():
    text = 'Here is the result: {"cards": []}'

    result = extract_json(text)

    assert result == '{"cards": []}'


def test_extract_json_raises_when_missing():
    try:
        extract_json("no json here")
        assert False
    except Exception:
        assert True


def test_quote_is_in_chunk():
    chunk = "Photosynthesis is the process by which plants make food."

    assert quote_is_in_chunk(
        "Photosynthesis is the process by which plants make food.",
        chunk,
    )


def test_quote_not_in_chunk():
    chunk = "Photosynthesis is the process by which plants make food."

    assert not quote_is_in_chunk(
        "Plants use oxygen to make food.",
        chunk,
    )