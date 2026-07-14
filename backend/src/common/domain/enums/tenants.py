from src.common.domain.enums.base_enum import BaseEnum


class TenantRoleStatus(BaseEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class TenantStatus(BaseEnum):
    ACTIVE = "ACTIVE"
    PENDING = "PENDING"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"


class TenantUserInvitationStatus(BaseEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
