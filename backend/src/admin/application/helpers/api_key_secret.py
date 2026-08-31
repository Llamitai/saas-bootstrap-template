import hashlib

from src.common.constants import API_KEY_SECRET_PREFIX, API_KEY_VISIBLE_PREFIX_CHARS


def get_api_key_prefix(raw_secret: str) -> str:
    """
    Extracts the prefix from the raw secret of an API key.
    """
    return f"{API_KEY_SECRET_PREFIX}{raw_secret[:API_KEY_VISIBLE_PREFIX_CHARS]}"


def hash_api_key_secret(raw_secret: str) -> str:
    """
    Hashes the raw secret of an API key.
    """
    return hashlib.sha256(raw_secret.encode("utf-8")).hexdigest()
