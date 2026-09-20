#!/usr/bin/env python3
"""
barcode_stamper.py — Optical 8x18 Data Matrix badge generator and stamper for MaMo proxies.

Encodes deck, slot, and player information into an 8x18 rectangular Data Matrix
barcode placed in the bottom center footer of the card (where the authenticity
hologram/stamp normally sits on real Magic cards).
"""

from pathlib import Path
from typing import Optional, Union

try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    from pystrich.datamatrix import DataMatrixEncoder
    HAS_PYSTRICH = True
except ImportError:
    HAS_PYSTRICH = False


def is_barcode_available() -> bool:
    """Return True if both PIL and pystrich are installed."""
    return HAS_PIL and HAS_PYSTRICH


def generate_barcode_badge(
    payload_hex: str,
    mod_scale: int = 4,
    qz_x: int = 4,
    qz_y: int = 3,
) -> Optional["Image.Image"]:
    """
    Generate an 8x18 Data Matrix badge as an RGBA PIL Image.

    Badge design:
      - Rectangular Data Matrix symbol (18 columns x 8 rows)
      - Scaled to (18 * mod_scale) x (8 * mod_scale), default 72x32 px
      - Rounded white pill container with subtle gray border
      - Total stamp dimensions: 80x38 px at default scale
    """
    if not is_barcode_available():
        return None

    cleaned_payload = payload_hex.strip().upper()
    try:
        enc = DataMatrixEncoder(cleaned_payload, symbol_shape="rectangular", quiet_zone=0)
        dm_raw = enc.get_pilimage(1).convert("L")
    except Exception as exc:
        print(f"Warning: Failed to encode Data Matrix for payload '{payload_hex}': {exc}")
        return None

    dm_w = 18 * mod_scale
    dm_h = 8 * mod_scale
    dm_scaled = dm_raw.resize((dm_w, dm_h), Image.Resampling.NEAREST)

    stamp_w = dm_w + 2 * qz_x
    stamp_h = dm_h + 2 * qz_y

    stamp = Image.new("RGBA", (stamp_w, stamp_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(stamp)
    draw.rounded_rectangle(
        [0, 0, stamp_w - 1, stamp_h - 1],
        radius=5,
        fill=(255, 255, 255, 255),
        outline=(130, 130, 130, 255),
        width=1,
    )

    # Paste black barcode modules using the inverted scaled mask
    stamp.paste(
        Image.new("RGBA", (dm_w, dm_h), (0, 0, 0, 255)),
        (qz_x, qz_y),
        mask=Image.eval(dm_scaled, lambda a: 255 - a),
    )

    return stamp


def stamp_card_image(
    base_image: Union[str, Path, "Image.Image"],
    payload_hex: str,
    output_path: Optional[Union[str, Path]] = None,
) -> Optional["Image.Image"]:
    """
    Stamp an 8x18 Data Matrix badge onto the card's bottom footer.

    Positioning:
      - Centered horizontally at width // 2
      - Positioned in bottom black footer: y = round(height * (872 / 936))
        (for standard 672x936 Scryfall images: y=872..910, avoiding text box border at y=868)
    """
    if not is_barcode_available():
        return None

    badge = generate_barcode_badge(payload_hex)
    if badge is None:
        return None

    if isinstance(base_image, (str, Path)):
        img = Image.open(str(base_image)).convert("RGBA")
    else:
        img = base_image.convert("RGBA")

    w, h = img.size
    badge_w, badge_h = badge.size

    x = (w - badge_w) // 2
    # Scale y position proportionally to reference 936px card height
    y = round(h * (872.0 / 936.0))

    img.paste(badge, (x, y), badge)

    if output_path is not None:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        # Convert to RGB if saving as JPEG
        if out.suffix.lower() in (".jpg", ".jpeg"):
            img.convert("RGB").save(str(out), "JPEG", quality=95)
        else:
            img.save(str(out), "PNG")

    return img
