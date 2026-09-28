import asyncio

import bcrypt

# bcrypt is deliberately slow (~100-300 ms); it runs in a worker thread so a login
# or registration never blocks the event loop for every other request.


def _hash_password(raw_password: str) -> str:
    return bcrypt.hashpw(raw_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _check_password(raw_password: str, encoded_password: str) -> bool:
    try:
        return bcrypt.checkpw(raw_password.encode("utf-8"), encoded_password.encode("utf-8"))
    except ValueError, TypeError:
        return False


async def hash_password(raw_password: str) -> str:
    return await asyncio.to_thread(_hash_password, raw_password)


async def check_password(raw_password: str, encoded_password: str) -> bool:
    return await asyncio.to_thread(_check_password, raw_password, encoded_password)
