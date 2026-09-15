import pytest

from gqmrmed.generation.providers import GeneratedIllustration, ImageGenerationError
from gqmrmed.services.image_router import ImageProviderRouter


class FailingProvider:
    async def generate(self, *, prompt: str, width: int, height: int) -> GeneratedIllustration:
        raise ImageGenerationError("first_provider_failed")


class WorkingProvider:
    async def generate(self, *, prompt: str, width: int, height: int) -> GeneratedIllustration:
        return GeneratedIllustration(
            image_bytes=b"png",
            width=width,
            height=height,
        )


@pytest.mark.asyncio
async def test_image_router_uses_next_provider_after_failure() -> None:
    router = ImageProviderRouter((FailingProvider(), WorkingProvider()))
    result = await router.generate(prompt="medical", width=1024, height=1536)
    assert result.image_bytes == b"png"
    assert (result.width, result.height) == (1024, 1536)


@pytest.mark.asyncio
async def test_image_router_fails_after_all_providers_fail() -> None:
    router = ImageProviderRouter((FailingProvider(), FailingProvider()))
    with pytest.raises(ImageGenerationError, match="all_image_providers_failed"):
        await router.generate(prompt="medical", width=1024, height=1536)
