#!/usr/bin/env python3
"""
CVE Data Loader - Simple script to load CVE data
"""

import asyncio
import sqlite3
import aiohttp
import os
from datetime import datetime

DB_PATH = "db/cve.db"
NVD_API_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"

async def fetch_cve_page(start_index=0, results_per_page=2000):
    """Fetch one page of CVE data"""
    params = {
        "startIndex": start_index,
        "resultsPerPage": results_per_page
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(NVD_API_URL, params=params) as resp:
            if resp.status != 200:
                raise Exception(f"HTTP {resp.status}: {await resp.text()}")
            return await resp.json()

def save_cve_batch(cve_list):
    """Save a batch of CVEs to database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Ensure table exists
    cursor.execute("""
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
        
        # Extract vendor and product
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
        
        cursor.execute("""
            INSERT OR REPLACE INTO cve (id, description, cvss_v3, published_date, last_modified, vendor, product, epss)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (cve_id, desc, cvss_v3, published, last_modified, vendor, product, None))
    
    conn.commit()
    conn.close()

async def load_all_cves():
    """Load all CVEs from NVD"""
    print("🚀 Starting CVE data load...")
    
    try:
        # Get total count
        print("📊 Getting total CVE count...")
        initial_data = await fetch_cve_page(start_index=0, results_per_page=1)
        total_results = initial_data.get('totalResults', 0)
        print(f"Total CVEs available: {total_results:,}")
        
        if total_results == 0:
            print("❌ No CVEs found")
            return False
        
        # Calculate pages
        page_size = 2000
        total_pages = (total_results + page_size - 1) // page_size
        print(f"Will load {total_pages} pages of {page_size} CVEs each")
        
        # Load all pages
        loaded_count = 0
        for page in range(total_pages):
            start_index = page * page_size
            current_page_size = min(page_size, total_results - start_index)
            
            print(f"📥 Loading page {page + 1}/{total_pages} (CVE {start_index + 1}-{start_index + current_page_size})")
            
            try:
                data = await fetch_cve_page(start_index=start_index, results_per_page=current_page_size)
                vulnerabilities = data.get('vulnerabilities', [])
                
                if vulnerabilities:
                    save_cve_batch(vulnerabilities)
                    loaded_count += len(vulnerabilities)
                    print(f"  ✅ Saved {len(vulnerabilities)} CVEs (Total: {loaded_count:,})")
                else:
                    print(f"  ⚠️  No CVEs in this page")
                    break
                
                # Rate limiting
                await asyncio.sleep(0.6)
                
            except Exception as e:
                print(f"  ❌ Error loading page {page + 1}: {e}")
                continue
        
        print(f"\n🎉 CVE data load completed!")
        print(f"📊 Total CVEs loaded: {loaded_count:,}")
        
        # Show statistics
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM cve")
        total_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM cve WHERE cvss_v3 >= 9.0")
        critical_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM cve WHERE id LIKE 'CVE-2025%'")
        cve_2025_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT id FROM cve WHERE id = 'CVE-2025-32463'")
        target_cve = cursor.fetchone()
        
        conn.close()
        
        print(f"\n📈 Database statistics:")
        print(f"  Total CVEs: {total_count:,}")
        print(f"  Critical CVEs (CVSS >= 9.0): {critical_count:,}")
        print(f"  CVE 2025: {cve_2025_count:,}")
        print(f"  Target CVE-2025-32463: {'✅ Found' if target_cve else '❌ Not found'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error loading CVE data: {e}")
        return False

def main():
    """Main function"""
    print("🔧 CVE Data Loader")
    print("=" * 50)
    
    # Check if database exists
    if os.path.exists(DB_PATH):
        response = input(f"Database {DB_PATH} already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("❌ Cancelled")
            return
    
    # Load CVE data
    success = asyncio.run(load_all_cves())
    
    if success:
        print("\n✅ CVE data loaded successfully!")
        print("You can now run the bot with: python3 -m bot.main")
    else:
        print("\n❌ Failed to load CVE data")

if __name__ == "__main__":
    main()
