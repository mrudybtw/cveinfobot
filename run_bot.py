#!/usr/bin/env python3
"""
Автономный запуск CVE Info Bot с автоматической загрузкой и обновлением CVE
"""

import asyncio
import sys
import os
import signal
import logging
from pathlib import Path
from datetime import datetime, timedelta
import sqlite3

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Импортируем настройку логирования
from bot.utils.logging_config import setup_logging, get_logger, log_system_info

# Настройка логирования с ротацией и UTC+3
setup_logging()
logger = get_logger(__name__)

class BotManager:
    def __init__(self):
        self.bot_task = None
        self.update_task = None
        self.running = False
        self.last_update = None
        self.last_cve_id = None
        
    async def check_environment(self):
        """Проверка окружения"""
        logger.info("🔍 Проверка окружения...")
        
        # Проверка .env файла
        if not Path(".env").exists():
            logger.error("❌ .env файл не найден. Создайте его с TELEGRAM_TOKEN")
            return False
        
        # Проверка базы данных
        if not Path("db/cve.db").exists():
            logger.info("📊 База данных не найдена. Инициализация...")
            try:
                from db.init_db import init_database
                init_database()
                logger.info("✅ База данных инициализирована")
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации БД: {e}")
                return False
        
        # Проверка Ollama
        try:
            import subprocess
            result = subprocess.run(['ollama', '--version'], capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                logger.warning("⚠️ Ollama не найден. AI-анализ будет недоступен")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("⚠️ Ollama не найден. AI-анализ будет недоступен")
        
        logger.info("✅ Проверка окружения завершена")
        return True
    
    async def load_initial_cve_data(self):
        """Первоначальная загрузка CVE данных"""
        logger.info("📥 Проверка необходимости загрузки CVE данных...")
        
        try:
            conn = sqlite3.connect('db/cve.db')
            cursor = conn.cursor()
            
            # Проверяем количество записей
            cursor.execute("SELECT COUNT(*) FROM cve")
            count = cursor.fetchone()[0]
            
            if count == 0:
                logger.info("📊 База данных пуста. Начинаем загрузку CVE...")
                from load_cve_data import main as load_cve_main
                await load_cve_main()
                logger.info("✅ Первоначальная загрузка CVE завершена")
                
                # Загружаем EPSS данные
                logger.info("📊 Загружаем EPSS данные...")
                from load_epss_data import main as load_epss_main
                load_epss_main()
                logger.info("✅ Загрузка EPSS данных завершена")
            else:
                logger.info(f"📊 В базе данных уже есть {count:,} CVE записей")
                
                # Проверяем наличие EPSS данных
                cursor.execute("SELECT COUNT(*) FROM cve WHERE epss IS NOT NULL")
                epss_count = cursor.fetchone()[0]
                
                if epss_count == 0:
                    logger.info("📊 EPSS данные отсутствуют. Загружаем...")
                    from load_epss_data import main as load_epss_main
                    load_epss_main()
                    logger.info("✅ Загрузка EPSS данных завершена")
                else:
                    logger.info(f"📊 EPSS данные доступны для {epss_count:,} CVE")
                
                # Получаем информацию о последнем обновлении
                cursor.execute("SELECT MAX(published_date) FROM cve")
                last_date = cursor.fetchone()[0]
                if last_date:
                    self.last_update = last_date
                    logger.info(f"📅 Последнее обновление: {last_date}")
                
                # Получаем последний CVE ID
                cursor.execute("SELECT id FROM cve ORDER BY published_date DESC LIMIT 1")
                last_cve = cursor.fetchone()
                if last_cve:
                    self.last_cve_id = last_cve[0]
                    logger.info(f"🆔 Последний CVE: {self.last_cve_id}")
            
            conn.close()
            
        except Exception as e:
            logger.error(f"❌ Ошибка при загрузке CVE данных: {e}")
            return False
        
        return True
    
    async def update_cve_data(self):
        """Обновление CVE данных"""
        logger.info("🔄 Начинаем обновление CVE данных...")
        
        try:
            from load_cve_data import load_cves_incremental
            
            # Получаем количество записей до обновления
            conn = sqlite3.connect('db/cve.db')
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM cve")
            old_count = cursor.fetchone()[0]
            conn.close()
            
            # Запускаем инкрементное обновление
            success = await load_cves_incremental()
            
            if not success:
                logger.error("❌ Ошибка при загрузке CVE данных")
                return
            
            # Получаем количество записей после обновления
            conn = sqlite3.connect('db/cve.db')
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM cve")
            new_count = cursor.fetchone()[0]
            
            # Получаем последний CVE
            cursor.execute("SELECT id, published_date FROM cve ORDER BY published_date DESC LIMIT 1")
            last_cve = cursor.fetchone()
            
            conn.close()
            
            added_count = new_count - old_count
            self.last_update = datetime.now().isoformat()
            
            if last_cve:
                self.last_cve_id = last_cve[0]
                logger.info(f"✅ Обновление завершено! Добавлено {added_count:,} новых CVE")
                logger.info(f"🆔 Последний CVE: {self.last_cve_id} ({last_cve[1]})")
            else:
                logger.info(f"✅ Обновление завершено! Добавлено {added_count:,} новых CVE")
            
            # Обновляем EPSS данные раз в день
            logger.info("📊 Проверяем необходимость обновления EPSS данных...")
            from load_epss_data import main as load_epss_main
            load_epss_main()
            logger.info("✅ EPSS данные обновлены")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при обновлении CVE: {e}")
    
    async def periodic_update(self):
        """Периодическое обновление CVE каждый час"""
        while self.running:
            try:
                await asyncio.sleep(3600)  # Ждем 1 час
                if self.running:
                    await self.update_cve_data()
            except Exception as e:
                logger.error(f"❌ Ошибка в периодическом обновлении: {e}")
                await asyncio.sleep(300)  # Ждем 5 минут при ошибке
    
    async def start_bot(self):
        """Запуск бота"""
        logger.info("🤖 Запуск Telegram бота...")
        
        try:
            from bot.main import main as bot_main
            await bot_main()
        except Exception as e:
            logger.error(f"❌ Ошибка запуска бота: {e}")
            raise
    
    async def get_stats(self):
        """Получение статистики"""
        try:
            conn = sqlite3.connect('db/cve.db')
            cursor = conn.cursor()
            
            # Общее количество CVE
            cursor.execute("SELECT COUNT(*) FROM cve")
            total_cve = cursor.fetchone()[0]
            
            # Количество критических CVE
            cursor.execute("SELECT COUNT(*) FROM cve WHERE cvss_v3 >= 9.0")
            critical_cve = cursor.fetchone()[0]
            
            # Последнее обновление
            cursor.execute("SELECT MAX(published_date) FROM cve")
            last_update = cursor.fetchone()[0]
            
            # Последний CVE
            cursor.execute("SELECT id FROM cve ORDER BY published_date DESC LIMIT 1")
            last_cve = cursor.fetchone()
            
            conn.close()
            
            return {
                'total_cve': total_cve,
                'critical_cve': critical_cve,
                'last_update': last_update,
                'last_cve': last_cve[0] if last_cve else None
            }
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")
            return None
    
    def signal_handler(self, signum, frame):
        """Обработчик сигналов для graceful shutdown"""
        logger.info(f"🛑 Получен сигнал {signum}. Останавливаем бота...")
        self.running = False
    
    async def run(self):
        """Основной цикл работы"""
        logger.info("🚀 Запуск CVE Info Bot...")
        
        # Логируем системную информацию
        log_system_info()
        
        # Настройка обработчиков сигналов
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        try:
            # Проверка окружения
            if not await self.check_environment():
                logger.error("❌ Проверка окружения не пройдена")
                return
            
            # Загрузка CVE данных
            if not await self.load_initial_cve_data():
                logger.error("❌ Ошибка загрузки CVE данных")
                return
            
            self.running = True
            
            # Запуск периодического обновления
            self.update_task = asyncio.create_task(self.periodic_update())
            
            # Запуск бота
            self.bot_task = asyncio.create_task(self.start_bot())
            
            # Ожидание завершения
            await asyncio.gather(self.bot_task, self.update_task, return_exceptions=True)
            
        except KeyboardInterrupt:
            logger.info("👋 Остановка по Ctrl+C")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка: {e}")
        finally:
            self.running = False
            if self.update_task:
                self.update_task.cancel()
            if self.bot_task:
                self.bot_task.cancel()
            logger.info("🛑 Бот остановлен")

def main():
    """Главная функция"""
    manager = BotManager()
    asyncio.run(manager.run())

if __name__ == "__main__":
    main()