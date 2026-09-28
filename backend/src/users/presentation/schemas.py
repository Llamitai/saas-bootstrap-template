from uuid import UUID

from src.common.presentation.schemas.base import ApiSchema
from src.common.presentation.schemas.shared import EmailAddressResponse


class RegisteredUserResponse(ApiSchema):
    """RegisteredUserPresenter."""

    uuid: UUID
    username: str
    first_name: str | None
    last_name: str | None
    email_address: EmailAddressResponse | None
