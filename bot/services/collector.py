import asyncio
import aiohttp
import sqlite3
import os
from datetime import datetime
from config import Config

DB_PATH = Config.DB_PATH
NVD_API_URL = Config.NVD_API_URL
NVD_API_KEY = Config.get_nvd_api_key()  # Опциональный API ключ для NVD
EPSS_API_URL = Config.EPSS_API_URL

# Проверяем, что API ключ не является заглушкой
if NVD_API_KEY and NVD_API_KEY.startswith('your_'):
    NVD_API_KEY = ""  # Убираем недействительный ключ

async def fetch_cve(start_index=0, results_per_page=2000, max_retries=3):
    """
    Загружает CVE с умной обработкой rate limiting
    """
    params = {
        "startIndex": start_index,
        "resultsPerPage": results_per_page
    }
    
    headers = {}
    if NVD_API_KEY:
        headers["apiKey"] = NVD_API_KEY
    
    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(NVD_API_URL, params=params, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data
                    elif resp.status == 429:  # Rate limited
                        if attempt < max_retries - 1:
                            wait_time = (2 ** attempt) * 5  # Экспоненциальная задержка: 5, 10, 20 секунд
                            print(f"  ⏳ Rate limited, ждем {wait_time} секунд... (попытка {attempt + 1}/{max_retries})")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            error_text = await resp.text()
                            raise Exception(f"HTTP {resp.status}: Rate limited after {max_retries} попыток")
                    else:
                        error_text = await resp.text()
                        raise Exception(f"HTTP {resp.status}: {error_text}")
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 2  # Экспоненциальная задержка для других ошибок
                print(f"  ⚠️  Ошибка: {e}, ждем {wait_time} секунд... (попытка {attempt + 1}/{max_retries})")
                await asyncio.sleep(wait_time)
                continue
            else:
                raise e
    
    raise Exception("Не удалось загрузить данные после всех попыток")

def save_cve_to_db(cve_list):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS cve (
            id TEXT PRIMARY KEY,
            description TEXT,
            cvss_v3 REAL,
            published_date TEXT,
            last_modified TEXT,
            vendor TEXT,
            product TEXT,
            epss REAL
        )
    """)
    
    # Создаем таблицу метаданных если её нет
    c.execute("""
        CREATE TABLE IF NOT EXISTS db_metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    for item in cve_list:
        cve_id = item['cve']['id']
        published = item['cve']['published']
        last_modified = item['cve']['lastModified']
        desc = item['cve']['descriptions'][0]['value'] if item['cve']['descriptions'] else ''
        
        # Extract CVSS v3 score
        cvss_v3 = None
        metrics = item['cve'].get('metrics', {})
        if 'cvssMetricV31' in metrics and metrics['cvssMetricV31']:
            cvss_v3 = float(metrics['cvssMetricV31'][0]['cvssData']['baseScore'])
        
        # Extract vendor and product from configurations
        vendor = ""
        product = ""
        if 'configurations' in item['cve'] and item['cve']['configurations']:
            for config in item['cve']['configurations']:
                if 'nodes' in config:
                    for node in config['nodes']:
                        if 'cpeMatch' in node:
                            for cpe in node['cpeMatch']:
                                if 'criteria' in cpe:
                                    cpe_parts = cpe['criteria'].split(':')
                                    if len(cpe_parts) >= 5:
                                        vendor = cpe_parts[3]
                                        product = cpe_parts[4]
                                        break
                            if vendor and product:
                                break
                    if vendor and product:
                        break
        
        c.execute("""
            INSERT OR REPLACE INTO cve (id, description, cvss_v3, published_date, last_modified, vendor, product, epss)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (cve_id, desc, cvss_v3, published, last_modified, vendor, product, None))
    
    # Обновляем время последнего обновления базы данных
    current_time = datetime.utcnow().isoformat() + 'Z'
    c.execute("""
        INSERT OR REPLACE INTO db_metadata (key, value) 
        VALUES ('last_db_update', ?)
    """, (current_time,))
    
    conn.commit()
    conn.close()

def get_last_update_time():
    """Получить время последнего обновления базы данных"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Сначала пытаемся получить время из метаданных
        cursor.execute("SELECT value FROM db_metadata WHERE key = 'last_db_update'")
        result = cursor.fetchone()
        
        if result and result[0]:
            conn.close()
            return result[0]
        
        # Fallback: используем MAX(last_modified) из CVE
        cursor.execute("SELECT MAX(last_modified) FROM cve")
        result = cursor.fetchone()
        conn.close()
        return result[0] if result and result[0] else None
    except:
        return None

def is_database_empty():
    """Проверить, пуста ли база данных"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cve")
        count = cursor.fetchone()[0]
        conn.close()
        return count == 0
    except:
        return True

async def load_all_cves():
    """Загрузить CVE с умной обработкой rate limiting"""
    print(f"[{datetime.utcnow().isoformat()}] Starting CVE database load...")
    
    try:
        # Получаем общее количество CVE
        initial_data = await fetch_cve(start_index=0, results_per_page=1)
        total_results = initial_data.get('totalResults', 0)
        print(f"Total CVEs available: {total_results}")
        
        if total_results == 0:
            print("No CVEs found in NVD")
            return False
        
        # Ограничиваем загрузку для избежания rate limiting
        # Загружаем только последние 50,000 CVE для начальной настройки
        max_cves = min(total_results, 50000)
        page_size = 1000  # Уменьшаем размер страницы
        total_pages = (max_cves + page_size - 1) // page_size
        
        # Начинаем с конца, чтобы получить самые новые CVE
        start_index = max(0, total_results - max_cves)
        
        print(f"Loading last {max_cves} CVEs (from index {start_index}) in {total_pages} pages...")
        print("💡 This is a subset to avoid rate limiting. The bot will update automatically.")
        
        all_vulnerabilities = []
        
        for page in range(total_pages):
            current_start_index = start_index + page * page_size
            current_page_size = min(page_size, max_cves - page * page_size)
            
            print(f"Loading page {page + 1}/{total_pages} (CVE {current_start_index + 1}-{current_start_index + current_page_size})")
            
            try:
                data = await fetch_cve(start_index=current_start_index, results_per_page=current_page_size)
                vulnerabilities = data.get('vulnerabilities', [])
                
                if vulnerabilities:
                    all_vulnerabilities.extend(vulnerabilities)
                    print(f"  ✅ Loaded {len(vulnerabilities)} CVEs from this page")
                else:
                    print(f"  ⚠️  No CVEs found on page {page + 1}")
                    break
                    
                # Увеличиваем паузу между запросами для избежания rate limiting
                if page < total_pages - 1:  # Не ждем после последней страницы
                    wait_time = 2.0  # 2 секунды между запросами
                    print(f"  ⏳ Waiting {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                
            except Exception as e:
                print(f"  ❌ Error loading page {page + 1}: {e}")
                # При ошибке ждем дольше перед следующей попыткой
                if page < total_pages - 1:
                    print(f"  ⏳ Waiting 10 seconds before next page...")
                    await asyncio.sleep(10)
                continue
        
        if all_vulnerabilities:
            print(f"\n💾 Saving {len(all_vulnerabilities)} CVEs to database...")
            save_cve_to_db(all_vulnerabilities)
            print(f"[{datetime.utcnow().isoformat()}] ✅ CVE database loaded successfully. Loaded {len(all_vulnerabilities)} CVEs.")
            print(f"💡 Note: This is a subset of all available CVEs to avoid rate limiting.")
            print(f"💡 The bot will automatically update with newer CVEs every hour.")
            return True
        else:
            print("❌ No vulnerabilities loaded")
            return False
            
    except Exception as e:
        print(f"❌ Error loading CVEs: {e}")
        return False

async def load_incremental_cves():
    """Загрузить только новые CVE (инкрементное обновление) с умной обработкой rate limiting"""
    print(f"[{datetime.utcnow().isoformat()}] Starting INCREMENTAL CVE update...")
    
    try:
        # Проверяем, пуста ли база данных
        if is_database_empty():
            print("❌ Database is empty! Please run 'python3 load_cve_data.py' first to load initial data.")
            return False
        
        # Простое обновление - загружаем последние 10,000 CVE
        # Это покроет все новые CVE за последние несколько дней
        print("🔄 Loading recent CVEs for update...")
        
        # Получаем общее количество CVE
        initial_data = await fetch_cve(start_index=0, results_per_page=1)
        total_results = initial_data.get('totalResults', 0)
        
        # Загружаем последние 10,000 CVE
        load_limit = min(10000, total_results)
        start_index = max(0, total_results - load_limit)
        
        print(f"Loading last {load_limit} CVEs (from index {start_index} to {total_results})")
        
        all_vulnerabilities = []
        page_size = 2000
        current_index = start_index
        
        while current_index < total_results:
            remaining = total_results - current_index
            current_page_size = min(page_size, remaining)
            
            try:
                data = await fetch_cve(start_index=current_index, results_per_page=current_page_size)
                vulnerabilities = data.get('vulnerabilities', [])
                
                if vulnerabilities:
                    all_vulnerabilities.extend(vulnerabilities)
                    print(f"  ✅ Loaded {len(vulnerabilities)} CVEs")
                else:
                    break
                    
                current_index += current_page_size
                await asyncio.sleep(0.6)
                
            except Exception as e:
                print(f"  ❌ Error: {e}")
                break
        
        if all_vulnerabilities:
            print(f"💾 Updating database with {len(all_vulnerabilities)} CVEs...")
            save_cve_to_db(all_vulnerabilities)  # INSERT OR REPLACE обновит существующие
            print(f"✅ Update completed. Processed {len(all_vulnerabilities)} CVEs.")
        else:
            print("✅ No new CVEs found")
        
        return True
        
    except Exception as e:
        print(f"❌ Error updating CVE database: {e}")
        return False


async def update_cve_db():
    """Простое инкрементное обновление CVE базы данных"""
    print(f"[{datetime.utcnow().isoformat()}] Checking for CVE updates...")
    
    try:
        # Проверяем, пуста ли база данных
        if is_database_empty():
            print("❌ Database is empty! Please run 'python3 load_cve_data.py' first to load initial data.")
            return False
        
        # Простое обновление - загружаем последние 10,000 CVE
        # Это покроет все новые CVE за последние несколько дней
        print("🔄 Loading recent CVEs for update...")
        
        # Получаем общее количество CVE
        initial_data = await fetch_cve(start_index=0, results_per_page=1)
        total_results = initial_data.get('totalResults', 0)
        
        # Загружаем последние 10,000 CVE
        load_limit = min(10000, total_results)
        start_index = max(0, total_results - load_limit)
        
        print(f"Loading last {load_limit} CVEs (from index {start_index} to {total_results})")
        
        all_vulnerabilities = []
        page_size = 2000
        current_index = start_index
        
        while current_index < total_results:
            remaining = total_results - current_index
            current_page_size = min(page_size, remaining)
            
            try:
                data = await fetch_cve(start_index=current_index, results_per_page=current_page_size)
                vulnerabilities = data.get('vulnerabilities', [])
                
                if vulnerabilities:
                    all_vulnerabilities.extend(vulnerabilities)
                    print(f"  ✅ Loaded {len(vulnerabilities)} CVEs")
                else:
                    break
                    
                current_index += current_page_size
                await asyncio.sleep(0.6)
                
            except Exception as e:
                print(f"  ❌ Error: {e}")
                break
        
        if all_vulnerabilities:
            print(f"💾 Updating database with {len(all_vulnerabilities)} CVEs...")
            save_cve_to_db(all_vulnerabilities)  # INSERT OR REPLACE обновит существующие
            print(f"✅ Update completed. Processed {len(all_vulnerabilities)} CVEs.")
        else:
            print("✅ No new CVEs found")
        
        return True
        
    except Exception as e:
        print(f"❌ Error updating CVE database: {e}")
        return False


async def fetch_epss_data():
    """Загружает ВСЕ доступные данные EPSS из FIRST.org API"""
    try:
        print(f"[{datetime.utcnow().isoformat()}] Загружаем ВСЕ доступные данные EPSS...")
        
        all_epss_data = []
        
        # Загружаем данные по годам, начиная с 2021 года
        years = ['2021', '2022', '2023', '2024', '2025']
        
        async with aiohttp.ClientSession() as session:
            for year in years:
                print(f"📊 Загружаем EPSS данные за {year} год...")
                
                # Параметры для загрузки данных за конкретный год
                params = {
                    'date': f'{year}-01-01',
                    'limit': '100000'
                }
                
                try:
                    async with session.get(EPSS_API_URL, params=params) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            epss_data = data.get('data', [])
                            
                            if epss_data:
                                all_epss_data.extend(epss_data)
                                print(f"  ✅ Загружено {len(epss_data)} записей EPSS за {year} год")
                                
                                # Небольшая пауза между запросами
                                await asyncio.sleep(1)
                            else:
                                print(f"  ⚠️  Нет EPSS данных за {year} год")
                        else:
                            print(f"  ❌ HTTP {resp.status} для {year} года")
                            
                except Exception as e:
                    print(f"  ❌ Ошибка загрузки EPSS данных за {year} год: {e}")
                    continue
        
        print(f"📊 Всего загружено {len(all_epss_data)} записей EPSS")
        return all_epss_data
        
    except Exception as e:
        print(f"❌ Ошибка загрузки EPSS данных: {e}")
        return []

def save_epss_to_db(epss_data):
    """Сохраняет данные EPSS в базу данных"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Обновляем EPSS данные для существующих CVE
        updated_count = 0
        for item in epss_data:
            cve_id = item.get('cve')
            epss_score = item.get('epss')
            
            if cve_id and epss_score is not None:
                c.execute("""
                    UPDATE cve 
                    SET epss = ? 
                    WHERE id = ?
                """, (float(epss_score), cve_id))
                
                if c.rowcount > 0:
                    updated_count += 1
        
        conn.commit()
        conn.close()
        
        print(f"✅ Обновлено {updated_count} CVE с EPSS данными")
        return updated_count
        
    except Exception as e:
        print(f"❌ Ошибка сохранения EPSS данных: {e}")
        return 0

async def load_epss_data():
    """Загружает и сохраняет данные EPSS"""
    try:
        print(f"[{datetime.utcnow().isoformat()}] Начинаем загрузку EPSS данных...")
        
        # Загружаем данные EPSS
        epss_data = await fetch_epss_data()
        
        if not epss_data:
            print("❌ Не удалось загрузить данные EPSS")
            return False
        
        print(f"📊 Загружено {len(epss_data)} записей EPSS")
        
        # Сохраняем в базу данных
        updated_count = save_epss_to_db(epss_data)
        
        if updated_count > 0:
            print(f"✅ EPSS данные успешно загружены и обновлены для {updated_count} CVE")
            
            # Обновляем время последнего обновления EPSS
            update_epss_metadata()
            return True
        else:
            print("⚠️  EPSS данные загружены, но не найдено соответствующих CVE в базе")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка загрузки EPSS данных: {e}")
        return False

def update_epss_metadata():
    """Обновляет метаданные о последнем обновлении EPSS"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Создаем таблицу метаданных если её нет
        c.execute("""
            CREATE TABLE IF NOT EXISTS db_metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        # Обновляем время последнего обновления EPSS
        current_time = datetime.utcnow().isoformat() + 'Z'
        c.execute("""
            INSERT OR REPLACE INTO db_metadata (key, value) 
            VALUES ('last_epss_update', ?)
        """, (current_time,))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка обновления метаданных EPSS: {e}")

def get_last_epss_update():
    """Получает время последнего обновления EPSS"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT value FROM db_metadata WHERE key = 'last_epss_update'")
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result and result[0] else None
    except:
        return None

async def should_update_epss():
    """Проверяет, нужно ли обновлять EPSS данные"""
    try:
        last_update = get_last_epss_update()
        
        if not last_update:
            print("📊 EPSS данные никогда не обновлялись")
            return True
        
        # Проверяем, прошло ли больше часа с последнего обновления
        from datetime import datetime as dt, timezone
        last_update_dt = dt.fromisoformat(last_update.replace('Z', '+00:00'))
        now = dt.now(timezone.utc)
        
        time_diff = (now - last_update_dt).total_seconds()
        hours_passed = time_diff / 3600
        
        print(f"📊 Последнее обновление EPSS: {hours_passed:.1f} часов назад")
        
        return hours_passed >= 1  # Обновляем каждый час
        
    except Exception as e:
        print(f"❌ Ошибка проверки времени обновления EPSS: {e}")
        return True  # В случае ошибки обновляем

async def update_all_periodically(interval_seconds: int = 3600):
    """Автообновление CVE и EPSS каждые interval_seconds секунд"""
    while True:
        # Обновляем CVE данные
        await update_cve_db()
        
        # Проверяем и обновляем EPSS данные
        if await should_update_epss():
            print("🔄 Обновляем EPSS данные...")
            await load_epss_data()
        else:
            print("⏭️  Пропускаем обновление EPSS (еще не прошло часа)")
        
        await asyncio.sleep(interval_seconds)
