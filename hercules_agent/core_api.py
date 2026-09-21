"""Hercules core agent API.

Public interface for the Hercules agent system, decoupled from CLI concerns.

This module provides:
  - AIAgent initialization and execution
  - Tool registry and resolution
  - Model provider configuration
  - Conversation loop control
  - No dependencies on hercules_cli package

Purpose:
  - Break circular dependency (CLI imports core, core imports CLI)
  - Enable standalone SDK usage (hercules-agent library)
  - Allow parallel development and testing
  - Support headless execution without CLI layer
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class ProviderMode(Enum):
    """Provider API modes supported by Hercules."""
    ANTHROPIC = "anthropic_messages"
    ANTHROPIC_LEGACY = "anthropic"
    OPENAI = "openai"
    BEDROCK = "bedrock"
    CODEX = "codex"
    MOA = "moa"


@dataclass
class AgentConfig:
    """Core agent configuration (serializable, no CLI dependencies).

    This thin config object contains only the essentials for agent execution.
    Environment-specific setup, secrets management, and UI concerns live
    in hercules_cli, which imports this and builds on it.
    """

    # Model configuration
    model_name: str
    provider_mode: ProviderMode
    base_url: Optional[str] = None
    api_key: Optional[str] = None

    # Execution parameters
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    max_iterations: int = 25

    # Compression and context
    compression_strategy: str = "balanced"
    context_size: int = 100000

    # Tool execution
    allow_tool_execution: bool = True
    concurrent_tools: bool = True
    max_tool_calls_per_turn: int = 10

    # Fallback behavior
    enable_fallback: bool = True
    fallback_models: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "model_name": self.model_name,
            "provider_mode": self.provider_mode.value,
            "base_url": self.base_url,
            "api_key": self.api_key,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "max_iterations": self.max_iterations,
            "compression_strategy": self.compression_strategy,
            "context_size": self.context_size,
            "allow_tool_execution": self.allow_tool_execution,
            "concurrent_tools": self.concurrent_tools,
            "max_tool_calls_per_turn": self.max_tool_calls_per_turn,
            "enable_fallback": self.enable_fallback,
            "fallback_models": self.fallback_models,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentConfig:
        """Create from dictionary."""
        provider_mode_str = data.get("provider_mode", "anthropic_messages")
        return cls(
            model_name=data["model_name"],
            provider_mode=ProviderMode(provider_mode_str),
            base_url=data.get("base_url"),
            api_key=data.get("api_key"),
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("max_tokens"),
            max_iterations=data.get("max_iterations", 25),
            compression_strategy=data.get("compression_strategy", "balanced"),
            context_size=data.get("context_size", 100000),
            allow_tool_execution=data.get("allow_tool_execution", True),
            concurrent_tools=data.get("concurrent_tools", True),
            max_tool_calls_per_turn=data.get("max_tool_calls_per_turn", 10),
            enable_fallback=data.get("enable_fallback", True),
            fallback_models=data.get("fallback_models"),
        )


class AgentBuilder:
    """Builder for creating configured Agent instances.

    Example:
        builder = AgentBuilder()
        builder.with_model("claude-opus-5")
        builder.with_provider(ProviderMode.ANTHROPIC)
        builder.enable_compression("balanced")
        agent = builder.build()
    """

    def __init__(self):
        self.config = AgentConfig(
            model_name="claude-opus-5",
            provider_mode=ProviderMode.ANTHROPIC,
        )

    def with_model(self, model_name: str) -> AgentBuilder:
        """Set model name."""
        self.config.model_name = model_name
        return self

    def with_provider(self, mode: ProviderMode | str) -> AgentBuilder:
        """Set provider mode."""
        if isinstance(mode, str):
            self.config.provider_mode = ProviderMode(mode)
        else:
            self.config.provider_mode = mode
        return self

    def with_base_url(self, url: str) -> AgentBuilder:
        """Set custom base URL."""
        self.config.base_url = url
        return self

    def with_api_key(self, key: str) -> AgentBuilder:
        """Set API key."""
        self.config.api_key = key
        return self

    def with_temperature(self, temp: float) -> AgentBuilder:
        """Set temperature."""
        self.config.temperature = max(0.0, min(1.0, temp))
        return self

    def with_max_tokens(self, tokens: int) -> AgentBuilder:
        """Set max output tokens."""
        self.config.max_tokens = tokens
        return self

    def with_max_iterations(self, iterations: int) -> AgentBuilder:
        """Set max conversation iterations."""
        self.config.max_iterations = max(1, iterations)
        return self

    def enable_compression(self, strategy: str) -> AgentBuilder:
        """Enable compression with strategy."""
        self.config.compression_strategy = strategy
        return self

    def with_context_size(self, size: int) -> AgentBuilder:
        """Set maximum context size."""
        self.config.context_size = size
        return self

    def enable_tools(self, enabled: bool = True) -> AgentBuilder:
        """Enable/disable tool execution."""
        self.config.allow_tool_execution = enabled
        return self

    def concurrent_tool_execution(self, enabled: bool = True) -> AgentBuilder:
        """Enable concurrent tool calls."""
        self.config.concurrent_tools = enabled
        return self

    def with_fallback_models(self, models: List[str]) -> AgentBuilder:
        """Set fallback models."""
        self.config.fallback_models = models
        return self

    def build(self) -> AgentConfig:
        """Build and return agent config."""
        return self.config


def create_agent(config: AgentConfig) -> Any:
    """Create an AIAgent instance from config.

    This function is the integration point between the core API (this module)
    and the actual AIAgent implementation (run_agent.py).

    Importing is deferred to avoid circular dependencies.

    Args:
        config: AgentConfig instance

    Returns:
        Configured AIAgent instance
    """
    # Lazy import to avoid circular dependency
    from run_agent import AIAgent

    return AIAgent(
        model=config.model_name,
        api_mode=config.provider_mode.value,
        base_url=config.base_url,
        api_key=config.api_key,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        max_iterations=config.max_iterations,
    )


def run_conversation(
    agent: Any,
    user_message: str,
) -> str:
    """Run a single conversation turn.

    Args:
        agent: AIAgent instance
        user_message: User's input

    Returns:
        Agent's response
    """
    # This will integrate with agent.run_conversation_step()
    # or similar when implementation is complete
    raise NotImplementedError("Integration point for conversation execution")


__all__ = [
    "ProviderMode",
    "AgentConfig",
    "AgentBuilder",
    "create_agent",
    "run_conversation",
]
