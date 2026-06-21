from bot.services.voice_expense_extraction import normalize_voice_expense_payload


def test_normalize_voice_payload_keeps_quantity_in_description_and_amount_price():
    payload = {
        "transcript": "рыба сушеная 290 жигулевская 1 литр 180 р",
        "items": [
            {"description": "рыба сушеная", "amount": 290, "currency": None, "confidence": 0.95},
            {"description": "жигулевская 1 литр", "amount": 180, "currency": None, "confidence": 0.94},
        ],
    }

    normalized = normalize_voice_expense_payload(payload)

    assert normalized is not None
    assert normalized["items"][1] == {
        "description": "жигулевская 1 литр",
        "amount": 180.0,
        "currency": None,
        "confidence": 0.94,
    }


def test_normalize_voice_payload_demotes_unit_number_from_amount():
    payload = {
        "transcript": "жигулевская 1 литр",
        "items": [
            {"description": "жигулевская 1 литр", "amount": 1, "currency": None, "confidence": 0.8},
        ],
    }

    normalized = normalize_voice_expense_payload(payload)

    assert normalized is not None
    assert normalized["items"][0]["amount"] is None


def test_normalize_voice_payload_accepts_spoken_number_amount():
    payload = {
        "transcript": "мороженое сто десять рублей",
        "items": [
            {"description": "мороженое", "amount": 110, "currency": "RUB", "confidence": 0.9},
        ],
    }

    normalized = normalize_voice_expense_payload(payload)

    assert normalized is not None
    assert normalized["items"][0]["amount"] == 110.0
    assert normalized["items"][0]["currency"] == "RUB"


def test_normalize_voice_payload_rejects_missing_transcript():
    payload = {
        "items": [
            {"description": "мороженое", "amount": 110, "currency": None, "confidence": 0.9},
        ],
    }

    assert normalize_voice_expense_payload(payload) is None
