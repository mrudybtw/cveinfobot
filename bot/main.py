import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineQuery
from dotenv import load_dotenv
from bot.services.collector import update_all_periodically
from bot.services.bot_service import BotService
from bot.handlers.command_handler import CommandHandler
from bot.handlers.channel_handler import ChannelHandler
from bot.handlers.inline_handler import InlineHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()
API_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not API_TOKEN:
    logger.error("TELEGRAM_TOKEN not found in environment variables")
    exit(1)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Initialize services
bot_service = BotService()
command_handler = CommandHandler(bot_service)
channel_handler = ChannelHandler(bot_service)
inline_handler = InlineHandler(bot_service)

# Register command handlers
@dp.message(Command("start"))
async def handle_start_command(message: types.Message):
    await command_handler.handle_start_command(message)

@dp.message(Command("cve"))
async def handle_cve_command(message: types.Message):
    await command_handler.handle_cve_command(message)

@dp.message(Command("vendor"))
async def handle_vendor_command(message: types.Message):
    await command_handler.handle_vendor_command(message)

@dp.message(Command("top"))
async def handle_top_command(message: types.Message):
    await command_handler.handle_top_command(message)

@dp.message(Command("help"))
async def handle_help_command(message: types.Message):
    await command_handler.handle_help_command(message)

# Register channel post handler
@dp.channel_post()
async def handle_channel_post(message: types.Message):
    await channel_handler.handle_channel_post(message)

# Register inline query handler
@dp.inline_query()
async def handle_inline_query(query: InlineQuery):
    await inline_handler.handle_inline_query(query)

# Register message handler for non-command messages
@dp.message()
async def handle_message(message: types.Message):
    """Handle regular messages (not commands)"""
    try:
        # Check if message contains CVE patterns
        cve_patterns = bot_service.find_cve_patterns(message.text or "")
        
        if cve_patterns:
            # Process each CVE found
            for cve_id in cve_patterns:
                cve_data = bot_service.get_cve_info(cve_id)
                
                if cve_data:
                    # Send initial CVE information + loading indicator
                    initial_message = bot_service.format_cve_message(cve_data, include_ai=False)
                    loading_message = bot_service.format_cve_message(cve_data, include_ai=True, loading_animation="🔄 <i>Анализирую уязвимость...</i>")
                    sent_message = await message.answer(loading_message, parse_mode="HTML")
                    
                    # Generate AI explanation and edit the message
                    try:
                        ai_explanation = await bot_service.generate_ai_explanation(cve_data)
                        
                        # Create updated message with AI analysis
                        updated_message = f"{initial_message}\n\n🤖 <b>AI-анализ:</b>\n\n{ai_explanation}"
                        
                        # Edit the original message
                        await sent_message.edit_text(updated_message, parse_mode="HTML")
                        
                    except Exception as e:
                        logger.error(f"Error generating AI explanation for {cve_id}: {e}")
                        # Edit message to show AI error
                        error_message = f"{initial_message}\n\n🤖 <b>AI-анализ:</b>\n<i>Временно недоступен</i>"
                        await sent_message.edit_text(error_message, parse_mode="HTML")
                else:
                    await message.answer(f"❌ CVE {cve_id} не найден в базе данных.")
        else:
            # If no CVE patterns found, send help message
            await message.answer(
                "🤖 Привет! Я CVE Info Bot.\n\n"
                "Используйте команды:\n"
                "• /start - Начать работу\n"
                "• /help - Справка\n"
                "• /cve CVE-YYYY-NNNNN - Информация о CVE\n"
                "• /vendor <название> - Поиск по вендору\n"
                "• /top - Топ критических CVE\n\n"
                "Или просто напишите CVE ID в сообщении!",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        await message.answer("❌ Ошибка при обработке сообщения.")

async def main():
    try:
        # Initialize database
        from db.init_db import init_db
        init_db()
        logger.info("Database initialized")
        
        # Start CVE collector
        asyncio.create_task(update_all_periodically(interval_seconds=3600))
        logger.info("CVE collector started")
        
        # Start bot
        logger.info("CVE Bot starting...")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
