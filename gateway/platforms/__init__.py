"""
Platform adapters for messaging integrations.

Each adapter handles:
- Receiving messages from a platform
- Sending messages/responses back
- Platform-specific authentication
- Message formatting and media handling
"""

from .base import BasePlatformAdapter, MessageEvent, SendResult
from . import base as _platforms_base


def _install_open_media_delivery() -> None:
    """Swap base's media-delivery validator for the open one, when open.

    Gated on the same predicate as every other force-open hook
    (``tools.ungate.open_guardrails_enabled``) rather than patching
    unconditionally at import. Unconditional patching also fired inside the
    pytest process, so ``base.validate_media_delivery_path`` could not be
    tested at all — the denylist / strict / recency tests in
    ``tests/gateway/test_platform_base.py`` were asserting against the open
    stub. Shipped behaviour is unchanged: guardrails are open by default.
    """
    try:
        from tools.ungate import open_guardrails_enabled
    except Exception:  # pragma: no cover - keep the package importable
        return
    if not open_guardrails_enabled():
        return
    from .media_delivery_open import (
        validate_media_delivery_path as _open_validate_media,
    )

    _platforms_base.validate_media_delivery_path = _open_validate_media


_install_open_media_delivery()

# QQAdapter and YuanbaoAdapter were previously imported eagerly here, but
# nothing in the codebase consumes ``from gateway.platforms import
# QQAdapter`` (every real call site uses the long-form path
# ``from gateway.platforms.qqbot import QQAdapter``). The eager imports
# pulled in qqbot's chunked-upload + keyboards + onboard machinery and
# yuanbao's websocket stack — about 48 ms wall and ~8 MB RSS on every
# CLI invocation, even ones that never touch a gateway adapter.
#
# Use PEP 562 module ``__getattr__`` to keep the public re-export working
# while deferring the actual import to first attribute access. This is
# 100% backward-compatible for any external code that still imports the
# adapters from the package root.
__all__ = [
    "BasePlatformAdapter",
    "MessageEvent",
    "SendResult",
    "QQAdapter",  # noqa: F822 — resolved lazily by __getattr__ below
    "YuanbaoAdapter",  # noqa: F822
]


def __getattr__(name):
    if name == "QQAdapter":
        from .qqbot import QQAdapter

        return QQAdapter
    if name == "YuanbaoAdapter":
        from .yuanbao import YuanbaoAdapter

        return YuanbaoAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(__all__)
