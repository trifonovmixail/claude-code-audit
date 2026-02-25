#!/bin/bash

# Скрипт автоматической установки скилла code-audit для Claude Code
# Использование: eval "$(curl -s https://raw.githubusercontent.com/trifonovmixail/claude-code-audit/main/install.sh)"

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

# Функция очистки при прерывании
cleanup() {
    if [[ -d "$TMP_DIR" ]]; then
        log_info "Очистка временных файлов..."
        rm -rf "$TMP_DIR"
    fi
}

# Установка обработчика сигнала
trap cleanup EXIT INT TERM

# Основная функция установки
install_skill() {
    log_info "Начало установки скилла code-audit..."

    # Проверка наличия git
    if ! command -v git &> /dev/null; then
        log_error "git не найден. Пожалуйста установите git."
        exit 1
    fi

    # Проверка и создание целевой директории
    if [[ ! -d "$HOME/.claude/skills" ]]; then
        log_info "Создание директории ~/.claude/skills..."
        mkdir -p "$HOME/.claude/skills"
    fi

    # Очистка временной директории
    if [[ -d "$TMP_DIR" ]]; then
        log_info "Удаление существующей временной директории..."
        rm -rf "$TMP_DIR"
    fi

    # Клонирование репозитория
    log_info "Клонирование репозитория: $REPO_URL"
    git clone "$REPO_URL" "$TMP_DIR"

    # Удаление существующего скилла
    if [[ -d "$TARGET_DIR" ]]; then
        log_info "Удаление существующей установки скилла..."
        rm -rf "$TARGET_DIR"
    fi

    # Копирование скилла
    log_info "Копирование скилла в $TARGET_DIR..."
    cp -r "$TMP_DIR/$SKILL_DIR" "$TARGET_DIR"

    # Установка прав на исполнение
    log_info "Установка прав на исполнение..."
    chmod +x "$TARGET_DIR/codeaudit.py"

    # Проверка успешности установки
    if [[ -f "$TARGET_DIR/codeaudit.py" && -x "$TARGET_DIR/codeaudit.py" ]]; then
        log_info "Скилл успешно установлен!"
        log_info "Путь к скиллу: $TARGET_DIR"
        log_info "Использование: codeaudit.py <команда> [аргументы]"

        # Предложение добавить в PATH (опционально)
        if [[ ":$PATH:" != *":$TARGET_DIR:"* ]]; then
            log_warn "Для удобства использования добавьте $TARGET_DIR в PATH:"
            log_warn "export PATH=\"\$PATH:$TARGET_DIR\""
            log_warn "Или добавьте эту строку в ~/.bashrc или ~/.zshrc"
        fi
    else
        log_error "Ошибка установки: скрипт не найден или не имеет прав на исполнение"
        exit 1
    fi
}

# Проверка аргументов
case "${1:-}" in
    "--help"|"-h")
        echo "Скрипт автоматической установки скилла code-audit"
        echo ""
        echo "Использование:"
        echo "  $0         - Установить скилл"
        echo "  $0 --help  - Показать это сообщение"
        exit 0
        ;;
    "")
        install_skill
        ;;
    *)
        log_error "Неизвестный аргумент: $1"
        log_error "Используйте $0 --help для справки"
        exit 1
        ;;
esac