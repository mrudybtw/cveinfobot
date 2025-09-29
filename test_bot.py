#!/usr/bin/env python3
"""
Test script for CVE Info Bot
"""

import asyncio
import sqlite3
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_database():
    """Test database initialization and basic operations"""
    print("🧪 Testing database...")
    
    try:
        from db.init_db import init_db
        init_db()
        
        # Test database connection
        conn = sqlite3.connect("db/cve.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        conn.close()
        
        print(f"✅ Database initialized. Tables: {[t[0] for t in tables]}")
        return True
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_bot_service():
    """Test bot service functionality"""
    print("🧪 Testing bot service...")
    
    try:
        from bot.services.bot_service import BotService
        service = BotService()
        
        # Test CVE pattern detection
        test_text = "Check out CVE-2023-1234 and CVE-2024-5678"
        patterns = service.find_cve_patterns(test_text)
        print(f"✅ CVE pattern detection: {patterns}")
        
        # Test database query
        cve_info = service.get_cve_info("CVE-2023-1234")
        print(f"✅ CVE lookup: {cve_info is not None}")
        
        return True
    except Exception as e:
        print(f"❌ Bot service test failed: {e}")
        return False

async def test_ollama_service():
    """Test Ollama service"""
    print("🧪 Testing Ollama service...")
    
    try:
        from bot.services.ollama_service import OllamaService
        service = OllamaService()
        
        # Test with mock data
        test_cve = {
            'id': 'CVE-2023-1234',
            'description': 'Test vulnerability description',
            'cvss_v3': 7.5,
            'vendor': 'test-vendor',
            'product': 'test-product'
        }
        
        explanation = await service.generate_cve_explanation(test_cve)
        print(f"✅ Ollama service: {len(explanation)} characters generated")
        return True
    except Exception as e:
        print(f"❌ Ollama service test failed: {e}")
        print("   Make sure Ollama is running: ollama serve")
        return False

async def test_collector():
    """Test CVE collector"""
    print("🧪 Testing CVE collector...")
    
    try:
        from bot.services.collector import update_cve_db
        await update_cve_db()
        
        # Check if data was inserted
        conn = sqlite3.connect("db/cve.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cve")
        count = cursor.fetchone()[0]
        conn.close()
        
        print(f"✅ CVE collector: {count} CVEs in database")
        return True
    except Exception as e:
        print(f"❌ CVE collector test failed: {e}")
        return False

def test_imports():
    """Test all imports"""
    print("🧪 Testing imports...")
    
    try:
        from bot.main import bot, dp
        from bot.handlers.command_handler import CommandHandler
        from bot.handlers.channel_handler import ChannelHandler
        from bot.handlers.inline_handler import InlineHandler
        from bot.services.bot_service import BotService
        from bot.services.ollama_service import OllamaService
        from bot.services.collector import update_cve_db
        from config import Config
        
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("🚀 Running CVE Info Bot tests...\n")
    
    tests = [
        ("Imports", test_imports),
        ("Database", test_database),
        ("Bot Service", test_bot_service),
        ("CVE Collector", test_collector),
        ("Ollama Service", test_ollama_service),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
        print()
    
    # Summary
    print("📊 Test Results:")
    print("=" * 50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<20} {status}")
        if result:
            passed += 1
    
    print("=" * 50)
    print(f"Total: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n🎉 All tests passed! Bot is ready to run.")
        print("\nNext steps:")
        print("1. Set up your .env file with TELEGRAM_TOKEN")
        print("2. Start Ollama: ollama serve")
        print("3. Run the bot: python -m bot.main")
    else:
        print("\n⚠️  Some tests failed. Please check the errors above.")
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(main())
