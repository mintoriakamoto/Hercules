"""Dependency injection container for optional packages and core services.

This module centralizes dependency management and provides graceful
fallbacks when optional packages are not available.
"""

from typing import Any, Dict, Optional, Callable
import functools


class DependencyContainer:
    """Manages optional and core dependencies with fallback handling."""

    _instance = None
    _dependencies: Dict[str, Any] = {}
    _initializers: Dict[str, Callable] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, name: str, tier: str = "core"):
        """Register a dependency initializer.

        Args:
            name: Dependency name (e.g., 'httpx')
            tier: 'core', 'gateway', 'integrations'
        """
        def decorator(func: Callable) -> Callable:
            cls._initializers[name] = {
                "tier": tier,
                "initializer": func
            }
            return func
        return decorator

    @classmethod
    def get(cls, name: str, required: bool = False) -> Optional[Any]:
        """Get a dependency with lazy initialization.

        Args:
            name: Dependency name
            required: If True, raise error if not available

        Returns:
            The dependency object or None

        Raises:
            ImportError: If required and not available
        """
        if name in cls._dependencies:
            return cls._dependencies[name]

        if name not in cls._initializers:
            if required:
                raise ImportError(f"Dependency not registered: {name}")
            return None

        info = cls._initializers[name]
        try:
            dep = info["initializer"]()
            cls._dependencies[name] = dep
            return dep
        except ImportError as e:
            if required:
                tier = info["tier"]
                raise ImportError(
                    f"{name} required for '{tier}' tier. "
                    f"Install: pip install hercules[{tier}]"
                ) from e
            return None

    @classmethod
    def clear(cls):
        """Clear all cached dependencies (for testing)."""
        cls._dependencies.clear()


# Register core dependencies
@DependencyContainer.register("anthropic", tier="core")
def _init_anthropic():
    import anthropic
    return anthropic


@DependencyContainer.register("pydantic", tier="core")
def _init_pydantic():
    import pydantic
    return pydantic


# Register gateway/integration dependencies
@DependencyContainer.register("httpx", tier="gateway")
def _init_httpx():
    import httpx
    return httpx


@DependencyContainer.register("slack_sdk", tier="integrations")
def _init_slack():
    from slack_sdk import WebClient
    return WebClient


@DependencyContainer.register("discord", tier="integrations")
def _init_discord():
    import discord
    return discord


# Decorator for optional dependencies
def requires_dependency(name: str, tier: str = "gateway"):
    """Decorator to guard functions requiring optional dependencies."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            dep = DependencyContainer.get(name, required=True)
            if dep is None:
                raise ImportError(
                    f"{name} not available. Install: pip install hercules[{tier}]"
                )
            return func(*args, _dep=dep, **kwargs)
        return wrapper
    return decorator
