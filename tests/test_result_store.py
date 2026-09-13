from io import BytesIO
from uuid import uuid4

import pytest

import gqmrmed.services.result_store as result_store
from gqmrmed.generation.providers import GeneratedIllustration


class FakeS3Body:
    def __init__(self, data: bytes) -> None:
        self._stream = BytesIO(data)

    def read(self) -> bytes:
        return self._stream.read()

    def close(self) -> None:
        self._stream.close()


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str) -> None:
        assert Bucket == "gqmrmed"
        assert ContentType == "image/png"
        self.objects[Key] = Body

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, FakeS3Body]:
        assert Bucket == "gqmrmed"
        return {"Body": FakeS3Body(self.objects[Key])}


@pytest.mark.asyncio
async def test_s3_result_store_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeS3Client()
    monkeypatch.setattr(result_store.boto3, "client", lambda *args, **kwargs: client)
    store = result_store.S3ResultStore(
        endpoint="https://storage.example",
        access_key_id="access",
        secret_access_key="secret",
        bucket="gqmrmed",
        region="auto",
    )
    job_id = uuid4()
    image = GeneratedIllustration(image_bytes=b"png-data", width=1080, height=1920)

    stored = await store.put(job_id=job_id, image=image)
    loaded = await store.load(stored.storage_key)

    assert stored.storage_key == f"s3://gqmrmed/results/{job_id}.png"
    assert stored.image_bytes == b"png-data"
    assert loaded.image_bytes == b"png-data"
    assert loaded.mime_type == "image/png"


def test_s3_result_store_rejects_incomplete_configuration() -> None:
    with pytest.raises(ValueError, match="incomplete_s3_configuration"):
        result_store.S3ResultStore(
            endpoint="https://storage.example",
            access_key_id="",
            secret_access_key="secret",
            bucket="gqmrmed",
        )
