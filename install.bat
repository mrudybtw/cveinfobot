@echo off
REM CVE Info Bot - Автоматическая установка для Windows
REM Автор: mrudybtw
REM Версия: 1.0

setlocal enabledelayedexpansion

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                    CVE Info Bot Installer                    ║
echo ║                     Автоматическая установка                 ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

REM Проверка Python
echo [INFO] Проверка Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python не найден. Установите Python 3.8+ с https://python.org
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [SUCCESS] Python !PYTHON_VERSION! найден

REM Проверка pip
echo [INFO] Проверка pip...
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] pip не найден. Установите pip и повторите попытку.
    pause
    exit /b 1
)
echo [SUCCESS] pip найден

REM Установка зависимостей
echo [INFO] Установка зависимостей Python...
if exist requirements.txt (
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Ошибка установки зависимостей
        pause
        exit /b 1
    )
    echo [SUCCESS] Зависимости установлены
) else (
    echo [ERROR] Файл requirements.txt не найден
    pause
    exit /b 1
)

REM Создание директорий
echo [INFO] Создание необходимых директорий...
if not exist logs mkdir logs
if not exist db mkdir db
echo [SUCCESS] Директории созданы

REM Создание .env файла
echo [INFO] Создание файла конфигурации...
if not exist .env (
    (
        echo # Telegram Bot Configuration
        echo TELEGRAM_TOKEN=your_telegram_bot_token_here
        echo.
        echo # Ollama Configuration
        echo OLLAMA_BASE_URL=http://localhost:11434
        echo OLLAMA_MODEL=llama3.1:8b
        echo.
        echo # Database Configuration
        echo DB_PATH=db/cve.db
        echo.
        echo # NVD API Configuration
        echo NVD_API_URL=https://services.nvd.nist.gov/rest/json/cves/2.0
        echo NVD_API_KEY=your_nvd_api_key_here_optional
        echo NVD_UPDATE_INTERVAL=3600
        echo.
        echo # Logging Configuration
        echo LOG_LEVEL=INFO
        echo LOG_DIR=logs
        echo LOG_MAX_SIZE=10485760
        echo LOG_BACKUP_COUNT=5
        echo TIMEZONE=UTC+3
        echo.
        echo # EPSS Configuration
        echo EPSS_API_URL=https://api.first.org/data/v1/epss
    ) > .env
    echo [SUCCESS] Файл .env создан
    echo [WARNING] Не забудьте отредактировать .env файл и добавить ваш TELEGRAM_TOKEN!
) else (
    echo [WARNING] Файл .env уже существует, пропускаем создание
)

REM Проверка Ollama
echo [INFO] Проверка Ollama (опционально)...
ollama --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [SUCCESS] Ollama найден
    curl -s http://localhost:11434/api/tags >nul 2>&1
    if %errorlevel% equ 0 (
        echo [SUCCESS] Ollama сервер запущен
    ) else (
        echo [WARNING] Ollama сервер не запущен. Запустите: ollama serve
    )
) else (
    echo [WARNING] Ollama не найден. AI-анализ будет недоступен.
    echo [WARNING] Для установки Ollama: https://ollama.ai/download
)

REM Тест установки
echo [INFO] Тестирование установки...
python -c "
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
"
if %errorlevel% neq 0 (
    echo [ERROR] Тест установки не прошел
    pause
    exit /b 1
)
echo [SUCCESS] Тест установки прошел успешно

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                    УСТАНОВКА ЗАВЕРШЕНА!                    ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
echo Следующие шаги:
echo 1. Отредактируйте файл .env и добавьте ваш TELEGRAM_TOKEN
echo 2. (Опционально) Установите и запустите Ollama для AI-анализа
echo 3. Запустите бота: python run_bot.py
echo.
echo Дополнительная информация:
echo • Документация: README.md
echo • Логи: logs\bot.log
echo • База данных: db\cve.db
echo.
echo Удачного использования! 🚀
echo.
pause
