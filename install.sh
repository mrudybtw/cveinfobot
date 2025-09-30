#!/bin/bash

# CVE Info Bot - Автоматическая установка
# Автор: mrudybtw
# Версия: 1.0

set -e  # Остановка при ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция для вывода сообщений
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка операционной системы
check_os() {
    print_status "Проверка операционной системы..."
    
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
        print_success "Обнаружена Linux система"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        print_success "Обнаружена macOS система"
    else
        print_error "Неподдерживаемая операционная система: $OSTYPE"
        exit 1
    fi
}

# Проверка Python
check_python() {
    print_status "Проверка Python..."
    
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
        print_success "Python $PYTHON_VERSION найден"
        
        # Проверка версии Python
        if python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
            print_success "Версия Python подходящая (>= 3.8)"
        else
            print_error "Требуется Python 3.8 или выше. Текущая версия: $PYTHON_VERSION"
            exit 1
        fi
    else
        print_error "Python3 не найден. Установите Python 3.8+ и повторите попытку."
        exit 1
    fi
}

# Проверка pip
check_pip() {
    print_status "Проверка pip..."
    
    if command -v pip3 &> /dev/null; then
        print_success "pip3 найден"
    else
        print_error "pip3 не найден. Установите pip и повторите попытку."
        exit 1
    fi
}

# Установка зависимостей
install_dependencies() {
    print_status "Установка зависимостей Python..."
    
    if [ -f "requirements.txt" ]; then
        pip3 install -r requirements.txt --user
        print_success "Зависимости установлены"
    else
        print_error "Файл requirements.txt не найден"
        exit 1
    fi
}

# Создание .env файла
create_env_file() {
    print_status "Создание файла конфигурации..."
    
    if [ ! -f ".env" ]; then
        cat > .env << EOF
# Telegram Bot Configuration
TELEGRAM_TOKEN=your_telegram_bot_token_here

# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

# Database Configuration
DB_PATH=db/cve.db

# NVD API Configuration
NVD_API_URL=https://services.nvd.nist.gov/rest/json/cves/2.0
NVD_API_KEY=your_nvd_api_key_here_optional
NVD_UPDATE_INTERVAL=3600

# Logging Configuration
LOG_LEVEL=INFO
LOG_DIR=logs
LOG_MAX_SIZE=10485760
LOG_BACKUP_COUNT=5
TIMEZONE=UTC+3

# EPSS Configuration
EPSS_API_URL=https://api.first.org/data/v1/epss
EOF
        print_success "Файл .env создан"
        print_warning "Не забудьте отредактировать .env файл и добавить ваш TELEGRAM_TOKEN!"
    else
        print_warning "Файл .env уже существует, пропускаем создание"
    fi
}

# Создание директорий
create_directories() {
    print_status "Создание необходимых директорий..."
    
    mkdir -p logs
    mkdir -p db
    print_success "Директории созданы"
}

# Установка Ollama
install_ollama() {
    print_status "Установка Ollama..."
    
    if command -v ollama &> /dev/null; then
        print_success "Ollama уже установлен"
        return 0
    fi
    
    print_status "Скачивание и установка Ollama..."
    
    if [[ "$OS" == "linux" ]]; then
        # Linux установка
        curl -fsSL https://ollama.ai/install.sh | sh
        if [ $? -eq 0 ]; then
            print_success "Ollama установлен для Linux"
        else
            print_error "Ошибка установки Ollama для Linux"
            return 1
        fi
    elif [[ "$OS" == "macos" ]]; then
        # macOS установка через Homebrew
        if command -v brew &> /dev/null; then
            brew install ollama
            if [ $? -eq 0 ]; then
                print_success "Ollama установлен через Homebrew"
            else
                print_error "Ошибка установки Ollama через Homebrew"
                return 1
            fi
        else
            print_warning "Homebrew не найден. Установите Ollama вручную: https://ollama.ai/download"
            return 1
        fi
    fi
}

# Запуск Ollama сервера
start_ollama() {
    print_status "Запуск Ollama сервера..."
    
    # Проверяем, запущен ли уже сервер
    if curl -s http://localhost:11434/api/tags &> /dev/null; then
        print_success "Ollama сервер уже запущен"
        return 0
    fi
    
    # Запускаем сервер в фоне
    nohup ollama serve > logs/ollama.log 2>&1 &
    OLLAMA_PID=$!
    
    # Ждем запуска сервера
    print_status "Ожидание запуска Ollama сервера..."
    for i in {1..30}; do
        if curl -s http://localhost:11434/api/tags &> /dev/null; then
            print_success "Ollama сервер запущен (PID: $OLLAMA_PID)"
            echo $OLLAMA_PID > logs/ollama.pid
            return 0
        fi
        sleep 2
    done
    
    print_error "Не удалось запустить Ollama сервер"
    return 1
}

# Скачивание модели LLaMA
download_llama_model() {
    print_status "Скачивание модели LLaMA 3.1 8B..."
    
    # Проверяем, есть ли уже модель
    if curl -s http://localhost:11434/api/tags | grep -q "llama3.1:8b"; then
        print_success "Модель LLaMA 3.1 8B уже загружена"
        return 0
    fi
    
    print_status "Скачивание модели (это может занять несколько минут)..."
    ollama pull llama3.1:8b
    
    if [ $? -eq 0 ]; then
        print_success "Модель LLaMA 3.1 8B загружена"
    else
        print_error "Ошибка загрузки модели LLaMA 3.1 8B"
        return 1
    fi
}

# Проверка Ollama (опционально)
check_ollama() {
    print_status "Проверка Ollama..."
    
    if command -v ollama &> /dev/null; then
        print_success "Ollama найден"
        
        # Проверка запущенного сервера
        if curl -s http://localhost:11434/api/tags &> /dev/null; then
            print_success "Ollama сервер запущен"
        else
            print_warning "Ollama сервер не запущен. Запустите: ollama serve"
        fi
    else
        print_warning "Ollama не найден. AI-анализ будет недоступен."
        print_warning "Для установки Ollama: https://ollama.ai/download"
    fi
}

# Тест установки
test_installation() {
    print_status "Тестирование установки..."
    
    if python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from bot.main import bot, dp
    from bot.services.bot_service import BotService
    from config import Config
    print('✅ Все модули импортируются успешно')
except Exception as e:
    print(f'❌ Ошибка импорта: {e}')
    sys.exit(1)
"; then
        print_success "Тест установки прошел успешно"
    else
        print_error "Тест установки не прошел"
        exit 1
    fi
}

# Создание systemd сервиса (только для Linux)
create_systemd_service() {
    if [[ "$OS" == "linux" ]]; then
        print_status "Создание systemd сервиса..."
        
        SERVICE_FILE="/etc/systemd/system/cveinfobot.service"
        CURRENT_DIR=$(pwd)
        
        if [ -w "/etc/systemd/system" ]; then
            sudo tee $SERVICE_FILE > /dev/null << EOF
[Unit]
Description=CVE Info Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$CURRENT_DIR
ExecStart=/usr/bin/python3 $CURRENT_DIR/run_bot.py
Restart=always
RestartSec=10
Environment=PYTHONPATH=$CURRENT_DIR

[Install]
WantedBy=multi-user.target
EOF
            print_success "Systemd сервис создан: $SERVICE_FILE"
            print_warning "Для запуска сервиса выполните:"
            print_warning "  sudo systemctl enable cveinfobot"
            print_warning "  sudo systemctl start cveinfobot"
        else
            print_warning "Нет прав для создания systemd сервиса"
        fi
    fi
}

# Основная функция
main() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    CVE Info Bot Installer                    ║"
    echo "║                     Автоматическая установка                 ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    # Проверки
    check_os
    check_python
    check_pip
    
    # Установка
    install_dependencies
    create_directories
    create_env_file
    
    # Установка и настройка Ollama
    if install_ollama; then
        if start_ollama; then
            download_llama_model
        fi
    else
        print_warning "Ollama не установлен. AI-анализ будет недоступен."
    fi
    
    # Тестирование
    test_installation
    
    # Дополнительные настройки
    create_systemd_service
    
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗"
    echo -e "║                    УСТАНОВКА ЗАВЕРШЕНА!                    ║"
    echo -e "╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}Следующие шаги:${NC}"
    echo "1. Отредактируйте файл .env и добавьте ваш TELEGRAM_TOKEN"
    echo "2. Запустите бота: python3 run_bot.py"
    echo ""
    echo -e "${BLUE}Ollama статус:${NC}"
    if [ -f "logs/ollama.pid" ]; then
        echo "• Ollama сервер запущен (PID: $(cat logs/ollama.pid))"
        echo "• Модель LLaMA 3.1 8B загружена"
        echo "• AI-анализ доступен"
    else
        echo "• Ollama не установлен или не запущен"
        echo "• AI-анализ недоступен"
    fi
    echo ""
    echo -e "${BLUE}Дополнительная информация:${NC}"
    echo "• Документация: README.md"
    echo "• Логи: logs/bot.log"
    echo "• База данных: db/cve.db"
    echo ""
    echo -e "${GREEN}Удачного использования! 🚀${NC}"
}

# Запуск
main "$@"
