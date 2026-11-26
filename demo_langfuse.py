#!/usr/bin/env python3
"""
Langfuse Integration Demo for Hercules Agent

This script demonstrates end-to-end Langfuse instrumentation:
1. Creates a mock Hercules agent
2. Instruments it with Langfuse
3. Executes a conversation
4. Traces appear in Langfuse project

Setup:
    1. Create Langfuse account: https://langfuse.com/cloud
    2. Create a new project
    3. Get API keys from Settings → API Keys
    4. Set environment variables:
       export LANGFUSE_PUBLIC_KEY="pk-lf-..."
       export LANGFUSE_SECRET_KEY="sk-lf-..."
       export LANGFUSE_BASE_URL="https://cloud.langfuse.com"
    5. Run: python demo_langfuse.py

Output:
    - Traces visible at: https://cloud.langfuse.com/project/<project-id>/traces
"""

import os
import sys
import logging
import json
import time
from typing import Optional, List, Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)


class MockAIAgent:
    """Mock Hercules AIAgent for demo purposes."""

    def __init__(self, model: str = "claude-opus-4", base_url: str = "http://localhost:30000/v1"):
        self.model = model
        self.base_url = base_url
        self.message_history: List[Dict[str, str]] = []

    def run_conversation(self, user_prompt: str, **kwargs) -> str:
        """Simulate agent conversation."""
        logger.info(f"[Agent] User: {user_prompt}")

        # Simulate thinking time
        time.sleep(0.5)

        # Mock response
        response = f"I received your prompt: '{user_prompt}'. "
        response += f"I would process this using my {self.model} model. "
        response += "This is a demo response showing Langfuse integration."

        logger.info(f"[Agent] Assistant: {response[:100]}...")
        return response


def demo_basic_tracing():
    """Demo 1: Basic conversation tracing."""
    print("\n" + "="*70)
    print("DEMO 1: Basic Conversation Tracing")
    print("="*70)

    from langfuse_integration import LangfuseObserver

    try:
        # Initialize observer
        observer = LangfuseObserver()
        logger.info(f"✓ Connected to Langfuse at {observer.base_url}")

        # Create mock agent
        agent = MockAIAgent()

        # Instrument agent
        agent = observer.instrument_agent(agent)
        logger.info("✓ Agent instrumented with Langfuse")

        # Run conversation (auto-traced)
        response = agent.run_conversation("What is machine learning?")

        # Flush events
        observer.flush()
        logger.info("✓ Trace flushed to Langfuse")

        print(f"\n✓ Response: {response[:100]}...")
        print(f"✓ Traces visible in Langfuse dashboard")
        return True

    except Exception as e:
        logger.error(f"✗ Demo failed: {e}")
        return False


def demo_manual_tracing():
    """Demo 2: Manual span and event tracing."""
    print("\n" + "="*70)
    print("DEMO 2: Manual Span & Tool Tracing")
    print("="*70)

    from langfuse_integration import LangfuseObserver

    try:
        observer = LangfuseObserver()

        # Start trace
        trace_id = observer.start_trace(
            name="agent-with-tools",
            metadata={"scenario": "search-and-summarize"}
        )
        logger.info(f"✓ Trace started: {trace_id}")

        try:
            # Simulate tool execution 1: Search
            with observer.span_context("web-search") as span:
                logger.info("  - Searching web for 'Python ML libraries'...")
                time.sleep(0.3)
                search_results = [
                    {"title": "NumPy Documentation", "url": "numpy.org"},
                    {"title": "scikit-learn", "url": "scikit-learn.org"},
                    {"title": "TensorFlow", "url": "tensorflow.org"},
                ]
                span.update(output=search_results)
                logger.info(f"  - Found {len(search_results)} results")

            # Simulate LLM generation
            observer.log_generation(
                model="claude-opus-4",
                prompt="Summarize these ML libraries: NumPy, scikit-learn, TensorFlow",
                completion="NumPy provides numerical computing, scikit-learn offers ML algorithms, TensorFlow enables deep learning.",
                input_tokens=45,
                output_tokens=28,
                cost_usd=0.00125,
                name="summarize-libraries"
            )
            logger.info("✓ LLM generation logged")

            # Simulate tool execution 2: Save to database
            observer.log_tool_call(
                tool_name="save-summary",
                tool_input={"key": "ml-libs-summary"},
                tool_output={"id": "doc_123", "saved_at": "2026-11-26T10:30:00Z"},
                success=True,
                duration_ms=150
            )
            logger.info("✓ Tool execution logged")

            # End trace
            observer.end_trace(metadata={
                "tools_used": 2,
                "tokens_total": 73,
                "cost_usd": 0.00125,
            })

        except Exception as e:
            observer.end_trace(metadata={"error": str(e)})
            raise

        observer.flush()
        logger.info("✓ All spans and events flushed")
        return True

    except Exception as e:
        logger.error(f"✗ Demo failed: {e}")
        return False


def demo_error_tracking():
    """Demo 3: Error and retry tracking."""
    print("\n" + "="*70)
    print("DEMO 3: Error Tracking & Recovery")
    print("="*70)

    from langfuse_integration import LangfuseObserver

    try:
        observer = LangfuseObserver()

        with observer.trace_context("agent-with-error-recovery") as trace_id:
            logger.info(f"✓ Trace started for error demo: {trace_id}")

            # Simulate first attempt failure
            with observer.span_context("api-call-attempt-1") as span:
                try:
                    logger.info("  - Attempt 1: Calling external API...")
                    time.sleep(0.2)
                    raise Exception("API timeout")
                except Exception as e:
                    span.update(metadata={
                        "status": "failed",
                        "error": str(e),
                        "attempt": 1,
                    })
                    logger.warning(f"  - Attempt 1 failed: {e}")

            # Simulate retry
            time.sleep(0.3)
            with observer.span_context("api-call-attempt-2") as span:
                logger.info("  - Attempt 2: Retrying...")
                time.sleep(0.2)
                result = {"data": "success"}
                span.update(output=result, metadata={
                    "status": "succeeded",
                    "attempt": 2,
                    "recovery_time_ms": 300,
                })
                logger.info("  - Attempt 2 succeeded")

            observer.end_trace(metadata={
                "retries": 1,
                "final_status": "recovered",
            })

        observer.flush()
        logger.info("✓ Error recovery trace complete")
        return True

    except Exception as e:
        logger.error(f"✗ Demo failed: {e}")
        return False


def print_setup_instructions():
    """Print setup instructions."""
    print("\n" + "="*70)
    print("SETUP INSTRUCTIONS")
    print("="*70)

    creds = {
        "public_key": os.getenv("LANGFUSE_PUBLIC_KEY", "NOT SET"),
        "secret_key": os.getenv("LANGFUSE_SECRET_KEY", "NOT SET"),
        "base_url": os.getenv("LANGFUSE_BASE_URL", "NOT SET"),
    }

    all_set = all(v != "NOT SET" for v in creds.values())

    if all_set:
        print("\n✓ Langfuse credentials are configured!")
        print(f"  Public Key: {creds['public_key'][:20]}...")
        print(f"  Base URL: {creds['base_url']}")
    else:
        print("\n✗ Langfuse credentials not fully configured.\n")
        print("To set up Langfuse:")
        print("  1. Create account: https://langfuse.com/cloud")
        print("  2. Create a new project")
        print("  3. Get API keys from Settings → API Keys")
        print("  4. Set environment variables:\n")
        print("     export LANGFUSE_PUBLIC_KEY=\"pk-lf-...\"")
        print("     export LANGFUSE_SECRET_KEY=\"sk-lf-...\"")
        print("     export LANGFUSE_BASE_URL=\"https://cloud.langfuse.com\"")
        print("\n  5. Run this script again")

    print("\n  After running demos, view traces at:")
    print("  → https://cloud.langfuse.com/project/<project-id>/traces\n")


def main():
    """Run all demos."""
    print("\n╔" + "="*68 + "╗")
    print("║" + " "*15 + "HERCULES + LANGFUSE OBSERVABILITY DEMO" + " "*13 + "║")
    print("╚" + "="*68 + "╝")

    print_setup_instructions()

    # Check credentials
    if not all([
        os.getenv("LANGFUSE_PUBLIC_KEY"),
        os.getenv("LANGFUSE_SECRET_KEY"),
    ]):
        print("\n⚠  Skipping demos - Langfuse credentials not set")
        print("   Set environment variables and try again")
        return False

    results = {}

    # Run demos
    try:
        results["Basic Tracing"] = demo_basic_tracing()
    except Exception as e:
        logger.error(f"Basic tracing demo error: {e}")
        results["Basic Tracing"] = False

    try:
        results["Manual Tracing"] = demo_manual_tracing()
    except Exception as e:
        logger.error(f"Manual tracing demo error: {e}")
        results["Manual Tracing"] = False

    try:
        results["Error Tracking"] = demo_error_tracking()
    except Exception as e:
        logger.error(f"Error tracking demo error: {e}")
        results["Error Tracking"] = False

    # Summary
    print("\n" + "="*70)
    print("DEMO SUMMARY")
    print("="*70)
    for name, success in results.items():
        status = "✓ PASSED" if success else "✗ FAILED"
        print(f"{status}: {name}")

    all_passed = all(results.values())

    print("\n" + "="*70)
    if all_passed:
        print("✓ All demos completed successfully!")
        print("\nNext steps:")
        print("  1. View traces: https://cloud.langfuse.com/dashboard")
        print("  2. Check metrics on the Traces page")
        print("  3. Integrate into your Hercules agent code:")
        print("     from langfuse_integration import LangfuseObserver")
        print("     observer = LangfuseObserver()")
        print("     agent = observer.instrument_agent(agent)")
    else:
        print("✗ Some demos failed - check logs above")
    print("="*70 + "\n")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
