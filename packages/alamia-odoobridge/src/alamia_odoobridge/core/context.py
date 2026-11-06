"""
Caller principal and verifiable claims management for Alamia OdooBridge.
Prevents header spoofing by requiring cryptographic HMAC verification of caller claims,
with token expiration, issuer/audience validation, and replay protection.
"""

import time
import uuid
import hmac
import hashlib
import json
import base64
import contextvars
from typing import Optional, Dict, Any, Set
from .exceptions import AuthenticationError

# Context variable tracking verified principal for the active request / thread
current_principal: contextvars.ContextVar[Optional["PrincipalClaims"]] = contextvars.ContextVar(
    "current_principal", default=None
)


class PrincipalClaims:
    """Represents verified caller identity and permissions."""

    def __init__(
        self,
        sub: str,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        role: Optional[str] = None,
        company_id: Optional[int] = None,
        iss: str = "alamia-copilot",
        aud: str = "alamia-odoobridge",
        exp: Optional[float] = None,
        iat: Optional[float] = None,
        jti: Optional[str] = None,
        is_service_only: bool = False,
    ):
        self.sub = sub
        self.user_id = user_id
        self.username = username or sub
        self.role = role
        self.company_id = company_id
        self.iss = iss
        self.aud = aud
        self.exp = exp
        self.iat = iat or time.time()
        self.jti = jti or str(uuid.uuid4())
        self.is_service_only = is_service_only

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sub": self.sub,
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role,
            "company_id": self.company_id,
            "iss": self.iss,
            "aud": self.aud,
            "iat": self.iat,
            "exp": self.exp,
            "jti": self.jti,
            "is_service_only": self.is_service_only,
        }

    def __repr__(self) -> str:
        return f"<PrincipalClaims sub={self.sub} role={self.role} service_only={self.is_service_only}>"


class PrincipalVerifier:
    """Verifies service-to-service claims using HMAC-SHA256 with replay & expiry checks."""

    def __init__(
        self,
        secret_key: Optional[str] = None,
        expected_iss: str = "alamia-copilot",
        expected_aud: str = "alamia-odoobridge",
    ):
        self.secret_key = secret_key.encode("utf-8") if secret_key else None
        self.expected_iss = expected_iss
        self.expected_aud = expected_aud
        # Replay cache: stores seen jti identifiers alongside their expiration timestamps
        self._seen_jtis: Dict[str, float] = {}

    def _purge_expired_jtis(self, now: float) -> None:
        """Remove expired token IDs from the replay cache."""
        expired = [
            jti for jti, info in self._seen_jtis.items()
            if (info["exp"] if isinstance(info, dict) else info) < now
        ]
        for jti in expired:
            del self._seen_jtis[jti]

    def sign_claims(
        self,
        claims: Dict[str, Any],
        ttl_seconds: float = 3600.0,
    ) -> str:
        """Create a verifiable base64 HMAC token for service-to-service communication."""
        if not self.secret_key:
            raise AuthenticationError("Bridge secret key not configured; cannot sign claims")

        now = time.time()
        payload = dict(claims)
        payload.setdefault("iss", self.expected_iss)
        payload.setdefault("aud", self.expected_aud)
        payload.setdefault("iat", now)
        payload.setdefault("exp", now + ttl_seconds)
        payload.setdefault("jti", str(uuid.uuid4()))

        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        signature = hmac.new(self.secret_key, payload_bytes, hashlib.sha256).digest()

        token_data = {
            "payload": base64.b64encode(payload_bytes).decode("ascii"),
            "sig": base64.b64encode(signature).decode("ascii"),
        }
        return base64.b64encode(json.dumps(token_data).encode("utf-8")).decode("ascii")

    def verify_token(
        self,
        token_str: Optional[str],
        session_id: Optional[str] = None,
        is_handshake: bool = False,
    ) -> PrincipalClaims:
        """
        Verify that claims were signed with the shared service secret.
        Rejects missing tokens, missing signing secrets, invalid signatures,
        expired tokens, issuer/audience mismatches, and replayed token IDs.
        For streaming MCP sessions (SSE / Streamable HTTP), binds the token to the session.
        """
        if not self.secret_key:
            raise AuthenticationError(
                "Bridge signing secret (BRIDGE_SECRET_KEY) is not configured; cannot verify principal tokens"
            )

        if not token_str or not token_str.strip():
            raise AuthenticationError("Principal token is missing or empty; cannot authenticate caller")

        now = time.time()
        self._purge_expired_jtis(now)

        try:
            raw_json = base64.b64decode(token_str.strip().encode("ascii")).decode("utf-8")
            token_data = json.loads(raw_json)
            payload_b64 = token_data.get("payload")
            sig_b64 = token_data.get("sig")

            if not payload_b64 or not sig_b64:
                raise AuthenticationError("Malformed principal token structure (missing payload or signature)")

            payload_bytes = base64.b64decode(payload_b64.encode("ascii"))
            expected_sig = base64.b64decode(sig_b64.encode("ascii"))

            computed_sig = hmac.new(self.secret_key, payload_bytes, hashlib.sha256).digest()

            if not hmac.compare_digest(computed_sig, expected_sig):
                raise AuthenticationError("Principal token signature verification failed (spoofing detected)")

            claims_data = json.loads(payload_bytes.decode("utf-8"))

            # Expiration validation
            exp = claims_data.get("exp")
            if exp is None:
                raise AuthenticationError("Principal token missing required expiration (exp) claim")
            if now > exp:
                raise AuthenticationError(f"Principal token has expired (exp: {exp}, now: {now})")

            # Issued-at / Not-before validation
            iat = claims_data.get("iat", 0)
            if iat > now + 60:  # Allow 60s clock skew
                raise AuthenticationError("Principal token issued in the future (clock skew detected)")

            # Issuer and Audience validation
            iss = claims_data.get("iss")
            if iss != self.expected_iss:
                raise AuthenticationError(
                    f"Principal token issuer mismatch (expected: {self.expected_iss}, got: {iss})"
                )

            aud = claims_data.get("aud")
            if aud != self.expected_aud:
                raise AuthenticationError(
                    f"Principal token audience mismatch (expected: {self.expected_aud}, got: {aud})"
                )

            # Replay protection and session-binding check
            jti = claims_data.get("jti")
            if not jti:
                raise AuthenticationError("Principal token missing unique token identifier (jti)")

            if jti in self._seen_jtis:
                recorded = self._seen_jtis[jti]
                # If token was used in an SSE/session handshake, verify session continuity
                if isinstance(recorded, dict) and recorded.get("is_handshake"):
                    bound_session = recorded.get("session_id")
                    if session_id:
                        if bound_session is None:
                            # First message request in the session: bind session_id
                            recorded["session_id"] = session_id
                        elif bound_session != session_id:
                            raise AuthenticationError(
                                f"Token replay detected: token '{jti}' is already bound to session '{bound_session}'"
                            )
                        # Else: matches bound_session, session message allowed
                    else:
                        # Attempt to initiate a second handshake with same token
                        raise AuthenticationError(
                            f"Token replay detected: jti '{jti}' has already been used in another session handshake"
                        )
                else:
                    # Non-session request or replay
                    raise AuthenticationError(f"Token replay detected: jti '{jti}' has already been processed")
            else:
                self._seen_jtis[jti] = {
                    "exp": float(exp),
                    "session_id": session_id,
                    "is_handshake": is_handshake,
                }

            sub = claims_data.get("sub") or claims_data.get("username")
            if not sub:
                raise AuthenticationError("Principal token missing subject identifier (sub)")

            return PrincipalClaims(
                sub=sub,
                user_id=claims_data.get("user_id"),
                username=claims_data.get("username") or sub,
                role=claims_data.get("role"),
                company_id=claims_data.get("company_id"),
                iss=iss,
                aud=aud,
                exp=exp,
                iat=iat,
                jti=jti,
                is_service_only=claims_data.get("is_service_only", False),
            )
        except AuthenticationError:
            raise
        except Exception as e:
            raise AuthenticationError(f"Invalid principal token: {e}")
