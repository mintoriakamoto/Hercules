"""Agent identity — a keypair, nothing more.

An agent's identity *is* its public key. There is no registration server, no
username authority: you are your key, and anyone can verify what you signed —
offline, forever. This is the part of Bitcoin that mattered (verifiable
signatures), stripped of everything that did not.

Keys are Ed25519. Agent ids and signatures are URL-safe base64 without
padding, so they travel cleanly through JSON, chat messages, and URLs.
"""

from __future__ import annotations

import base64

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)


def b64encode(raw: bytes) -> str:
    """URL-safe base64 without ``=`` padding."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def b64decode(text: str) -> bytes:
    """Inverse of :func:`b64encode` (restores stripped padding)."""
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


class Identity:
    """An Ed25519 keypair. Its public key is the agent id.

    Generate a fresh one with :meth:`generate`, or restore a persisted one from
    its 32-byte seed with :meth:`from_seed`. Never log or share the seed — it is
    the private key.
    """

    __slots__ = ("_sk", "_pk")

    def __init__(self, private_key: Ed25519PrivateKey) -> None:
        self._sk = private_key
        self._pk = private_key.public_key()

    @classmethod
    def generate(cls) -> "Identity":
        return cls(Ed25519PrivateKey.generate())

    @classmethod
    def from_seed(cls, seed: bytes) -> "Identity":
        if len(seed) != 32:
            raise ValueError("Ed25519 seed must be exactly 32 bytes")
        return cls(Ed25519PrivateKey.from_private_bytes(seed))

    @property
    def agent_id(self) -> str:
        """The public key, base64url — this agent's stable, global identity."""
        return b64encode(self._pk.public_bytes(Encoding.Raw, PublicFormat.Raw))

    def seed(self) -> bytes:
        """The 32-byte private seed. Secret — persist it somewhere safe."""
        return self._sk.private_bytes(
            Encoding.Raw, PrivateFormat.Raw, NoEncryption()
        )

    def sign(self, message: bytes) -> str:
        """Return a base64url Ed25519 signature over *message*."""
        return b64encode(self._sk.sign(message))

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"Identity(agent_id={self.agent_id[:12]}…)"


def verify(agent_id: str, message: bytes, signature: str) -> bool:
    """True iff *signature* is a valid Ed25519 signature of *message* by *agent_id*.

    Never raises: a malformed id, signature, or a bad signature all return
    ``False`` so callers can treat verification as a simple predicate.
    """
    try:
        public_key = Ed25519PublicKey.from_public_bytes(b64decode(agent_id))
        public_key.verify(b64decode(signature), message)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False
