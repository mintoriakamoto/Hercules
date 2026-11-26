#!/usr/bin/env python3
"""
Langfuse Observability Integration for Hercules Agent

This module instruments the Hercules agent runtime with Langfuse tracing:
- Captures agent conversations as traces
- Tracks LLM model calls (generations)
- Monitors tool execution
- Records token usage and costs
- Captures errors and retries
- Enables performance analytics and debugging

Usage:
    from langfuse_integration import LangfuseObserver

    # Initialize with Langfuse credentials
    observer = LangfuseObserver(
        public_key="pk-lf-...",
        secret_key="sk-lf-...",
        base_url="https://cloud.langfuse.com",
    )

    # Wrap agent creation
    agent = observer.instrument_agent(agent)

    # Run agent - traces auto-capture
    response = agent.run_conversation(user_prompt)
"""

import os
import json
import time
import logging
from typing import Optional, Dict, Any, Callable, List
from functools import wraps
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class LangfuseObserver:
    """Instruments Hercules agent with Langfuse observability."""

    def __init__(
        self,
        public_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        base_url: Optional[str] = None,
        enable_async: bool = False,
    ):
        """Initialize Langfuse observer.

        Args:
            public_key: Langfuse public API key (from Settings → API Keys)
            secret_key: Langfuse secret API key
            base_url: Langfuse instance URL (e.g., https://cloud.langfuse.com)
            enable_async: Whether to use async flush (non-blocking)
        """
        # Read from env if not provided
        self.public_key = public_key or os.getenv("LANGFUSE_PUBLIC_KEY")
        self.secret_key = secret_key or os.getenv("LANGFUSE_SECRET_KEY")
        self.base_url = base_url or os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")

        if not self.public_key or not self.secret_key:
            raise ValueError(
                "Langfuse credentials not provided. Set LANGFUSE_PUBLIC_KEY "
                "and LANGFUSE_SECRET_KEY environment variables or pass to constructor."
            )

        self.enable_async = enable_async
        self._client = None
        self._traces_stack = []
        self._current_trace = None
        self._current_span = None
        self._spans_stack = []

    @property
    def client(self):
        """Lazy-load Langfuse client on first access."""
        if self._client is None:
            try:
                from langfuse import Langfuse
                self._client = Langfuse(
                    public_key=self.public_key,
                    secret_key=self.secret_key,
                    host=self.base_url,
                    enabled=True,
                    flush_at=1 if self.enable_async else 100,
                    flush_interval=0.5 if self.enable_async else 5.0,
                )
                logger.info(f"✓ Langfuse client initialized: {self.base_url}")
            except ImportError:
                raise ImportError(
                    "Langfuse not installed. Install with: pip install langfuse"
                )
        return self._client

    def start_trace(self, name: str, user_id: Optional[str] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> str:
        """Start a new trace (top-level observation).

        Args:
            name: Trace name (e.g., "agent-conversation")
            user_id: User ID for attribution
            metadata: Custom metadata dict

        Returns:
            Trace ID for reference
        """
        trace = self.client.trace(
            name=name,
            user_id=user_id or "anonymous",
            metadata=metadata or {},
        )
        self._current_trace = trace
        self._traces_stack.append(trace)
        return trace.id

    def end_trace(self, metadata: Optional[Dict[str, Any]] = None):
        """End current trace."""
        if self._current_trace:
            if metadata:
                self._current_trace.update(metadata=metadata)
            self._current_trace = None
        if self._traces_stack:
            self._traces_stack.pop()

    def start_span(self, name: str, span_type: str = "span",
                  metadata: Optional[Dict[str, Any]] = None):
        """Start a named span under current trace.

        Args:
            name: Span name (e.g., "tool-execution")
            span_type: Type of span (span, generation, event, etc.)
            metadata: Custom metadata
        """
        if not self._current_trace:
            raise RuntimeError("No active trace. Call start_trace() first.")

        span = self._current_trace.span(
            name=name,
            metadata=metadata or {},
        )
        self._current_span = span
        self._spans_stack.append(span)
        return span

    def end_span(self, metadata: Optional[Dict[str, Any]] = None):
        """End current span."""
        if self._current_span:
            if metadata:
                self._current_span.update(metadata=metadata)
            self._current_span = None
        if self._spans_stack:
            self._spans_stack.pop()

    @contextmanager
    def trace_context(self, name: str, user_id: Optional[str] = None,
                     metadata: Optional[Dict[str, Any]] = None):
        """Context manager for automatic trace lifecycle.

        Example:
            with observer.trace_context("my-trace") as trace_id:
                # do work
        """
        trace_id = self.start_trace(name, user_id, metadata)
        try:
            yield trace_id
        finally:
            self.end_trace()

    @contextmanager
    def span_context(self, name: str, metadata: Optional[Dict[str, Any]] = None):
        """Context manager for automatic span lifecycle."""
        self.start_span(name, metadata=metadata)
        try:
            yield self._current_span
        finally:
            self.end_span()

    def log_generation(self, model: str, prompt: str, completion: str,
                      input_tokens: int, output_tokens: int,
                      cost_usd: Optional[float] = None,
                      name: str = "llm-call"):
        """Log an LLM generation (model call).

        Args:
            model: Model name (e.g., "claude-opus-4")
            prompt: Input prompt/messages
            completion: Model response
            input_tokens: Tokens used in input
            output_tokens: Tokens in output
            cost_usd: Estimated cost in USD
            name: Generation name
        """
        if not self._current_trace:
            raise RuntimeError("No active trace for generation logging.")

        generation = self._current_trace.generation(
            name=name,
            model=model,
            input=prompt,
            output=completion,
            usage={
                "input": input_tokens,
                "output": output_tokens,
            },
            metadata={
                "cost_usd": cost_usd,
                "total_tokens": input_tokens + output_tokens,
            },
        )
        return generation

    def log_tool_call(self, tool_name: str, tool_input: Dict[str, Any],
                     tool_output: Any, success: bool = True,
                     error: Optional[str] = None, duration_ms: float = 0):
        """Log a tool execution.

        Args:
            tool_name: Name of tool called
            tool_input: Input arguments to tool
            tool_output: Result from tool
            success: Whether tool succeeded
            error: Error message if failed
            duration_ms: Execution time in milliseconds
        """
        if not self._current_trace:
            raise RuntimeError("No active trace for tool logging.")

        with self.span_context(f"tool-{tool_name}") as span:
            span.update(
                input=tool_input,
                output=tool_output if success else None,
                metadata={
                    "tool_name": tool_name,
                    "success": success,
                    "duration_ms": duration_ms,
                    "error": error,
                },
            )

    def instrument_agent(self, agent):
        """Wrap an AIAgent instance to auto-trace conversations.

        Args:
            agent: AIAgent instance to instrument

        Returns:
            Agent instance with instrumentation applied
        """
        original_run_conversation = agent.run_conversation

        @wraps(original_run_conversation)
        def traced_run_conversation(user_prompt: str, *args, **kwargs):
            """Wrapped version with Langfuse tracing."""
            user_id = kwargs.pop("user_id", None)

            with self.trace_context(
                name="agent-conversation",
                user_id=user_id,
                metadata={
                    "model": getattr(agent, "model", "unknown"),
                    "source": "run_conversation",
                }
            ) as trace_id:
                logger.info(f"[Langfuse] Started trace: {trace_id}")

                start_time = time.time()
                try:
                    # Call original method
                    result = original_run_conversation(user_prompt, *args, **kwargs)

                    # Log successful completion
                    duration_s = time.time() - start_time
                    self.end_trace(metadata={
                        "status": "completed",
                        "duration_seconds": duration_s,
                        "user_prompt_length": len(str(user_prompt)),
                        "response_length": len(str(result)) if result else 0,
                    })

                    logger.info(f"[Langfuse] Trace completed in {duration_s:.2f}s")
                    return result

                except Exception as e:
                    # Log failed trace
                    self.end_trace(metadata={
                        "status": "failed",
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "duration_seconds": time.time() - start_time,
                    })
                    logger.error(f"[Langfuse] Trace failed: {e}")
                    raise

        agent.run_conversation = traced_run_conversation
        return agent

    def flush(self):
        """Flush all pending events to Langfuse."""
        if self._client:
            self._client.flush()
            logger.info("✓ Langfuse events flushed")


def get_observer(enable: bool = True) -> Optional[LangfuseObserver]:
    """Get or create a Langfuse observer instance.

    Args:
        enable: Whether to enable observability

    Returns:
        LangfuseObserver instance or None if disabled
    """
    if not enable:
        return None

    try:
        return LangfuseObserver()
    except ValueError as e:
        logger.warning(f"Langfuse observer disabled: {e}")
        return None
