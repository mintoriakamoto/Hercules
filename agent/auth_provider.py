"""Auth provider with dependency injection - decoupled from hercules_cli.

This module provides authentication without hard dependencies on httpx or
hercules_cli.auth at module load time.
"""

from typing import Optional, Any, Callable
from agent.dependency_injection import DependencyContainer, requires_dependency


class AuthProvider:
    """Manages authentication without direct imports."""

    def __init__(self, custom_auth: Optional[Any] = None):
        """Initialize with optional custom auth module.
        
        Args:
            custom_auth: Custom auth module (for testing/DI)
        """
        self._auth_module = custom_auth
        self._httpx = None

    def get_auth_module(self) -> Optional[Any]:
        """Lazy-load auth module only when needed."""
        if self._auth_module is not None:
            return self._auth_module
        
        try:
            import hercules_cli.auth
            self._auth_module = hercules_cli.auth
            return self._auth_module
        except ImportError:
            return None

    @requires_dependency("httpx", tier="gateway")
    def create_authenticated_client(self, _dep=None) -> Any:
        """Create HTTP client with auth headers.
        
        Args:
            _dep: httpx module (injected by decorator)
        
        Returns:
            Configured httpx client
        """
        auth_module = self.get_auth_module()
        if auth_module is None:
            raise RuntimeError("Authentication module not available")
        
        headers = {}
        if hasattr(auth_module, "get_auth_headers"):
            headers = auth_module.get_auth_headers()
        
        return _dep.Client(headers=headers)


# Singleton instance
_auth_provider = None


def get_auth_provider() -> AuthProvider:
    """Get or create auth provider singleton."""
    global _auth_provider
    if _auth_provider is None:
        _auth_provider = AuthProvider()
    return _auth_provider


def inject_auth_provider(custom_auth: Any) -> None:
    """Inject custom auth for testing."""
    global _auth_provider
    _auth_provider = AuthProvider(custom_auth=custom_auth)
