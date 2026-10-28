import pytest

from app.core.signing import InvalidToken, sign, verify


def test_round_trip() -> None:
    payload = {"u": "https://example.com/a?b=1", "s": "cdjapan", "a": 52991, "c": "SG"}
    assert verify(sign(payload, "key"), "key") == payload


@pytest.mark.parametrize(
    "token_change",
    [
        lambda t: t[:-2] + ("AA" if not t.endswith("AA") else "BB"),  # altered signature
        lambda t: "x" + t,  # altered body
        lambda t: t.split(".")[0],  # signature removed
        lambda t: "",
    ],
)
def test_tampered_tokens_are_rejected(token_change) -> None:
    token = sign({"u": "https://example.com"}, "key")
    with pytest.raises(InvalidToken):
        verify(token_change(token), "key")


def test_wrong_key_is_rejected() -> None:
    with pytest.raises(InvalidToken):
        verify(sign({"u": "https://example.com"}, "key"), "other-key")
