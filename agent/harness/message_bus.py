"""Message bus for inter-agent communication.

Implements formal message protocol with:
- FIFO delivery guarantees
- Idempotent message handling
- Async/await pattern
- Correlation tracking
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Callable, List
from enum import Enum
from datetime import datetime
import uuid


class MessageType(Enum):
    """Message types in harness protocol."""
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


@dataclass
class Message:
    """Formal message in agent communication."""
    message_id: str
    correlation_id: str  # Links related messages
    from_agent: str
    to_agent: str
    message_type: MessageType
    payload: Dict[str, Any]
    timestamp: float
    reply_to: Optional[str] = None
    idempotency_key: Optional[str] = None

    def is_response_to(self, other: "Message") -> bool:
        """Check if this is a response to another message."""
        return self.reply_to == other.message_id


@dataclass
class DeliveryGuarantee:
    """Delivery guarantee for message."""
    level: str  # "at_most_once", "at_least_once", "exactly_once"
    retry_count: int = 0
    max_retries: int = 3
    timeout_s: int = 30


class MessageBus:
    """Central message bus for agent communication."""

    def __init__(self):
        self.queues: Dict[str, asyncio.Queue] = {}
        self.message_log: List[Message] = []
        self.sent_messages: Dict[str, Message] = {}
        self.delivered_messages: set = set()  # For idempotency

    async def register_agent(self, agent_id: str):
        """Register agent with bus."""
        if agent_id not in self.queues:
            self.queues[agent_id] = asyncio.Queue()

    async def send_message(
        self,
        from_agent: str,
        to_agent: str,
        message_type: MessageType,
        payload: Dict[str, Any],
        guarantee: DeliveryGuarantee = None,
        idempotency_key: Optional[str] = None,
    ) -> str:
        """Send message with delivery guarantee."""
        if guarantee is None:
            guarantee = DeliveryGuarantee(level="at_most_once")

        message_id = str(uuid.uuid4())
        correlation_id = str(uuid.uuid4())

        message = Message(
            message_id=message_id,
            correlation_id=correlation_id,
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            payload=payload,
            timestamp=datetime.now().timestamp(),
            idempotency_key=idempotency_key,
        )

        # Store for idempotent delivery
        if idempotency_key:
            if idempotency_key in self.delivered_messages:
                return message_id  # Already delivered

        self.sent_messages[message_id] = message
        self.message_log.append(message)

        # Queue message
        if to_agent in self.queues:
            await self.queues[to_agent].put(message)

            # Mark as delivered for idempotency
            if idempotency_key:
                self.delivered_messages.add(idempotency_key)

        return message_id

    async def receive_message(
        self, agent_id: str, timeout_s: int = 30
    ) -> Optional[Message]:
        """Receive next message for agent (blocking)."""
        if agent_id not in self.queues:
            return None

        try:
            message = await asyncio.wait_for(
                self.queues[agent_id].get(), timeout=timeout_s
            )
            return message
        except asyncio.TimeoutError:
            return None

    async def send_reply(
        self,
        from_agent: str,
        original_message: Message,
        payload: Dict[str, Any],
    ) -> str:
        """Send reply to message."""
        message_id = str(uuid.uuid4())

        reply = Message(
            message_id=message_id,
            correlation_id=original_message.correlation_id,
            from_agent=from_agent,
            to_agent=original_message.from_agent,
            message_type=MessageType.RESPONSE,
            payload=payload,
            timestamp=datetime.now().timestamp(),
            reply_to=original_message.message_id,
        )

        self.message_log.append(reply)

        if original_message.from_agent in self.queues:
            await self.queues[original_message.from_agent].put(reply)

        return message_id

    def get_conversation(self, correlation_id: str) -> List[Message]:
        """Get all messages in a conversation."""
        return [m for m in self.message_log if m.correlation_id == correlation_id]

    def get_agent_trace(self, agent_id: str) -> List[Message]:
        """Get all messages involving an agent."""
        return [
            m for m in self.message_log
            if m.from_agent == agent_id or m.to_agent == agent_id
        ]


class MessageBusPool:
    """Pool of message buses for multi-harness systems."""

    def __init__(self, num_buses: int = 1):
        self.buses = [MessageBus() for _ in range(num_buses)]
        self.agent_to_bus: Dict[str, int] = {}

    async def register_agent(self, agent_id: str, bus_id: int = 0):
        """Register agent to specific bus."""
        if bus_id >= len(self.buses):
            raise ValueError(f"Bus {bus_id} does not exist")

        self.agent_to_bus[agent_id] = bus_id
        await self.buses[bus_id].register_agent(agent_id)

    async def send_message(
        self,
        from_agent: str,
        to_agent: str,
        message_type: MessageType,
        payload: Dict[str, Any],
    ) -> str:
        """Send message (routes to correct bus)."""
        if from_agent not in self.agent_to_bus:
            raise ValueError(f"Agent {from_agent} not registered")

        bus_id = self.agent_to_bus[from_agent]
        return await self.buses[bus_id].send_message(
            from_agent, to_agent, message_type, payload
        )


__all__ = [
    "Message",
    "MessageType",
    "MessageBus",
    "MessageBusPool",
    "DeliveryGuarantee",
]
