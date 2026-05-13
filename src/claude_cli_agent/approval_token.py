"""Signed short-lived approval token challenges."""

from __future__ import annotations

import hmac
import os
import secrets
import time
from dataclasses import dataclass
from hashlib import sha256


@dataclass
class ApprovalChallenge:
    stage: str
    expires_at: int
    nonce: str
    token: str

    @property
    def expires_in(self) -> int:
        return max(0, self.expires_at - int(time.time()))


class ApprovalTokenManager:
    """Issues signed, short-lived, one-time approval challenges."""

    def __init__(self, secret: str | None = None) -> None:
        self.secret = (secret or os.environ.get("CAGENT_APPROVAL_SECRET") or secrets.token_hex(24)).encode(
            "utf-8"
        )
        self._used: set[str] = set()

    def issue(self, stage: str, ttl_seconds: int = 90) -> ApprovalChallenge:
        expires_at = int(time.time()) + max(10, ttl_seconds)
        nonce = secrets.token_hex(6)
        payload = f"{stage}|{expires_at}|{nonce}"
        sig = hmac.new(self.secret, payload.encode("utf-8"), sha256).hexdigest()[:10]
        token = f"{nonce}-{sig}"
        return ApprovalChallenge(stage=stage, expires_at=expires_at, nonce=nonce, token=token)

    def verify(self, challenge: ApprovalChallenge, provided_token: str) -> bool:
        if provided_token in self._used:
            return False
        if int(time.time()) > challenge.expires_at:
            return False
        payload = f"{challenge.stage}|{challenge.expires_at}|{challenge.nonce}"
        expected_sig = hmac.new(self.secret, payload.encode("utf-8"), sha256).hexdigest()[:10]
        expected = f"{challenge.nonce}-{expected_sig}"
        if not hmac.compare_digest(expected, provided_token.strip()):
            return False
        self._used.add(provided_token.strip())
        return True
