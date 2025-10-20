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
from config import Config

# Настройка логирования с ротацией и UTC+3
setup_logging()
logger = get_logger(__name__)

class BotManager:
    def __init__(self):
        self.bot_task = None
        self.update_task = None
        self.full_load_task = None  # Фоновая загрузка всех CVE
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
                from db.init_db import init_db
                init_db()
                logger.info("✅ База данных инициализирована")
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации БД: {e}")
                return False
        
        # Проверка наличия CVE в базе данных
        if not await self.check_cve_database():
            logger.info("📊 База данных CVE пуста. Загружаем начальные данные...")
            if not await self.initialize_cve_database():
                logger.error("❌ Не удалось загрузить начальные CVE данные")
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
    
    async def check_cve_database(self):
        """Проверка наличия CVE в базе данных"""
        try:
            conn = sqlite3.connect(Config.DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM cve")
            count = cursor.fetchone()[0]
            conn.close()
            
            if count > 0:
                logger.info(f"✅ База данных содержит {count:,} CVE")
                return True
            else:
                logger.info("⚠️  База данных CVE пуста")
                return False
        except Exception as e:
            logger.error(f"❌ Ошибка проверки базы данных: {e}")
            return False
    
    async def check_cve_statistics(self):
        """Проверка статистики CVE в NVD и базе данных"""
        try:
            logger.info("📊 Проверка статистики CVE...")
            
            # Количество CVE в NVD
            nvd_count = await self.get_nvd_cve_count()
            if nvd_count:
                logger.info(f"📊 CVE в NVD: {nvd_count:,}")
            
            # Количество CVE в базе данных
            conn = sqlite3.connect(Config.DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM cve")
            db_count = cursor.fetchone()[0]
            conn.close()
            
            logger.info(f"📊 CVE в базе данных: {db_count:,}")
            
            if nvd_count and db_count:
                percentage = (db_count / nvd_count) * 100
                logger.info(f"📊 Покрытие: {percentage:.3f}% ({db_count:,}/{nvd_count:,})")
                
                if percentage < 50:
                    logger.info("💡 Рекомендуется полная загрузка CVE")
                    return True  # Нужна полная загрузка
                else:
                    logger.info("✅ База данных достаточно полная")
                    return False  # Полная загрузка не нужна
            
            return db_count < 100000  # Если меньше 100k CVE, нужна полная загрузка
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки статистики CVE: {e}")
            return True  # В случае ошибки запускаем полную загрузку
    
    async def initialize_cve_database(self):
        """Инициализация базы данных CVE с умной обработкой rate limiting"""
        try:
            from bot.services.collector import load_all_cves
            
            logger.info("🔄 Загружаем начальные CVE данные...")
            logger.info("💡 Это может занять несколько минут из-за rate limiting...")
            
            success = await load_all_cves()
            
            if success:
                # Проверяем результат
                conn = sqlite3.connect(Config.DB_PATH)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM cve")
                count = cursor.fetchone()[0]
                conn.close()
                
                logger.info(f"✅ Успешно загружено {count:,} CVE")
                return True
            else:
                logger.error("❌ Не удалось загрузить CVE данные")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации CVE базы данных: {e}")
            return False
    
    async def full_cve_load_background(self):
        """Фоновая загрузка всех CVE в фоновом режиме"""
        try:
            logger.info("🔄 Запуск фоновой загрузки всех CVE...")
            logger.info("💡 Это займет несколько часов, но бот работает нормально")
            
            # Сначала проверяем количество CVE в NVD
            nvd_count = await self.get_nvd_cve_count()
            if nvd_count:
                logger.info(f"📊 Всего CVE в NVD: {nvd_count:,}")
            
            # Используем нашу функцию загрузки с большим лимитом
            success = await self.load_all_cves_with_limit(300000)  # 300k CVE
            
            if success:
                conn = sqlite3.connect(Config.DB_PATH)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM cve")
                count = cursor.fetchone()[0]
                conn.close()
                
                logger.info(f"🎉 Фоновая загрузка CVE завершена! Всего CVE: {count:,}")
                
                # После загрузки CVE начинаем загружать EPSS
                logger.info("📊 Начинаем загрузку EPSS данных...")
                from bot.services.collector import load_epss_data
                epss_success = await load_epss_data()
                if epss_success:
                    logger.info("✅ EPSS данные загружены")
                else:
                    logger.warning("⚠️  Не удалось загрузить EPSS данные")
            else:
                logger.error("❌ Ошибка фоновой загрузки CVE")
                
        except Exception as e:
            logger.error(f"❌ Ошибка фоновой загрузки: {e}")
    
    async def get_nvd_cve_count(self):
        """Получает общее количество CVE в NVD"""
        try:
            from bot.services.collector import fetch_cve
            data = await fetch_cve(start_index=0, results_per_page=1)
            return data.get('totalResults', 0)
        except Exception as e:
            logger.error(f"❌ Ошибка получения количества CVE из NVD: {e}")
            return None
    
    async def load_all_cves_with_limit(self, max_cves=300000):
        """Загрузка CVE с указанным лимитом"""
        try:
            from bot.services.collector import fetch_cve
            import aiohttp # type: ignore
            
            logger.info(f"🔄 Загружаем до {max_cves:,} CVE...")
            
            # Получаем общее количество CVE
            initial_data = await fetch_cve(start_index=0, results_per_page=1)
            total_results = initial_data.get('totalResults', 0)
            logger.info(f"📊 Всего доступно CVE: {total_results:,}")
            
            if total_results == 0:
                logger.error("No CVEs found in NVD")
                return False
            
            # Загружаем ВСЕ CVE, а не только первые 300k
            max_cves = total_results  # Загружаем все доступные CVE
            page_size = 1000
            total_pages = (max_cves + page_size - 1) // page_size
            
            logger.info(f"📥 Загружаем ВСЕ {max_cves:,} CVE в {total_pages} страниц...")
            
            all_vulnerabilities = []
            
            for page in range(total_pages):
                start_index = page * page_size
                current_page_size = min(page_size, max_cves - start_index)
                
                if page % 10 == 0:  # Логируем каждые 10 страниц
                    logger.info(f"📄 Фоновая загрузка: {page}/{total_pages} страниц ({len(all_vulnerabilities):,} CVE)")
                
                try:
                    data = await fetch_cve(start_index=start_index, results_per_page=current_page_size)
                    vulnerabilities = data.get('vulnerabilities', [])
                    
                    if vulnerabilities:
                        all_vulnerabilities.extend(vulnerabilities)
                    else:
                        logger.warning(f"⚠️  No CVEs found on page {page + 1}")
                        break
                        
                    # Пауза между запросами
                    if page < total_pages - 1:
                        await asyncio.sleep(2.0)
                        
                except Exception as e:
                    logger.error(f"❌ Error loading page {page + 1}: {e}")
                    if page < total_pages - 1:
                        await asyncio.sleep(10)  # Больше пауза при ошибке
                    continue
            
            if all_vulnerabilities:
                logger.info(f"💾 Сохраняем {len(all_vulnerabilities):,} CVE в базу данных...")
                from bot.services.collector import save_cve_to_db
                save_cve_to_db(all_vulnerabilities)
                logger.info(f"✅ Успешно загружено {len(all_vulnerabilities):,} CVE")
                return True
            else:
                logger.error("❌ No vulnerabilities loaded")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error loading CVEs: {e}")
            return False
    
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
                from bot.services.collector import load_all_cves
                success = await load_all_cves()
                if success:
                    logger.info("✅ Первоначальная загрузка CVE завершена")
                else:
                    logger.error("❌ Ошибка загрузки CVE данных")
                    return False
                
                # Загружаем EPSS данные
                logger.info("📊 Загружаем EPSS данные...")
                from bot.services.collector import load_epss_data
                epss_success = await load_epss_data()
                if epss_success:
                    logger.info("✅ EPSS данные загружены")
                else:
                    logger.warning("⚠️  Не удалось загрузить EPSS данные")
            else:
                logger.info(f"📊 В базе данных уже есть {count:,} CVE записей")
                
                # Проверяем наличие EPSS данных
                cursor.execute("SELECT COUNT(*) FROM cve WHERE epss IS NOT NULL")
                epss_count = cursor.fetchone()[0]
                
                if epss_count == 0:
                    logger.info("📊 EPSS данные отсутствуют. Загружаем ВСЕ данные...")
                    from bot.services.collector import load_epss_data
                    
                    epss_success = await load_epss_data()
                    if epss_success:
                        logger.info("✅ EPSS данные загружены")
                    else:
                        logger.warning("⚠️  Не удалось загрузить EPSS данные")
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
            from bot.services.collector import load_incremental_cves
            
            # Получаем количество записей до обновления
            conn = sqlite3.connect('db/cve.db')
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM cve")
            old_count = cursor.fetchone()[0]
            conn.close()
            
            # Запускаем инкрементное обновление
            success = await load_incremental_cves()
            
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
                logger.info(f"📊 Всего CVE в базе: {new_count:,}")
            else:
                logger.info(f"✅ Обновление завершено! Добавлено {added_count:,} новых CVE")
                logger.info(f"📊 Всего CVE в базе: {new_count:,}")
            
            # Обновляем EPSS данные инкрементально
            logger.info("📊 Обновляем EPSS данные...")
            from bot.services.collector import load_epss_data, should_update_epss
            
            if await should_update_epss():
                epss_success = await load_epss_data()
                if epss_success:
                    logger.info("✅ EPSS данные обновлены")
                else:
                    logger.warning("⚠️  Не удалось обновить EPSS данные")
            else:
                logger.info("⏭️  EPSS данные недавно обновлялись, пропускаем")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при обновлении CVE: {e}")
    
    async def periodic_update(self):
        """Периодическое обновление CVE каждый час"""
        from datetime import datetime
        logger.info(f"🔄 Запуск периодического обновления каждые {Config.NVD_UPDATE_INTERVAL} секунд")
        while self.running:
            try:
                current_time = datetime.now().strftime("%H:%M:%S")
                logger.info(f"⏰ [{current_time}] Ожидание {Config.NVD_UPDATE_INTERVAL} секунд до следующего обновления...")
                await asyncio.sleep(Config.NVD_UPDATE_INTERVAL)  # Ждем согласно конфигурации
                if self.running:
                    current_time = datetime.now().strftime("%H:%M:%S")
                    logger.info(f"🔄 [{current_time}] Начинаем периодическое обновление CVE...")
                    await self.update_cve_data()
                    current_time = datetime.now().strftime("%H:%M:%S")
                    logger.info(f"✅ [{current_time}] Периодическое обновление завершено")
                else:
                    logger.info("⏹️  Обновление отменено, бот остановлен")
            except Exception as e:
                current_time = datetime.now().strftime("%H:%M:%S")
                logger.error(f"❌ [{current_time}] Ошибка в периодическом обновлении: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
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
        
        # Останавливаем фоновую загрузку если она запущена
        if self.full_load_task and not self.full_load_task.done():
            logger.info("🛑 Останавливаем фоновую загрузку CVE...")
            self.full_load_task.cancel()
    
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
            
            # Проверяем, нужна ли полная загрузка CVE
            needs_full_load = await self.check_cve_statistics()
            
            if needs_full_load:
                logger.info("🔄 Запуск фоновой загрузки ВСЕХ CVE...")
                logger.info("💡 Это займет несколько часов, но бот работает нормально")
                self.full_load_task = asyncio.create_task(self.full_cve_load_background())
            else:
                logger.info("✅ База данных достаточно полная, фоновая загрузка не нужна")
                
                # Если полная загрузка не нужна, но EPSS данных нет, загружаем их
                conn = sqlite3.connect(Config.DB_PATH)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM cve WHERE epss IS NOT NULL")
                epss_count = cursor.fetchone()[0]
                conn.close()
                
                if epss_count == 0:
                    logger.info("📊 EPSS данные отсутствуют. Загружаем ВСЕ данные...")
                    from bot.services.collector import load_epss_data
                    
                    epss_success = await load_epss_data()
                    if epss_success:
                        logger.info("✅ EPSS данные загружены")
                    else:
                        logger.warning("⚠️  Не удалось загрузить EPSS данные")
            
            # Запуск бота
            self.bot_task = asyncio.create_task(self.start_bot())
            
            # Ожидание завершения
            tasks = [self.bot_task, self.update_task]
            if self.full_load_task:
                tasks.append(self.full_load_task)
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
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