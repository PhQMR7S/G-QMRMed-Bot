import struct

import pytest

from gqmrmed.services.quality import (
    RenderQualityError,
    validate_png_contract,
    validate_svg_contract,
)


def _png(width: int, height: int) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">I", 8) + b"IHDR" + struct.pack(">II", width, height)
    return signature + ihdr + b"\x00" * 4


def test_png_quality_checks_actual_dimensions() -> None:
    validate_png_contract(_png(1080, 1350), width=1080, height=1350)

    with pytest.raises(RenderQualityError, match="png_quality_dimensions_mismatch"):
        validate_png_contract(_png(1000, 1350), width=1080, height=1350)


def test_png_quality_rejects_non_png_bytes() -> None:
    with pytest.raises(RenderQualityError, match="png_quality_invalid_signature"):
        validate_png_contract(b"not-an-image", width=1080, height=1350)


def test_svg_quality_requires_contract_and_forbids_scripts() -> None:
    svg = '<svg width="1080" height="1350"><text>DKA</text><text>GQMRMed</text></svg>'
    validate_svg_contract(
        svg,
        title="DKA",
        watermark="GQMRMed",
        width=1080,
        height=1350,
    )

    with pytest.raises(RenderQualityError, match="svg_quality_script_forbidden"):
        validate_svg_contract(
            svg.replace("</svg>", "<script>alert(1)</script></svg>"),
            title="DKA",
            watermark="GQMRMed",
            width=1080,
            height=1350,
        )
