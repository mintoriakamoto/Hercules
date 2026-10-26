"""Advanced code understanding and semantic analysis.

Implements AST parsing, dependency analysis, and code structure
understanding to provide agents with deep code awareness.
"""

import ast
import json
from pathlib import Path
from typing import Dict, List, Set, Any, Optional
from collections import defaultdict


class CodeAnalyzer:
    """Analyze code structure, dependencies, and semantics."""

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.content = filepath.read_text(encoding="utf-8")
        self.tree = ast.parse(self.content)
        self._analyze()

    def _analyze(self):
        """Parse and extract code information."""
        self.functions = {}
        self.classes = {}
        self.imports = set()
        self.dependencies = defaultdict(set)
        self.exports = set()
        self.complexity = {}
        self.docstrings = {}

        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef):
                self._process_function(node)
            elif isinstance(node, ast.ClassDef):
                self._process_class(node)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                self._process_import(node)

    def _process_function(self, node: ast.FunctionDef):
        """Extract function metadata."""
        self.functions[node.name] = {
            "lineno": node.lineno,
            "col_offset": node.col_offset,
            "args": [arg.arg for arg in node.args.args],
            "returns": ast.unparse(node.returns) if node.returns else None,
            "decorators": [ast.unparse(d) for d in node.decorator_list],
            "docstring": ast.get_docstring(node),
            "complexity": self._cyclomatic_complexity(node),
        }
        self.exports.add(node.name)

    def _process_class(self, node: ast.ClassDef):
        """Extract class metadata."""
        methods = {}
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                methods[item.name] = {
                    "lineno": item.lineno,
                    "args": [arg.arg for arg in item.args.args],
                }

        self.classes[node.name] = {
            "lineno": node.lineno,
            "bases": [ast.unparse(b) for b in node.bases],
            "methods": methods,
            "docstring": ast.get_docstring(node),
        }
        self.exports.add(node.name)

    def _process_import(self, node):
        """Track imports and dependencies."""
        if isinstance(node, ast.Import):
            for alias in node.names:
                self.imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                self.imports.add(node.module)

    def _cyclomatic_complexity(self, node: ast.AST) -> int:
        """Calculate cyclomatic complexity."""
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        return complexity

    def get_summary(self) -> Dict[str, Any]:
        """Get high-level code summary."""
        return {
            "functions": list(self.functions.keys()),
            "classes": list(self.classes.keys()),
            "imports": list(self.imports),
            "exports": list(self.exports),
            "total_complexity": sum(self.complexity.values()),
            "avg_complexity": (
                sum(self.complexity.values()) / len(self.complexity)
                if self.complexity
                else 0
            ),
        }


class CodeRepository:
    """Analyze entire repository structure."""

    def __init__(self, root: Path = Path(".")):
        self.root = root
        self.files: Dict[str, CodeAnalyzer] = {}
        self.graph: Dict[str, Set[str]] = defaultdict(set)
        self._scan_repository()

    def _scan_repository(self):
        """Scan and analyze all Python files."""
        for py_file in self.root.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                analyzer = CodeAnalyzer(py_file)
                self.files[str(py_file)] = analyzer

                # Build dependency graph
                for imp in analyzer.imports:
                    self.graph[str(py_file)].add(imp)
            except SyntaxError:
                pass

    def find_related_files(self, filepath: str, depth: int = 2) -> Set[str]:
        """Find files related by imports/dependencies."""
        related = {filepath}
        to_process = {filepath}

        for _ in range(depth):
            next_level = set()
            for f in to_process:
                # Find files that import f
                for file_path, imports in self.graph.items():
                    if any(imp in self.files[f].exports for imp in imports):
                        next_level.add(file_path)
            
            related.update(next_level)
            to_process = next_level

        return related

    def get_complexity_report(self) -> Dict[str, Any]:
        """Generate complexity analysis report."""
        files_by_complexity = sorted(
            self.files.items(),
            key=lambda x: x[1]._cyclomatic_complexity,
            reverse=True
        )

        return {
            "most_complex_files": [
                (f, analyzer._cyclomatic_complexity)
                for f, analyzer in files_by_complexity[:10]
            ],
            "total_files": len(self.files),
            "avg_file_complexity": (
                sum(f._cyclomatic_complexity for f in self.files.values()) /
                len(self.files) if self.files else 0
            ),
        }


__all__ = ["CodeAnalyzer", "CodeRepository"]
