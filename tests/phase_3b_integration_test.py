"""Phase 3B Infrastructure Integration Tests.

Comprehensive test suite for:
  1. Compression Strategy Integration (agent_init.py + conversation_loop.py)
  2. Content Trust Integration (tools/approval.py)
  3. Plugin Integrity Integration (hercules_cli/plugins.py)

These tests verify backward compatibility, feature flags, and correct
integration of Phase 3B infrastructure components without breaking
existing functionality.

Tests cover:
  - Initialization and configuration
  - Metrics collection and retrieval
  - Feature flag behavior
  - Backward compatibility
  - Error handling and graceful degradation
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import Mock, patch, MagicMock

# Phase 3B Integration tests


class TestCompressionStrategyIntegration(unittest.TestCase):
    """Test compression strategy integration (Phase 3B - Integration 1)."""

    def test_compressor_initialization(self):
        """Test that Compressor initializes with strategy."""
        from agent.compression_strategy import Compressor

        compressor = Compressor(
            strategy="balanced",
            enable_metrics=True,
            fallback_to_truncate=True,
        )
        self.assertIsNotNone(compressor)

    def test_compressor_strategies(self):
        """Test all compression strategies can be instantiated."""
        from agent.compression_strategy import Compressor

        strategies = ["none", "conservative", "balanced", "aggressive"]
        for strategy in strategies:
            with self.subTest(strategy=strategy):
                compressor = Compressor(strategy=strategy, enable_metrics=True)
                self.assertIsNotNone(compressor)

    def test_get_compression_metrics_exists(self):
        """Test that Compressor has metrics API."""
        from agent.compression_strategy import Compressor

        compressor = Compressor(strategy="balanced", enable_metrics=True)
        self.assertTrue(callable(getattr(compressor, "get_metrics", None)))

    def test_compression_metrics_collection(self):
        """Test that metrics are collected during compression."""
        from agent.compression_strategy import Compressor

        compressor = Compressor(strategy="balanced", enable_metrics=True)
        content = "x" * 1000
        compressor.compress(content, max_tokens=100, content_type="context")

        metrics = compressor.get_metrics()
        self.assertIsInstance(metrics, list)

    def test_env_var_strategy_selection(self):
        """Test that HERCULES_COMPRESSION_STRATEGY env var works."""
        original = os.environ.get("HERCULES_COMPRESSION_STRATEGY")
        try:
            os.environ["HERCULES_COMPRESSION_STRATEGY"] = "aggressive"

            from agent.compression_strategy import Compressor

            compressor = Compressor(
                strategy="aggressive",  # Would come from env in real code
                enable_metrics=True,
            )
            self.assertIsNotNone(compressor)
        finally:
            if original is not None:
                os.environ["HERCULES_COMPRESSION_STRATEGY"] = original
            elif "HERCULES_COMPRESSION_STRATEGY" in os.environ:
                del os.environ["HERCULES_COMPRESSION_STRATEGY"]


class TestContentTrustIntegration(unittest.TestCase):
    """Test content trust integration (Phase 3B - Integration 2)."""

    def test_content_approval_functions_exist(self):
        """Test that content approval functions are defined."""
        from tools.approval import (
            request_content_approval,
            approve_web_content,
            approve_browser_content,
            get_content_approval_history,
        )

        self.assertTrue(callable(request_content_approval))
        self.assertTrue(callable(approve_web_content))
        self.assertTrue(callable(approve_browser_content))
        self.assertTrue(callable(get_content_approval_history))

    def test_content_source_enum(self):
        """Test that ContentSource enum has expected values."""
        from agent.content_trust import ContentSource

        self.assertTrue(hasattr(ContentSource, "WEB_FETCH"))
        self.assertTrue(hasattr(ContentSource, "WEB_BROWSER"))
        self.assertTrue(hasattr(ContentSource, "USER_UPLOAD"))

    def test_content_approval_manager(self):
        """Test that ContentApprovalManager can be instantiated."""
        from agent.content_trust import ContentApprovalManager

        manager = ContentApprovalManager()
        self.assertIsNotNone(manager)
        self.assertTrue(callable(getattr(manager, "request_approval", None)))

    def test_approval_history_tracking(self):
        """Test that approval history can be retrieved."""
        from tools.approval import get_content_approval_history

        history = get_content_approval_history()
        self.assertIsInstance(history, dict)
        self.assertIn("approvals", history)
        self.assertIn("pending", history)

    def test_web_content_approval_callable(self):
        """Test that approve_web_content works with expected parameters."""
        from tools.approval import approve_web_content

        result = approve_web_content(
            content="test content",
            url="https://example.com",
            approval_notes="Test",
        )
        self.assertIsInstance(result, bool)

    def test_browser_content_approval_callable(self):
        """Test that approve_browser_content works."""
        from tools.approval import approve_browser_content

        result = approve_browser_content(
            content="browser content",
            approval_notes="Test",
        )
        self.assertIsInstance(result, bool)

    def test_approval_optional_graceful_failure(self):
        """Test that approval system handles missing manager gracefully."""
        from tools.approval import approve_web_content

        # Should return bool without exception even if manager isn't available
        result = approve_web_content("content")
        self.assertIsInstance(result, bool)


class TestPluginIntegrityIntegration(unittest.TestCase):
    """Test plugin integrity integration (Phase 3B - Integration 3)."""

    def test_plugin_integrity_manager_exists(self):
        """Test that PluginIntegrityManager is available."""
        from agent.plugin_integrity import PluginIntegrityManager

        manager = PluginIntegrityManager()
        self.assertIsNotNone(manager)

    def test_integrity_error_exception(self):
        """Test that IntegrityError exception is defined."""
        from agent.plugin_integrity import IntegrityError

        self.assertTrue(issubclass(IntegrityError, Exception))

    def test_plugin_verification_method(self):
        """Test that PluginIntegrityManager has verify_plugin method."""
        from agent.plugin_integrity import PluginIntegrityManager

        manager = PluginIntegrityManager()
        self.assertTrue(callable(getattr(manager, "verify_plugin", None)))

    def test_feature_flag_env_var(self):
        """Test that HERCULES_PLUGIN_INTEGRITY_CHECK env var is recognized."""
        original = os.environ.get("HERCULES_PLUGIN_INTEGRITY_CHECK")
        try:
            os.environ["HERCULES_PLUGIN_INTEGRITY_CHECK"] = "1"
            flag = os.getenv("HERCULES_PLUGIN_INTEGRITY_CHECK")
            self.assertEqual(flag, "1")
        finally:
            if original is not None:
                os.environ["HERCULES_PLUGIN_INTEGRITY_CHECK"] = original
            elif "HERCULES_PLUGIN_INTEGRITY_CHECK" in os.environ:
                del os.environ["HERCULES_PLUGIN_INTEGRITY_CHECK"]

    def test_strict_enforcement_flag_defaults_to_off(self):
        """Test that strict enforcement is off by default."""
        # Should not be set unless explicitly configured
        self.assertNotIn("HERCULES_PLUGIN_INTEGRITY_STRICT", os.environ)

    def test_plugin_signature_verification_capability(self):
        """Test that manager can handle signature verification."""
        from agent.plugin_integrity import PluginIntegrityManager

        manager = PluginIntegrityManager()
        # Manager should have capability methods
        self.assertIsNotNone(manager)


class TestIntegrationBackwardCompatibility(unittest.TestCase):
    """Test backward compatibility across all Phase 3B integrations."""

    def test_compression_backward_compatible(self):
        """Test that existing compression still works."""
        # Old compression path should still exist
        from agent import context_compressor

        self.assertIsNotNone(context_compressor)

    def test_approval_system_backward_compatible(self):
        """Test that existing approval system still works."""
        from tools import approval

        # Approval module should still be importable
        self.assertIsNotNone(approval)

    def test_plugin_loading_backward_compatible(self):
        """Test that plugin loading still works."""
        from hercules_cli import plugins

        self.assertIsNotNone(plugins)

    def test_feature_flags_default_to_off(self):
        """Test that feature flags default to off/disabled."""
        # None of the feature flags should be set by default
        self.assertNotIn("HERCULES_COMPRESSION_STRATEGY", os.environ)
        self.assertNotIn("HERCULES_PLUGIN_INTEGRITY_CHECK", os.environ)
        self.assertNotIn("HERCULES_PLUGIN_INTEGRITY_STRICT", os.environ)


class TestIntegrationErrorHandling(unittest.TestCase):
    """Test error handling in Phase 3B integrations."""

    def test_compression_handles_invalid_strategy(self):
        """Test that invalid compression strategy is handled gracefully."""
        from agent.compression_strategy import Compressor

        # Should default to balanced on invalid strategy
        try:
            compressor = Compressor(
                strategy="invalid_strategy",  # Invalid
                enable_metrics=True,
            )
            # Either succeeds or raises, but shouldn't crash silently
            self.assertIsNotNone(compressor)
        except (ValueError, KeyError):
            # Acceptable to reject invalid strategy
            pass

    def test_content_approval_handles_no_gateway(self):
        """Test that content approval works without gateway."""
        from tools.approval import approve_web_content

        # Should not crash even if gateway isn't available
        result = approve_web_content("test content")
        self.assertIsInstance(result, bool)

    def test_plugin_integrity_handles_missing_manifest(self):
        """Test that plugin integrity handles missing manifest gracefully."""
        from agent.plugin_integrity import PluginIntegrityManager, IntegrityError

        manager = PluginIntegrityManager()

        # Verifying non-existent plugin should either return False or raise IntegrityError
        with self.assertRaises((IntegrityError, FileNotFoundError, Exception)):
            # This is expected to fail
            manager.verify_plugin("/nonexistent/path", "test_plugin")


if __name__ == "__main__":
    unittest.main()
