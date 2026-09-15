"""Deterministic SVG-to-PNG rasterization for final Telegram delivery."""

from __future__ import annotations

from typing import cast

import cairosvg

from gqmrmed.rendering.layout import HEIGHT, WIDTH


class RasterRenderError(RuntimeError):
    """Raised when an infographic cannot be rasterized."""


def render_png(svg: str, *, width: int = WIDTH, height: int = HEIGHT) -> bytes:
    """Rasterize a complete SVG into a bounded 2:3 PNG."""
    if not svg.strip():
        raise RasterRenderError("svg_empty")
    if width <= 0 or height <= 0:
        raise RasterRenderError("invalid_raster_dimensions")
    if width * 3 != height * 2:
        raise RasterRenderError("raster_dimensions_must_be_2_3")
    try:
        data = cast(
            bytes,
            cairosvg.svg2png(
                bytestring=svg.encode("utf-8"),
                output_width=width,
                output_height=height,
            ),
        )
    except Exception as exc:
        raise RasterRenderError("svg_rasterization_failed") from exc
    if not data:
        raise RasterRenderError("svg_rasterization_empty")
    return data


__all__ = ["RasterRenderError", "render_png"]
