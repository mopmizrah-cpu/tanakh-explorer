"""Draw the application icon (icon.ico for Windows, icon.png for the web UI).

Run: python tools/make_icon.py   (needs Pillow; not a runtime dependency)
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FRONT = ROOT / "tanakh_explorer" / "frontend"
FONT = FRONT / "fonts" / "NotoSerifHebrew.ttf"
NAVY, NAVY2, GOLD = (24, 47, 79), (47, 93, 138), (236, 196, 92)


def draw(size: int = 512) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    # vertical gradient in a rounded square
    grad = Image.new("RGBA", (size, size))
    gd = ImageDraw.Draw(grad)
    for y in range(size):
        t = y / (size - 1)
        gd.line([(0, y), (size, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(NAVY2, NAVY)) + (255,))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=size // 5, fill=255)
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    inset = size // 14
    d.rounded_rectangle([inset, inset, size - 1 - inset, size - 1 - inset], radius=size // 7,
                        outline=GOLD, width=max(2, size // 40))
    font = ImageFont.truetype(str(FONT), int(size * 0.62))
    try:
        font.set_variation_by_axes([800, 100])  # weight, width
    except Exception:
        pass
    letter = "ת"
    box = d.textbbox((0, 0), letter, font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    d.text(((size - w) / 2 - box[0], (size - h) / 2 - box[1]), letter, font=font, fill=GOLD)
    return img


if __name__ == "__main__":
    big = draw(512)
    big.resize((192, 192), Image.LANCZOS).save(FRONT / "icon.png")
    big.save(FRONT / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("wrote", FRONT / "icon.ico", FRONT / "icon.png")
