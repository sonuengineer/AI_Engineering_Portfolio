from app.core.redaction import CARD, EMAIL, PHONE, SECRET, redact, redact_text


def test_email_masked():
    assert redact_text("contact jane.doe+x@example.co.uk now") == f"contact {EMAIL} now"


def test_phone_numbers_masked():
    out = redact_text("call +1 415-555-0132 or (020) 7946 0958")
    assert out.count(PHONE) == 2
    assert "415" not in out


def test_bearer_and_api_keys_masked():
    out = redact_text("Authorization: Bearer abc.def-ghi_jklmnop and key sk-proj-ABCDEFGHIJKLMNOPQRSTU")
    assert "abc.def" not in out and "sk-proj" not in out
    assert out.count(SECRET) == 2


def test_google_key_jwt_and_kv_secret():
    jwt_like = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NSJ9.c2lnbmF0dXJlLXZhbHVl"
    out = redact_text(f"AIza{'A' * 35} token {jwt_like} password=hunter2!")
    assert "AIza" not in out and "eyJ" not in out and "hunter2" not in out


def test_credit_card_luhn_only():
    assert redact_text("card 4111 1111 1111 1111") == f"card {CARD}"
    # Not Luhn-valid: left alone (avoids masking order numbers)
    assert "1234 5678 9012 3456" in redact_text("ref 1234 5678 9012 3456")


def test_does_not_mask_dates_amounts_versions():
    s = "On 2026-05-01 revenue was 1,250.00 USD, version 1.2.3, qty 42, year 2024"
    assert redact_text(s) == s


def test_recursive_and_sensitive_keys():
    data = {"headers": {"Authorization": "Bearer xyz123456789", "X-Other": "ok"},
            "body": [{"email": "a@b.io"}, "call 555-123-4567"], "password": "pw", "n": 5}
    out = redact(data)
    assert out["headers"]["Authorization"] == SECRET
    assert out["headers"]["X-Other"] == "ok"
    assert out["body"][0]["email"] == EMAIL
    assert PHONE in out["body"][1]
    assert out["password"] == SECRET
    assert out["n"] == 5
