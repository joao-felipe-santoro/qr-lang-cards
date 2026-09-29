"""
Sanity checks on the committed data files.
Catches issues like the num_003 corrupt row (period instead of comma)
or missing translations before they surface at runtime.
"""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
CSV_PATH = ROOT / "data" / "cards_source.csv"
CONFIG_EXAMPLE = ROOT / "config.json.example"

REQUIRED_COLUMNS = {"category", "id", "emoji"}
ID_PREFIXES = {"animal_", "obj_", "inseto_", "num_", "letra_", "nat_", "ali_"}


def _load_rows():
    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _load_config_example():
    with open(CONFIG_EXAMPLE, encoding="utf-8") as f:
        return json.load(f)


def test_csv_exists():
    assert CSV_PATH.exists(), f"cards_source.csv not found at {CSV_PATH}"


def test_required_columns_present():
    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        header = set(csv.DictReader(f).fieldnames or [])
    missing = REQUIRED_COLUMNS - header
    assert not missing, f"Missing columns in CSV: {missing}"


def test_language_columns_present():
    cfg = _load_config_example()
    lang_keys = {l["key"] for l in cfg["languages"]}
    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        header = set(csv.DictReader(f).fieldnames or [])
    missing = lang_keys - header
    assert not missing, f"CSV missing language columns: {missing}"


def test_no_duplicate_ids():
    rows = _load_rows()
    ids = [r["id"].strip() for r in rows if r.get("id", "").strip()]
    duplicates = {i for i in ids if ids.count(i) > 1}
    assert not duplicates, f"Duplicate card IDs: {duplicates}"


def test_no_empty_id_or_category():
    rows = _load_rows()
    bad = [
        i + 2  # +2 accounts for header row and 0-index
        for i, r in enumerate(rows)
        if not r.get("id", "").strip() or not r.get("category", "").strip()
    ]
    assert not bad, f"Rows with empty id or category (line numbers): {bad}"


def test_all_translations_filled():
    cfg = _load_config_example()
    lang_keys = [l["key"] for l in cfg["languages"]]
    rows = _load_rows()
    missing = []
    for i, row in enumerate(rows, start=2):
        card_id = row.get("id", "").strip()
        if not card_id:
            continue
        for lk in lang_keys:
            if not row.get(lk, "").strip():
                missing.append(f"row {i} ({card_id}): missing '{lk}'")
    assert not missing, "Cards with missing translations:\n" + "\n".join(missing)


def test_all_non_letter_cards_have_emoji():
    rows = _load_rows()
    missing = [
        row["id"] for row in rows
        if not row.get("id", "").startswith("letra_")
        and row.get("id", "").strip()
        and not row.get("emoji", "").strip()
    ]
    assert not missing, f"Cards without emoji: {missing}"


def test_id_format_matches_known_prefixes():
    rows = _load_rows()
    unknown = [
        row["id"] for row in rows
        if row.get("id", "").strip()
        and not any(row["id"].startswith(p) for p in ID_PREFIXES)
    ]
    assert not unknown, f"Card IDs with unexpected prefix: {unknown}"


def test_config_example_valid_json():
    cfg = _load_config_example()
    assert isinstance(cfg, dict)


def test_config_example_required_keys():
    cfg = _load_config_example()
    assert "base_language" in cfg, "config.json.example missing 'base_language'"
    assert "languages" in cfg, "config.json.example missing 'languages'"
    assert isinstance(cfg["languages"], list)
    assert len(cfg["languages"]) > 0


def test_config_example_language_entries():
    cfg = _load_config_example()
    for lang in cfg["languages"]:
        assert "key" in lang, f"Language entry missing 'key': {lang}"
        assert "label" in lang, f"Language entry missing 'label': {lang}"


def test_config_example_base_language_in_list():
    cfg = _load_config_example()
    keys = [l["key"] for l in cfg["languages"]]
    assert cfg["base_language"] in keys, (
        f"base_language '{cfg['base_language']}' not in languages list: {keys}"
    )
