#!/usr/bin/env python3
"""
generate_cards_pdf.py — generates the printable card faces PDF

Reads cards_source.csv and config.json. Each card shows the word in all
configured languages plus a small QR code in the corner.

Dependencies:
  pip3 install -r requirements.txt

Usage:
  python3 generate_cards_pdf.py
  python3 generate_cards_pdf.py --out my_cards.pdf
  python3 generate_cards_pdf.py --cols 2 --rows 3
"""

import io
import sys
import subprocess
import argparse
import csv
import json
import urllib.request
from pathlib import Path

# ── Auto-install dependencies ─────────────────────────────────────────────────
def _install(pkg):
    print(f"📦 Installing {pkg}...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

try:
    from reportlab.lib.pagesizes import A4
except ImportError:
    _install("reportlab")
    from reportlab.lib.pagesizes import A4

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    _install("pillow")
    from PIL import Image, ImageDraw, ImageFont

from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.graphics.barcode import qr as rl_qr
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderSVG
from reportlab.graphics import renderPDF
from reportlab.lib.utils import ImageReader

# ── Args ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent

parser = argparse.ArgumentParser(description="Generate printable card faces PDF")
parser.add_argument("--out",    default=str(BASE_DIR / "cards_to_print.pdf"))
parser.add_argument("--config", default=str(BASE_DIR / "config.json"))
parser.add_argument("--source", default=str(BASE_DIR / "cards_source.csv"))
parser.add_argument("--cols",       default=2, type=int)
parser.add_argument("--rows",       default=3, type=int)
parser.add_argument("--cheatsheet", action="store_true",
                    help="Print emoji codepoint table and exit")
args = parser.parse_args()

# ── Config ────────────────────────────────────────────────────────────────────
with open(args.config, encoding="utf-8") as f:
    cfg = json.load(f)

LANGUAGES  = cfg["languages"]
LANG_KEYS  = [l["key"] for l in LANGUAGES]
LANG_LABEL = {l["key"]: l["label"] for l in LANGUAGES}
BASE_LANG  = cfg.get("base_language", LANG_KEYS[0])

# ── Load cards (category order preserved, emoji included for PDF) ─────────────
categories = {}   # {category: [(card_id, card), ...]}
with open(args.source, encoding="utf-8", newline="") as f:
    for row in csv.DictReader(f):
        cat     = row.get("category", "").strip()
        card_id = row.get("id", "").strip()
        if cat and card_id:
            card = {lk: row.get(lk, "").strip() for lk in LANG_KEYS}
            card["emoji"] = row.get("emoji", "").strip()
            categories.setdefault(cat, []).append((card_id, card))

all_cards = [(cat, cid, card) for cat, items in categories.items() for cid, card in items]
print(f"✅ {len(all_cards)} cards across {len(categories)} categories")

if args.cheatsheet:
    print(f"\n{'Card ID':<16} {'Emoji':<6} {'Codepoints (no FE0F)':<28} {'Codepoints (with FE0F)':<28} Noto filename")
    print("-" * 100)
    for cat, cid, card in all_cards:
        emoji = card.get("emoji", "")
        if not emoji:
            continue
        no_fe0f  = "_".join(f"{ord(c):04x}" for c in emoji if ord(c) != 0xFE0F)
        with_fe0f = "_".join(f"{ord(c):04x}" for c in emoji)
        noto = f"emoji_u{no_fe0f}.png"
        if with_fe0f != no_fe0f:
            noto += f"  →  emoji_u{with_fe0f}.png"
        print(f"{cid:<16} {emoji:<6} {no_fe0f:<28} {with_fe0f:<28} {noto}")
    sys.exit(0)

# ── Category palette (auto-assigned) ─────────────────────────────────────────
_BG = [
    (0.97, 0.90, 1.00), (0.86, 0.94, 1.00), (0.84, 0.96, 0.88),
    (1.00, 0.92, 0.84), (1.00, 0.94, 0.80), (0.92, 0.88, 1.00),
    (0.98, 0.88, 0.88),
]
_AC = [
    (0.52, 0.18, 0.70), (0.10, 0.36, 0.78), (0.08, 0.50, 0.22),
    (0.78, 0.28, 0.04), (0.70, 0.48, 0.02), (0.38, 0.18, 0.72),
    (0.72, 0.12, 0.12),
]
CAT_STYLE = {
    cat: {"bg": _BG[i % len(_BG)], "ac": _AC[i % len(_AC)]}
    for i, cat in enumerate(categories)
}

# ── Font helpers ──────────────────────────────────────────────────────────────
_BOLD_FONT_PATHS = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "C:/Windows/Fonts/arialbd.ttf",
]

def _load_bold_font(size):
    for fp in _BOLD_FONT_PATHS:
        if Path(fp).exists():
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()

# ── Twemoji emoji renderer ────────────────────────────────────────────────────
_NOTO_BASE = "https://raw.githubusercontent.com/googlefonts/noto-emoji/main/2D/png/512"
_EMOJI_DISK_CACHE = BASE_DIR / "emoji_cache"
_emoji_mem: dict = {}

def _cp(c: str) -> str:
    """Hex codepoint with 4-digit minimum (matches Noto filename convention)."""
    return f"{ord(c):04x}"

def _noto_urls(emoji_char: str) -> list[str]:
    """Return candidate URLs: first without FE0F (most emoji), then with (keycap sequences)."""
    without = "_".join(_cp(c) for c in emoji_char if ord(c) != 0xFE0F)
    with_fe = "_".join(_cp(c) for c in emoji_char)
    urls = [f"{_NOTO_BASE}/emoji_u{without}.png"]
    if with_fe != without:
        urls.append(f"{_NOTO_BASE}/emoji_u{with_fe}.png")
    return urls

def render_emoji(emoji_char: str, size: int = 260):
    """Download emoji PNG from Noto Emoji (cached to disk). Returns ImageReader or None."""
    if emoji_char in _emoji_mem:
        src = _emoji_mem[emoji_char]
        if src is None:
            return None
        return ImageReader(src.copy().resize((size, size), Image.LANCZOS))

    _EMOJI_DISK_CACHE.mkdir(exist_ok=True)
    codepoints = "_".join(_cp(c) for c in emoji_char if ord(c) != 0xFE0F)
    cache_file = _EMOJI_DISK_CACHE / f"emoji_u{codepoints}.png"

    if not cache_file.exists():
        for url in _noto_urls(emoji_char):
            try:
                urllib.request.urlretrieve(url, cache_file)
                break
            except Exception:
                continue
        else:
            _emoji_mem[emoji_char] = None
            return None

    try:
        img = Image.open(cache_file).convert("RGBA")
    except Exception:
        _emoji_mem[emoji_char] = None
        return None

    _emoji_mem[emoji_char] = img
    return ImageReader(img.copy().resize((size, size), Image.LANCZOS))

def render_word_badge(text: str, color_rgb: tuple, size: int = 260) -> ImageReader:
    """Word centred on a coloured circle — used as fallback when no emoji font."""
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    r    = int(size * 0.46)
    cx, cy = size // 2, size // 2
    fill = tuple(int(c * 255) for c in color_rgb) + (230,)
    draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill=fill)
    fs   = max(28, int(size * 0.30) - max(0, (len(text) - 5) * 8))
    font = _load_bold_font(fs)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - tw//2 - bbox[0], cy - th//2 - bbox[1]),
              text, font=font, fill=(255, 255, 255, 255))
    return ImageReader(img)

def render_letter(letter: str, color_rgb: tuple, size: int = 260) -> ImageReader:
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    r    = int(size * 0.46)
    cx, cy = size // 2, size // 2
    fill = tuple(int(c * 255) for c in color_rgb) + (235,)
    draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill=fill)
    font = _load_bold_font(int(size * 0.55))
    bbox = draw.textbbox((0, 0), letter, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - tw//2 - bbox[0], cy - th//2 - bbox[1]),
              letter, font=font, fill=(255, 255, 255, 255))
    return ImageReader(img)

def central_image(card_id: str, card: dict, ac: tuple) -> ImageReader:
    # Letters always render as a styled letter, ignoring the generic 🔤 emoji
    if card_id.startswith("letra_"):
        return render_letter(card.get(BASE_LANG, "?"), ac)
    # Try emoji rendering (requires NotoColorEmoji)
    emoji = card.get("emoji", "")
    if emoji:
        rendered = render_emoji(emoji)
        if rendered:
            return rendered
    # Fallback: word badge
    return render_word_badge(card.get(BASE_LANG, "?"), ac)

# ── PDF layout ────────────────────────────────────────────────────────────────
W, H   = A4
COLS   = args.cols
ROWS   = args.rows
CARD_W = 88 * mm
CARD_H = 88 * mm
PAD_X  = (W - COLS * CARD_W) / (COLS + 1)
PAD_Y  = (H - ROWS * CARD_H) / (ROWS + 1)

def draw_card(c, cat, card_id, card, cx, cy):
    style = CAT_STYLE.get(cat, {"bg": (1, 1, 1), "ac": (0.4, 0.4, 0.4)})
    bg, ac = style["bg"], style["ac"]

    # Shadow
    c.setFillColorRGB(0.78, 0.78, 0.78)
    c.roundRect(cx + 3, cy - 3, CARD_W, CARD_H, 10, fill=1, stroke=0)

    # Card background
    c.setFillColorRGB(*bg)
    c.setStrokeColorRGB(*ac)
    c.setLineWidth(1.8)
    c.roundRect(cx, cy, CARD_W, CARD_H, 10, fill=1, stroke=1)

    # Category banner
    bar_h = 13 * mm
    c.setFillColorRGB(*ac)
    c.roundRect(cx, cy + CARD_H - bar_h, CARD_W, bar_h, 10, fill=1, stroke=0)
    c.rect(cx, cy + CARD_H - bar_h, CARD_W, bar_h / 2, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawCentredString(cx + CARD_W / 2, cy + CARD_H - 7.5 * mm, cat.upper())

    # Central image
    img_sz      = 50 * mm
    text_area_h = 22 * mm
    available_h = CARD_H - bar_h - text_area_h
    img_x = cx + (CARD_W - img_sz) / 2
    img_y = cy + text_area_h + (available_h - img_sz) / 2
    c.drawImage(
        central_image(card_id, card, ac),
        img_x, img_y, width=img_sz, height=img_sz,
        mask="auto", preserveAspectRatio=True,
    )

    # Base language word
    base_word = card.get(BASE_LANG, "")
    fs = 15 if len(base_word) <= 10 else 12 if len(base_word) <= 16 else 10
    c.setFillColorRGB(0.10, 0.10, 0.10)
    c.setFont("Helvetica-Bold", fs)
    c.drawCentredString(cx + CARD_W / 2, cy + 13.5 * mm, base_word)

    # Other languages
    c.setFont("Helvetica", 7.5)
    c.setFillColorRGB(0.38, 0.38, 0.38)
    others = [lk for lk in LANG_KEYS if lk != BASE_LANG]
    for j, lk in enumerate(others):
        label = f"{LANG_LABEL[lk]}: {card.get(lk, '')}"
        c.drawCentredString(cx + CARD_W / 2, cy + (8.5 - j * 4) * mm, label)

    # QR code (corner)
    qr_sz = 14 * mm
    qr_x  = cx + CARD_W - qr_sz - 3 * mm
    qr_y  = cy + 2.5 * mm
    c.setFillColorRGB(1, 1, 1)
    c.setStrokeColorRGB(0.80, 0.80, 0.80)
    c.setLineWidth(0.4)
    c.roundRect(qr_x - 1.5, qr_y - 1.5, qr_sz + 3, qr_sz + 3, 3, fill=1, stroke=1)
    qr_widget            = rl_qr.QrCodeWidget(card_id)
    qr_widget.barWidth   = qr_sz
    qr_widget.barHeight  = qr_sz
    d = Drawing(qr_sz, qr_sz)
    d.add(qr_widget)
    renderPDF.draw(d, c, qr_x, qr_y)

# ── Generate PDF ──────────────────────────────────────────────────────────────
out      = Path(args.out)
c        = rl_canvas.Canvas(str(out), pagesize=A4)
langs_str = " | ".join(LANG_LABEL[lk] for lk in LANG_KEYS)
c.setTitle(f"Lang Cards — {langs_str}")
c.setAuthor("Lang Card Reader")

per_page = COLS * ROWS
total    = len(all_cards)
pages    = (total + per_page - 1) // per_page
print(f"📄 Generating {total} cards across {pages} page(s) → {out.name}")

for page_i in range(pages):
    if page_i > 0:
        c.showPage()

    batch = all_cards[page_i * per_page : (page_i + 1) * per_page]
    for i, (cat, card_id, card) in enumerate(batch):
        col = i % COLS
        row = i // COLS
        cx  = PAD_X + col * (CARD_W + PAD_X)
        cy  = H - PAD_Y - (row + 1) * CARD_H - row * PAD_Y
        draw_card(c, cat, card_id, card, cx, cy)

    # Cut guides
    c.setStrokeColorRGB(0.72, 0.72, 0.72)
    c.setLineWidth(0.3)
    c.setDash(4, 5)
    for col in range(1, COLS):
        x = PAD_X + col * (CARD_W + PAD_X) - PAD_X / 2
        c.line(x, 8, x, H - 8)
    for row in range(1, ROWS):
        y = H - PAD_Y - row * (CARD_H + PAD_Y) + PAD_Y / 2
        c.line(8, y, W - 8, y)
    c.setDash()

    # Footer
    c.setFont("Helvetica", 6.5)
    c.setFillColorRGB(0.62, 0.62, 0.62)
    c.drawCentredString(
        W / 2, 6 * mm,
        f"Lang Cards  {langs_str}  •  Page {page_i + 1}/{pages}  •  Cut along dashed lines",
    )

c.save()
import os
sz = os.path.getsize(out)
print(f"✅ {out}  ({sz // 1024} KB) — open to review before printing!")
