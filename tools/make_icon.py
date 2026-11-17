"""Генерирует assets/icon.ico для окна и exe.

Иконка рисуется кодом, чтобы в репозитории не лежал бинарник неизвестного
происхождения: чип с контактами — узнаваемый символ менеджера устройств.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 256
BG = (15, 18, 22, 255)
BORDER = (37, 46, 58, 255)
ACCENT = (76, 154, 255, 255)
TEXT = (231, 238, 247, 255)


def draw_icon() -> Image.Image:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        (6, 6, SIZE - 6, SIZE - 6), radius=56, fill=BG, outline=BORDER, width=4
    )
    draw.rounded_rectangle(
        (80, 80, 176, 176), radius=20, outline=ACCENT, width=11
    )
    draw.rounded_rectangle((110, 110, 146, 146), radius=7, fill=ACCENT)

    for offset in (96, 128, 160):
        draw.line((58, offset, 80, offset), fill=TEXT, width=9)
        draw.line((176, offset, 198, offset), fill=TEXT, width=9)
        draw.line((offset, 58, offset, 80), fill=TEXT, width=9)
        draw.line((offset, 176, offset, 198), fill=TEXT, width=9)

    return image


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    assets = root / "assets"
    assets.mkdir(exist_ok=True)
    icon = draw_icon()
    icon.save(assets / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    icon.save(assets / "icon.png")
    print(f"Готово: {assets / 'icon.ico'}")


if __name__ == "__main__":
    main()
