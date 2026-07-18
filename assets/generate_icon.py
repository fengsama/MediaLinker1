from pathlib import Path

from PIL import Image, ImageDraw


CANVAS = 1024
OUTPUT_DIR = Path(__file__).resolve().parent


def diagonal_gradient(start: str, end: str) -> Image.Image:
    start_rgb = tuple(bytes.fromhex(start.removeprefix("#")))
    end_rgb = tuple(bytes.fromhex(end.removeprefix("#")))
    image = Image.new("RGBA", (CANVAS, CANVAS))
    pixels = image.load()
    for y in range(CANVAS):
        for x in range(CANVAS):
            ratio = (x + y) / (2 * (CANVAS - 1))
            pixels[x, y] = tuple(
                round(left + (right - left) * ratio)
                for left, right in zip(start_rgb, end_rgb)
            ) + (255,)
    return image


def build_icon() -> Image.Image:
    icon = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(icon)
    draw.rounded_rectangle(
        (28, 28, CANVAS - 28, CANVAS - 28),
        radius=224,
        fill="#0d1521",
        outline="#1d3147",
        width=18,
    )

    link_mask = Image.new("L", (CANVAS, CANVAS), 0)
    link_draw = ImageDraw.Draw(link_mask)
    link_draw.arc((184, 274, 544, 750), 58, 302, fill=255, width=104)
    link_draw.arc((480, 274, 840, 750), 238, 482, fill=255, width=104)
    gradient = diagonal_gradient("#58f0c5", "#20a592")
    icon.alpha_composite(Image.composite(gradient, Image.new("RGBA", icon.size), link_mask))

    draw = ImageDraw.Draw(icon)
    draw.rounded_rectangle((354, 454, 670, 570), radius=44, fill="#f4f7ff")
    draw.rounded_rectangle((386, 482, 638, 542), radius=28, fill="#dbe5f4")
    return icon


if __name__ == "__main__":
    master = build_icon()
    master.resize((512, 512), Image.Resampling.LANCZOS).save(
        OUTPUT_DIR / "MediaLinker.png", optimize=True
    )
    master.save(
        OUTPUT_DIR / "MediaLinker.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
