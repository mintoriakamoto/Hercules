"""Unified gateway platform management.

Separates message platform routing (Telegram, Discord, Feishu) from tool
extensibility (plugins/skills). Each platform handler runs independently
with its own lifecycle and configuration.

Design:
  - PlatformHandler: base for message routing adapters
  - PlatformRegistry: lifecycle management for all platforms
  - PlatformConfig: per-platform settings (credentials, webhooks, etc.)
  - PlatformManager: orchestrates startup/shutdown across all platforms
"""

from __future__ import annotations

import abc
import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PlatformType(Enum):
    """Types of message platforms supported by Hercules Gateway."""
    TELEGRAM = "telegram"
    DISCORD = "discord"
    FEISHU = "feishu"
    SLACK = "slack"
    MATRIX = "matrix"
    WHATSAPP = "whatsapp"
    CUSTOM = "custom"


@dataclass
class PlatformConfig:
    """Configuration for a message platform."""
    platform_type: PlatformType
    name: str
    enabled: bool = True

    # Authentication
    api_token: Optional[str] = None
    api_secret: Optional[str] = None
    webhook_url: Optional[str] = None

    # Settings
    settings: Dict[str, Any] = None

    # Resource limits
    max_concurrent_messages: int = 10
    message_timeout_seconds: float = 30.0

    def __post_init__(self):
        if self.settings is None:
            self.settings = {}


class PlatformError(Exception):
    """Raised when platform operation fails."""
    def __init__(self, platform_name: str, reason: str):
        self.platform_name = platform_name
        self.reason = reason
        super().__init__(
            f"Platform '{platform_name}' error: {reason}"
        )


class PlatformHandler(abc.ABC):
    """Abstract base for message platform handlers.

    Each platform (Telegram, Discord, Feishu, etc.) implements this interface
    to handle incoming messages and send outgoing responses.
    """

    def __init__(self, config: PlatformConfig):
        self.config = config
        self.is_running = False

    @abc.abstractmethod
    async def start(self) -> None:
        """Start the platform handler.

        Connect to platform, establish webhooks/polling, etc.
        """
        pass

    @abc.abstractmethod
    async def stop(self) -> None:
        """Stop the platform handler gracefully."""
        pass

    @abc.abstractmethod
    async def send_message(
        self,
        channel_id: str,
        message: str,
    ) -> str:
        """Send a message to a channel/user.

        Args:
            channel_id: Platform-specific channel/user identifier
            message: Message text to send

        Returns:
            Message ID from platform
        """
        pass

    @abc.abstractmethod
    async def handle_incoming_message(
        self,
        message_data: Dict[str, Any],
    ) -> None:
        """Handle an incoming message from the platform.

        Args:
            message_data: Platform-specific message data
        """
        pass

    async def health_check(self) -> bool:
        """Check if platform connection is healthy.

        Returns:
            True if healthy
        """
        return self.is_running


class PlatformRegistry:
    """Registry and lifecycle manager for platform handlers."""

    def __init__(self):
        self.handlers: Dict[str, PlatformHandler] = {}
        self.configs: Dict[str, PlatformConfig] = {}

    def register(self, config: PlatformConfig, handler: PlatformHandler) -> None:
        """Register a platform handler.

        Args:
            config: Platform configuration
            handler: Handler instance
        """
        platform_name = config.name
        self.configs[platform_name] = config
        self.handlers[platform_name] = handler
        logger.info("Registered platform handler: %s (%s)", platform_name, config.platform_type.value)

    def get_handler(self, platform_name: str) -> Optional[PlatformHandler]:
        """Get a platform handler by name."""
        return self.handlers.get(platform_name)

    def get_config(self, platform_name: str) -> Optional[PlatformConfig]:
        """Get platform configuration by name."""
        return self.configs.get(platform_name)

    def list_handlers(self) -> List[str]:
        """List all registered platform names."""
        return sorted(self.handlers.keys())

    def list_enabled(self) -> List[str]:
        """List enabled platform names."""
        return [
            name for name, config in self.configs.items()
            if config.enabled
        ]


class PlatformManager:
    """Orchestrates lifecycle of all message platforms.

    Responsibilities:
      - Load platform configurations
      - Create and register handlers
      - Start/stop all platforms
      - Monitor platform health
      - Handle platform failures and restarts
    """

    def __init__(self, registry: Optional[PlatformRegistry] = None):
        self.registry = registry or PlatformRegistry()
        self.startup_tasks: List[asyncio.Task] = []
        self.health_check_task: Optional[asyncio.Task] = None

    async def load_from_config(self, config_path: Path) -> None:
        """Load platform configurations from file.

        Args:
            config_path: Path to platforms.json
        """
        import json

        if not config_path.exists():
            logger.warning("Platform config not found: %s", config_path)
            return

        try:
            with open(config_path, 'r') as f:
                data = json.load(f)

            for platform_name, platform_data in data.items():
                try:
                    platform_type = PlatformType(platform_data["type"])
                    config = PlatformConfig(
                        platform_type=platform_type,
                        name=platform_name,
                        enabled=platform_data.get("enabled", True),
                        api_token=platform_data.get("api_token"),
                        api_secret=platform_data.get("api_secret"),
                        webhook_url=platform_data.get("webhook_url"),
                        settings=platform_data.get("settings", {}),
                    )

                    # Create handler instance
                    handler = self._create_handler(config)
                    if handler:
                        self.registry.register(config, handler)

                except Exception as e:
                    logger.error("Failed to load platform %s: %s", platform_name, e)

            logger.info(
                "Loaded %d platform configurations",
                len(self.registry.list_handlers())
            )

        except Exception as e:
            logger.error("Failed to load platform config from %s: %s", config_path, e)

    def _create_handler(self, config: PlatformConfig) -> Optional[PlatformHandler]:
        """Factory: create appropriate handler for platform type.

        Args:
            config: Platform configuration

        Returns:
            Handler instance or None if type not supported
        """
        # This will be dynamically populated as handlers are implemented
        handlers = {
            # PlatformType.TELEGRAM: TelegramHandler,
            # PlatformType.DISCORD: DiscordHandler,
            # PlatformType.FEISHU: FeishuHandler,
        }

        handler_cls = handlers.get(config.platform_type)
        if not handler_cls:
            logger.warning(
                "No handler available for platform type: %s",
                config.platform_type.value
            )
            return None

        try:
            return handler_cls(config)
        except Exception as e:
            logger.error("Failed to create handler for %s: %s", config.name, e)
            return None

    async def start(self) -> None:
        """Start all enabled platforms."""
        enabled_platforms = self.registry.list_enabled()
        logger.info("Starting %d platforms", len(enabled_platforms))

        self.startup_tasks = []
        for platform_name in enabled_platforms:
            handler = self.registry.get_handler(platform_name)
            if handler:
                task = asyncio.create_task(
                    self._start_platform(platform_name, handler)
                )
                self.startup_tasks.append(task)

        # Wait for all to start
        results = await asyncio.gather(*self.startup_tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("Platform startup failed: %s", result)

        # Start health check
        self.health_check_task = asyncio.create_task(self._health_check_loop())

    async def _start_platform(
        self,
        platform_name: str,
        handler: PlatformHandler,
    ) -> None:
        """Start a single platform handler."""
        try:
            await handler.start()
            handler.is_running = True
            logger.info("Platform started: %s", platform_name)
        except Exception as e:
            logger.error("Failed to start platform %s: %s", platform_name, e)
            raise PlatformError(platform_name, str(e))

    async def stop(self) -> None:
        """Stop all platforms gracefully."""
        logger.info("Stopping all platforms")

        # Cancel health check
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass

        # Stop all handlers
        stop_tasks = []
        for platform_name in self.registry.list_handlers():
            handler = self.registry.get_handler(platform_name)
            if handler and handler.is_running:
                stop_tasks.append(
                    self._stop_platform(platform_name, handler)
                )

        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)

        logger.info("All platforms stopped")

    async def _stop_platform(
        self,
        platform_name: str,
        handler: PlatformHandler,
    ) -> None:
        """Stop a single platform handler."""
        try:
            await handler.stop()
            handler.is_running = False
            logger.info("Platform stopped: %s", platform_name)
        except Exception as e:
            logger.error("Error stopping platform %s: %s", platform_name, e)

    async def _health_check_loop(self) -> None:
        """Periodically check platform health."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every 60 seconds

                for platform_name in self.registry.list_handlers():
                    handler = self.registry.get_handler(platform_name)
                    if handler:
                        try:
                            is_healthy = await handler.health_check()
                            if not is_healthy:
                                logger.warning(
                                    "Platform health check failed: %s",
                                    platform_name
                                )
                        except Exception as e:
                            logger.error(
                                "Health check error for %s: %s",
                                platform_name,
                                e
                            )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Unexpected error in health check loop: %s", e)

    def get_status(self) -> Dict[str, Any]:
        """Get status of all platforms."""
        status = {
            "platforms": {}
        }

        for platform_name in self.registry.list_handlers():
            config = self.registry.get_config(platform_name)
            handler = self.registry.get_handler(platform_name)

            status["platforms"][platform_name] = {
                "type": config.platform_type.value,
                "enabled": config.enabled,
                "running": handler.is_running if handler else False,
            }

        return status
