import asyncio
import aiohttp
import sqlite3
import os
from datetime import datetime
from config import Config

DB_PATH = Config.DB_PATH
NVD_API_URL = Config.NVD_API_URL
NVD_API_KEY = Config.get_nvd_api_key()  # Опциональный API ключ для NVD

# Проверяем, что API ключ не является заглушкой
if NVD_API_KEY and NVD_API_KEY.startswith('your_'):
    NVD_API_KEY = ""  # Убираем недействительный ключ

async def fetch_cve(start_index=0, results_per_page=2000):
    params = {
        "startIndex": start_index,
        "resultsPerPage": results_per_page
    }
    
    headers = {}
    if NVD_API_KEY:
        headers["apiKey"] = NVD_API_KEY
    
    async with aiohttp.ClientSession() as session:
        async with session.get(NVD_API_URL, params=params, headers=headers) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise Exception(f"HTTP {resp.status}: {error_text}")
            data = await resp.json()
            return data

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
    """Загрузить ВСЕ CVE (первая загрузка)"""
    print(f"[{datetime.utcnow().isoformat()}] Starting FULL CVE database load...")
    
    try:
        # Получаем общее количество CVE
        initial_data = await fetch_cve(start_index=0, results_per_page=1)
        total_results = initial_data.get('totalResults', 0)
        print(f"Total CVEs available: {total_results}")
        
        if total_results == 0:
            print("No CVEs found in NVD")
            return False
        
        # Загружаем ВСЕ CVE постранично
        all_vulnerabilities = []
        page_size = 2000
        total_pages = (total_results + page_size - 1) // page_size
        
        print(f"Loading ALL {total_pages} pages of CVEs...")
        
        for page in range(total_pages):
            start_index = page * page_size
            current_page_size = min(page_size, total_results - start_index)
            
            print(f"Loading page {page + 1}/{total_pages} (CVE {start_index + 1}-{start_index + current_page_size})")
            
            try:
                data = await fetch_cve(start_index=start_index, results_per_page=current_page_size)
                vulnerabilities = data.get('vulnerabilities', [])
                
                if vulnerabilities:
                    all_vulnerabilities.extend(vulnerabilities)
                    print(f"  ✅ Loaded {len(vulnerabilities)} CVEs from this page")
                else:
                    print(f"  ⚠️  No CVEs found on page {page + 1}")
                    break
                    
                # Пауза между запросами
                await asyncio.sleep(0.6)
                
            except Exception as e:
                print(f"  ❌ Error loading page {page + 1}: {e}")
                continue
        
        if all_vulnerabilities:
            print(f"\n💾 Saving {len(all_vulnerabilities)} CVEs to database...")
            save_cve_to_db(all_vulnerabilities)
            print(f"[{datetime.utcnow().isoformat()}] ✅ FULL CVE database loaded successfully. Loaded {len(all_vulnerabilities)} CVEs.")
            return True
        else:
            print("❌ No vulnerabilities loaded")
            return False
            
    except Exception as e:
        print(f"❌ Error loading all CVEs: {e}")
        return False

async def load_incremental_cves():
    """Загрузить только новые CVE (инкрементное обновление)"""
    print(f"[{datetime.utcnow().isoformat()}] Starting INCREMENTAL CVE update...")
    
    try:
        last_update = get_last_update_time()
        if not last_update:
            print("No previous update time found, doing full load...")
            return await load_all_cves()
        
        print(f"Last update time: {last_update}")
        
        # NVD API 2.0 не поддерживает фильтрацию по дате изменения
        # Поэтому загружаем последние CVE и проверяем их в базе
        
        print("Loading recent CVEs for update...")
        
        # Загружаем последние CVE (последние 1000)
        all_vulnerabilities = []
        page_size = 1000
        start_index = 0
        
        try:
            data = await fetch_cve(start_index=start_index, results_per_page=page_size)
            vulnerabilities = data.get('vulnerabilities', [])
            
            if vulnerabilities:
                all_vulnerabilities.extend(vulnerabilities)
                print(f"  ✅ Loaded {len(vulnerabilities)} recent CVEs")
            else:
                print("  ⚠️  No recent CVEs found")
                
        except Exception as e:
            print(f"  ❌ Error loading recent CVEs: {e}")
            return False
        
        if all_vulnerabilities:
            print(f"\n💾 Saving {len(all_vulnerabilities)} new/updated CVEs to database...")
            save_cve_to_db(all_vulnerabilities)  # INSERT OR REPLACE обновит существующие
            print(f"[{datetime.utcnow().isoformat()}] ✅ INCREMENTAL update completed. Updated {len(all_vulnerabilities)} CVEs.")
            return True
        else:
            print("✅ No new CVEs found")
            return True
            
    except Exception as e:
        print(f"❌ Error in incremental update: {e}")
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

async def update_all_periodically(interval_seconds: int = 3600):
    """Автообновление CVE каждые interval_seconds секунд"""
    while True:
        await update_cve_db()
        await asyncio.sleep(interval_seconds)
