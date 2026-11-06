"""
Unit tests for Alamia OdooBridge Principal Token Verification,
including cryptographic signing, tampered claims, expiration, issuer/audience validation,
and replay protection.
"""

import time
import pytest
from alamia_odoobridge.core.context import PrincipalVerifier
from alamia_odoobridge.core.exceptions import AuthenticationError


def test_sign_and_verify_principal():
    secret = "test_super_secret_bridge_key_123"
    verifier = PrincipalVerifier(secret)

    claims = {
        "sub": "dr_smith",
        "user_id": 5,
        "username": "dr_smith",
        "role": "doctor",
        "company_id": 1,
    }

    token = verifier.sign_claims(claims, ttl_seconds=60)
    assert token is not None

    verified = verifier.verify_token(token)
    assert verified.sub == "dr_smith"
    assert verified.user_id == 5
    assert verified.username == "dr_smith"
    assert verified.role == "doctor"
    assert verified.is_service_only is False


def test_missing_signing_secret_rejected():
    verifier = PrincipalVerifier(None)
    with pytest.raises(AuthenticationError) as exc:
        verifier.verify_token("some_token")
    assert "BRIDGE_SECRET_KEY" in str(exc.value)

    with pytest.raises(AuthenticationError) as exc_sign:
        verifier.sign_claims({"sub": "test"})
    assert "cannot sign claims" in str(exc_sign.value)


def test_missing_or_empty_token_rejected():
    verifier = PrincipalVerifier("test_secret")
    with pytest.raises(AuthenticationError) as exc:
        verifier.verify_token(None)
    assert "missing or empty" in str(exc.value)

    with pytest.raises(AuthenticationError) as exc2:
        verifier.verify_token("   ")
    assert "missing or empty" in str(exc2.value)


def test_tampered_token_rejected():
    secret = "test_super_secret_bridge_key_123"
    verifier = PrincipalVerifier(secret)

    claims = {"sub": "dr_smith", "user_id": 5, "role": "doctor"}
    token = verifier.sign_claims(claims)

    malicious_verifier = PrincipalVerifier("different_attacker_key")
    with pytest.raises(AuthenticationError) as exc_info:
        malicious_verifier.verify_token(token)
    assert "spoofing detected" in str(exc_info.value)


def test_expired_token_rejected():
    verifier = PrincipalVerifier("test_secret")
    claims = {"sub": "dr_smith", "role": "doctor"}
    
    # Sign with negative TTL to immediately expire
    token = verifier.sign_claims(claims, ttl_seconds=-5.0)
    
    with pytest.raises(AuthenticationError) as exc:
        verifier.verify_token(token)
    assert "expired" in str(exc.value)


def test_issuer_and_audience_mismatch_rejected():
    verifier = PrincipalVerifier("test_secret", expected_iss="custom-issuer", expected_aud="custom-aud")
    claims = {"sub": "dr_smith"}
    token = verifier.sign_claims(claims)

    wrong_iss_verifier = PrincipalVerifier("test_secret", expected_iss="different-iss", expected_aud="custom-aud")
    with pytest.raises(AuthenticationError) as exc_iss:
        wrong_iss_verifier.verify_token(token)
    assert "issuer mismatch" in str(exc_iss.value)

    wrong_aud_verifier = PrincipalVerifier("test_secret", expected_iss="custom-issuer", expected_aud="different-aud")
    with pytest.raises(AuthenticationError) as exc_aud:
        wrong_aud_verifier.verify_token(token)
    assert "audience mismatch" in str(exc_aud.value)


def test_token_replay_rejected():
    verifier = PrincipalVerifier("test_secret")
    claims = {"sub": "dr_smith", "role": "doctor"}
    token = verifier.sign_claims(claims, ttl_seconds=60)

    # First verification must succeed
    claims1 = verifier.verify_token(token)
    assert claims1.sub == "dr_smith"

    # Second verification of the exact same token must fail due to replay protection
    with pytest.raises(AuthenticationError) as exc:
        verifier.verify_token(token)
    assert "Token replay detected" in str(exc.value)
