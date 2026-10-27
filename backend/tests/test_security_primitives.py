from app.core.security import otp_digest, otp_matches, token_digest


def test_otp_hmac_depends_on_pepper() -> None:
    assert otp_digest("123456", "pepper-a") != otp_digest("123456", "pepper-b")


def test_otp_matches_expected_digest() -> None:
    digest = otp_digest("123456", "unit-test-pepper")
    assert otp_matches("123456", digest, "unit-test-pepper")
    assert not otp_matches("123455", digest, "unit-test-pepper")


def test_token_digest_is_stable_and_not_plaintext() -> None:
    digest = token_digest("random-high-entropy-token")
    assert len(digest) == 64
    assert digest != "random-high-entropy-token"
