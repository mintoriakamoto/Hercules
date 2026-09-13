"""Hercules AI Agent SDK.

Standalone Python library for running conversational AI agents with tool execution,
model provider flexibility, and sophisticated context management.

This package is decoupled from CLI concerns to enable:
  - Standalone SDK usage
  - Programmatic agent control
  - Embedded agent deployment
  - Third-party integrations

Quick start:
    from hercules_agent import AgentBuilder, create_agent

    config = (AgentBuilder()
        .with_model("claude-opus-5")
        .with_provider("anthropic_messages")
        .enable_compression("balanced")
        .build()
    )

    agent = create_agent(config)
    response = agent.run("What is 2+2?")

See core_api.py for full API reference.
"""

from hercules_agent.core_api import (
    AgentBuilder,
    AgentConfig,
    ProviderMode,
    create_agent,
    run_conversation,
)

__version__ = "0.1.0"
__all__ = [
    "AgentBuilder",
    "AgentConfig",
    "ProviderMode",
    "create_agent",
    "run_conversation",
]
