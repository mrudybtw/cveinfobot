# CVE Info Bot

Telegram bot for automatic CVE vulnerability analysis and reporting with AI-powered explanations.

## 🚀 Features

### MVP (Phase 1)
- **Automatic CVE Detection**: Monitors channel posts for CVE patterns (`CVE-XXXX-YYYYY`)
- **Local Database**: SQLite storage with NVD data synchronization
- **AI Explanations**: Ollama-powered vulnerability analysis and recommendations
- **Auto-commenting**: Automatic replies to channel posts containing CVEs

### Phase 2 (Extended)
- **Inline Search**: Use `@cveinfobot` for inline CVE search
- **Vendor Search**: Search CVEs by vendor/product name
- **Multiple Channels**: Support for multiple Telegram channels
- **Command Interface**: Direct bot commands for CVE lookup

## 🛠️ Installation

### Prerequisites
- Python 3.8+
- Ollama (for AI explanations)
- Telegram Bot Token

### Quick Setup
```bash
# Clone the repository
git clone <repository-url>
cd cveinfobot-main

# Run setup script
python3 setup.py

# Update .env file with your Telegram token
# Load CVE data (IMPORTANT!)
python3 load_cve_data.py

# Start Ollama
ollama serve

# Run the bot
python3 -m bot.main
```

### Manual Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Install Ollama (macOS)
brew install ollama

# Pull AI model
ollama pull llama3.1:8b

# Initialize database
python3 db/init_db.py

# Load CVE data (REQUIRED!)
python3 load_cve_data.py

# Configure environment
# Edit .env with your Telegram token

# Start the bot
python3 -m bot.main
```

## 📋 Configuration

Create a `.env` file with the following variables:

```env
# Required
TELEGRAM_TOKEN=your_telegram_bot_token_here

# Optional (defaults shown)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
DB_PATH=db/cve.db
NVD_UPDATE_INTERVAL=3600
LOG_LEVEL=INFO
```

## 🤖 Usage

### Channel Monitoring
The bot automatically monitors channel posts and responds to CVE mentions:

```
User posts: "Check out this vulnerability CVE-2023-1234"
Bot replies: [CVE information + AI analysis]
```

### Commands
- `/cve CVE-YYYY-NNNNN` - Get detailed CVE information
- `/vendor <name>` - Search CVEs by vendor/product
- `/top` - Show top 5 critical CVEs
- `/help` - Show help information

### Inline Search
Type `@cveinfobot` in any chat to search for CVEs:
- Search by CVE ID: `@cveinfobot CVE-2023-1234`
- Search by vendor: `@cveinfobot microsoft`
- Browse recent critical CVEs

## 🏗️ Architecture

```
bot/
├── main.py              # Main bot entry point
├── handlers/            # Message handlers
│   ├── channel_handler.py   # Channel post monitoring
│   ├── command_handler.py   # Bot commands
│   └── inline_handler.py    # Inline search
└── services/            # Core services
    ├── bot_service.py       # Main bot logic
    ├── collector.py         # NVD data collection
    └── ollama_service.py    # AI integration

db/
├── cve.db              # SQLite database
└── init_db.py          # Database initialization
```

## 🔄 Data Flow

1. **NVD Collector**: Fetches CVE data from NVD API every hour
2. **Database Storage**: Stores CVE information in SQLite
3. **Channel Monitoring**: Bot watches for CVE patterns in posts
4. **AI Analysis**: Ollama generates explanations and recommendations
5. **Response**: Bot replies with formatted CVE information

## 🧪 Testing

```bash
# Test database initialization
python db/init_db.py

# Test CVE collection
python -c "from bot.services.collector import update_cve_db; import asyncio; asyncio.run(update_cve_db())"

# Test Ollama connection
python -c "from bot.services.ollama_service import OllamaService; import asyncio; print(asyncio.run(OllamaService().generate_cve_explanation({'id': 'CVE-2023-1234', 'description': 'Test'})))"
```

## 🚀 Deployment

### Local Development
```bash
# Terminal 1: Start Ollama
ollama serve

# Terminal 2: Start bot
python -m bot.main
```

### Production (Phase 2)
- Docker containerization
- PostgreSQL database
- Multiple bot instances
- Channel management system

## 📊 Database Schema

```sql
CREATE TABLE cve (
    id TEXT PRIMARY KEY,
    description TEXT,
    cvss_v3 REAL,
    published_date TEXT,
    last_modified TEXT,
    vendor TEXT,
    product TEXT,
    epss REAL
);
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License.

## 🆘 Support

For issues and questions:
1. Check the logs for error messages
2. Verify Ollama is running: `ollama list`
3. Test database: `python -c "import sqlite3; print(sqlite3.connect('db/cve.db').execute('SELECT COUNT(*) FROM cve').fetchone())"`
4. Check Telegram bot token validity

## 🔮 Roadmap

- [ ] Docker support
- [ ] PostgreSQL migration
- [ ] Web dashboard
- [ ] CVE notifications
- [ ] Multi-language support
- [ ] API endpoints
- [ ] Metrics and analytics