"""Shared validation for user-supplied image uploads.

Guards multipart image endpoints against two abuse vectors:

- Oversized bodies: the declared size is checked first, then the body is
  read in bounded chunks with a hard cap so an oversized (or lying)
  upload can never be fully buffered in memory.
- Content-type spoofing: the client-declared Content-Type is never
  trusted — the actual magic bytes are sniffed and matched against a
  whitelist of image signatures.
"""

from fastapi import UploadFile

from src.common.domain.exceptions.uploads import ImageTooLargeError, InvalidImageTypeError

MAX_IMAGE_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB

_READ_CHUNK_BYTES = 64 * 1024

# Magic-byte signatures per whitelisted type: every (offset, magic) pair must match.
_IMAGE_SIGNATURES: dict[str, tuple[tuple[int, bytes], ...]] = {
    "jpeg": ((0, b"\xff\xd8\xff"),),
    "png": ((0, b"\x89PNG\r\n\x1a\n"),),
    "webp": ((0, b"RIFF"), (8, b"WEBP")),
}


def sniff_image_type(header: bytes) -> str | None:
    """Return the image type detected from its magic bytes, or ``None``."""
    for image_type, signature in _IMAGE_SIGNATURES.items():
        if all(header[offset : offset + len(magic)] == magic for offset, magic in signature):
            return image_type
    return None


async def read_validated_image(
    upload: UploadFile,
    max_size_bytes: int = MAX_IMAGE_UPLOAD_BYTES,
) -> bytes:
    """Read an uploaded image enforcing a size cap and a magic-byte whitelist.

    Raises ``ImageTooLargeError`` (413) when the upload exceeds
    ``max_size_bytes`` and ``InvalidImageTypeError`` (400) when the content
    is not a whitelisted image format.
    """
    if upload.size is not None and upload.size > max_size_bytes:
        raise ImageTooLargeError(context={"max_size_bytes": max_size_bytes})

    chunks: list[bytes] = []
    total_read = 0

    while chunk := await upload.read(_READ_CHUNK_BYTES):
        total_read += len(chunk)
        if total_read > max_size_bytes:
            raise ImageTooLargeError(context={"max_size_bytes": max_size_bytes})
        if not chunks and sniff_image_type(chunk) is None:
            raise InvalidImageTypeError()
        chunks.append(chunk)

    if not chunks:
        raise InvalidImageTypeError()

    return b"".join(chunks)
