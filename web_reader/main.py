#!/usr/bin/env python3
"""
Lang Card Reader — Web Camera edition
======================================
Uses Arduino App Lab bricks:
  - camera_code_detection  : reads QR codes from USB camera
  - web_ui                 : serves real-time feedback interface at :7000
  - dbstorage_sqlstore     : persists scan history

Run inside Arduino App Lab (Network Mode or SBC mode).
Access the interface at  http://<board-name>.local:7000
"""

import json
import time
import threading
from pathlib import Path

from PIL.Image import Image as PILImage

from arduino.app_utils import App
from arduino.app_peripherals.usb_camera import USBCamera
from arduino.app_bricks.camera_code_detection import CameraCodeDetection, Detection
from arduino.app_bricks.web_ui import WebUI
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

# ── Bricks ────────────────────────────────────────────────────────────────────
camera   = USBCamera(resolution=(640, 480), fps=30)
detector = CameraCodeDetection(camera=camera, detect_barcode=False)
ui       = WebUI(assets_dir_path=str(Path(__file__).parent / "assets"))
db       = SQLStore("lang_card_scans.db")

# ── Audio ─────────────────────────────────────────────────────────────────────
_pygame_ready = False
tocando = False

def _get_pygame():
    global _pygame_ready
    import pygame
    if not _pygame_ready:
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        pygame.mixer.music.set_volume(0.9)
        _pygame_ready = True
    return pygame

def cache_path(card_id: str, lang: str) -> Path:
    return CACHE_DIR / f"{card_id}_{lang}.mp3"

def gerar_audio(card_id: str, text: str, lang: str) -> Path:
    path = cache_path(card_id, lang)
    if not path.exists():
        from gtts import gTTS
        gTTS(text=text, lang=lang, slow=False).save(str(path))
    return path

def tocar(path: Path):
    pg = _get_pygame()
    pg.mixer.music.load(str(path))
    pg.mixer.music.play()
    while pg.mixer.music.get_busy():
        time.sleep(0.05)

def falar_carta(card_id: str, card: dict):
    for lang in LANG_KEYS:
        try:
            tocar(gerar_audio(card_id, card[lang], lang))
            time.sleep(0.4)
        except Exception as e:
            print(f"⚠️  [{lang}]: {e}")

# ── Detection callback ────────────────────────────────────────────────────────
def on_code_detected(frame: PILImage, detection: Detection):
    global tocando
    card_id = detection.content.strip()

    # If audio is playing, defer re-detection so the same card can be scanned again
    if tocando:
        detector.already_seen_codes.discard(card_id)
        return

    if card_id not in ALL_CARDS:
        print(f"⚠️  Unknown ID: '{card_id}'")
        ui.send_message('scan_result', {'status': 'unknown', 'card_id': card_id})
        detector.already_seen_codes.discard(card_id)
        return

    card = ALL_CARDS[card_id]
    ts   = time.time()

    db.store('scans', {'card_id': card_id, 'timestamp': ts, 'type': detection.type})

    ui.send_message('scan_result', {
        'status':    'ok',
        'card_id':   card_id,
        'words':     {l['key']: card[l['key']] for l in LANGUAGES},
        'labels':    {l['key']: l['label']     for l in LANGUAGES},
        'timestamp': ts,
    })

    parts = '  |  '.join(f"{l['label']}: {card[l['key']]}" for l in LANGUAGES)
    print(f"🃏 {card_id}  {parts}")

    tocando = True
    def _play(cid=card_id, c=card):
        global tocando
        falar_carta(cid, c)
        tocando = False
        detector.already_seen_codes.discard(cid)
    threading.Thread(target=_play, daemon=True).start()

def on_error(e: Exception):
    print(f"❌ Camera error: {e}")

# ── REST + WebSocket ──────────────────────────────────────────────────────────
def on_list_scans(request):
    return db.read('scans', order_by='timestamp DESC', limit=10)

def on_reset(sid, data):
    detector.already_seen_codes.clear()
    print("🔄 Detection reset by UI")

# ── Wire up ───────────────────────────────────────────────────────────────────
detector.on_detect(on_code_detected)
detector.on_error(on_error)
ui.expose_camera('/stream', camera)
ui.expose_api('GET', '/list_scans', on_list_scans)
ui.on_message('reset', on_reset)

App.run()
