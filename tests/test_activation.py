import re

from gqmrmed.services.activation import generate_activation_code


def test_activation_code_is_human_readable_and_high_entropy() -> None:
    code = generate_activation_code("PLUS")
    assert re.fullmatch(r"GQMR-PLUS-[A-HJ-NP-Z2-9]{6}-[A-HJ-NP-Z2-9]{6}", code)
    assert len(code.split("-")[-1]) == 6
    assert not any(character in code for character in "01IO")
