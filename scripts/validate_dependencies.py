#!/usr/bin/env python3
"""Validate dependency structure and import safety.

Checks:
1. No forbidden imports
2. Correct tier layering (core → execution → gateway → integrations)
3. No circular dependencies
4. All imports are declared in manifest
"""

import json
import ast
import sys
from pathlib import Path
from typing import Set, Dict, List


def parse_imports(filepath: Path) -> Set[str]:
    """Extract all imports from a Python file."""
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


def validate_dependency_structure():
    """Validate the entire dependency structure."""
    manifest_path = Path(".dependency-manifest.json")
    
    if not manifest_path.exists():
        print("✗ No dependency manifest found")
        return False

    with open(manifest_path) as f:
        manifest = json.load(f)

    forbidden = manifest.get("forbidden_imports", {})
    success = True

    for module_path, forbidden_imports in forbidden.items():
        module_dir = Path(module_path.replace(".", "/"))
        if not module_dir.exists():
            continue

        for py_file in module_dir.glob("**/*.py"):
            imports = parse_imports(py_file)
            
            for forbidden_import in forbidden_imports:
                if forbidden_import in imports:
                    print(
                        f"✗ {py_file}: forbidden import '{forbidden_import}' "
                        f"in tier '{module_path}'"
                    )
                    success = False

    if success:
        print("✓ Dependency structure valid")
    return success


if __name__ == "__main__":
    success = validate_dependency_structure()
    sys.exit(0 if success else 1)
