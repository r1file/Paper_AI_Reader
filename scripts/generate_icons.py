from __future__ import annotations

import math
import shutil
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets"
ICONSET_DIR = ASSET_DIR / "app-icon-macos.iconset"


@dataclass(frozen=True)
class PlatformIcon:
    name: str
    size: int


MACOS = PlatformIcon("macos", 1024)
WINDOWS = PlatformIcon("windows", 1024)
LINUX = PlatformIcon("linux", 1024)


def rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    clean = hex_color.lstrip("#")
    return tuple(int(clean[index : index + 2], 16) for index in (0, 2, 4)) + (alpha,)


def lerp(start: int, end: int, amount: float) -> int:
    return round(start + (end - start) * amount)


def lerp_color(start: tuple[int, int, int, int], end: tuple[int, int, int, int], amount: float) -> tuple[int, int, int, int]:
    return tuple(lerp(start[index], end[index], amount) for index in range(4))


def rounded_rect_gradient(
    size: int,
    rect: tuple[int, int, int, int],
    radius: int,
    top: tuple[int, int, int, int],
    bottom: tuple[int, int, int, int],
) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(rect, radius=radius, fill=255)
    gradient = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pixels = gradient.load()
    y0, y1 = rect[1], rect[3]
    for y in range(rect[1], rect[3] + 1):
        amount = (y - y0) / max(1, y1 - y0)
        color = lerp_color(top, bottom, amount)
        for x in range(rect[0], rect[2] + 1):
            pixels[x, y] = color
    layer.alpha_composite(gradient)
    layer.putalpha(mask)
    return layer


def drop_shadow(
    base: Image.Image,
    rect: tuple[int, int, int, int],
    radius: int,
    offset: tuple[int, int],
    blur: int,
    color: tuple[int, int, int, int],
) -> None:
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sx, sy = offset
    shifted = (rect[0] + sx, rect[1] + sy, rect[2] + sx, rect[3] + sy)
    ImageDraw.Draw(shadow).rounded_rectangle(shifted, radius=radius, fill=color)
    base.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(blur)))


def clear_tiny_alpha(image: Image.Image, threshold: int = 3) -> Image.Image:
    clean = image.copy()
    pixels = clean.load()
    for y in range(clean.height):
        for x in range(clean.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha <= threshold:
                pixels[x, y] = (red, green, blue, 0)
    return clean


def draw_document(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], *, radius: int, fold: int) -> None:
    x0, y0, x1, y1 = rect
    draw.rounded_rectangle(rect, radius=radius, fill=rgba("#f9fbff"), outline=rgba("#d4e1ee"), width=max(2, (x1 - x0) // 120))
    fold_points = [(x1 - fold, y0), (x1, y0 + fold), (x1 - fold, y0 + fold)]
    draw.polygon(fold_points, fill=rgba("#e8f0f8"))
    draw.line([(x1 - fold, y0), (x1 - fold, y0 + fold), (x1, y0 + fold)], fill=rgba("#c4d4e3"), width=max(2, fold // 32))

    line_h = max(10, (y1 - y0) // 31)
    line_radius = line_h // 2
    line_x = x0 + (x1 - x0) * 19 // 100
    line_y = y0 + (y1 - y0) * 35 // 100
    line_color = rgba("#9fb2c4")
    for width, dy in ((0.58, 0), (0.54, 72), (0.30, 144)):
        lx1 = line_x + int((x1 - x0) * width)
        draw.rounded_rectangle((line_x, line_y + dy, lx1, line_y + dy + line_h), radius=line_radius, fill=line_color)


def draw_network(draw: ImageDraw.ImageDraw, center: tuple[int, int], scale: float, *, glow: bool = False) -> None:
    cx, cy = center
    nodes = [
        (cx - int(120 * scale), cy - int(20 * scale), "#f6b64c"),
        (cx - int(120 * scale), cy + int(115 * scale), "#ffca55"),
        (cx + int(10 * scale), cy + int(35 * scale), "#ffcc55"),
        (cx + int(145 * scale), cy - int(20 * scale), "#34d3d2"),
        (cx + int(145 * scale), cy + int(115 * scale), "#42cfd2"),
        (cx + int(15 * scale), cy + int(190 * scale), "#9ad37c"),
    ]
    edges = [
        (0, 2),
        (1, 2),
        (2, 3),
        (2, 4),
        (2, 5),
        (0, 3),
        (1, 5),
        (3, 4),
    ]
    line_w = max(7, round(16 * scale))
    if glow:
        for left, right in edges:
            draw.line([nodes[left][:2], nodes[right][:2]], fill=rgba("#6ee9e5", 70), width=line_w * 3)
    for left, right in edges:
        draw.line([nodes[left][:2], nodes[right][:2]], fill=rgba("#e8fffb"), width=line_w)
        draw.line([nodes[left][:2], nodes[right][:2]], fill=rgba("#3ddbd7"), width=max(4, line_w // 2))
    for index, (x, y, color) in enumerate(nodes):
        radius = round((54 if index == 2 else 38) * scale)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=rgba("#ffffff"), outline=rgba("#eafcff"), width=max(2, round(8 * scale)))
        draw.ellipse(
            (x - radius + max(7, round(10 * scale)), y - radius + max(7, round(10 * scale)), x + radius - max(7, round(10 * scale)), y + radius - max(7, round(10 * scale))),
            fill=rgba(color),
        )


def draw_macos_icon() -> Image.Image:
    size = MACOS.size
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    tile = (104, 104, 920, 920)
    drop_shadow(img, tile, 196, (0, 24), 24, rgba("#0a1b2a", 64))
    img.alpha_composite(rounded_rect_gradient(size, tile, 196, rgba("#16406f"), rgba("#07182f")))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((122, 122, 902, 902), radius=176, outline=rgba("#61dcff", 96), width=8)
    draw.arc((114, 114, 910, 910), 32, 118, fill=rgba("#6be9ff", 172), width=14)
    draw.arc((116, 116, 908, 908), 174, 250, fill=rgba("#f2b94f", 180), width=15)
    draw_document(draw, (272, 214, 698, 786), radius=42, fold=118)
    draw_network(draw, (608, 522), 1.08, glow=True)
    return clear_tiny_alpha(img)


def draw_windows_icon() -> Image.Image:
    size = WINDOWS.size
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    tile = (96, 96, 928, 928)
    drop_shadow(img, tile, 92, (0, 18), 28, rgba("#0b1320", 42))
    img.alpha_composite(rounded_rect_gradient(size, tile, 92, rgba("#0f6cbd"), rgba("#073763")))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((124, 124, 900, 900), radius=72, outline=rgba("#8ee8ff", 86), width=5)
    draw_document(draw, (294, 206, 696, 768), radius=22, fold=100)
    draw_network(draw, (616, 514), 0.98, glow=False)
    return clear_tiny_alpha(img)


def draw_linux_icon() -> Image.Image:
    size = LINUX.size
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    drop_shadow(img, (116, 116, 908, 908), 176, (0, 20), 32, rgba("#0b1b1c", 50))
    draw.rounded_rectangle((116, 116, 908, 908), radius=176, fill=rgba("#0b5d69"))
    draw.rounded_rectangle((146, 146, 878, 878), radius=146, outline=rgba("#87f4d8", 90), width=8)
    draw_document(draw, (306, 218, 676, 760), radius=34, fold=96)
    draw_network(draw, (600, 508), 0.94, glow=False)
    return clear_tiny_alpha(img)


def save_pngs() -> dict[str, Path]:
    ASSET_DIR.mkdir(exist_ok=True)
    images = {
        "macos": draw_macos_icon(),
        "windows": draw_windows_icon(),
        "linux": draw_linux_icon(),
    }
    paths = {}
    for name, image in images.items():
        path = ASSET_DIR / f"app-icon-{name}.png"
        image.save(path)
        paths[name] = path
    images["macos"].save(ASSET_DIR / "app-icon.png")
    return paths


def resized(source: Path, size: int) -> Image.Image:
    return Image.open(source).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)


def write_icns(source: Path) -> None:
    if ICONSET_DIR.exists():
        shutil.rmtree(ICONSET_DIR)
    ICONSET_DIR.mkdir()
    names = {
        "icon_16x16.png": 16,
        "icon_16x16@2x.png": 32,
        "icon_32x32.png": 32,
        "icon_32x32@2x.png": 64,
        "icon_128x128.png": 128,
        "icon_128x128@2x.png": 256,
        "icon_256x256.png": 256,
        "icon_256x256@2x.png": 512,
        "icon_512x512.png": 512,
        "icon_512x512@2x.png": 1024,
    }
    for name, size in names.items():
        resized(source, size).save(ICONSET_DIR / name)
    subprocess.run(["iconutil", "-c", "icns", str(ICONSET_DIR), "-o", str(ASSET_DIR / "app-icon-macos.icns")], check=True)
    shutil.rmtree(ICONSET_DIR)


def write_ico(source: Path) -> None:
    entries: list[tuple[int, bytes]] = []
    for size in (16, 24, 32, 48, 64, 128, 256):
        png_path = ASSET_DIR / f".app-icon-windows-{size}.png"
        resized(source, size).save(png_path)
        entries.append((size, png_path.read_bytes()))
        png_path.unlink()
    header = struct.pack("<HHH", 0, 1, len(entries))
    offset = 6 + 16 * len(entries)
    directory = bytearray()
    blob = bytearray()
    for size, data in entries:
        dimension = 0 if size == 256 else size
        directory.extend(struct.pack("<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(data), offset))
        blob.extend(data)
        offset += len(data)
    (ASSET_DIR / "app-icon-windows.ico").write_bytes(header + directory + blob)


def write_linux_sizes(source: Path) -> None:
    for size in (16, 32, 48, 64, 128, 256, 512):
        resized(source, size).save(ASSET_DIR / f"app-icon-linux-{size}.png")


def write_preview() -> None:
    checker = Image.new("RGBA", (1280, 560), rgba("#f7f8fb"))
    draw = ImageDraw.Draw(checker)
    for y in range(0, checker.height, 32):
        for x in range(0, checker.width, 32):
            if (x // 32 + y // 32) % 2 == 0:
                draw.rectangle((x, y, x + 31, y + 31), fill=rgba("#e7ebf1"))
    labels = [("macOS", "app-icon-macos.png"), ("Windows", "app-icon-windows.png"), ("Linux", "app-icon-linux.png")]
    for index, (label, filename) in enumerate(labels):
        x = 84 + index * 412
        icon = Image.open(ASSET_DIR / filename).convert("RGBA").resize((256, 256), Image.Resampling.LANCZOS)
        checker.alpha_composite(icon, (x, 86))
        small = icon.resize((64, 64), Image.Resampling.LANCZOS)
        checker.alpha_composite(small, (x + 96, 370))
        draw.text((x + 88, 460), label, fill=rgba("#152034"))
    checker.save(ASSET_DIR / "app-icon-preview.png")


def main() -> None:
    paths = save_pngs()
    write_icns(paths["macos"])
    write_ico(paths["windows"])
    write_linux_sizes(paths["linux"])
    write_preview()


if __name__ == "__main__":
    main()
