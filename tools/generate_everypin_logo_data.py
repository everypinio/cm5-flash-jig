from __future__ import annotations

import argparse
from pathlib import Path


DEFAULT_SOURCE = Path("images/everypin black pink 260x62.png")
DEFAULT_OUTPUT = Path("data/everypin_logo_data.py")
DEFAULT_X = 30
DEFAULT_Y = 89


def classify_pixel(pixel: tuple[int, ...]) -> int | None:
    r, g, b = pixel[:3]
    a = pixel[3] if len(pixel) > 3 else 255
    if a == 0 or (r > 245 and g > 245 and b > 245):
        return None
    if r > 150 and b > 150:
        return 1
    return 0


def image_runs(image: object) -> list[list[tuple[int, int, int]]]:
    rows: list[list[tuple[int, int, int]]] = []
    width, height = image.size

    for y in range(height):
        row: list[tuple[int, int, int]] = []
        x = 0
        while x < width:
            color_index = classify_pixel(image.getpixel((x, y)))
            if color_index is None:
                x += 1
                continue

            x0 = x
            while x + 1 < width:
                next_color = classify_pixel(image.getpixel((x + 1, y)))
                if next_color != color_index:
                    break
                x += 1

            row.append((color_index, x0, x))
            x += 1
        rows.append(row)

    return rows


def merge_vertical_runs(
    rows: list[list[tuple[int, int, int]]],
) -> list[tuple[int, int, int, int, int]]:
    rects: list[list[int]] = []
    active: dict[tuple[int, int, int], list[int]] = {}

    for y, row in enumerate(rows):
        next_active: dict[tuple[int, int, int], list[int]] = {}
        for color_index, x0, x1 in row:
            key = (color_index, x0, x1)
            if key in active:
                rect = active[key]
                rect[4] = y
            else:
                rect = [color_index, x0, x1, y, y]
                rects.append(rect)
            next_active[key] = rect
        active = next_active

    return [
        (color_index, x0, y0, x1 - x0 + 1, y1 - y0 + 1)
        for color_index, x0, x1, y0, y1 in rects
    ]


def render_module(
    *,
    source: Path,
    width: int,
    height: int,
    x: int,
    y: int,
    rects: list[tuple[int, int, int, int, int]],
) -> str:
    lines = [
        "from __future__ import annotations",
        "",
        f"# Generated from {source.as_posix()}.",
        "# Regenerate with tools/generate_everypin_logo_data.py.",
        "",
        f'LOGO_SOURCE = "{source.as_posix()}"',
        f"LOGO_WIDTH = {width}",
        f"LOGO_HEIGHT = {height}",
        f"LOGO_X = {x}",
        f"LOGO_Y = {y}",
        "",
        "# Tuples are (color_index, x, y, width, height); 0=black, 1=Everypin pink.",
        "LOGO_RECTS = (",
    ]
    lines.extend(f"    {rect!r}," for rect in rects)
    lines.append(")")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--x", type=int, default=DEFAULT_X)
    parser.add_argument("--y", type=int, default=DEFAULT_Y)
    args = parser.parse_args()

    try:
        from PIL import Image
    except ImportError as exc:
        raise SystemExit(
            "Pillow is required only to regenerate Everypin logo data. "
            "Install it with: python -m pip install pillow"
        ) from exc

    image = Image.open(args.source).convert("RGBA")
    rects = merge_vertical_runs(image_runs(image))
    args.output.write_text(
        render_module(
            source=args.source,
            width=image.width,
            height=image.height,
            x=args.x,
            y=args.y,
            rects=rects,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(rects)} rects to {args.output}")


if __name__ == "__main__":
    main()
