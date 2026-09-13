"""Plugin integrity and capability control system.

Prevents supply chain compromise by:
  - Verifying plugin content hashes
  - Enforcing signed manifests
  - Per-plugin capability whitelists
  - Blocking dangerous override patterns

This module secures the plugin loading pipeline at:
  1. Manifest verification (hash check)
  2. Signature verification (if signing key present)
  3. Capability whitelist enforcement
  4. Override approval gating
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class PluginCapability(Enum):
    """Plugin capabilities that require explicit approval."""

    # Message handling
    MESSAGE_RECEIVE = "message.receive"
    MESSAGE_SEND = "message.send"

    # Tool invocation
    TOOL_INVOKE = "tool.invoke"
    TOOL_OVERRIDE = "tool.override"  # Override built-in tools

    # File operations
    FILE_READ = "file.read"
    FILE_WRITE = "file.write"

    # Network operations
    NETWORK = "network"
    HTTP_FETCH = "http.fetch"

    # Process operations
    PROCESS_EXEC = "process.exec"
    PROCESS_SPAWN = "process.spawn"

    # System operations
    SYSTEM_ENV = "system.env"  # Access environment variables
    SYSTEM_CONFIG = "system.config"  # Read config files


@dataclass
class PluginManifest:
    """Plugin metadata for integrity verification."""

    name: str
    version: str
    content_hash: str  # SHA256 of __init__.py
    signature: Optional[str] = None  # Ed25519 signature (optional)
    capabilities: List[str] = field(default_factory=list)
    description: Optional[str] = None
    author: Optional[str] = None
    requires_approval: bool = True

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "version": self.version,
            "content_hash": self.content_hash,
            "signature": self.signature,
            "capabilities": self.capabilities,
            "description": self.description,
            "author": self.author,
            "requires_approval": self.requires_approval,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> PluginManifest:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            version=data["version"],
            content_hash=data["content_hash"],
            signature=data.get("signature"),
            capabilities=data.get("capabilities", []),
            description=data.get("description"),
            author=data.get("author"),
            requires_approval=data.get("requires_approval", True),
        )


class IntegrityError(Exception):
    """Raised when plugin integrity check fails."""
    def __init__(self, plugin_name: str, reason: str):
        self.plugin_name = plugin_name
        self.reason = reason
        super().__init__(f"Plugin '{plugin_name}' integrity check failed: {reason}")


class CapabilityDenied(Exception):
    """Raised when plugin uses unauthorized capability."""
    def __init__(self, plugin_name: str, capability: str):
        self.plugin_name = plugin_name
        self.capability = capability
        super().__init__(
            f"Plugin '{plugin_name}' not authorized for capability: {capability}"
        )


class OverrideDenied(Exception):
    """Raised when plugin tries to override without approval."""
    def __init__(self, plugin_name: str, tool_name: str):
        self.plugin_name = plugin_name
        self.tool_name = tool_name
        super().__init__(
            f"Plugin '{plugin_name}' not approved to override tool: {tool_name}"
        )


class PluginVerifier:
    """Verifies plugin integrity and capabilities."""

    def __init__(self, signing_key: Optional[bytes] = None):
        """Initialize verifier.

        Args:
            signing_key: Ed25519 public key for signature verification (optional)
        """
        self.signing_key = signing_key

    def verify_content(
        self,
        plugin_path: Path,
        expected_hash: str,
    ) -> str:
        """Verify plugin content hash.

        Args:
            plugin_path: Path to plugin __init__.py
            expected_hash: Expected SHA256 hash

        Returns:
            Actual hash

        Raises:
            IntegrityError: If hash mismatch
        """
        entry = plugin_path / "__init__.py"
        if not entry.exists():
            raise IntegrityError(
                plugin_path.name,
                f"__init__.py not found at {entry}",
            )

        with open(entry, 'rb') as f:
            content = f.read()

        actual_hash = hashlib.sha256(content).hexdigest()

        if actual_hash != expected_hash:
            raise IntegrityError(
                plugin_path.name,
                f"content hash mismatch: expected {expected_hash}, got {actual_hash}",
            )

        logger.info("Plugin %s content verified (hash: %s)", plugin_path.name, actual_hash[:8])
        return actual_hash

    def verify_signature(
        self,
        plugin_path: Path,
        signature: str,
    ) -> bool:
        """Verify plugin signature.

        Args:
            plugin_path: Path to plugin __init__.py
            signature: Signature string (ed25519:...)

        Returns:
            True if signature valid

        Raises:
            IntegrityError: If signature invalid or no key configured
        """
        if not self.signing_key:
            raise IntegrityError(
                plugin_path.name,
                "No signing key configured for signature verification"
            )

        entry = plugin_path / "__init__.py"
        with open(entry, 'rb') as f:
            content = f.read()

        # Parse signature format: "ed25519:<base64-signature>"
        if not signature.startswith("ed25519:"):
            raise IntegrityError(
                plugin_path.name,
                f"Invalid signature format: {signature[:20]}...",
            )

        try:
            import base64
            sig_b64 = signature.split(":", 1)[1]
            sig_bytes = base64.b64decode(sig_b64)

            # Verify with libsodium/nacl
            import nacl.signing
            verify_key = nacl.signing.VerifyKey(self.signing_key)
            verify_key.verify(content, sig_bytes)

            logger.info("Plugin %s signature verified", plugin_path.name)
            return True

        except Exception as e:
            raise IntegrityError(
                plugin_path.name,
                f"Signature verification failed: {str(e)}"
            )


class CapabilityAuditor:
    """Audits and enforces plugin capability restrictions."""

    def __init__(self):
        self.approvals: Dict[str, Set[str]] = {}  # plugin_name -> approved_capabilities

    def approve_capabilities(
        self,
        plugin_name: str,
        capabilities: List[str],
    ) -> None:
        """Approve specific capabilities for a plugin.

        Args:
            plugin_name: Plugin identifier
            capabilities: List of PluginCapability values
        """
        self.approvals[plugin_name] = set(capabilities)
        logger.info(
            "Plugin %s approved for capabilities: %s",
            plugin_name,
            ", ".join(capabilities)
        )

    def check_capability(
        self,
        plugin_name: str,
        capability: str,
    ) -> bool:
        """Check if plugin has capability.

        Args:
            plugin_name: Plugin identifier
            capability: PluginCapability value

        Returns:
            True if approved

        Raises:
            CapabilityDenied: If not approved
        """
        approved = self.approvals.get(plugin_name, set())

        if capability not in approved:
            raise CapabilityDenied(plugin_name, capability)

        return True

    def check_override(
        self,
        plugin_name: str,
        tool_name: str,
        user_approved: bool = False,
    ) -> bool:
        """Check if plugin can override a tool.

        Args:
            plugin_name: Plugin identifier
            tool_name: Tool being overridden
            user_approved: Whether user explicitly approved override

        Returns:
            True if allowed

        Raises:
            OverrideDenied: If not approved
        """
        # Tool override requires explicit approval
        if not user_approved:
            raise OverrideDenied(plugin_name, tool_name)

        # Verify plugin has TOOL_OVERRIDE capability
        self.check_capability(plugin_name, PluginCapability.TOOL_OVERRIDE.value)

        logger.warning(
            "Plugin %s overriding tool: %s (user approved)",
            plugin_name,
            tool_name,
        )

        return True


class PluginIntegrityManager:
    """Orchestrates full plugin verification workflow."""

    def __init__(
        self,
        manifest_path: Optional[Path] = None,
        signing_key: Optional[bytes] = None,
    ):
        """Initialize integrity manager.

        Args:
            manifest_path: Path to plugins.json manifest
            signing_key: Ed25519 key for signature verification
        """
        self.manifest_path = manifest_path
        self.verifier = PluginVerifier(signing_key)
        self.auditor = CapabilityAuditor()
        self.manifests: Dict[str, PluginManifest] = {}

        if manifest_path and manifest_path.exists():
            self._load_manifest_file(manifest_path)

    def _load_manifest_file(self, path: Path) -> None:
        """Load manifest from JSON file."""
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            for name, manifest_data in data.items():
                self.manifests[name] = PluginManifest.from_dict(manifest_data)
            logger.info("Loaded %d plugin manifests from %s", len(self.manifests), path)
        except Exception as e:
            logger.error("Failed to load manifest file %s: %s", path, e)

    def verify_plugin(
        self,
        plugin_path: Path,
        plugin_name: str,
    ) -> PluginManifest:
        """Verify plugin and return manifest.

        Args:
            plugin_path: Path to plugin directory
            plugin_name: Plugin identifier

        Returns:
            PluginManifest

        Raises:
            IntegrityError: If verification fails
        """
        # Get manifest
        manifest = self.manifests.get(plugin_name)
        if manifest is None:
            raise IntegrityError(
                plugin_name,
                f"Plugin not in manifest"
            )

        # Verify content hash
        self.verifier.verify_content(plugin_path, manifest.content_hash)

        # Verify signature if provided
        if manifest.signature:
            self.verifier.verify_signature(plugin_path, manifest.signature)

        # Approve capabilities
        self.auditor.approve_capabilities(plugin_name, manifest.capabilities)

        logger.info("Plugin %s integrity verification complete", plugin_name)
        return manifest

    def save_manifest(self, path: Path) -> None:
        """Save manifests to JSON file."""
        data = {
            name: manifest.to_dict()
            for name, manifest in self.manifests.items()
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info("Saved %d manifests to %s", len(self.manifests), path)
