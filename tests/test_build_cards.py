import csv
import io
import pytest
from generate_cards import build_cards

LANG_KEYS = ["pt-br", "en", "de"]


def _csv(rows: list[dict], fieldnames=None) -> io.StringIO:
    fieldnames = fieldnames or ["category", "id", "emoji"] + LANG_KEYS
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    buf.seek(0)
    return buf


def _write_csv(tmp_path, rows, fieldnames=None):
    p = tmp_path / "cards.csv"
    fieldnames = fieldnames or ["category", "id", "emoji"] + LANG_KEYS
    with open(p, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return p


def test_basic_card_loaded(tmp_path):
    p = _write_csv(tmp_path, [
        {"category": "animais", "id": "animal_001", "emoji": "🐘",
         "pt-br": "Elefante", "en": "Elephant", "de": "Elefant"},
    ])
    cards = build_cards(p, LANG_KEYS)
    assert "animal_001" in cards
    assert cards["animal_001"]["pt-br"] == "Elefante"
    assert cards["animal_001"]["en"] == "Elephant"
    assert cards["animal_001"]["de"] == "Elefant"


def test_emoji_stored_as_metadata(tmp_path):
    p = _write_csv(tmp_path, [
        {"category": "animais", "id": "animal_001", "emoji": "🐘",
         "pt-br": "Elefante", "en": "Elephant", "de": "Elefant"},
    ])
    cards = build_cards(p, LANG_KEYS)
    assert cards["animal_001"]["emoji"] == "🐘"


def test_categories_flattened(tmp_path):
    p = _write_csv(tmp_path, [
        {"category": "animais", "id": "animal_001", "emoji": "🐘",
         "pt-br": "Elefante", "en": "Elephant", "de": "Elefant"},
        {"category": "objetos", "id": "obj_001", "emoji": "🪑",
         "pt-br": "Cadeira", "en": "Chair", "de": "Stuhl"},
    ])
    cards = build_cards(p, LANG_KEYS)
    assert set(cards.keys()) == {"animal_001", "obj_001"}


def test_row_with_empty_id_skipped(tmp_path):
    p = _write_csv(tmp_path, [
        {"category": "animais", "id": "", "emoji": "🐘",
         "pt-br": "Elefante", "en": "Elephant", "de": "Elefant"},
        {"category": "animais", "id": "animal_001", "emoji": "🦁",
         "pt-br": "Leão", "en": "Lion", "de": "Löwe"},
    ])
    cards = build_cards(p, LANG_KEYS)
    assert len(cards) == 1
    assert "animal_001" in cards


def test_row_with_empty_category_skipped(tmp_path):
    p = _write_csv(tmp_path, [
        {"category": "", "id": "animal_001", "emoji": "🐘",
         "pt-br": "Elefante", "en": "Elephant", "de": "Elefant"},
    ])
    cards = build_cards(p, LANG_KEYS)
    assert len(cards) == 0


def test_missing_language_column_exits(tmp_path):
    # CSV without the 'de' column
    p = _write_csv(tmp_path, [
        {"category": "animais", "id": "animal_001", "emoji": "🐘",
         "pt-br": "Elefante", "en": "Elephant"},
    ], fieldnames=["category", "id", "emoji", "pt-br", "en"])
    with pytest.raises(SystemExit):
        build_cards(p, LANG_KEYS)


def test_missing_translation_reported_but_continues(tmp_path, capsys):
    p = _write_csv(tmp_path, [
        {"category": "animais", "id": "animal_001", "emoji": "🐘",
         "pt-br": "Elefante", "en": "", "de": "Elefant"},
    ])
    cards = build_cards(p, LANG_KEYS)
    assert "animal_001" in cards
    assert cards["animal_001"]["en"] == ""
    captured = capsys.readouterr()
    assert "issue" in captured.out or "missing" in captured.out.lower()


def test_multiple_cards_same_category(tmp_path):
    p = _write_csv(tmp_path, [
        {"category": "animais", "id": f"animal_{i:03d}", "emoji": "🐘",
         "pt-br": f"Animal{i}", "en": f"Animal{i}", "de": f"Animal{i}"}
        for i in range(1, 6)
    ])
    cards = build_cards(p, LANG_KEYS)
    assert len(cards) == 5
