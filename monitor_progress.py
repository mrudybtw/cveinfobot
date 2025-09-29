#!/usr/bin/env python3
"""
Monitor CVE loading progress
"""

import sqlite3
import time
import os

def check_progress():
    """Check loading progress"""
    try:
        conn = sqlite3.connect("db/cve.db")
        cursor = conn.cursor()
        
        # Get total count
        cursor.execute("SELECT COUNT(*) FROM cve")
        count = cursor.fetchone()[0]
        
        # Get latest CVE
        cursor.execute("SELECT id, last_modified FROM cve ORDER BY last_modified DESC LIMIT 1")
        latest = cursor.fetchone()
        
        # Get CVE 2025 count
        cursor.execute("SELECT COUNT(*) FROM cve WHERE id LIKE 'CVE-2025%'")
        cve_2025_count = cursor.fetchone()[0]
        
        # Check for target CVE
        cursor.execute("SELECT id FROM cve WHERE id = 'CVE-2025-32463'")
        target_cve = cursor.fetchone()
        
        conn.close()
        
        print(f"📊 Progress: {count:,} CVEs loaded")
        if latest:
            print(f"📅 Latest CVE: {latest[0]} ({latest[1]})")
        print(f"🎯 CVE 2025: {cve_2025_count:,}")
        print(f"🎯 Target CVE-2025-32463: {'✅ Found' if target_cve else '❌ Not found'}")
        
        return count
        
    except Exception as e:
        print(f"❌ Error checking progress: {e}")
        return 0

if __name__ == "__main__":
    print("🔍 Monitoring CVE loading progress...")
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            count = check_progress()
            print("-" * 50)
            time.sleep(30)  # Check every 30 seconds
    except KeyboardInterrupt:
        print("\n👋 Monitoring stopped")
