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
DRY_RUN=false

usage() {
    cat <<'USAGE'
Usage: sudo ./install_hercules.sh [options]

  --no-gpu     Skip GPU driver and CUDA installation
  --dev        Editable install, including the dev extra
  --dry-run    Resolve and print the install plan, then exit having changed
               nothing. Needs no root and asks no questions.
  -h, --help   Show this message
USAGE
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-gpu) SKIP_GPU=true; shift ;;
        --dev) DEV_MODE=true; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        -h|--help) usage; exit 0 ;;
        # An unknown flag used to be swallowed by a bare `shift`, so a typo'd
        # `--no-gpus` installed drivers anyway, and `--dry-run` before this
        # existed ran the real install. Fail loudly instead.
        *) echo "Unknown option: $1" >&2; echo "" >&2; usage >&2; exit 2 ;;
    esac
done

# Installation directories
INSTALL_DIR="/opt/hercules"
# The agent's DATA home, distinct from the install dir. Default deliberately
# under $INSTALL_DIR rather than $HOME/.hercules: the gateway unit runs as the
# `hercules` user, and under ProtectSystem=strict only ReadWritePaths
# ($INSTALL_DIR) is writable -- a home under /root or /home would be read-only
# to the daemon, which has to write sessions, memory and logs there. It is also
# exactly that user's own ~/.hercules, so the app's built-in default agrees with
# the unit even if HERCULES_HOME is never exported.
HERCULES_HOME="${HERCULES_HOME:-$INSTALL_DIR/.hercules}"
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

log_warn() {
    echo -e "${YELLOW}!${NC} $1"
}

echo ""
echo -e "${CYAN}=========================================="
echo "  Hercules Agent - Complete Installation"
echo -e "==========================================${NC}"
echo ""

# Check if running as root. A dry run only reads, so it must not demand sudo --
# the point of it is inspecting the plan before granting root.
if [ "$DRY_RUN" = false ] && [ "$EUID" -ne 0 ]; then
    log_error "This script requires root privileges"
    echo "Run with: sudo ./install_hercules.sh"
    exit 1
fi

# ============================================================================
# [0/8] Selections and install plan
# ============================================================================
# Everything the install needs to ask is asked here, once, before the first
# mutating command. The prompts used to be interleaved with the work -- the
# Python extras question came after apt, the git clone and venv creation -- so
# an unattended run blocked twenty minutes in, and nothing could state up front
# what was about to happen to the machine.

# Ask a yes/no question; 0 = yes, 1 = no.
#
# Auto-answers "no" when there is nobody to ask (no TTY on stdin, or --dry-run).
# That case has to be explicit: a bare `read` hitting EOF returns non-zero, and
# under `set -e` that aborted the entire install, which is why this script could
# not be exercised in CI at all.
ask_yes_no() {
    local reply=""
    if [ "$DRY_RUN" = true ] || [ ! -t 0 ]; then
        echo "  $1 [y/N]: N   (non-interactive)"
        return 1
    fi
    read -p "  $1 [y/N]: " -r reply || reply=""
    [[ $reply =~ ^[Yy]$ ]]
}

# Core build and development tools (always required)
SYSTEM_DEPS=(
    build-essential git curl wget gnupg ca-certificates
    python3 python3-dev python3-pip python3-venv
    libssl-dev libffi-dev libreadline-dev libncurses-dev
    zlib1g-dev libbz2-dev libsqlite3-dev
    rustc cargo pkg-config
)

# Audio/Video processing and multimedia
AUDIO_VIDEO_DEPS=(
    ffmpeg libavcodec-dev libavformat-dev libswscale-dev
    alsa-utils pulseaudio
    v4l-utils libv4l-dev
    portaudio19-dev sox libsox-fmt-all
    # Audio processing libraries (required for TTS/voice features)
    libjack-dev libjack0 jackd
    libopus-dev libvorbis-dev libflac-dev
)

# Penetration testing tools (optional, can be skipped for production)
PENTEST_DEPS=(
    nmap metasploit-framework wireshark tcpdump
    openssl openssh-server openssh-client
    dnsmasq aircrack-ng hydra john hashcat
)

# Database and persistence backends (optional, for distributed deployments)
DATABASE_DEPS=(
    postgresql postgresql-contrib postgresql-client
    redis-server redis-tools
)

# Utility and development tools
UTILITY_DEPS=(
    tmux screen jq htop vim nano
    git-flow graphviz expect
    curl wget
)

# ---- system packages -------------------------------------------------------
INSTALL_DEPS=("${SYSTEM_DEPS[@]}" "${AUDIO_VIDEO_DEPS[@]}" "${UTILITY_DEPS[@]}")

echo ""
echo -e "${YELLOW}Optional system packages:${NC}"

if ask_yes_no "Penetration testing tools? (nmap, metasploit, wireshark)"; then
    INSTALL_DEPS+=("${PENTEST_DEPS[@]}")
else
    log_step "Skipping pentest tools (later: apt install nmap wireshark)"
fi

if ask_yes_no "Database servers? (PostgreSQL, Redis)"; then
    INSTALL_DEPS+=("${DATABASE_DEPS[@]}")
else
    log_step "Skipping database servers (later, or use cloud-hosted)"
fi

# ---- Python extras ---------------------------------------------------------
# Names here must match [project.optional-dependencies] in pyproject.toml.
EXTRAS=()
[ "$DEV_MODE" = true ] && EXTRAS+=(dev)

echo ""
echo -e "${YELLOW}Optional Python features:${NC}"

ask_yes_no "Machine learning? (huggingface-hub, transformers, torch)" && EXTRAS+=(ml)
ask_yes_no "Computer vision? (opencv-python)"                         && EXTRAS+=(vision)
ask_yes_no "Audio / TTS? (pyttsx3, pyaudio)"                          && EXTRAS+=(audio)
ask_yes_no "Data science? (pandas, scipy, scikit-learn)"              && EXTRAS+=(data)
ask_yes_no "Web framework? (Flask, gunicorn)"                         && EXTRAS+=(web-server)
ask_yes_no "Messaging platforms? (Telegram, Discord, Slack)"          && EXTRAS+=(messaging)

# Build the pip requirement. Only *extra names* belong inside the brackets:
# this previously accumulated onto the string "hercules-agent", producing
# `/opt/hercules/src[hercules-agent[ml]]` -- nested brackets around a package
# name in the extras slot, which pip rejects outright. With every prompt
# declined it was still `src[hercules-agent]`, and `hercules-agent` is not an
# extra, so no combination of answers could install.
PIP_SPEC="$SOURCE_DIR"
EXTRAS_DESC=""
if [ ${#EXTRAS[@]} -gt 0 ]; then
    EXTRAS_JOINED="$(IFS=,; printf '%s' "${EXTRAS[*]}")"
    PIP_SPEC="${SOURCE_DIR}[${EXTRAS_JOINED}]"
    EXTRAS_DESC=" with extras: ${EXTRAS_JOINED}"
fi

# ---- the plan --------------------------------------------------------------
echo ""
echo -e "${CYAN}Install plan:${NC}"
echo "  source        : $SOURCE_DIR (from github.com/mintoriakamoto/Hercules)"
echo "  virtualenv    : $VENV_DIR (Python 3.11)"
echo "  agent home    : $HERCULES_HOME"
echo "  pip spec      : $PIP_SPEC$([ "$DEV_MODE" = true ] && echo "  (editable)")"
echo "  apt packages  : ${#INSTALL_DEPS[@]}"
echo "  GPU / CUDA    : $([ "$SKIP_GPU" = true ] && echo "skipped (--no-gpu)" || echo "installed if an NVIDIA GPU is detected")"
echo "  systemd unit  : /etc/systemd/system/hercules-gateway.service"

if [ "$DRY_RUN" = true ]; then
    echo ""
    log_success "Dry run complete — nothing on this machine was changed."
    echo "  Re-run without --dry-run (as root) to install."
    exit 0
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

# The package set and the optional groups were resolved in [0/8].
apt install -y "${INSTALL_DEPS[@]}"
log_success "System dependencies installed (${#INSTALL_DEPS[@]} packages)"

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

# The extras were chosen in [0/8]; PIP_SPEC is already resolved.
log_step "Installing Hercules from $PIP_SPEC"
if [ "$DEV_MODE" = true ]; then
    pip install -e "$PIP_SPEC"
else
    pip install "$PIP_SPEC"
fi
log_success "Hercules framework installed${EXTRAS_DESC}"

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

# ----------------------------------------------------------------------------
# Supported models
# ----------------------------------------------------------------------------
# This build runs exactly two models. Anything else is unsupported: the agent
# loop, tool-call formatting and context budgets are tuned against these, and
# silently accepting a third model produces failures that look like agent bugs
# rather than a model mismatch.
#
# The repo ids are not baked in: set them via the environment (or edit here)
# once confirmed. Deliberately empty rather than guessed -- a wrong id fails at
# download time with a 404 that reads like a network fault, which is a far
# worse install experience than being told plainly that nothing is configured.
SUPPORTED_MODEL_PRIMARY="${HERCULES_MODEL_PRIMARY:-}"
SUPPORTED_MODEL_COMPACT="${HERCULES_MODEL_COMPACT:-}"

# Detection-first: a machine that already holds one of these must never be
# made to re-download tens of gigabytes. Scans the places local weights
# actually live rather than assuming any one runtime.
log_step "Checking for models already installed on this machine..."

FOUND_MODELS=""
_note_model() {  # $1 = where, $2 = what
    FOUND_MODELS="${FOUND_MODELS}${1}|${2}\n"
    log_success "Found (${1}): ${2}"
}

# Ollama
if command -v ollama > /dev/null 2>&1; then
    while IFS= read -r line; do
        case "$line" in
            *qwen*|*Qwen*) _note_model "ollama" "${line%% *}" ;;
        esac
    done < <(ollama list 2>/dev/null | tail -n +2)
fi

# GGUF weights: llama.cpp / LM Studio / Jan / a local models dir
for dir in \
    "$INSTALL_DIR/models" \
    "$HOME/.cache/llama.cpp" \
    "$HOME/.local/share/models" \
    "$HOME/.lmstudio/models" \
    "$HOME/.cache/lm-studio/models" \
    "$HOME/.jan/models" \
    "$HOME/models"
do
    [ -d "$dir" ] || continue
    while IFS= read -r f; do
        [ -n "$f" ] && _note_model "gguf" "$f"
    done < <(find "$dir" -maxdepth 3 -type f -iname "*qwen*.gguf" 2>/dev/null | head -20)
done

# Hugging Face hub cache (repo dirs are named models--org--name)
HF_CACHE="${HF_HOME:-$HOME/.cache/huggingface}/hub"
if [ -d "$HF_CACHE" ]; then
    while IFS= read -r d; do
        [ -n "$d" ] && _note_model "hf-cache" "$(basename "$d")"
    done < <(find "$HF_CACHE" -maxdepth 1 -type d -iname "models--*qwen*" 2>/dev/null | head -20)
fi

if [ -n "$FOUND_MODELS" ]; then
    log_success "Using models already present — skipping download"
    printf "%b" "$FOUND_MODELS" > "$INSTALL_DIR/models/DETECTED.txt"
    echo "  (inventory written to $INSTALL_DIR/models/DETECTED.txt)"
else
    log_warn "No supported model found locally."
    echo "  Hercules runs offline-first, but needs one of its supported models."
    if [ -n "$SUPPORTED_MODEL_PRIMARY" ] || [ -n "$SUPPORTED_MODEL_COMPACT" ]; then
        [ -n "$SUPPORTED_MODEL_PRIMARY" ] && echo "    primary : $SUPPORTED_MODEL_PRIMARY"
        [ -n "$SUPPORTED_MODEL_COMPACT" ] && echo "    compact : $SUPPORTED_MODEL_COMPACT"
        echo
        echo "  These are large downloads, so the installer does not fetch them"
        echo "  unattended. Pull one when ready:"
        [ -n "$SUPPORTED_MODEL_PRIMARY" ] && \
            echo "    hf download $SUPPORTED_MODEL_PRIMARY --local-dir $INSTALL_DIR/models/primary"
    else
        echo "  No model repository is configured in this build yet. Set one:"
        echo "    export HERCULES_MODEL_PRIMARY=<org>/<repo>   # the 27B"
        echo "    export HERCULES_MODEL_COMPACT=<org>/<repo>   # the A3B"
        echo "  then re-run this step, or skip it entirely and point Hercules"
        echo "  at weights you already have:"
    fi
    echo "    LOCAL_MODEL_PATH=/path/to/weights"
fi

log_success "AI models configured"

# ============================================================================
# [8/8] Configuration, Services, and Validation
# ============================================================================

log_step "[8/8] Finalizing configuration and services..."

# Generate secure credentials and create .env configuration file
if [ ! -f "$HERCULES_HOME/.env" ]; then
    log_step "Generating secure configuration and credentials..."

    # Generate secure random credentials
    DASHBOARD_PASSWORD=$(openssl rand -base64 24 2>/dev/null || head -c 24 /dev/urandom | base64)
    API_SERVER_KEY=$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | xxd -p)
    POSTGRES_PASSWORD=$(openssl rand -base64 32 2>/dev/null || head -c 32 /dev/urandom | base64)
    REDIS_PASSWORD=$(openssl rand -base64 32 2>/dev/null || head -c 32 /dev/urandom | base64)

    cat > "$HERCULES_HOME/.env" << EOF
# ============================================================================
# Hercules Agent Configuration
# ============================================================================
# Edit these settings to configure your Hercules instance.
# See https://github.com/mintoriakamoto/Hercules/blob/main/.env.example for
# complete documentation of all available options.

# ============================================================================
# [1] LLM Provider Configuration
# ============================================================================
# Primary provider for agent reasoning and responses
LLM_PROVIDER=openai
# Options: openai, anthropic, gemini, openrouter, ollama, bedrock, etc.

# Provider API Keys (leave empty for offline/local mode)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
GEMINI_API_KEY=

# Optional: OpenRouter (multi-provider aggregator)
# OPENROUTER_API_KEY=

# Optional: Local model support
LOCAL_MODEL_PATH=\${HERCULES_HOME}/models/phi-2
OLLAMA_BASE_URL=http://localhost:11434

# ============================================================================
# [2] Database & Persistence Layer
# ============================================================================
# Memory system (all session data, learned skills, persistent memory)
MEMORY_TYPE=sqlite
# Options: sqlite, postgresql, redis, mongodb

# Database connection URLs
DATABASE_URL=sqlite://\${HERCULES_HOME}/data/hercules.db
# For PostgreSQL: postgresql://hercules:${POSTGRES_PASSWORD}@localhost/hercules
# For Redis: redis://default:${REDIS_PASSWORD}@localhost:6379/0

# PostgreSQL credentials (if using MEMORY_TYPE=postgresql)
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_USER=hercules
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=hercules

# Redis credentials (if using MEMORY_TYPE=redis)
REDIS_PASSWORD=${REDIS_PASSWORD}
REDIS_HOST=localhost
REDIS_PORT=6379

# ============================================================================
# [3] Gateway & Service Configuration
# ============================================================================
# Web gateway for messaging platforms and dashboard

GATEWAY_HOST=0.0.0.0
GATEWAY_PORT=8000
GATEWAY_ALLOW_ALL_USERS=false

# Dashboard web UI configuration
HERCULES_DASHBOARD=0
# Set to 1 to enable dashboard (requires auth when exposed publicly)
HERCULES_DASHBOARD_HOST=127.0.0.1
HERCULES_DASHBOARD_PORT=9119
HERCULES_DASHBOARD_BASIC_AUTH_USERNAME=admin
HERCULES_DASHBOARD_BASIC_AUTH_PASSWORD=${DASHBOARD_PASSWORD}

# API Server configuration (for external integrations)
API_SERVER_HOST=
# Leave empty to disable. Set to 0.0.0.0 to expose publicly (requires KEY)
API_SERVER_PORT=8642
API_SERVER_KEY=${API_SERVER_KEY}

# ============================================================================
# [4] Messaging Platform Integrations
# ============================================================================
# Optional: Connect to messaging platforms for the gateway

# Telegram
# TELEGRAM_BOT_TOKEN=your_bot_token_here
# TELEGRAM_ALLOWED_USERS=123456789,987654321
# TELEGRAM_HOME_CHANNEL=your_home_channel_id

# Slack
# SLACK_BOT_TOKEN=xoxb-...
# SLACK_APP_TOKEN=xapp-...
# SLACK_ALLOWED_USERS=U1234567890

# Discord (requires plugin installation)
# DISCORD_TOKEN=your_token_here

# Email (IMAP/SMTP)
# EMAIL_ADDRESS=your@email.com
# EMAIL_PASSWORD=app_password_here
# EMAIL_IMAP_HOST=imap.gmail.com
# EMAIL_SMTP_HOST=smtp.gmail.com

# Matrix/Element
# MATRIX_HOMESERVER=https://matrix.org
# MATRIX_ACCESS_TOKEN=syt_your_token

# Microsoft Teams
# TEAMS_CLIENT_ID=
# TEAMS_CLIENT_SECRET=
# TEAMS_TENANT_ID=

# Google Chat
# GOOGLE_CHAT_PROJECT_ID=
# GOOGLE_CHAT_SERVICE_ACCOUNT_JSON=

# ============================================================================
# [5] Tool & Feature APIs
# ============================================================================
# Optional: Configure external tool providers

# Web search
# EXA_API_KEY=
# FIRECRAWL_API_KEY=

# Browser automation
# BROWSERBASE_API_KEY=
# BROWSERBASE_PROJECT_ID=

# Image generation
# FAL_KEY=

# Voice & Speech
# ELEVENLABS_API_KEY=
# STT_OPENAI_MODEL=whisper-1

# ============================================================================
# [6] Logging & Debugging
# ============================================================================
LOG_LEVEL=INFO
# Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_DIR=\${HERCULES_HOME}/logs

WEB_TOOLS_DEBUG=false
VISION_TOOLS_DEBUG=false

# ============================================================================
# [7] Agent Behavior
# ============================================================================
OFFLINE_MODE=false
# Set to true for completely offline operation (no API calls)

SKILLS_DIR=\${HERCULES_HOME}/skills
ENABLE_SKILL_AUTO_IMPROVE=true
# Automatically create and improve skills from complex interactions

CONTEXT_COMPRESSION_ENABLED=true
CONTEXT_COMPRESSION_THRESHOLD=50000

# Human-like response pacing (delay between responses)
HERCULES_HUMAN_DELAY_MODE=false
# HERCULES_HUMAN_DELAY_MIN_MS=100
# HERCULES_HUMAN_DELAY_MAX_MS=1000

# ============================================================================
# [8] Terminal Backend (for code execution)
# ============================================================================
# Options: local, docker, ssh, modal, singularity, daytona
TERMINAL_ENV=local

# For Docker backend:
# TERMINAL_DOCKER_IMAGE=nikolaik/python-nodejs:python3.11-nodejs20

# For SSH backend:
# TERMINAL_SSH_HOST=your.server.com
# TERMINAL_SSH_USER=hercules
# TERMINAL_SSH_PORT=22
# TERMINAL_SSH_KEY=\${HERCULES_HOME}/keys/id_rsa

TERMINAL_TIMEOUT=300
# Maximum execution time for tool commands (seconds)

# ============================================================================
# [9] Agent Swarm & Parallel Delegation (Multi-Agent Orchestration)
# ============================================================================
# Hercules supports parallel execution of specialized subagents for
# distributed analysis, code review, testing, and optimization.
#
# EXECUTION MODES:
#   thread   — Default. Lower overhead, I/O-bound tasks, GIL-constrained CPU work
#   process  — True parallelism, CPU-bound tasks, better isolation (no GIL)
#
HERCULES_DELEGATION_EXECUTOR=thread
# Set to "process" for compute-heavy subagent work (analysis, parsing, reasoning)
# HERCULES_DELEGATION_EXECUTOR=process

# Max concurrent subagents (default: CPU count)
# HERCULES_MAX_SUBAGENTS=6

# Subagent task timeout in seconds
# HERCULES_DELEGATION_TIMEOUT=300

# Enable detailed delegation logging
# HERCULES_DELEGATION_DEBUG=false

# ============================================================================
# [10] Optional: GitHub Integration
# ============================================================================
# GITHUB_TOKEN=your_personal_access_token
# GITHUB_APP_ID=
# GITHUB_APP_PRIVATE_KEY_PATH=\${HERCULES_HOME}/keys/github_app_key.pem

# ============================================================================
# Documentation: https://github.com/mintoriakamoto/Hercules/blob/main/.env.example
# ============================================================================
EOF
    chmod 600 "$HERCULES_HOME/.env"
    log_success "Comprehensive configuration created at $HERCULES_HOME/.env"
    echo ""
    echo -e "${YELLOW}📝 Configuration Summary:${NC}"
    echo "  Generated credentials (dashboard password, API server key,"
    echo "  database passwords) were written to $HERCULES_HOME/.env (mode 600)."
    echo "  Read them with:  sudo grep -E '^(DASHBOARD_PASSWORD|API_SERVER_KEY)=' $HERCULES_HOME/.env"
    echo "  They are deliberately not printed here: installer output commonly"
    echo "  lands in shell scrollback, tee logs and CI transcripts."
    echo ""
    echo -e "${YELLOW}⚠️  IMPORTANT:${NC}"
    echo "  1. Edit $HERCULES_HOME/.env to configure your LLM provider and API keys"
    echo "  2. Run: $VENV_DIR/bin/hercules setup  (interactive configuration wizard)"
    echo "  3. See INSTALL.md for platform-specific setup guides"
    echo ""
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
MEMORY_EOF
    sed -i "s/\$(date -u +%Y-%m-%dT%H:%M:%SZ)/$(date -u +%Y-%m-%dT%H:%M:%SZ)/g" "$MEMORY_INIT_FILE"
    chmod 600 "$MEMORY_INIT_FILE"
    log_success "Persistent memory initialized"
fi

# Create systemd service for gateway daemon
# Unquoted delimiter: the unit interpolates the paths resolved above, so it
# cannot drift from where the installer actually put things. The previous
# version hardcoded HERCULES_HOME=/opt/hercules -- the install *directory*, not
# the data home -- so the daemon looked for config in a tree of source and venv.
cat > /etc/systemd/system/hercules-gateway.service << SERVICE_EOF
[Unit]
Description=Hercules Agent Gateway
Documentation=https://github.com/mintoriakamoto/Hercules
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=hercules
WorkingDirectory=$SOURCE_DIR
Environment="PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin"
Environment="HERCULES_HOME=$HERCULES_HOME"
ExecStart=$VENV_DIR/bin/hercules gateway
Restart=on-failure
RestartSec=30
StandardOutput=journal
StandardError=journal
SyslogIdentifier=hercules-gateway

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=$INSTALL_DIR

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
# The gateway unit gets this path baked in. An interactive shell does not, and
# the CLI's own default is the *calling user's* ~/.hercules -- a different
# directory with no .env in it. Say so rather than let it be discovered.
echo "    (export HERCULES_HOME=$HERCULES_HOME so the CLI reads the same config"
echo "     as the gateway service; the service already has it)"
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
echo -e "${CYAN}Agent Swarm (Multi-Agent Orchestration):${NC}"
echo "  HERCULES_DELEGATION_EXECUTOR=process hercules analyze --parallel"
echo "  # Runs up to 6 specialized agents in parallel (code review, testing, etc.)"
echo ""
echo -e "${CYAN}Documentation:${NC}"
echo "  • Repository: $SOURCE_DIR"
echo "  • Principles: $INSTALL_DIR/PRINCIPLES.md"
echo "  • Wiki: https://github.com/mintoriakamoto/Hercules"
echo ""
echo -e "${GREEN}Hercules is ready to serve.${NC}"
echo "Online. Autonomous. Ethical."
echo ""
