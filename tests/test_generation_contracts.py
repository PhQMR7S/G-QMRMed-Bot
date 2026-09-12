import pytest
from pydantic import ValidationError

from gqmrmed.contracts.generation import GenerationProgress, GenerationRequest, InputType
from gqmrmed.services.subscriptions import hash_activation_code, normalize_activation_code


def test_text_generation_request_is_normalized() -> None:
    request = GenerationRequest(input_type=InputType.TEXT, text="  DKA  ")
    assert request.text == "DKA"
    request.validate_payload()


def test_generation_request_rejects_empty_payload() -> None:
    request = GenerationRequest(input_type=InputType.IMAGE, storage_key=None)
    with pytest.raises(ValueError, match="generation_input_required"):
        request.validate_payload()


def test_generation_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        GenerationRequest(input_type=InputType.TEXT, text="DKA", unexpected="x")


def test_progress_is_bounded() -> None:
    assert GenerationProgress(stage="researching", progress=0, elapsed_seconds=0).progress == 0
    with pytest.raises(ValidationError):
        GenerationProgress(stage="researching", progress=101, elapsed_seconds=0)


def test_activation_code_normalization_and_hashing() -> None:
    assert normalize_activation_code(" gqmr-plus-1234 ") == "GQMR-PLUS-1234"
    assert hash_activation_code("GQMR-PLUS-1234") == hash_activation_code(" gqmr-plus-1234 ")
