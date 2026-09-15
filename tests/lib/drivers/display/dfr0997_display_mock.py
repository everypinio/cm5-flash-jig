import logging
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont

    PIL_AVAILABLE = True
except ModuleNotFoundError:
    PIL_AVAILABLE = False


from tests.lib.drivers.display.dfr0997_display_interface import (
    BLACK,
    DFR0997DisplayInterface,
    rgb24,
)


class DFR0997MockDisplay(DFR0997DisplayInterface):
    """PIL-based mock implementation for DFR0997 display."""

    def __init__(self) -> None:
        self._mock_image = None
        self._mock_draw = None
        self._mock_font = None

        if PIL_AVAILABLE:
            try:
                self._mock_image = Image.new("RGB", (320, 240), (0, 0, 0))
                self._mock_draw = ImageDraw.Draw(self._mock_image)
                self._mock_font = ImageFont.load_default()
            except Exception as e:
                logging.warning(f"Failed to initialize Pillow mock display: {e}")
        else:
            logging.warning(
                "Pillow not available; mock display will not render images."
            )

        self._mock_logger = logging.getLogger("DFR0997Mock")
        if not self._mock_logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
            self._mock_logger.addHandler(handler)
            self._mock_logger.setLevel(logging.INFO)

    def close(self) -> None:
        pass

    def _update_mock_display(self) -> None:
        if self._mock_image:
            try:
                self._mock_image.save("mock_display.png")
            except Exception as e:
                self._mock_logger.error(f"Failed to save mock display image: {e}")

    def clear(self, delay_s: float = 1.5) -> None:
        if self._mock_image:
            self._mock_image = Image.new("RGB", (320, 240), (0, 0, 0))
            self._mock_draw = ImageDraw.Draw(self._mock_image)
            self._update_mock_display()
        self._mock_logger.info(f"Display CLEAR (delay={delay_s}s)")

    def background(self, color: int, delay_s: float = 0.3) -> None:
        if self._mock_image:
            rgb = tuple(rgb24(color))
            self._mock_image = Image.new("RGB", (320, 240), rgb)
            self._mock_draw = ImageDraw.Draw(self._mock_image)
            self._update_mock_display()
        self._mock_logger.info(f"Display BG_COLOR: {hex(color)} (delay={delay_s}s)")

    def text(
        self,
        x: int,
        y: int,
        value: str,
        *,
        size: int = 1,
        color: int = BLACK,
        obj_id: int = 1,
    ) -> None:
        if self._mock_image and self._mock_draw:
            rgb = tuple(rgb24(color))
            self._mock_draw.text((x, y), value, fill=rgb, font=self._mock_font)
            self._update_mock_display()
        self._mock_logger.info(
            f"Display TEXT at ({x}, {y}): {value} (color={hex(color)}, size={size})"
        )

    def draw_pixel(self, x: int, y: int, color: int, *, obj_id: int = 1) -> None:
        if self._mock_image and self._mock_draw:
            rgb = tuple(rgb24(color))
            self._mock_draw.point((x, y), fill=rgb)
            self._update_mock_display()
        self._mock_logger.info(f"Display PIXEL at ({x}, {y}): {hex(color)}")

    def draw_rect(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        *,
        fill_color: int,
        border_color: int | None = None,
        border_width: int = 0,
        rounded: int = 0,
        obj_id: int = 1,
    ) -> None:
        if self._mock_image and self._mock_draw:
            fill_rgb = tuple(rgb24(fill_color))
            border_rgb = tuple(
                rgb24(border_color if border_color is not None else fill_color)
            )
            self._mock_draw.rectangle(
                [x, y, x + width, y + height],
                fill=fill_rgb,
                outline=border_rgb,
                width=border_width,
            )
            self._update_mock_display()
        self._mock_logger.info(f"Display RECT at ({x}, {y}) {width}x{height}")

    def draw_icon_external(
        self,
        x: int,
        y: int,
        filename: str | Path,
        *,
        zoom: int = 256,
        obj_id: int = 1,
    ) -> None:
        if self._mock_image and self._mock_draw:
            try:
                img = Image.open(str(filename)).convert("RGB")
                # Simple zoom simulation by resizing
                w, h = img.size
                new_w = int(w * (zoom / 256))
                new_h = int(h * (zoom / 256))
                img = img.resize((new_w, new_h))
                self._mock_image.paste(img, (x, y))
                self._update_mock_display()
            except Exception as e:
                self._mock_logger.error(f"Failed to draw icon {filename}: {e}")
        self._mock_logger.info(
            f"Display ICON_EXTERNAL: {filename} at ({x}, {y}) zoom={zoom}"
        )

    def background_image(self, filename: str | Path, *, location: int = 1) -> None:
        if self._mock_image:
            try:
                fn_str = str(filename)
                img = Image.open(fn_str).convert("RGB").resize((320, 240))
                self._mock_image.paste(img, (0, 0))
                self._update_mock_display()
            except Exception as e:
                self._mock_logger.error(
                    f"Failed to load background image {filename}: {e}"
                )
        self._mock_logger.info(f"Display BG_IMAGE: {filename} (location={location})")
