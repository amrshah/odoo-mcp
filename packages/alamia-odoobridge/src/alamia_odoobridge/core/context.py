"""
Caller principal and verifiable claims management for Alamia OdooBridge.
Prevents header spoofing by requiring cryptographic HMAC verification of caller claims.
"""

import hmac
import hashlib
import json
import base64
from typing import Optional, Dict, Any
from .exceptions import AuthenticationError


class PrincipalClaims:
    """Represents verified caller identity and permissions."""

    def __init__(
        self,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        role: Optional[str] = None,
        company_id: Optional[int] = None,
        is_verified: bool = False,
    ):
        self.user_id = user_id
        self.username = username
        self.role = role
        self.company_id = company_id
        self.is_verified = is_verified

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role,
            "company_id": self.company_id,
            "is_verified": self.is_verified,
        }


class PrincipalVerifier:
    """Verifies service-to-service claims using HMAC-SHA256."""

    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = secret_key.encode("utf-8") if secret_key else None

    def sign_claims(self, claims: Dict[str, Any]) -> str:
        """Create a verifiable base64 HMAC token for service-to-service communication."""
        if not self.secret_key:
            raise AuthenticationError("Bridge secret key not configured; cannot sign claims")

        payload_bytes = json.dumps(claims, sort_keys=True).encode("utf-8")
        signature = hmac.new(self.secret_key, payload_bytes, hashlib.sha256).digest()
        
        token_data = {
            "payload": base64.b64encode(payload_bytes).decode("ascii"),
            "sig": base64.b64encode(signature).decode("ascii"),
        }
        return base64.b64encode(json.dumps(token_data).encode("utf-8")).decode("ascii")

    def verify_token(self, token_str: Optional[str]) -> PrincipalClaims:
        """
        Verify that claims were signed with the shared service secret.
        Never trust raw unverified headers.
        """
        if not token_str or not self.secret_key:
            # Fall back to unverified default service principal
            return PrincipalClaims(is_verified=False)

        try:
            token_json = json.loads(base64.b64decode(token_str.encode("ascii")).decode("utf-8"))
            payload_bytes = base64.b64decode(token_json["payload"].encode("ascii"))
            expected_sig = base64.b64decode(token_json["sig"].encode("ascii"))

            computed_sig = hmac.new(self.secret_key, payload_bytes, hashlib.sha256).digest()

            if not hmac.compare_digest(computed_sig, expected_sig):
                raise AuthenticationError("Principal token signature verification failed (spoofing detected)")

            claims_data = json.loads(payload_bytes.decode("utf-8"))
            return PrincipalClaims(
                user_id=claims_data.get("user_id"),
                username=claims_data.get("username"),
                role=claims_data.get("role"),
                company_id=claims_data.get("company_id"),
                is_verified=True,
            )
        except AuthenticationError:
            raise
        except Exception as e:
            raise AuthenticationError(f"Invalid principal token format: {e}")
