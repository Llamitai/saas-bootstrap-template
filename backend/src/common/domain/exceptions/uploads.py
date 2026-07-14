from src.common.domain.constants import status
from src.common.domain.exceptions._base import DomainError


class ImageTooLargeError(DomainError):
    def __init__(self, context=None):
        super().__init__(
            code="uploads.ImageTooLarge",
            message="Image exceeds the maximum allowed size",
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            context=context,
        )


class InvalidImageTypeError(DomainError):
    def __init__(self, context=None):
        super().__init__(
            code="uploads.InvalidImageType",
            message="File is not a supported image type (jpeg, png or webp)",
            status_code=status.HTTP_400_BAD_REQUEST,
            context=context,
        )
