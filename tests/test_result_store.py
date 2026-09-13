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


class FakeDriveUpload:
    def __init__(self, stream: BytesIO, **_: object) -> None:
        self.data = stream.getvalue()


class FakeDriveFiles:
    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}
        self.names: dict[str, str] = {}
        self.next_id = 1

    def list(self, *, q: str, **_: object) -> FakeDriveRequest:
        filename = q.split("name='")[1].split("'")[0]
        for file_id, name in self.names.items():
            if name == filename:
                return FakeDriveRequest({"files": [{"id": file_id}]})
        return FakeDriveRequest({"files": []})

    def create(self, *, body: dict[str, object], media_body: FakeDriveUpload, **_: object) -> object:
        file_id = f"file-{self.next_id}"
        self.next_id += 1
        self.names[file_id] = str(body["name"])
        self.data[file_id] = media_body.data
        return FakeDriveRequest({"id": file_id})

    def update(self, *, fileId: str, media_body: FakeDriveUpload, **_: object) -> object:
        self.data[fileId] = media_body.data
        return FakeDriveRequest({"id": fileId})

    def get_media(self, *, fileId: str, **_: object) -> object:
        return FakeDriveMediaRequest(self.data[fileId])


class FakeDriveRequest:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response

    def execute(self) -> dict[str, object]:
        return self.response


class FakeDriveMediaRequest:
    def __init__(self, data: bytes) -> None:
        self.data = data


class FakeDriveService:
    def __init__(self) -> None:
        self._files = FakeDriveFiles()

    def files(self) -> FakeDriveFiles:
        return self._files


class FakeDriveDownloader:
    def __init__(self, stream: BytesIO, request: FakeDriveMediaRequest) -> None:
        self.stream = stream
        self.request = request
        self.done = False

    def next_chunk(self) -> tuple[None, bool]:
        if not self.done:
            self.stream.write(self.request.data)
            self.done = True
        return None, True


@pytest.mark.asyncio
async def test_google_drive_result_store_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeDriveService()
    monkeypatch.setattr(
        result_store.service_account.Credentials,
        "from_service_account_info",
        lambda info, scopes: object(),
    )
    monkeypatch.setattr(result_store, "build", lambda *args, **kwargs: service)
    monkeypatch.setattr(result_store, "MediaIoBaseUpload", FakeDriveUpload)
    monkeypatch.setattr(result_store, "MediaIoBaseDownload", FakeDriveDownloader)

    store = result_store.GoogleDriveResultStore(
        credentials_json=(
            '{"client_email":"bot@example.com","private_key":"key",'
            '"token_uri":"uri"}'
        ),
        folder_id="folder-id",
    )
    job_id = uuid4()
    image = GeneratedIllustration(image_bytes=b"png-data", width=1080, height=1920)

    stored = await store.put(job_id=job_id, image=image)
    stored_again = await store.put(job_id=job_id, image=image)
    loaded = await store.load(stored.storage_key)

    assert stored.storage_key == stored_again.storage_key
    assert len(service.files().data) == 1
    assert stored.image_bytes == b"png-data"
    assert loaded.image_bytes == b"png-data"
    assert loaded.mime_type == "image/png"


def test_google_drive_result_store_rejects_invalid_credentials() -> None:
    with pytest.raises(ValueError, match="invalid_google_drive_credentials_json"):
        result_store.GoogleDriveResultStore(credentials_json="not-json", folder_id="folder-id")


def test_google_drive_result_store_rejects_missing_folder() -> None:
    with pytest.raises(ValueError, match="google_drive_folder_id_required"):
        result_store.GoogleDriveResultStore(
            credentials_json='{"client_email":"bot@example.com"}',
            folder_id="",
        )
