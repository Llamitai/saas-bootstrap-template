from abc import ABC, abstractmethod

ROTATION_PENDING = "__pending__"


class TokenStore(ABC):
    """Allowlist of refresh-token sessions and single-use tokens.

    Only what the store holds is valid, so a lost or evicted key rejects the token
    (fail-closed); nothing here ever makes a revoked token valid again.
    """

    # -> Sessions: one entry per (subject, session id) holding its current refresh jti.

    @abstractmethod
    async def open_session(self, sub: str, sid: str, jti: str, ttl: int, max_sessions: int, namespace: str):
        """Store a new session and close the least recently used ones beyond `max_sessions`."""
        raise NotImplementedError

    @abstractmethod
    async def current_jti(self, sub: str, sid: str, namespace: str) -> str | None:
        """The session's current refresh jti, or None when the session is closed or lost."""
        raise NotImplementedError

    @abstractmethod
    async def rotate_if_current(
        self, sub: str, sid: str, current_jti: str, new_jti: str, ttl: int, namespace: str
    ) -> bool:
        """Atomically replace the session's jti only while it still equals `current_jti`."""
        raise NotImplementedError

    @abstractmethod
    async def close_session(self, sub: str, sid: str, namespace: str):
        raise NotImplementedError

    @abstractmethod
    async def close_all_sessions(self, sub: str, namespace: str):
        raise NotImplementedError

    # -> Rotation grace: the first caller claims the presented refresh jti, then
    # publishes the pair it issued so concurrent or late duplicates reuse it.

    @abstractmethod
    async def claim_rotation(self, jti: str, ttl: int, namespace: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def publish_rotation(self, jti: str, payload: str, ttl: int, namespace: str):
        raise NotImplementedError

    @abstractmethod
    async def get_rotation(self, jti: str, namespace: str) -> str | None:
        """The published payload, `ROTATION_PENDING` while claimed, or None."""
        raise NotImplementedError

    @abstractmethod
    async def release_rotation(self, jti: str, namespace: str):
        raise NotImplementedError

    # -> Single-use tokens (password reset): valid only while allowed, consumed once.

    @abstractmethod
    async def allow_one_shot(self, jti: str, ttl: int, namespace: str):
        raise NotImplementedError

    @abstractmethod
    async def consume_one_shot(self, jti: str, namespace: str) -> bool:
        """Remove the allowance; True only for the caller that removed it."""
        raise NotImplementedError
