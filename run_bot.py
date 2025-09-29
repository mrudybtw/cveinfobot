#!/usr/bin/env python3
"""
Run script for CVE Info Bot
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def check_environment():
    """Check if environment is properly set up"""
    print("🔍 Checking environment...")
    
    # Check .env file
    if not Path(".env").exists():
        print("❌ .env file not found. Please create it with your TELEGRAM_TOKEN")
        return False
    
    # Check database
    if not Path("db/cve.db").exists():
        print("❌ Database not found. Please run: python db/init_db.py")
        return False
    
    # Check Ollama
    try:
        import subprocess
        result = subprocess.run(['ollama', '--version'], capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ Ollama not found. Please install it from https://ollama.ai/")
            return False
    except FileNotFoundError:
        print("❌ Ollama not found. Please install it from https://ollama.ai/")
        return False
    
    print("✅ Environment check passed")
    return True

def main():
    """Main run function"""
    print("🚀 Starting CVE Info Bot...")
    
    if not check_environment():
        print("\n❌ Environment check failed. Please fix the issues above.")
        sys.exit(1)
    
    try:
        # Import and run the bot
        from bot.main import main as bot_main
        asyncio.run(bot_main())
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Bot crashed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
