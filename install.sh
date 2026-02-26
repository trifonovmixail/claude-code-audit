#!/bin/sh

# CodeAudit skill installer for Claude Code
# Usage: eval "$(curl -s https://raw.githubusercontent.com/trifonovmixail/claude-code-audit/main/install.sh)"

set -euo pipefail

# Константы
REPO_URL="https://github.com/trifonovmixail/claude-code-audit.git"
TMP_DIR="/tmp/claude-code-audit-install"
TARGET_DIR="$HOME/.claude/skills/code-audit"
SKILL_DIR="code-audit"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функции для вывода сообщений
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Cleanup function on interruption
cleanup() {
    if [[ -d "$TMP_DIR" ]]; then
        log_info "Cleaning up temporary files..."
        rm -rf "$TMP_DIR"
    fi
}

# Set up signal handler
trap cleanup EXIT INT TERM

# Main installation function
install_skill() {
    log_info "Starting CodeAudit skill installation..."

    # Check git availability
    if ! command -v git &> /dev/null; then
        log_error "git not found. Please install git first."
        exit 1
    fi

    # Create target directory if it doesn't exist
    if [[ ! -d "$HOME/.claude/skills" ]]; then
        log_info "Creating ~/.claude/skills directory..."
        mkdir -p "$HOME/.claude/skills"
    fi

    # Clean temporary directory
    if [[ -d "$TMP_DIR" ]]; then
        log_info "Removing existing temporary directory..."
        rm -rf "$TMP_DIR"
    fi

    # Clone repository
    log_info "Cloning repository: $REPO_URL"
    git clone -q "$REPO_URL" "$TMP_DIR"

    # Remove existing skill installation
    if [[ -d "$TARGET_DIR" ]]; then
        log_info "Removing existing skill installation..."
        rm -rf "$TARGET_DIR"
    fi

    # Copy skill
    log_info "Copying skill to $TARGET_DIR..."
    cp -r "$TMP_DIR/$SKILL_DIR" "$TARGET_DIR"

    # Set executable permissions
    log_info "Setting executable permissions..."
    chmod +x "$TARGET_DIR/codeaudit.py"

    # Verify successful installation
    if [[ -f "$TARGET_DIR/codeaudit.py" && -x "$TARGET_DIR/codeaudit.py" ]]; then
        log_info "Skill installed successfully!"
        log_info "Skill location: $TARGET_DIR"
        log_info "Usage: codeaudit.py <command> [arguments]"
    else
        log_error "Installation failed: script not found or not executable"
        exit 1
    fi
}

# Argument checking
case "${1:-}" in
    "--help"|"-h")
        echo "CodeAudit skill installer for Claude Code"
        echo ""
        echo "Usage:"
        echo "  $0         - Install the skill"
        echo "  $0 --help  - Show this message"
        exit 0
        ;;
    "")
        install_skill
        ;;
    *)
        log_error "Unknown argument: $1"
        log_error "Use $0 --help for help"
        exit 1
        ;;
esac