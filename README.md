# Lang Card Reader 🃏
### Arduino UNO Q + GM65 + Python TTS

An educational device for children to learn vocabulary in **multiple languages**.  
Scan a QR code card with the GM65 reader and the device speaks the word in all configured languages.

Languages are fully configurable via `python/config.json` — no code changes needed.  
The default set is **Brazilian Portuguese (`pt-br`), English (`en`), and German (`de`)**.

---

## How it works

```
QR Card → GM65 → STM32 → App Lab Bridge → reader.py (Linux)
                                               ↓
                                        cards_source.csv  ← source of truth
                                        config.json       ← language config
                                               ↓
                                        gTTS → pygame → speaker
```

On boot, `reader.py` loads cards directly from `cards_source.csv` and audio is generated on demand via gTTS, cached locally.

---

## Hardware

| Component | Qty | Notes |
|---|---|---|
| Arduino UNO Q 2GB | 1 | Main board |
| GM65 (QR code reader module) | 1 | UART TTL interface |
| 3.5mm speaker | 1 | Audio output |
| RGB LED | 1 | Visual feedback (optional) |
| 220Ω resistors | 3 | One per LED color |
| Male-female jumper wires | ~8 | Connections |
| USB-C cable | 1 | Power / programming |

**Estimated cost:** GM65 (~$10–15) + Arduino UNO Q

---

## Wiring

### GM65 → Arduino UNO Q (STM32)

```
GM65          Arduino UNO Q
─────         ─────────────
VCC    ──────  5V
GND    ──────  GND
TX     ──────  D0  (STM32 RX1)
RX     ──────  D1  (STM32 TX1)
```

> ⚠️ The GM65 operates at 5V. STM32 pins on the UNO Q are 5V-tolerant, but check your board revision's datasheet.

### RGB LED → Arduino UNO Q (STM32)

```
RGB LED (common anode)    Arduino UNO Q
──────────────────────    ─────────────
R  ──[ 220Ω ]──────────   D9
G  ──[ 220Ω ]──────────   D10
B  ──[ 220Ω ]──────────   D11
VCC ───────────────────   3.3V or 5V
```

> This build uses a **common anode** LED — `HIGH = on`. If your LED is common cathode, invert the logic in the sketch (`ledSet`).

### Speaker → Arduino UNO Q

Connect the speaker to the **3.5mm (P2) audio jack** on the Linux side of the board.  
Alternatively use Bluetooth — the QRB2210 has built-in BT 5.1.

---

## Installation

### 1. STM32 sketch (Arduino side)

Open **Arduino App Lab** and upload `arduino/stm32_sketch/stm32_sketch.ino`:

```
Tools → Board → Arduino UNO Q
Tools → Port  → (select the correct port)
Sketch → Upload
```

### 2. Python dependencies (UNO Q Linux side)

Connect via SSH to the UNO Q or use the App Lab terminal:

```bash
pip3 install -r python/requirements.txt
```

### 3. Copy project files to the UNO Q

```bash
scp -r python/ user@uno-q-ip:~/lang-card/
```

Or copy via USB drive. The files needed are:

```
python/
├── reader.py
├── config.json
└── cards_source.csv
```

### 4. Find the serial port

```bash
ls /dev/ttyUSB* /dev/ttyACM*
# Usually /dev/ttyUSB0 or /dev/ttyACM0
```

---

## Running

```bash
# Normal mode (GM65 connected)
python3 python/reader.py

# Different port
python3 python/reader.py --port /dev/ttyACM0

# Debug mode — no hardware, type card IDs at the prompt
python3 python/reader.py --dry-run

# Adjust volume (0.0–1.0)
python3 python/reader.py --volume 0.7
```

### First run

On the first run, audio files for all cards are generated and cached via gTTS.  
This takes **3–5 minutes** (requires internet).  
Subsequent runs are instant — audio is cached in `python/audio_cache/` (not committed to git).

---

## Language configuration

Edit `python/config.json` to change which languages are used:

```json
{
  "base_language": "pt-br",
  "languages": [
    { "key": "pt-br", "label": "Português Brasil" },
    { "key": "en",    "label": "English"          },
    { "key": "de",    "label": "Deutsch"           }
  ]
}
```

| Field | Purpose |
|---|---|
| `key` | Column name in `cards_source.csv`, runtime identifier, and gTTS language code |
| `label` | Display name shown in logs |
| `base_language` | Primary language (used as fallback ordering) |

The `key` doubles as the gTTS language code — use the codes from the [gTTS language list](https://gtts.readthedocs.io/en/latest/module.html#languages-gtts-lang) as your keys.  
To add a language: add an entry to `config.json` and a matching column to `cards_source.csv`.

---

## Managing cards

Cards live in `python/cards_source.csv` — the single source of truth. `reader.py` loads it directly on boot.

```
category,id,emoji,pt-br,en,de
animais,animal_001,🐘,Elefante,Elephant,Elefant
animais,animal_002,🦁,Leão,Lion,Löwe
...
```

**To add a card:** add a row to the CSV and restart `reader.py`.

**To export `cards.json`** (for inspection or use with other tools):

```bash
python3 python/generate_cards.py
# validates against config.json and writes python/cards.json

python3 python/generate_cards.py --validate   # check only, no file written
```

**To generate the card faces PDF** (emoji visual + word labels + embedded QR code, ready to print and cut):

```bash
python3 python/generate_cards_pdf.py
# → outputs python/cards_to_print.pdf  (2×3 cards per A4 page)

python3 python/generate_cards_pdf.py --cols 3 --rows 4   # denser layout

python3 python/generate_cards_pdf.py --cheatsheet        # print emoji codepoint table and exit
```

The PDF uses `base_language` as the main word label and the other languages as a subtitle.

Emoji images are downloaded automatically from [Noto Emoji](https://github.com/googlefonts/noto-emoji) on the first run and cached in `python/emoji_cache/` — no manual font installation needed.

---

## File structure

```
lang-card/
├── python/
│   ├── reader.py              # Main script — runs on the UNO Q Linux side
│   ├── config.json            # Language configuration
│   ├── config.json.example    # Config template
│   ├── cards_source.csv       # Card database — source of truth
│   ├── generate_cards.py      # CSV → cards.json export / validation utility
│   ├── generate_cards_pdf.py  # Card faces PDF generator (word + QR, print & cut)
│   └── requirements.txt       # Python dependencies
├── arduino/
│   └── stm32_sketch/
│       └── stm32_sketch.ino   # Arduino sketch — runs on the STM32 side
└── cards/
    └── cards_to_print.pdf     # Ready-to-print card sheet
```

> `python/audio_cache/`, `python/emoji_cache/`, `python/cards.json`, and `python/qrcodes_cards.pdf` are generated artifacts and are not committed to git.

---

## LED feedback (STM32)

| Event | LED |
|---|---|
| Boot | Blue double-blink |
| Valid card read | Green flash → `OK` sent to Linux |
| Unknown card ID | Red flash → `ERR` sent to Linux |

---

## Autostart on boot

```bash
sudo nano /etc/systemd/system/card-reader.service
```

```ini
[Unit]
Description=Lang Card Reader
After=sound.target network.target

[Service]
ExecStart=/usr/bin/python3 /home/user/lang-card/python/reader.py
WorkingDirectory=/home/user/lang-card/python
Restart=always
User=user

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable card-reader
sudo systemctl start card-reader
```

---

## Troubleshooting

**Serial port not found**
```bash
sudo usermod -aG dialout $USER
ls -la /dev/tty*
```

**GM65 not reading the card** — ideal distance: 5–15 cm. Check TX/RX aren't swapped.

**No audio**
```bash
aplay /usr/share/sounds/alsa/Front_Left.wav   # test system audio
alsamixer                                      # check volume
```

**Audio cuts out** — increase pygame buffer in `reader.py`: `buffer=1024`

---

*Built with [Claude Code](https://claude.com/claude-code)* 🤖
