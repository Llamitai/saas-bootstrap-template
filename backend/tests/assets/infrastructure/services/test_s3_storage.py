import threading

import pytest
from expects import be_false, equal, expect

from src.assets.infrastructure.services import s3_storage
from src.common.domain.entities.common.in_memory_file import InMemoryFile


class FakeS3Client:
    def __init__(self, threads: list[int]):
        self.threads = threads
        self.keys: list[str] = []

    def put_object(self, Bucket: str, Key: str, Body: bytes) -> None:
        self.threads.append(threading.get_ident())
        self.keys.append(Key)


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch) -> FakeS3Client:
    client = FakeS3Client(threads=[])
    monkeypatch.setattr(s3_storage, "get_s3_client", lambda: client)
    return client


async def test_upload_file__runs_boto3_off_the_event_loop_thread(fake_client: FakeS3Client):
    uploaded = await s3_storage.S3StorageService().upload_file(
        InMemoryFile(file_path="tenants/acme/logo.png", file_bytes=b"png")
    )

    expect(uploaded.file_path).to(equal("tenants/acme/logo.png"))
    expect(fake_client.keys).to(equal(["tenants/acme/logo.png"]))
    expect(threading.get_ident() in fake_client.threads).to(be_false)
