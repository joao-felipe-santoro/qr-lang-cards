#!/usr/bin/env python3
"""
Lang Card Reader — Web Camera edition
======================================
Uses Arduino App Lab bricks:
  - camera_code_detection  : reads QR codes from USB camera
  - web_ui                 : serves real-time feedback interface at :7000
  - dbstorage_sqlstore     : persists scan history

Audio plays in the browser — no pygame or PulseAudio needed on the device.
TTS files are generated/cached on the device and sent as base64 in the
code_detected event. The browser plays them in sequence.

Run inside Arduino App Lab (Network Mode or SBC mode).
Access the interface at  http://<board-name>.local:7000
"""

from datetime import datetime, UTC
import io
import base64
import json
from pathlib import Path

from PIL.Image import Image
from arduino.app_utils import App
from arduino.app_bricks.web_ui import WebUI
from arduino.app_bricks.camera_code_detection import CameraCodeDetection, Detection, draw_bounding_box
from arduino.app_bricks.dbstorage_sqlstore import SQLStore

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from generate_cards import build_cards

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent.parent
CSV_FILE    = BASE_DIR / "data" / "cards_source.csv"
CONFIG_FILE = BASE_DIR / "config.json"
CACHE_DIR   = BASE_DIR / "audio_cache"

with open(CONFIG_FILE, encoding="utf-8") as f:
    cfg = json.load(f)

LANGUAGES = cfg["languages"]
LANG_KEYS = [l["key"] for l in LANGUAGES]

CACHE_DIR.mkdir(exist_ok=True)
ALL_CARDS = build_cards(CSV_FILE, LANG_KEYS)
print(f"✅ {len(ALL_CARDS)} cards loaded")

# ── State ─────────────────────────────────────────────────────────────────────
detected = False

# ── Audio (generate/cache only — playback happens in the browser) ─────────────
def cache_path(card_id: str, lang: str) -> Path:
    return CACHE_DIR / f"{card_id}_{lang}.mp3"

def gerar_audio(card_id: str, text: str, lang: str) -> Path:
    path = cache_path(card_id, lang)
    if not path.exists():
        from gtts import gTTS
        print(f"   🔊 Gerando {card_id}_{lang}: {text}")
        gTTS(text=text, lang=lang, slow=False).save(str(path))
    return path

def get_audio_b64(card_id: str, card: dict) -> list[dict]:
    """Returns list of {lang, data (base64 mp3), type} for all languages."""
    result = []
    for lang_cfg in LANGUAGES:
        lang = lang_cfg["key"]
        try:
            path = gerar_audio(card_id, card[lang], lang)
            result.append({
                "lang":  lang,
                "label": lang_cfg["label"],
                "data":  base64.b64encode(path.read_bytes()).decode("utf-8"),
                "type":  "audio/mpeg",
            })
        except Exception as e:
            print(f"⚠️  Áudio [{lang}]: {e}")
    return result

# ── Camera callbacks ──────────────────────────────────────────────────────────
def on_code_detected(frame: Image, detection: Detection):
    global detected
    if detected:
        return

    detected = True
    card_id  = detection.content.strip()
    ts       = datetime.now(UTC).isoformat()

    frame_box = draw_bounding_box(frame, detection)
    buf = io.BytesIO()
    frame_box.save(buf, format="JPEG", quality=90)
    b64_frame = base64.b64encode(buf.getvalue()).decode("utf-8")

    if card_id not in ALL_CARDS:
        print(f"⚠️  Unknown ID: '{card_id}'")
        store.store("scan_log", {"card_id": card_id, "status": "unknown", "timestamp": ts})
        ui.send_message("code_detected", {
            "status":     "unknown",
            "card_id":    card_id,
            "timestamp":  ts,
            "image":      b64_frame,
            "image_type": "image/jpeg",
        })
        return

    card = ALL_CARDS[card_id]

    store.store("scan_log", {
        "card_id":   card_id,
        "status":    "ok",
        "timestamp": ts,
        "type":      detection.type,
    })

    parts = "  |  ".join(f"{l['label']}: {card[l['key']]}" for l in LANGUAGES)
    print(f"🃏 {card_id}  {parts}")

    ui.send_message("code_detected", {
        "status":     "ok",
        "card_id":    card_id,
        "words":      {l["key"]: card[l["key"]] for l in LANGUAGES},
        "labels":     {l["key"]: l["label"]     for l in LANGUAGES},
        "timestamp":  ts,
        "image":      b64_frame,
        "image_type": "image/jpeg",
        "audio":      get_audio_b64(card_id, card),
    })

def on_frame(frame: Image):
    if detected:
        return

    buf = io.BytesIO()
    frame.save(buf, format="JPEG", quality=80)
    b64_frame = base64.b64encode(buf.getvalue()).decode("utf-8")

    ui.send_message("frame_detected", {
        "timestamp":  datetime.now(UTC).isoformat(),
        "image":      b64_frame,
        "image_type": "image/jpeg",
    })

def on_error(e: Exception):
    ui.send_message("error", str(e))

# ── REST + WebSocket ──────────────────────────────────────────────────────────
def on_list_scans():
    scans = store.read("scan_log", order_by="timestamp DESC", limit=10)
    return {"scans": scans if scans else []}

def reset_detection(_, __):
    global detected
    detected = False

# ── Init ──────────────────────────────────────────────────────────────────────
store = SQLStore("lang-card-scans.db")

detector = CameraCodeDetection()
detector.on_detect(on_code_detected)
detector.on_frame(on_frame)
detector.on_error(on_error)

ui = WebUI()
ui.expose_api("GET", "/list_scans", on_list_scans)
ui.on_message("reset_detection", reset_detection)

App.run()
