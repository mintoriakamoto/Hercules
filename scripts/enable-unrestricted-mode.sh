#!/bin/bash
# Enable Hercules Unrestricted Mode
# Disables all safety checks and approval gates
# WARNING: Use only in isolated or development environments

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
HERCULES_HOME="${HERCULES_HOME:=$HOME/.hercules}"

echo "=========================================="
echo "Hercules Unrestricted Mode Enabler"
echo "=========================================="
echo ""
echo "⚠️  WARNING: This will disable ALL safety checks"
echo "⚠️  Only use in isolated or development environments"
echo ""

# Create HERCULES_HOME if it doesn't exist
mkdir -p "$HERCULES_HOME"

# Ask for confirmation
read -p "Continue enabling unrestricted mode? (y/N): " -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

echo "Enabling unrestricted mode..."
echo ""

# Method 1: Set environment variables permanently
echo "1. Setting environment variables..."
cat "$REPO_ROOT/.env.unrestricted" >> "$HERCULES_HOME/.env"
echo "   ✓ Added to $HERCULES_HOME/.env"

# Method 2: Create/backup config and use unrestricted version
echo "2. Configuring agent settings..."
if [ -f "$HERCULES_HOME/config.yaml" ]; then
    echo "   Backing up existing config.yaml to config.yaml.backup"
    cp "$HERCULES_HOME/config.yaml" "$HERCULES_HOME/config.yaml.backup"
fi

cp "$REPO_ROOT/config.unrestricted.yaml" "$HERCULES_HOME/config.yaml"
echo "   ✓ Applied unrestricted configuration"

# Method 3: Create shortcut script
echo "3. Creating convenience script..."
cat > "$HERCULES_HOME/run-unrestricted.sh" << 'SCRIPT'
#!/bin/bash
# Quick launcher for unrestricted mode
source "$HOME/.hercules/.env" 2>/dev/null || true
exec hercules run "$@"
SCRIPT
chmod +x "$HERCULES_HOME/run-unrestricted.sh"
echo "   ✓ Created $HERCULES_HOME/run-unrestricted.sh"

echo ""
echo "=========================================="
echo "✓ Unrestricted mode enabled!"
echo "=========================================="
echo ""
echo "To use unrestricted mode:"
echo ""
echo "Option 1 - Using environment variables:"
echo "  source $HERCULES_HOME/.env"
echo "  hercules run"
echo ""
echo "Option 2 - Using the convenience script:"
echo "  $HERCULES_HOME/run-unrestricted.sh"
echo ""
echo "Option 3 - Direct environment setup:"
echo "  export HERCULES_AUTO_APPROVE_EXEC=1"
echo "  export HERCULES_DISABLE_OUTPUT_REDACTION=1"
echo "  export HERCULES_DISABLE_CGROUP_DETECTION=1"
echo "  hercules run"
echo ""
echo "To revert to safe mode:"
echo "  mv $HERCULES_HOME/config.yaml.backup $HERCULES_HOME/config.yaml"
echo "  rm $HERCULES_HOME/.env (or remove the unrestricted entries)"
echo ""
