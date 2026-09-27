#!/usr/bin/env python3
"""
Lang Card Reader — Arduino UNO Q + GM65
========================================
Receives QR code IDs via serial port (from STM32 through the App Lab Bridge),
looks up the configured languages in cards_source.csv, and plays TTS audio in sequence.

Dependencies (install on the UNO Q Linux side):
  pip3 install -r requirements.txt

Usage:
  python3 reader.py
  python3 reader.py --port /dev/ttyUSB1   # override serial port if needed
  python3 reader.py --dry-run             # test without hardware
"""

import json
import sys
import time
import argparse
import threading
from pathlib import Path

from generate_cards import build_cards

# ── Argumentos ────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Leitor de cartas trilíngue")
parser.add_argument("--port",    default="/dev/ttyUSB0", help="Porta serial do GM65 via Bridge")
parser.add_argument("--baud",    default=9600, type=int,  help="Baud rate (padrão 9600)")
parser.add_argument("--dry-run", action="store_true",     help="Simula leitura sem serial")
parser.add_argument("--volume",  default=0.9, type=float, help="Volume (0.0 a 1.0)")
args = parser.parse_args()

# ── Config ────────────────────────────────────────────────────────────────────
CSV_FILE    = Path(__file__).parent / "cards_source.csv"
CONFIG_FILE = Path(__file__).parent / "config.json"
CACHE_DIR   = Path(__file__).parent / "audio_cache"
COOLDOWN_SEG = 2.5

with open(CONFIG_FILE, encoding="utf-8") as _f:
    _cfg = json.load(_f)

LANGUAGES = _cfg["languages"]
LANG_KEYS = [l["key"] for l in LANGUAGES]
BASE_LANG = _cfg.get("base_language", LANG_KEYS[0])

CACHE_DIR.mkdir(exist_ok=True)

# ── Load cards ────────────────────────────────────────────────────────────────
ALL_CARDS = build_cards(CSV_FILE, LANG_KEYS)
print(f"✅ {len(ALL_CARDS)} cards loaded from {CSV_FILE.name}")

# ── TTS / Áudio ───────────────────────────────────────────────────────────────
def cache_path(card_id: str, lang: str) -> Path:
    # Filename pattern: animal_001_pt-br.mp3, nat_003_en.mp3
    return CACHE_DIR / f"{card_id}_{lang}.mp3"

def gerar_audio(card_id: str, text: str, lang: str) -> Path:
    path = cache_path(card_id, lang)
    if not path.exists():
        from gtts import gTTS
        print(f"   🔊 Gerando {card_id}_{lang}: {text}")
        gTTS(text=text, lang=lang, slow=False).save(str(path))
    return path

def pre_cachear_todos():
    """Gera todos os áudios em background na primeira execução."""
    print("⏳ Pré-cacheando áudios (só na 1ª vez — pode demorar)...")
    total  = len(ALL_CARDS) * 3
    feitos = 0
    for card_id, card in ALL_CARDS.items():
        for lang in LANG_KEYS:
            try:
                gerar_audio(card_id, card[lang], lang)
                feitos += 1
                if feitos % 15 == 0:
                    print(f"   📦 {feitos}/{total} prontos...")
            except Exception as e:
                print(f"   ⚠️  {card_id}/{lang}: {e}")
    print(f"✅ Cache completo! {feitos} áudios prontos.")

_pygame = None
def _get_pygame():
    global _pygame
    if _pygame is None:
        import pygame
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        pygame.mixer.music.set_volume(args.volume)
        _pygame = pygame
    return _pygame

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
            print(f"   ⚠️  Erro ao tocar [{lang}]: {e}")

# ── Loop serial ───────────────────────────────────────────────────────────────
def loop_serial():
    import serial

    print(f"\n📡 Abrindo porta serial {args.port} @ {args.baud} baud...")
    try:
        ser = serial.Serial(args.port, args.baud, timeout=1)
    except serial.SerialException as e:
        print(f"❌ Não foi possível abrir {args.port}: {e}")
        print("   Verifique se o App Lab Bridge está ativo e a porta correta.")
        print("   Dica: use  ls /dev/ttyUSB*  para listar portas disponíveis.")
        sys.exit(1)

    print("✅ Serial aberta. Aguardando leituras do GM65...\n")

    ultimo_lido  = {}   # { card_id: timestamp }
    tocando      = False

    while True:
        try:
            raw = ser.readline()
        except serial.SerialException as e:
            print(f"⚠️  Erro de leitura serial: {e}")
            time.sleep(1)
            continue

        if not raw:
            continue

        card_id = raw.decode("utf-8", errors="ignore").strip()
        if not card_id:
            continue

        agora = time.time()
        print(f"📥 Recebido: '{card_id}'")

        # Cooldown
        if agora - ultimo_lido.get(card_id, 0) < COOLDOWN_SEG:
            continue
        if tocando:
            continue

        ultimo_lido[card_id] = agora

        if card_id not in ALL_CARDS:
            print(f"⚠️  Unknown ID: '{card_id}' — check cards_source.csv")
            continue

        card  = ALL_CARDS[card_id]
        parts = "  |  ".join(f"{l['label']}: {card.get(l['key'], '?')}" for l in LANGUAGES)
        print(f"🃏 {card_id}  {parts}")

        tocando = True
        def _tocar(cid=card_id, c=card):
            nonlocal tocando
            falar_carta(cid, c)
            tocando = False
        threading.Thread(target=_tocar, daemon=True).start()

# ── Modo dry-run (debug sem hardware) ─────────────────────────────────────────
def loop_dry_run():
    print("\n🧪 Modo dry-run — digite IDs de carta para testar (ex: animal_001)")
    print("   IDs disponíveis:", ", ".join(list(ALL_CARDS.keys())[:5]), "...\n")

    tocando = False
    while True:
        try:
            card_id = input("ID > ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not card_id:
            continue
        if card_id not in ALL_CARDS:
            print(f"⚠️  '{card_id}' não encontrado.")
            continue

        card  = ALL_CARDS[card_id]
        parts = "  |  ".join(f"{l['label']}: {card.get(l['key'], '?')}" for l in LANGUAGES)
        print(f"🃏 {card_id}  {parts}")

        if not tocando:
            tocando = True
            def _tocar(cid=card_id, c=card):
                nonlocal tocando
                falar_carta(cid, c)
                tocando = False
            threading.Thread(target=_tocar, daemon=True).start()

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("\n🍓 Leitor de Cartas Trilíngue — Arduino UNO Q + GM65")
    print("=" * 52)

    # Pré-cacheia áudios em background
    threading.Thread(target=pre_cachear_todos, daemon=True).start()
    time.sleep(0.5)

    try:
        if args.dry_run:
            loop_dry_run()
        else:
            loop_serial()
    except KeyboardInterrupt:
        print("\n\n👋 Encerrando...")

if __name__ == "__main__":
    main()