#!/usr/bin/env python3
"""
Setup script for CVE Info Bot
"""

import os
import sys
import subprocess
import sqlite3
from pathlib import Path

def check_ollama():
    """Check if Ollama is installed and running"""
    try:
        result = subprocess.run(['ollama', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Ollama is installed")
            return True
        else:
            print("❌ Ollama is not installed or not working")
            return False
    except FileNotFoundError:
        print("❌ Ollama is not installed")
        return False

def setup_ollama_model():
    """Setup Ollama model"""
    try:
        print("🔄 Pulling Ollama model...")
        result = subprocess.run(['ollama', 'pull', 'llama3.1:8b'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Ollama model pulled successfully")
            return True
        else:
            print(f"❌ Failed to pull model: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error setting up Ollama model: {e}")
        return False

def create_env_file():
    """Create .env file from template"""
    env_file = Path(".env")
    if not env_file.exists():
        print("📝 Creating .env file...")
        env_content = """# Telegram Bot Configuration
TELEGRAM_TOKEN=your_telegram_bot_token_here

# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

# Database Configuration
DB_PATH=db/cve.db

# NVD API Configuration
NVD_API_URL=https://services.nvd.nist.gov/rest/json/cves/2.0
NVD_UPDATE_INTERVAL=3600

# Logging Configuration
LOG_LEVEL=INFO
"""
        with open(env_file, 'w') as f:
            f.write(env_content)
        print("✅ .env file created. Please update TELEGRAM_TOKEN")
    else:
        print("✅ .env file already exists")

def init_database():
    """Initialize database"""
    try:
        print("🔄 Initializing database...")
        from db.init_db import init_db
        init_db()
        print("✅ Database initialized")
        return True
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        return False

def install_dependencies():
    """Install Python dependencies"""
    try:
        print("🔄 Installing dependencies...")
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Dependencies installed")
            return True
        else:
            print(f"❌ Failed to install dependencies: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error installing dependencies: {e}")
        return False

def main():
    """Main setup function"""
    print("🚀 Setting up CVE Info Bot...")
    
    # Check if we're in the right directory
    if not Path("bot").exists() or not Path("db").exists():
        print("❌ Please run this script from the project root directory")
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        print("❌ Setup failed at dependency installation")
        sys.exit(1)
    
    # Create .env file
    create_env_file()
    
    # Initialize database
    if not init_database():
        print("❌ Setup failed at database initialization")
        sys.exit(1)
    
    # Check Ollama
    if not check_ollama():
        print("⚠️  Ollama is not installed. Please install it from https://ollama.ai/")
        print("   After installation, run: ollama pull llama3.1:8b")
    else:
        # Setup Ollama model
        setup_ollama_model()
    
    print("\n✅ Setup completed!")
    print("\n📋 Next steps:")
    print("1. Update .env file with your Telegram bot token")
    print("2. Load CVE data: python3 load_cve_data.py")
    print("3. Start Ollama: ollama serve")
    print("4. Run the bot: python3 -m bot.main")
    print("\n🔧 Commands:")
    print("• /cve CVE-YYYY-NNNNN - Get CVE information")
    print("• /vendor <name> - Search by vendor/product")
    print("• /top - Show top critical CVEs")
    print("• /help - Show help")
    print("\n⚠️  IMPORTANT: Run 'python3 load_cve_data.py' to load CVE data first!")

if __name__ == "__main__":
    main()
