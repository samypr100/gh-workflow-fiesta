"""Signed run tokens and derived user keys.

The backend keeps no run registry. A run token carries everything the backend
needs and proves its own integrity, so a poll is a signature check rather than
a lookup. The frontend receives an opaque string and never learns the
repository or the GitHub run identifier.
"""

import base64
import hashlib
import hmac

from pydantic import BaseModel, ConfigDict, ValidationError

USER_KEY_LENGTH = 16
SIGNATURE_BYTES = 32


class InvalidRunToken(Exception):  # noqa: N818
    """Raised when a run token is malformed, unsigned, altered, or expired."""


class RunTokenPayload(BaseModel):
    """The state a run token carries on the client's behalf.

    Attributes:
        run_id: GitHub workflow run identifier.
        submission_id: Opaque identifier for the submission.
        user_key: Derived key of the user who created the run.
        expires_at: Unix timestamp after which the token is refused.
    """

    model_config = ConfigDict(frozen=True)

    run_id: int
    submission_id: str
    user_key: str
    expires_at: int


def _encode(raw: bytes) -> str:
    """Encode bytes as unpadded base64url.

    Args:
        raw: Bytes to encode.

    Returns:
        The encoded text.
    """
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode(text: str) -> bytes:
    """Decode unpadded base64url text.

    Args:
        text: Encoded text.

    Returns:
        The decoded bytes.

    Raises:
        InvalidRunToken: If the text is not valid base64url.
    """
    padded = text + "=" * (-len(text) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as error:
        raise InvalidRunToken("token is not valid base64url") from error


def _sign(body: str, secret: str) -> str:
    """Compute the signature for an encoded body.

    Args:
        body: Encoded payload.
        secret: Signing key.

    Returns:
        The encoded signature.
    """
    digest = hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256)
    return _encode(digest.digest())


def sign_run_token(payload: RunTokenPayload, *, secret: str) -> str:
    """Produce an opaque, tamper-evident token.

    Args:
        payload: State to embed.
        secret: Signing key.

    Returns:
        A token of the form `<body>.<signature>`.
    """
    body = _encode(payload.model_dump_json().encode("utf-8"))
    return f"{body}.{_sign(body, secret)}"


def verify_run_token(token: str, *, secret: str, now: int) -> RunTokenPayload:
    """Validate a token and recover its payload.

    Args:
        token: Token presented by the client.
        secret: Signing key.
        now: Current Unix timestamp.

    Returns:
        The embedded payload.

    Raises:
        InvalidRunToken: If the token is malformed, altered, or expired.
    """
    body, separator, signature = token.partition(".")
    if separator == "" or body == "" or signature == "":
        raise InvalidRunToken("token is malformed")
    if not hmac.compare_digest(signature, _sign(body, secret)):
        raise InvalidRunToken("token signature does not match")

    try:
        payload = RunTokenPayload.model_validate_json(_decode(body))
    except ValidationError as error:
        raise InvalidRunToken("token payload is not well formed") from error

    if payload.expires_at <= now:
        raise InvalidRunToken("token has expired")
    return payload


def derive_user_key(client_ip: str, *, secret: str) -> str:
    """Derive a stable, non-reversible key for a client address.

    The key is embedded in the workflow run name, so it must be short and
    alphanumeric. It never reveals the address it came from.

    Args:
        client_ip: Address observed for the request.
        secret: Derivation key.

    Returns:
        A 16-character hexadecimal key.
    """
    digest = hmac.new(secret.encode("utf-8"), client_ip.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()[:USER_KEY_LENGTH]
