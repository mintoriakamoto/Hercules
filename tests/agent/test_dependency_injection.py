"""Test dependency injection container."""

import unittest
from unittest.mock import Mock, patch

from agent.dependency_injection import DependencyContainer, requires_dependency


class TestDependencyContainer(unittest.TestCase):
    """Test the dependency injection container."""

    def setUp(self):
        """Clear dependencies before each test."""
        DependencyContainer.clear()

    def test_register_and_get(self):
        """Test registering and retrieving a dependency."""
        @DependencyContainer.register("test_dep", tier="core")
        def create_test():
            return "test_value"

        result = DependencyContainer.get("test_dep")
        self.assertEqual(result, "test_value")

    def test_lazy_initialization(self):
        """Test that dependencies are lazy-initialized."""
        call_count = 0

        @DependencyContainer.register("lazy_dep", tier="core")
        def create_lazy():
            nonlocal call_count
            call_count += 1
            return "lazy"

        # First call initializes
        DependencyContainer.get("lazy_dep")
        self.assertEqual(call_count, 1)

        # Second call returns cached
        DependencyContainer.get("lazy_dep")
        self.assertEqual(call_count, 1)

    def test_required_dependency_missing(self):
        """Test that required missing dependencies raise errors."""
        with self.assertRaises(ImportError):
            DependencyContainer.get("nonexistent_dep", required=True)

    def test_optional_dependency_missing(self):
        """Test that optional missing dependencies return None."""
        result = DependencyContainer.get("nonexistent_dep", required=False)
        self.assertIsNone(result)

    def test_requires_dependency_decorator(self):
        """Test the requires_dependency decorator."""
        @requires_dependency("test_func_dep", tier="core")
        def my_function(_dep=None):
            return _dep.value

        @DependencyContainer.register("test_func_dep", tier="core")
        def create_test_func():
            mock = Mock()
            mock.value = 42
            return mock

        result = my_function()
        self.assertEqual(result, 42)

    def test_clear_cache(self):
        """Test clearing the dependency cache."""
        @DependencyContainer.register("clear_test", tier="core")
        def create_clear():
            return "clear_value"

        DependencyContainer.get("clear_test")
        DependencyContainer.clear()

        call_count = 0

        @DependencyContainer.register("clear_test", tier="core")
        def create_clear_v2():
            nonlocal call_count
            call_count += 1
            return "clear_value_v2"

        DependencyContainer.get("clear_test")
        self.assertEqual(call_count, 1)


if __name__ == "__main__":
    unittest.main()
