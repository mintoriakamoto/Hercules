"""Tests for dependency structure and import safety."""

import json
import ast
import sys
from pathlib import Path


class TestDependencyStructure:
    """Validate dependency tier separation."""

    @staticmethod
    def get_manifest():
        """Load dependency manifest."""
        manifest_path = Path(".dependency-manifest.json")
        with open(manifest_path) as f:
            return json.load(f)

    @staticmethod
    def get_imports(filepath: Path):
        """Extract imports from a Python file."""
        imports = set()
        try:
            with open(filepath) as f:
                tree = ast.parse(f.read())
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module.split('.')[0])
        except SyntaxError:
            pass
        
        return imports

    def test_no_forbidden_imports(self):
        """Ensure forbidden imports are not present."""
        manifest = self.get_manifest()
        forbidden = manifest.get("forbidden_imports", {})

        failures = []
        for module_path, forbidden_imports in forbidden.items():
            module_dir = Path(module_path.replace(".", "/"))
            if not module_dir.exists():
                continue

            for py_file in module_dir.glob("**/*.py"):
                imports = self.get_imports(py_file)
                for forbidden_import in forbidden_imports:
                    if forbidden_import in imports:
                        failures.append(
                            f"{py_file}: forbidden '{forbidden_import}' in {module_path}"
                        )

        assert not failures, "\n".join(failures)

    def test_core_has_no_external_deps(self):
        """Core tier should only import stdlib + anthropic + pydantic."""
        allowed = {
            "asyncio", "json", "time", "logging", "collections",
            "dataclasses", "typing", "functools", "hashlib",
            "anthropic", "pydantic", "agent"
        }
        
        core_dir = Path("agent/core")
        if not core_dir.exists():
            return

        for py_file in core_dir.glob("**/*.py"):
            if py_file.name == "__pycache__":
                continue
            
            imports = self.get_imports(py_file)
            disallowed = imports - allowed
            
            assert not disallowed, (
                f"{py_file} imports disallowed packages: {disallowed}"
            )

    def test_execution_tier_dependencies(self):
        """Execution tier should only depend on core."""
        exec_dir = Path("agent/execution")
        if not exec_dir.exists():
            return

        allowed = {
            "asyncio", "json", "time", "logging", "collections",
            "dataclasses", "typing", "functools", "hashlib",
            "anthropic", "pydantic", "agent"
        }

        for py_file in exec_dir.glob("**/*.py"):
            if py_file.name == "__pycache__":
                continue
            
            imports = self.get_imports(py_file)
            disallowed = imports - allowed
            
            assert not disallowed, (
                f"{py_file} imports disallowed: {disallowed}"
            )


if __name__ == "__main__":
    test = TestDependencyStructure()
    test.test_no_forbidden_imports()
    test.test_core_has_no_external_deps()
    test.test_execution_tier_dependencies()
    print("✓ All dependency structure tests passed")
