#!/usr/bin/env bash
# ==============================================================================
# Firefly Mini — Automated Environment Setup Script v2.1.0
# Idempotent installer with distro detection (Arch, Debian/Ubuntu, Fedora)
# Features: --dry-run, --check, --force
# ==============================================================================

set -euo pipefail

CYAN='\033[0;36m'
PURPLE='\033[0;35m'
AMBER='\033[0;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

DRY_RUN=false
CHECK_ONLY=false
FORCE=false

# Parse flags
for arg in "$@"; do
    case "$arg" in
        --dry-run)
            DRY_RUN=true
            ;;
        --check)
            CHECK_ONLY=true
            ;;
        --force|-f)
            FORCE=true
            ;;
        --help|-h)
            echo "Usage: ./setup.sh [OPTIONS]"
            echo "Options:"
            echo "  --dry-run    Simulate steps without installing packages or files"
            echo "  --check      Verify environment dependencies and exit"
            echo "  --force, -f  Re-run full installation even if dependencies exist"
            echo "  --help, -h   Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $arg${NC}"
            exit 1
            ;;
    esac
done

echo -e "${PURPLE}✦ ============================================================ ✦${NC}"
echo -e "${CYAN}   FIREFLY MINI — Cyber-Cat Linux Setup Sentinel v2.1.0        ${NC}"
echo -e "${PURPLE}✦ ============================================================ ✦${NC}"

# Detect distribution from /etc/os-release
DISTRO_ID="unknown"
if [ -f /etc/os-release ]; then
    # shellcheck disable=SC1091
    source /etc/os-release
    DISTRO_ID="${ID:-unknown}"
fi

if command -v pacman &>/dev/null || [[ "$DISTRO_ID" =~ (arch|manjaro|endeavouros) ]]; then
    PKG_MGR="pacman"
elif command -v apt-get &>/dev/null || [[ "$DISTRO_ID" =~ (debian|ubuntu|linuxmint|pop) ]]; then
    PKG_MGR="apt"
elif command -v dnf &>/dev/null || [[ "$DISTRO_ID" =~ (fedora|rhel|centos) ]]; then
    PKG_MGR="dnf"
else
    PKG_MGR="unknown"
fi

echo -e "${AMBER}🐾 OS Distribution: ${DISTRO_ID} (Package manager: ${PKG_MGR})${NC}"

# Check for essential binaries
check_dep() {
    local bin="$1"
    if command -v "$bin" &>/dev/null; then
        echo -e "  [${GREEN}✔${NC}] $bin: $(command -v "$bin")"
        return 0
    else
        echo -e "  [${RED}✘${NC}] $bin: missing"
        return 1
    fi
}

echo -e "\n${CYAN}🔍 Checking prerequisite utilities...${NC}"
DEPS_OK=true
check_dep python3 || DEPS_OK=false
check_dep ffmpeg || DEPS_OK=false
check_dep curl || DEPS_OK=false

if [ "$CHECK_ONLY" = true ]; then
    if [ "$DEPS_OK" = true ]; then
        echo -e "\n${GREEN}✔ All core dependencies are present.${NC}"
        exit 0
    else
        echo -e "\n${RED}✘ Some dependencies are missing. Run ./setup.sh to install them.${NC}"
        exit 1
    fi
fi

if [ "$DRY_RUN" = true ]; then
    echo -e "\n${AMBER}⚡ DRY-RUN MODE: No changes will be made to system or directories.${NC}"
    echo "  Would execute package installation via $PKG_MGR"
    echo "  Would set up virtualenv .venv and install package in editable mode"
    exit 0
fi

install_packages() {
    echo -e "\n${CYAN}📦 Installing system libraries and utilities via ${PKG_MGR}...${NC}"
    if [ "$PKG_MGR" = "apt" ]; then
        sudo apt-get update -qq || true
        sudo apt-get install -y -qq \
            ffmpeg \
            xdotool \
            feh \
            grim \
            slurp \
            scrot \
            alsa-utils \
            pulseaudio-utils \
            bubblewrap \
            curl \
            python3-pip \
            python3-venv || true
    elif [ "$PKG_MGR" = "pacman" ]; then
        sudo pacman -Sy --noconfirm --needed \
            ffmpeg \
            xdotool \
            feh \
            grim \
            slurp \
            scrot \
            bubblewrap \
            alsa-utils || true
    elif [ "$PKG_MGR" = "dnf" ]; then
        sudo dnf install -y \
            ffmpeg \
            xdotool \
            feh \
            grim \
            slurp \
            scrot \
            bubblewrap \
            alsa-utils || true
    fi
}

# Prompt or install if requested
if [ "${FORCE}" = true ] || [ "$DEPS_OK" = false ]; then
    if [ "${EUID:-$(id -u)}" -ne 0 ] && command -v sudo &>/dev/null; then
        echo -e "${AMBER}Install missing system dependencies with sudo? [y/N]: ${NC}"
        read -r -t 10 response || response="y"
        if [[ "$response" =~ ^[Yy]$ ]]; then
            install_packages
        fi
    fi
fi

# Set up Python virtual environment idempotently
echo -e "\n${CYAN}🐍 Setting up Python virtual environment...${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if command -v uv &>/dev/null; then
    if [ ! -d ".venv" ] || [ "$FORCE" = true ]; then
        uv venv .venv
    fi
    echo -e "${CYAN}📦 Installing Python package and dependencies via uv...${NC}"
    uv pip install --python .venv/bin/python -e ".[dev]" pyyaml
else
    if [ ! -d ".venv" ] || [ "$FORCE" = true ]; then
        python3 -m venv .venv
    fi
    if [ -f ".venv/bin/pip" ]; then
        .venv/bin/pip install --upgrade pip -q
        .venv/bin/pip install -e ".[dev]" pyyaml -q
    fi
fi

# Ensure executable permissions
chmod +x main.py setup.sh 2>/dev/null || true

echo -e "\n${GREEN}✔ Idempotent environment setup completed successfully!${NC}"
echo -e "${PURPLE}🐾 Test Firefly Mini health check:${NC}"
echo -e "   ${AMBER}.venv/bin/firefly doctor${NC}"
echo -e "${PURPLE}🐾 Launch interactive Cyberpunk HUD:${NC}"
echo -e "   ${AMBER}.venv/bin/firefly hud --live${NC}"
