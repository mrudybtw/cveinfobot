#!/usr/bin/env python3
"""
Конфигурация логирования для CVE Info Bot
"""

import logging
import logging.handlers
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

class UTCPlus3Formatter(logging.Formatter):
    """Форматтер для времени UTC+3"""
    
    def formatTime(self, record, datefmt=None):
        # Получаем время в UTC+3
        utc_plus_3 = timezone(timedelta(hours=3))
        dt = datetime.fromtimestamp(record.created, tz=utc_plus_3)
        
        if datefmt:
            return dt.strftime(datefmt)
        else:
            return dt.strftime('%Y-%m-%d %H:%M:%S %Z')

def setup_logging(log_level=None, log_dir=None):
    """
    Настройка логирования с ротацией файлов и временем UTC+3
    
    Args:
        log_level: Уровень логирования (по умолчанию из Config)
        log_dir: Директория для логов (по умолчанию из Config)
    """
    # Импортируем Config здесь, чтобы избежать циклических импортов
    from config import Config
    
    # Используем значения по умолчанию из Config
    if log_level is None:
        log_level = getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO)
    if log_dir is None:
        log_dir = Config.LOG_DIR
    
    # Создаем директорию для логов
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # Создаем форматтер с UTC+3
    formatter = UTCPlus3Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Настраиваем root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Очищаем существующие обработчики
    root_logger.handlers.clear()
    
    # Обработчик для консоли
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Обработчик для файла с ротацией (максимум 10MB, 5 файлов)
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_path / "bot.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Обработчик для ошибок (отдельный файл)
    error_handler = logging.handlers.RotatingFileHandler(
        filename=log_path / "errors.log",
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)
    
    # Настройка уровней для конкретных модулей
    logging.getLogger('aiogram').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    # Логируем информацию о настройке
    logger = logging.getLogger(__name__)
    logger.info(f"Логирование настроено. Уровень: {logging.getLevelName(log_level)}")
    logger.info(f"Логи сохраняются в: {log_path.absolute()}")
    logger.info(f"Время отображается в UTC+3")
    
    return logger

def get_logger(name: str) -> logging.Logger:
    """Получить логгер с указанным именем"""
    return logging.getLogger(name)

def log_system_info():
    """Логирование системной информации"""
    logger = logging.getLogger(__name__)
    
    # Информация о системе
    import platform
    import sys
    
    logger.info("=== СИСТЕМНАЯ ИНФОРМАЦИЯ ===")
    logger.info(f"Платформа: {platform.platform()}")
    logger.info(f"Python версия: {sys.version}")
    logger.info(f"Архитектура: {platform.architecture()}")
    logger.info(f"Процессор: {platform.processor()}")
    
    # Информация о памяти
    try:
        import psutil
        memory = psutil.virtual_memory()
        logger.info(f"Память: {memory.total // (1024**3)} GB (доступно: {memory.available // (1024**3)} GB)")
        logger.info(f"Использование CPU: {psutil.cpu_percent()}%")
    except ImportError:
        logger.warning("psutil не установлен, информация о системе ограничена")
    
    logger.info("==========================")

if __name__ == "__main__":
    # Тестирование конфигурации логирования
    setup_logging()
    logger = get_logger(__name__)
    
    logger.info("Тест информационного сообщения")
    logger.warning("Тест предупреждения")
    logger.error("Тест ошибки")
    
    log_system_info()
