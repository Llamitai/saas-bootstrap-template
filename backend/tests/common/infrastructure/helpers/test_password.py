import threading

import bcrypt
import pytest
from expects import be_false, be_true, equal, expect

from src.common.infrastructure.helpers import password


@pytest.fixture
def bcrypt_threads(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    threads: list[int] = []
    original_hashpw, original_checkpw = bcrypt.hashpw, bcrypt.checkpw

    def hashpw(raw: bytes, salt: bytes) -> bytes:
        threads.append(threading.get_ident())
        return original_hashpw(raw, salt)

    def checkpw(raw: bytes, hashed: bytes) -> bool:
        threads.append(threading.get_ident())
        return original_checkpw(raw, hashed)

    monkeypatch.setattr(password.bcrypt, "hashpw", hashpw)
    monkeypatch.setattr(password.bcrypt, "checkpw", checkpw)
    return threads


async def test_hash_password__runs_bcrypt_off_the_event_loop_thread(bcrypt_threads: list[int]):
    hashed = await password.hash_password("s3cret-password")
    matches = await password.check_password("s3cret-password", hashed)

    expect(matches).to(be_true)
    expect(len(bcrypt_threads)).to(equal(2))
    expect(threading.get_ident() in bcrypt_threads).to(be_false)


async def test_check_password__rejects_a_wrong_password():
    hashed = await password.hash_password("s3cret-password")

    expect(await password.check_password("other-password", hashed)).to(be_false)


async def test_check_password__rejects_a_malformed_hash():
    expect(await password.check_password("s3cret-password", "not-a-bcrypt-hash")).to(be_false)
