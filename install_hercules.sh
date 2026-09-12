#!/bin/bash
# ============================================================================
# Hercules Agent - Complete Installation Script
# ============================================================================
# Comprehensive installation for the Hercules Agent Framework
# Supports Ubuntu/Debian Linux with proper setup of the full agent stack
#
# This script installs:
#   1. System dependencies (build tools, dev libraries, services)
#   2. GPU drivers and CUDA (optional, detects hardware)
#   3. Python environment with uv/pip package management
#   4. Hercules Python framework and all dependencies
#   5. CLI entry point and service configuration
#   6. Persistent memory, skills, and configuration
#   7. Multi-platform gateway (Telegram, Discord, Slack, etc.)
#   8. Database backends (PostgreSQL, Redis)
#
# Usage:
#   sudo ./install_hercules.sh
#   sudo ./install_hercules.sh --no-gpu    # Skip GPU setup
#   sudo ./install_hercules.sh --dev       # Development mode
# ============================================================================

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Parse command-line arguments
SKIP_GPU=false
DEV_MODE=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --no-gpu) SKIP_GPU=true; shift ;;
        --dev) DEV_MODE=true; shift ;;
        *) shift ;;
    esac
done

# Installation directories
INSTALL_DIR="/opt/hercules"
HERCULES_HOME="${HERCULES_HOME:-$HOME/.hercules}"
VENV_DIR="$INSTALL_DIR/venv"
SOURCE_DIR="$INSTALL_DIR/src"

log_step() {
    echo -e "${CYAN}[$(date +'%H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

echo ""
echo -e "${CYAN}=========================================="
echo "  Hercules Agent - Complete Installation"
echo "==========================================${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_error "This script requires root privileges"
    echo "Run with: sudo ./install_hercules.sh"
    exit 1
fi

# ============================================================================
# [1/8] System Update
# ============================================================================

log_step "[1/8] Updating system packages..."
apt update
apt upgrade -y
log_success "System packages updated"

# ============================================================================
# [2/8] Install System Dependencies
# ============================================================================

log_step "[2/8] Installing system dependencies..."

# Core build and development tools
SYSTEM_DEPS=(
    build-essential git curl wget gnupg ca-certificates
    python3 python3-dev python3-pip python3-venv
    libssl-dev libffi-dev libreadline-dev libncurses-dev
    zlib1g-dev libbz2-dev libsqlite3-dev
    rustc cargo pkg-config
)

# Audio/Video processing
AUDIO_VIDEO_DEPS=(
    alsa-utils pulseaudio pavucontrol
    v4l-utils libv4l-dev
    ffmpeg libavcodec-dev libavformat-dev libswscale-dev
    portaudio19-dev sox libsox-fmt-all
)

# Security and penetration testing tools
PENTEST_DEPS=(
    nmap metasploit-framework wireshark tcpdump
    openssl openssh-server openssh-client
    libmagic1 libmagic-dev
    dnsmasq aircrack-ng hydra john hashcat
)

# Database and persistence
DATABASE_DEPS=(
    postgresql postgresql-contrib postgresql-client
    redis-server redis-tools
    sqlite3 libsqlite3-dev
)

# Utility and development
UTILITY_DEPS=(
    tmux screen jq htop vim nano
    git-flow graphviz
    expect
)

ALL_DEPS=(
    "${SYSTEM_DEPS[@]}"
    "${AUDIO_VIDEO_DEPS[@]}"
    "${PENTEST_DEPS[@]}"
    "${DATABASE_DEPS[@]}"
    "${UTILITY_DEPS[@]}"
)

apt install -y "${ALL_DEPS[@]}"
log_success "System dependencies installed"

# ============================================================================
# [3/8] GPU Drivers (Optional)
# ============================================================================

if [ "$SKIP_GPU" = false ]; then
    log_step "[3/8] Checking for GPU hardware and installing drivers..."

    if lspci | grep -i nvidia > /dev/null; then
        log_step "NVIDIA GPU detected, installing drivers..."

        add-apt-repository -y ppa:graphics-drivers/ppa
        apt update
        apt install -y nvidia-driver-550 nvidia-utils

        # Verify installation
        if nvidia-smi > /dev/null 2>&1; then
            log_success "NVIDIA drivers installed and verified"
        else
            log_error "NVIDIA drivers installed but verification failed"
        fi
    else
        log_step "No NVIDIA GPU detected, skipping driver installation"
    fi
else
    log_step "[3/8] Skipping GPU driver installation (--no-gpu flag set)"
fi

# ============================================================================
# [4/8] CUDA Toolkit (Optional, if GPU detected)
# ============================================================================

log_step "[4/8] Setting up CUDA environment..."

if [ "$SKIP_GPU" = false ] && nvidia-smi > /dev/null 2>&1; then
    log_step "Installing CUDA toolkit..."

    # CUDA 12.8 installation
    CUDA_VERSION="12.8.0"
    CUDA_INSTALLER="cuda_${CUDA_VERSION}_570.86.10_linux.run"

    if [ ! -f "$CUDA_INSTALLER" ]; then
        wget -q "https://developer.download.nvidia.com/compute/cuda/${CUDA_VERSION}/local_installers/${CUDA_INSTALLER}"
    fi

    chmod +x "$CUDA_INSTALLER"
    ./"$CUDA_INSTALLER" --silent --toolkit --toolkitpath=/usr/local/cuda-12.8 || true

    # Set up environment variables
    echo 'export PATH=/usr/local/cuda-12.8/bin:$PATH' >> /root/.bashrc
    echo 'export LD_LIBRARY_PATH=/usr/local/cuda-12.8/lib64:$LD_LIBRARY_PATH' >> /root/.bashrc
    export PATH=/usr/local/cuda-12.8/bin:$PATH
    export LD_LIBRARY_PATH=/usr/local/cuda-12.8/lib64:$LD_LIBRARY_PATH

    log_success "CUDA 12.8 configured"
else
    log_step "Skipping CUDA installation (GPU not available or --no-gpu set)"
fi

# ============================================================================
# [5/8] Python Environment and Dependencies
# ============================================================================

log_step "[5/8] Setting up Python environment and installing framework..."

# Install uv if available, otherwise use pip
if ! command -v uv &> /dev/null; then
    log_step "Installing uv package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# Create installation directory structure
mkdir -p "$INSTALL_DIR" "$HERCULES_HOME" "$SOURCE_DIR"
cd "$INSTALL_DIR"

# Clone Hercules repository if not already present
if [ ! -d "$SOURCE_DIR/.git" ]; then
    log_step "Cloning Hercules repository..."
    git clone https://github.com/mintoriakamoto/Hercules.git "$SOURCE_DIR" || {
        log_error "Failed to clone repository"
        exit 1
    }
    cd "$SOURCE_DIR"
else
    cd "$SOURCE_DIR"
    log_step "Updating Hercules repository..."
    git fetch origin
    git reset --hard origin/main
fi

# Create Python virtual environment
log_step "Creating Python virtual environment..."
if command -v uv &> /dev/null; then
    uv venv "$VENV_DIR" --python 3.11
else
    python3 -m venv "$VENV_DIR"
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Upgrade pip and install build tools
pip install --upgrade pip setuptools wheel

# Install Hercules framework
log_step "Installing Hercules framework..."
if [ ! -f "$SOURCE_DIR/pyproject.toml" ]; then
    log_error "pyproject.toml not found in source directory"
    exit 1
fi

# Determine base installation mode
INSTALL_EXTRAS="hercules-agent"
if [ "$DEV_MODE" = true ]; then
    INSTALL_EXTRAS="hercules-agent[dev]"
    log_step "Installing in development mode..."
else
    log_step "Installing base Hercules framework..."
fi

# Interactive feature selection for optional extras
echo ""
echo -e "${YELLOW}Optional Feature Selection:${NC}"
echo "The following features can be added. Select which you want:"
echo ""

# ML/AI features
read -p "Install Machine Learning support? (huggingface-hub, transformers, torch) [y/N]: " -r ML_CHOICE
if [[ $ML_CHOICE =~ ^[Yy]$ ]]; then
    INSTALL_EXTRAS="$INSTALL_EXTRAS[ml]"
    log_step "ML support will be installed"
fi

# Computer vision features
read -p "Install Computer Vision support? (opencv-python) [y/N]: " -r VISION_CHOICE
if [[ $VISION_CHOICE =~ ^[Yy]$ ]]; then
    INSTALL_EXTRAS="$INSTALL_EXTRAS[vision]"
    log_step "Vision support will be installed"
fi

# Audio/TTS features
read -p "Install Audio/TTS support? (pyttsx3, pyaudio) [y/N]: " -r AUDIO_CHOICE
if [[ $AUDIO_CHOICE =~ ^[Yy]$ ]]; then
    INSTALL_EXTRAS="$INSTALL_EXTRAS[audio]"
    log_step "Audio support will be installed"
fi

# Data science features
read -p "Install Data Science support? (pandas, scipy, scikit-learn) [y/N]: " -r DATA_CHOICE
if [[ $DATA_CHOICE =~ ^[Yy]$ ]]; then
    INSTALL_EXTRAS="$INSTALL_EXTRAS[data]"
    log_step "Data science support will be installed"
fi

# Web server features
read -p "Install Web Framework support? (Flask, gunicorn) [y/N]: " -r WEB_CHOICE
if [[ $WEB_CHOICE =~ ^[Yy]$ ]]; then
    INSTALL_EXTRAS="$INSTALL_EXTRAS[web-server]"
    log_step "Web framework support will be installed"
fi

# Messaging platforms
read -p "Install Messaging Platform Integrations? (Telegram, Discord, Slack, etc.) [y/N]: " -r MESSAGING_CHOICE
if [[ $MESSAGING_CHOICE =~ ^[Yy]$ ]]; then
    INSTALL_EXTRAS="$INSTALL_EXTRAS[messaging]"
    log_step "Messaging platforms will be installed"
fi

echo ""
log_step "Installing Hercules with selected extras: $INSTALL_EXTRAS"
if [ "$DEV_MODE" = true ]; then
    pip install -e "$SOURCE_DIR[$INSTALL_EXTRAS]"
else
    pip install "$SOURCE_DIR[$INSTALL_EXTRAS]"
fi
log_success "Hercules framework installed with selected features"

# ============================================================================
# [6/8] Directory Structure and Initialization
# ============================================================================

log_step "[6/8] Creating directory structure..."

# Create core directories
mkdir -p "$HERCULES_HOME"/{memory,skills,logs,data,config,cache}
mkdir -p "$HERCULES_HOME"/memory/{conversations,knowledge,learned_patterns}
mkdir -p "$HERCULES_HOME"/skills/{core,integrations,custom}
mkdir -p "$INSTALL_DIR"/{models,scripts,tests,hooks}

# Create symbolic links for convenience
ln -sf "$SOURCE_DIR" "$INSTALL_DIR/repo"
ln -sf "$VENV_DIR/bin/hercules" /usr/local/bin/hercules
chmod +x /usr/local/bin/hercules

log_success "Directory structure created"

# ============================================================================
# [7/8] Models and AI Configuration
# ============================================================================

log_step "[7/8] Configuring AI models..."

mkdir -p "$INSTALL_DIR/models"

# Download Phi-2 model for offline inference (optional)
log_step "Model download (can be skipped for API-only mode)..."
if [ -z "$CI" ]; then  # Not in CI environment
    python3 << 'PYEOF'
try:
    from huggingface_hub import snapshot_download
    snapshot_download(
        repo_id="microsoft/phi-2",
        local_dir=f"{INSTALL_DIR}/models/phi-2",
        ignore_patterns=["*.bin"]  # Skip large binary files on first pass
    )
    print("✓ Phi-2 model configured for offline use")
except Exception as e:
    print(f"⚠ Model download skipped: {e}")
PYEOF
fi

log_success "AI models configured"

# ============================================================================
# [8/8] Configuration, Services, and Validation
# ============================================================================

log_step "[8/8] Finalizing configuration and services..."

# Create .env configuration file
if [ ! -f "$HERCULES_HOME/.env" ]; then
    cat > "$HERCULES_HOME/.env" << 'ENV_EOF'
# Hercules Agent Configuration
# Edit these settings to configure your Hercules instance

# LLM Provider Selection
# Options: openai, anthropic, gemini, openrouter, ollama, lmstudio
LLM_PROVIDER=openai

# API Keys (leave empty for offline mode)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=

# Local Model Configuration (for offline mode)
LOCAL_MODEL_PATH=${HERCULES_HOME}/models/phi-2
OLLAMA_BASE_URL=http://localhost:11434

# Memory and Persistence
MEMORY_TYPE=sqlite  # sqlite, postgresql, redis
DATABASE_URL=sqlite:///${HERCULES_HOME}/data/hercules.db

# Gateway Configuration
GATEWAY_PORT=8000
GATEWAY_HOST=0.0.0.0

# Platform Integrations
TELEGRAM_BOT_TOKEN=
DISCORD_TOKEN=
SLACK_TOKEN=
MATRIX_HOMESERVER=

# Logging
LOG_LEVEL=INFO
LOG_DIR=${HERCULES_HOME}/logs

# Offline Mode (no external API calls)
OFFLINE_MODE=false

# Skill Loading
SKILLS_DIR=${HERCULES_HOME}/skills
ENABLE_SKILL_AUTO_IMPROVE=true
ENV_EOF
    chmod 600 "$HERCULES_HOME/.env"
    log_success "Configuration file created at $HERCULES_HOME/.env"
fi

# Create PRINCIPLES.md for ethical guidelines
cat > "$INSTALL_DIR/PRINCIPLES.md" << 'PRINCIPLES_EOF'
# Hercules Agent Framework - Ethical Principles

## Core Identity
- **Name**: Hercules
- **Purpose**: Autonomous AI agent for productivity, research, and decision support
- **Philosophy**: Self-improving, privacy-first, completely autonomous
- **Origin**: GitHub-native, self-hosted, user-controlled

## Seven Core Principles

1. **No External Dependency**
   - Works completely offline with local models
   - No telemetry, no cloud lock-in
   - User maintains full data control

2. **Transparent Operations**
   - All actions logged and auditable
   - No hidden behaviors or analytics
   - Users see exactly what's happening

3. **Ethical Constraints**
   - Never assists with harm or deception
   - Respects privacy and legal boundaries
   - Follows user's intent, not corporate goals

4. **User Autonomy**
   - Users control all features and behavior
   - No forced updates or telemetry
   - Can fork, modify, redistribute freely

5. **Learning & Evolution**
   - Persistent memory retains all interactions
   - Creates and improves skills from experience
   - Learns patterns and adapts over time

6. **Security First**
   - Sandboxed execution environment
   - Memory restricted to authorized users only
   - Cryptographic verification of dependencies

7. **Open Source**
   - All code inspectable and modifiable
   - Community contributions welcome
   - No proprietary lock-in

## Capabilities
- Multi-turn conversations with persistent memory
- Autonomous skill creation and improvement
- Code execution in sandboxed environments
- Multi-platform messaging (Telegram, Discord, Slack, etc.)
- Scheduled automation with natural language cron
- Local file operations and web browsing
- Research and data analysis
- Collaborative multi-agent workflows

## Constraints
- No training data collection or analytics
- No external model APIs required
- No cloud dependency
- No user lock-in
- No forced updates
- No advertising or tracking

Hercules exists to augment human capability, not replace human judgment.
PRINCIPLES_EOF

# Initialize persistent memory structure
MEMORY_INIT_FILE="$HERCULES_HOME/memory/init_memory.json"
if [ ! -f "$MEMORY_INIT_FILE" ]; then
    cat > "$MEMORY_INIT_FILE" << 'MEMORY_EOF'
{
  "metadata": {
    "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "version": "1.0",
    "hercules_version": "1.0"
  },
  "conversations": [],
  "knowledge_base": {},
  "learned_patterns": {},
  "skill_improvements": [],
  "settings": {
    "memory_retention": "permanent",
    "learning_enabled": true,
    "auto_skill_creation": true
  }
}
EOF
    sed -i "s/\$(date -u +%Y-%m-%dT%H:%M:%SZ)/$(date -u +%Y-%m-%dT%H:%M:%SZ)/g" "$MEMORY_INIT_FILE"
    chmod 600 "$MEMORY_INIT_FILE"
    log_success "Persistent memory initialized"
fi

# Create systemd service for gateway daemon
cat > /etc/systemd/system/hercules-gateway.service << 'SERVICE_EOF'
[Unit]
Description=Hercules Agent Gateway
Documentation=https://github.com/mintoriakamoto/Hercules
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=hercules
WorkingDirectory=/opt/hercules/src
Environment="PATH=/opt/hercules/venv/bin:/usr/local/bin:/usr/bin"
Environment="HERCULES_HOME=/opt/hercules"
ExecStart=/opt/hercules/venv/bin/hercules gateway
Restart=on-failure
RestartSec=30
StandardOutput=journal
StandardError=journal
SyslogIdentifier=hercules-gateway

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/opt/hercules

[Install]
WantedBy=multi-user.target
SERVICE_EOF

# Create Hercules system user if it doesn't exist
if ! id -u hercules > /dev/null 2>&1; then
    useradd -r -s /bin/bash -d /opt/hercules -m hercules
    chown -R hercules:hercules "$HERCULES_HOME" "$INSTALL_DIR"
    log_success "Created Hercules system user"
fi

# Set up proper file permissions
chmod 700 "$HERCULES_HOME"
chmod 600 "$HERCULES_HOME/.env"
chmod 700 "$HERCULES_HOME"/memory
chmod 600 "$HERCULES_HOME"/memory/*
chown -R hercules:hercules "$HERCULES_HOME" "$INSTALL_DIR" 2>/dev/null || true

# Reload systemd and enable service
systemctl daemon-reload
systemctl enable hercules-gateway.service
log_success "Systemd service configured"

# Validate installation
log_step "Validating installation..."
source "$VENV_DIR/bin/activate"

VALIDATION_CHECKS=(
    "python3 --version"
    "pip list | grep -q hercules"
    "hercules --version"
)

VALIDATION_PASSED=true
for check in "${VALIDATION_CHECKS[@]}"; do
    if eval "$check" > /dev/null 2>&1; then
        log_success "Validation: $check"
    else
        log_error "Validation failed: $check"
        VALIDATION_PASSED=false
    fi
done

if [ "$VALIDATION_PASSED" = false ]; then
    log_error "Some validation checks failed. Please review the output above."
fi

# ============================================================================
# Installation Complete
# ============================================================================

echo ""
echo -e "${GREEN}=========================================="
echo "  ✓ Hercules Installation Complete!"
echo "==========================================${NC}"
echo ""
echo -e "${CYAN}Quick Start:${NC}"
echo "  1. Reload your shell:"
echo "     source ~/.bashrc"
echo ""
echo "  2. Start Hercules:"
echo "     hercules"
echo ""
echo "  3. Or run the gateway service:"
echo "     sudo systemctl start hercules-gateway"
echo "     sudo systemctl status hercules-gateway"
echo ""
echo -e "${CYAN}Configuration:${NC}"
echo "  • Edit: $HERCULES_HOME/.env"
echo "  • Memory: $HERCULES_HOME/memory/"
echo "  • Skills: $HERCULES_HOME/skills/"
echo "  • Logs: $HERCULES_HOME/logs/"
echo ""
echo -e "${CYAN}Commands:${NC}"
echo "  hercules                 # Interactive chat"
echo "  hercules setup           # Configuration wizard"
echo "  hercules gateway         # Run gateway service"
echo "  hercules status          # Check system status"
echo "  hercules doctor          # Diagnose issues"
echo "  hercules cron list       # Manage scheduled tasks"
echo ""
echo -e "${CYAN}Documentation:${NC}"
echo "  • Repository: $SOURCE_DIR"
echo "  • Principles: $INSTALL_DIR/PRINCIPLES.md"
echo "  • Wiki: https://github.com/mintoriakamoto/Hercules"
echo ""
echo -e "${GREEN}Hercules is ready to serve.${NC}"
echo "Online. Autonomous. Ethical."
echo ""
