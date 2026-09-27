# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Educational device for children to learn vocabulary in Portuguese, English, and German. Scanning a QR Code card with the GM65 reader causes the device to speak the word in all three languages.

## Architecture

The system runs on an **Arduino UNO Q 2GB**, which has two chips:

- **STM32U585** (Arduino side): reads QR codes from GM65 via UART1 (D0/D1 at 9600 baud), forwards IDs to Linux side via App Lab Bridge, controls RGB LED
- **QRB2210 (Qualcomm, Linux/Debian side)**: runs Python, receives IDs via serial, looks up `cards.json`, generates/plays TTS audio via gTTS + pygame

```
QR Card → GM65 → STM32 → App Lab Bridge → reader.py (Linux)
                                             ↓ cards.json → gTTS → pygame → audio
```

The STM32 and Linux side communicate via the App Lab Bridge, which exposes the STM32 as `/dev/ttyUSB0` or `/dev/ttyACM0` on the Linux side.

## Commands

### Run the card reader (on the UNO Q Linux side)

```bash
# Normal mode (GM65 connected)
python3 python/reader.py

# Debug mode — no hardware needed, type card IDs at prompt
python3 python/reader.py --dry-run

# Specific serial port
python3 python/reader.py --port /dev/ttyACM0

# Adjust volume (0.0–1.0)
python3 python/reader.py --volume 0.7
```

First run generates and caches audio files via gTTS (requires internet, takes 3–5 min). Subsequent runs are instant.

### Regenerate QR Code PDF

```bash
python3 python/generate_qrcodes.py
# → outputs qrcodes_cards.pdf
```

### Install dependencies (on the UNO Q Linux side)

```bash
pip3 install -r requirements.txt
# pyserial, gTTS, pygame
```

### Find the serial port

```bash
ls /dev/ttyUSB* /dev/ttyACM*
```

## Key Files

| File | Purpose |
|---|---|
| `python/reader.py` | Main Python script (Linux side) |
| `python/cards.json` | Card database — 78 cards + emoji, language keys match config |
| `python/config.json` | Language configuration (base_language + languages list) |
| `arduino/stm32_sketch/stm32_sketch.ino` | Arduino sketch for STM32 side |
| `python/generate_qrcodes.py` | Generates `qrcodes_cards.pdf` for printing |
| `cards/cards_to_print.pdf` | Pre-generated card PDF (ready to print) |

## cards.json Structure

```json
{
  "animais": { "animal_001": { "pt": "Elefante", "en": "Elephant", "de": "Elefant", "emoji": "🐘" } },
  "objetos": { ... },
  "numeros": { ... },
  "letras":  { ... }
}
```

78 cards total: 20 animals (`animal_001`–`020`), 20 objects (`obj_001`–`020`), 12 numbers (`num_001`–`012`, covering 0–10 + twenty), 26 letters (`letra_A`–`letra_Z`).

`reader.py` flattens all categories into a single dict on startup.

## LED Protocol (STM32 ↔ Linux)

- On QR read: STM32 flashes green and sends card ID over serial
- Linux sends `"OK\n"` (valid card) or `"ERR\n"` (unknown ID) back to STM32
- STM32 responds: green flash for OK, red flash for ERR, blue double-blink on boot

## Autostart on Boot (UNO Q Linux)

```bash
sudo systemctl enable card-reader
sudo systemctl start card-reader
# Service file: /etc/systemd/system/card-reader.service
```

## Hardware Notes

- **RGB LED** in this build is **common anode** — `HIGH = on`. If using common cathode, invert logic in `stm32_sketch.ino` (`ledSet`) and in the README wiring diagram.
- GM65 default baud rate: 9600. Both `reader.py` and the sketch use this.
- Audio cache stored in `python/audio_cache/` (auto-created, named `<card_id>_<lang>.mp3`).
- pygame buffer is 512 samples; increase to 1024 in `reader.py` if audio cuts out.
