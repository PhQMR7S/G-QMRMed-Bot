"""Deterministic quality gates for generated infographic artifacts."""

from __future__ import annotations

import struct

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class RenderQualityError(RuntimeError):
    """Raised when a generated artifact violates the output contract."""


def validate_svg_contract(
    svg: str,
    *,
    title: str,
    watermark: str,
    width: int,
    height: int,
) -> None:
    """Validate the deterministic SVG boundary before rasterization."""
    if not svg.strip():
        raise RenderQualityError("svg_quality_empty")
    required = (
        f'width="{width}"',
        f'height="{height}"',
        "<svg ",
        title,
        watermark,
    )
    if any(fragment not in svg for fragment in required):
        raise RenderQualityError("svg_quality_contract_failed")
    if "<script" in svg.lower():
        raise RenderQualityError("svg_quality_script_forbidden")


def validate_png_contract(
    data: bytes,
    *,
    width: int,
    height: int,
) -> None:
    """Validate PNG signature and actual IHDR dimensions, not only metadata."""
    if len(data) < 24 or data[:8] != PNG_SIGNATURE:
        raise RenderQualityError("png_quality_invalid_signature")
    chunk_length = struct.unpack(">I", data[8:12])[0]
    chunk_type = data[12:16]
    if chunk_type != b"IHDR" or chunk_length < 8:
        raise RenderQualityError("png_quality_missing_ihdr")
    actual_width, actual_height = struct.unpack(">II", data[16:24])
    if (actual_width, actual_height) != (width, height):
        raise RenderQualityError("png_quality_dimensions_mismatch")


__all__ = ["RenderQualityError", "validate_png_contract", "validate_svg_contract"]
