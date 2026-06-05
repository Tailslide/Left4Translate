"""Generate res/icon.ico for the Left4Translate desktop app.

A dark rounded tile with two overlapping speech bubbles — an orange one
(brand accent) and a blue one (survivor accent) — evoking "translation".
Run from the repo root: ``python res/make_icon.py``.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

BG = (19, 19, 22, 255)        # #131316
ORANGE = (224, 90, 43, 255)   # #e05a2b
BLUE = (90, 169, 230, 255)    # #5aa9e6
TEXT = (255, 255, 255, 255)

SIZE = 1024  # supersample, then downscale to icon sizes


def _rounded(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def _bubble(draw, box, radius, fill, tail_left):
    x0, y0, x1, y1 = box
    _rounded(draw, box, radius, fill)
    # Little speech-bubble tail at the bottom.
    if tail_left:
        tx = x0 + (x1 - x0) * 0.22
        draw.polygon([(tx, y1 - radius * 0.4), (tx + radius * 0.9, y1 - radius * 0.4),
                      (tx, y1 + radius * 0.7)], fill=fill)
    else:
        tx = x1 - (x1 - x0) * 0.22
        draw.polygon([(tx, y1 - radius * 0.4), (tx - radius * 0.9, y1 - radius * 0.4),
                      (tx, y1 + radius * 0.7)], fill=fill)


def _font(size, cjk=False):
    names = (
        ["/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "wqy-zenhei.ttc",
         "msyh.ttc", "NotoSansCJK-Bold.ttc"]
        if cjk else
        ["DejaVuSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf"]
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _centered_text(draw, center, text, font, fill):
    l, t, r, b = draw.textbbox((0, 0), text, font=font)
    draw.text((center[0] - (r - l) / 2 - l, center[1] - (b - t) / 2 - t),
              text, font=font, fill=fill)


def build() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    m = SIZE * 0.06
    _rounded(d, (m, m, SIZE - m, SIZE - m), radius=SIZE * 0.20, fill=BG)

    # Back (blue) bubble, upper-right; front (orange) bubble, lower-left.
    _bubble(d, (SIZE * 0.40, SIZE * 0.20, SIZE * 0.82, SIZE * 0.52),
            radius=SIZE * 0.07, fill=BLUE, tail_left=False)
    _bubble(d, (SIZE * 0.18, SIZE * 0.44, SIZE * 0.62, SIZE * 0.78),
            radius=SIZE * 0.07, fill=ORANGE, tail_left=True)

    # Glyphs hinting "translate": a latin A and a CJK-ish mark.
    _centered_text(d, (SIZE * 0.61, SIZE * 0.355), "A", _font(int(SIZE * 0.16)), TEXT)
    _centered_text(d, (SIZE * 0.40, SIZE * 0.595), "文", _font(int(SIZE * 0.18), cjk=True), TEXT)
    return img


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "icon.ico")
    master = build()
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    icons = [master.resize(s, Image.LANCZOS) for s in sizes]
    icons[0].save(out, format="ICO", sizes=sizes)
    # Also emit a PNG preview for docs / quick inspection.
    master.resize((256, 256), Image.LANCZOS).save(os.path.join(here, "icon_preview.png"))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
