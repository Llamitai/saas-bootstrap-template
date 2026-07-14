"""Unit tests for the shared image-upload validator."""

from io import BytesIO

import pytest
from expects import be_none, equal, expect
from fastapi import UploadFile

from src.common.domain.exceptions.uploads import ImageTooLargeError, InvalidImageTypeError
from src.common.infrastructure.helpers.image_upload import (
    MAX_IMAGE_UPLOAD_BYTES,
    read_validated_image,
    sniff_image_type,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 64
WEBP_BYTES = b"RIFF\x24\x00\x00\x00WEBP" + b"\x00" * 64


def _build_upload(data: bytes, size: int | None = None) -> UploadFile:
    return UploadFile(file=BytesIO(data), size=size, filename="upload.bin")


@pytest.mark.parametrize(
    ("header", "expected_type"),
    [
        (PNG_BYTES, "png"),
        (JPEG_BYTES, "jpeg"),
        (WEBP_BYTES, "webp"),
    ],
)
def test_sniff_image_type__detects_whitelisted_signatures(header: bytes, expected_type: str):
    result = sniff_image_type(header)

    expect(result).to(equal(expected_type))


@pytest.mark.parametrize(
    "header",
    [
        b"",
        b"GIF89a" + b"\x00" * 16,
        b"%PDF-1.7" + b"\x00" * 16,
        b"RIFF\x24\x00\x00\x00WAVE",  # RIFF container but not WEBP
        b"\x89PN",  # truncated PNG magic
    ],
)
def test_sniff_image_type__returns_none_for_unknown_signatures(header: bytes):
    result = sniff_image_type(header)

    expect(result).to(be_none)


async def test_read_validated_image__accepts_valid_png():
    upload = _build_upload(PNG_BYTES, size=len(PNG_BYTES))

    result = await read_validated_image(upload)

    expect(result).to(equal(PNG_BYTES))


@pytest.mark.parametrize("body", [JPEG_BYTES, WEBP_BYTES])
async def test_read_validated_image__accepts_other_whitelisted_types(body: bytes):
    upload = _build_upload(body, size=len(body))

    result = await read_validated_image(upload)

    expect(result).to(equal(body))


async def test_read_validated_image__rejects_oversized_declared_size_without_reading():
    upload = _build_upload(PNG_BYTES, size=MAX_IMAGE_UPLOAD_BYTES + 1)

    with pytest.raises(ImageTooLargeError):
        await read_validated_image(upload)


async def test_read_validated_image__rejects_oversized_body_when_size_is_undeclared():
    body = PNG_BYTES + b"\x00" * 128
    upload = _build_upload(body, size=None)

    with pytest.raises(ImageTooLargeError):
        await read_validated_image(upload, max_size_bytes=32)


async def test_read_validated_image__rejects_bad_magic_bytes():
    upload = _build_upload(b"<script>alert(1)</script>", size=25)

    with pytest.raises(InvalidImageTypeError):
        await read_validated_image(upload)


async def test_read_validated_image__rejects_spoofed_extension_content():
    upload = _build_upload(b"%PDF-1.7" + b"\x00" * 64, size=72)

    with pytest.raises(InvalidImageTypeError):
        await read_validated_image(upload)


async def test_read_validated_image__rejects_empty_file():
    upload = _build_upload(b"", size=0)

    with pytest.raises(InvalidImageTypeError):
        await read_validated_image(upload)
