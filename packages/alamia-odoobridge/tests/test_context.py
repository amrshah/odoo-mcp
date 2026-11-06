"""
Unit tests for Alamia OdooBridge Principal Token Verification.
"""

import pytest
from alamia_odoobridge.core.context import PrincipalVerifier
from alamia_odoobridge.core.exceptions import AuthenticationError


def test_sign_and_verify_principal():
    secret = "test_super_secret_bridge_key_123"
    verifier = PrincipalVerifier(secret)

    claims = {
        "user_id": 5,
        "username": "dr_smith",
        "role": "doctor",
        "company_id": 1,
    }

    token = verifier.sign_claims(claims)
    assert token is not None

    verified = verifier.verify_token(token)
    assert verified.is_verified is True
    assert verified.user_id == 5
    assert verified.username == "dr_smith"
    assert verified.role == "doctor"


def test_tampered_token_rejected():
    secret = "test_super_secret_bridge_key_123"
    verifier = PrincipalVerifier(secret)

    claims = {"user_id": 5, "role": "doctor"}
    token = verifier.sign_claims(claims)

    # Tamper with the token with a different secret
    malicious_verifier = PrincipalVerifier("different_attacker_key")
    with pytest.raises(AuthenticationError) as exc_info:
        malicious_verifier.verify_token(token)
    assert "verification failed" in str(exc_info.value)
