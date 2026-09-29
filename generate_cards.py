#!/usr/bin/env python3
"""
generate_cards.py — converts cards_source.csv → cards.json

Language keys are read from config.json. Any CSV column that is not
'category', 'id', or a language key is passed through as a metadata field.
Empty metadata values are omitted from the output.

Usage:
  python3 generate_cards.py
  python3 generate_cards.py --source cards_source.csv --out cards.json
  python3 generate_cards.py --validate        # check only, no output written
"""

import csv
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent


def build_cards(csv_path: Path, lang_keys: list) -> dict:
    """
    Read cards_source.csv and return a flat {card_id: {lang: word, ...}} dict.
    Exits with an error message if required language columns are missing.
    """
    reserved = {"category", "id"} | set(lang_keys)

    with open(csv_path, encoding="utf-8", newline="") as f:
        reader    = csv.DictReader(f)
        rows      = list(reader)
        header    = reader.fieldnames or []

    missing = [lk for lk in lang_keys if lk not in header]
    if missing:
        print(f"❌  Missing language columns in CSV: {missing}")
        print(f"   Configured languages : {lang_keys}")
        print(f"   CSV columns          : {list(header)}")
        sys.exit(1)

    meta_keys = [col for col in header if col not in reserved]
    errors    = []
    db        = {}

    for i, row in enumerate(rows, start=2):
        cat     = row.get("category", "").strip()
        card_id = row.get("id", "").strip()

        if not cat or not card_id:
            errors.append(f"Row {i}: missing 'category' or 'id'")
            continue

        card = {}

        for lk in lang_keys:
            val = row.get(lk, "").strip()
            if not val:
                errors.append(f"Row {i} ({card_id}): missing translation for '{lk}'")
            card[lk] = val

        for mk in meta_keys:
            val = row.get(mk, "").strip()
            if val:
                try:
                    card[mk] = int(val)
                except ValueError:
                    try:
                        card[mk] = float(val)
                    except ValueError:
                        card[mk] = val

        db.setdefault(cat, {})[card_id] = card

    if errors:
        print(f"⚠️  {len(errors)} issue(s) in {csv_path.name}:")
        for e in errors:
            print(f"   • {e}")

    # Return flat dict {card_id: card}
    return {cid: card for cat in db.values() for cid, card in cat.items()}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build cards.json from CSV source")
    parser.add_argument("--source",   default=str(BASE_DIR / "data" / "cards_source.csv"))
    parser.add_argument("--out",      default=str(BASE_DIR / "cards.json"))
    parser.add_argument("--config",   default=str(BASE_DIR / "config.json"))
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = json.load(f)

    lang_keys = [l["key"] for l in cfg["languages"]]
    cards     = build_cards(Path(args.source), lang_keys)
    total     = len(cards)

    print(f"📊  {total} cards  |  🌐  Languages: {lang_keys}")

    if args.validate:
        print("✅  Validation complete — no file written (--validate mode).")
        sys.exit(0)

    # Reconstruct categorised structure for the JSON file
    with open(args.source, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    db = {}
    for row in rows:
        cat     = row.get("category", "").strip()
        card_id = row.get("id", "").strip()
        if cat and card_id and card_id in cards:
            db.setdefault(cat, {})[card_id] = cards[card_id]

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

    print(f"✅  {args.out} written ({total} cards).")
