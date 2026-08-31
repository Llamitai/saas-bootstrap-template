from src.common.domain.constants import status
from src.common.domain.exceptions import DomainError


class ApiKeyNotFoundError(DomainError):
    def __init__(self, context=None):
        super().__init__(
            code="admin.ApiKeyNotFound",
            message="Api key not found",
            status_code=status.HTTP_404_NOT_FOUND,
            context=context,
        )
