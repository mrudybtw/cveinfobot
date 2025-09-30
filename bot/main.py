import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineQuery, CallbackQuery
from bot.services.bot_service import BotService
from bot.handlers.command_handler import CommandHandler
from bot.handlers.channel_handler import ChannelHandler
from bot.handlers.inline_handler import InlineHandler
from bot.utils.logging_config import get_logger
from config import Config

# Получаем логгер
logger = get_logger(__name__)

# Валидируем конфигурацию
Config.validate()
API_TOKEN = Config.get_telegram_token()

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

@dp.message(Command("stats"))
async def handle_stats_command(message: types.Message):
    await command_handler.handle_stats_command(message)

@dp.message(Command("update"))
async def handle_update_command(message: types.Message):
    await command_handler.handle_update_command(message)

# Register channel post handler
@dp.channel_post()
async def handle_channel_post(message: types.Message):
    await channel_handler.handle_channel_post(message)

# Register channel message handler (for messages in channels)
@dp.message(lambda message: message.chat.type == 'channel')
async def handle_channel_message(message: types.Message):
    await channel_handler.handle_channel_post(message)

# Register inline query handler
@dp.inline_query()
async def handle_inline_query(query: InlineQuery):
    await inline_handler.handle_inline_query(query)

# Register callback query handler
@dp.callback_query()
async def handle_callback_query(callback: CallbackQuery):
    """Handle callback queries from inline keyboards"""
    try:
        if callback.data.startswith("cve_detail_"):
            cve_id = callback.data.replace("cve_detail_", "")
            
            # Get CVE data
            cve_data = bot_service.get_cve_info(cve_id)
            
            if cve_data:
                # Send detailed CVE information
                initial_message = bot_service.format_cve_message(cve_data, include_ai=False)
                loading_message = bot_service.format_cve_message(cve_data, include_ai=True, loading_animation="🔄 <i>Анализирую уязвимость...</i>")
                
                # Answer callback query
                await callback.answer()
                
                # Send detailed message
                sent_message = await callback.message.answer(loading_message, parse_mode="HTML", disable_web_page_preview=True)
                
                # Generate AI explanation and edit the message
                try:
                    ai_explanation = await bot_service.generate_ai_explanation(cve_data)
                    
                    # Create updated message with AI analysis
                    updated_message = f"{initial_message}\n\n🤖 <b>AI-анализ:</b>\n\n{ai_explanation}"
                    
                    # Edit the original message
                    await sent_message.edit_text(updated_message, parse_mode="HTML", disable_web_page_preview=True)
                    
                except Exception as e:
                    logger.error(f"Error generating AI explanation for {cve_id}: {e}")
                    # Edit message to show AI error
                    error_message = f"{initial_message}\n\n🤖 <b>AI-анализ:</b>\n<i>Временно недоступен</i>"
                    await sent_message.edit_text(error_message, parse_mode="HTML", disable_web_page_preview=True)
            else:
                await callback.answer("❌ CVE не найден в базе данных.", show_alert=True)
        elif callback.data == "top_more":
            # Show additional 5 CVEs with buttons
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            results = bot_service.get_top_critical_cves(limit=10)
            
            if len(results) > 5:
                response = "🔴 <b>Дополнительные критические CVE (6-10):</b>\n\n"
                
                # Создаем кнопки для дополнительных CVE
                keyboard_buttons = []
                
                for i, cve in enumerate(results[5:10], 6):
                    cvss = cve.get('cvss_v3', 'N/A')
                    epss = cve.get('epss')
                    
                    if cvss and cvss >= 9.0:
                        severity_emoji = "🔴"
                    elif cvss and cvss >= 7.0:
                        severity_emoji = "🟠"
                    else:
                        severity_emoji = "🟡"
                    
                    epss_text = ""
                    if epss is not None:
                        if epss > 0.8:
                            epss_emoji = "⚠️"
                        elif epss > 0.5:
                            epss_emoji = "🚨"
                        elif epss > 0.2:
                            epss_emoji = "🟡"
                        else:
                            epss_emoji = "🟢"
                        epss_text = f" {epss_emoji}"
                    
                    description = cve.get('description', 'No description')
                    if len(description) > 50:
                        description = description[:50] + "..."
                    
                    vendor = cve.get('vendor', '').strip()
                    product = cve.get('product', '').strip()
                    
                    # Если вендор/продукт отсутствуют, пытаемся извлечь из описания
                    if not vendor or not product:
                        # Ищем паттерны в описании для извлечения вендора/продукта
                        desc = cve.get('description', '')
                        if 'DOXENSE' in desc:
                            vendor = 'DOXENSE'
                            product = 'WATCHDOC'
                        elif 'HaruTheme' in desc:
                            vendor = 'HaruTheme'
                            product = 'WooCommerce Designer Pro'
                        elif 'TalentSys' in desc:
                            vendor = 'TalentSys'
                            product = 'Consulting Information Technology'
                        elif 'flowiseai' in desc or 'Flowise' in desc:
                            vendor = 'flowiseai'
                            product = 'flowise'
                        elif 'Delta Electronics' in desc:
                            vendor = 'Delta Electronics'
                            product = 'DIALink'
                        elif 'Spring Cloud' in desc:
                            vendor = 'Spring'
                            product = 'Cloud Gateway'
                        elif 'Digiever' in desc:
                            vendor = 'Digiever'
                            product = 'NVR'
                        else:
                            # Пытаемся извлечь первое значимое слово из описания как вендор
                            words = desc.split()
                            if words:
                                # Пропускаем служебные слова
                                skip_words = ['A', 'An', 'The', 'In', 'Unrestricted', 'Improper', 'Certain', 'Directory', 'Authorization']
                                for word in words:
                                    if word not in skip_words and len(word) > 2:
                                        vendor = word
                                        product = 'Unknown'
                                        break
                    
                    # Если все еще пустые, используем Unknown
                    if not vendor:
                        vendor = 'Unknown'
                    if not product:
                        product = 'Unknown'
                    
                    response += f"{i}. {severity_emoji} <b>{cve['id']}</b> (CVSS: {cvss}){epss_text}\n"
                    response += f"   <i>{vendor} {product}</i>\n"
                    response += f"   {description}\n\n"
                
                # Создаем кнопки в удобном формате (по 2 в ряду для 6-10)
                for i in range(6, 11):
                    if i % 2 == 0:  # Четные номера - начало нового ряда
                        if i == 10:  # Последняя кнопка - отдельно
                            keyboard_buttons.append([
                                InlineKeyboardButton(
                                    text=f"{i}",
                                    callback_data=f"cve_detail_{results[i-1]['id']}"
                                )
                            ])
                        else:  # Первая кнопка в ряду
                            keyboard_buttons.append([
                                InlineKeyboardButton(
                                    text=f"{i}",
                                    callback_data=f"cve_detail_{results[i-1]['id']}"
                                ),
                                InlineKeyboardButton(
                                    text=f"{i+1}",
                                    callback_data=f"cve_detail_{results[i]['id']}"
                                )
                            ])
                
                # Создаем клавиатуру
                keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
                
                await callback.answer()
                await callback.message.answer(response, parse_mode="HTML", disable_web_page_preview=True, reply_markup=keyboard)
            else:
                await callback.answer("❌ Больше CVE не найдено.", show_alert=True)
        else:
            await callback.answer("❌ Неизвестная команда.", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error handling callback query: {e}")
        await callback.answer("❌ Ошибка при обработке запроса.", show_alert=True)

# Register message handler for non-command messages
@dp.message()
async def handle_message(message: types.Message):
    """Handle regular messages (not commands)"""
    try:
        # Skip if this is a channel post (handled by channel_post handler)
        if message.chat.type in ['channel']:
            return
        
        # Check if message contains CVE patterns
        cve_patterns = bot_service.find_cve_patterns(message.text or "")
        
        if cve_patterns:
            # Process each CVE found
            for cve_id in cve_patterns:
                cve_data = bot_service.get_cve_info(cve_id)
                
                if cve_data:
                    # Send initial CVE information + loading indicator as reply
                    initial_message = bot_service.format_cve_message(cve_data, include_ai=False)
                    loading_message = bot_service.format_cve_message(cve_data, include_ai=True, loading_animation="🔄 <i>Анализирую уязвимость...</i>")
                    sent_message = await message.reply(loading_message, parse_mode="HTML", disable_web_page_preview=True)
                    
                    # Generate AI explanation and edit the message
                    try:
                        ai_explanation = await bot_service.generate_ai_explanation(cve_data)
                        
                        # Create updated message with AI analysis
                        updated_message = f"{initial_message}\n\n🤖 <b>AI-анализ:</b>\n\n{ai_explanation}"
                        
                        # Edit the original message
                        await sent_message.edit_text(updated_message, parse_mode="HTML", disable_web_page_preview=True)
                        
                    except Exception as e:
                        logger.error(f"Error generating AI explanation for {cve_id}: {e}")
                        # Edit message to show AI error
                        error_message = f"{initial_message}\n\n🤖 <b>AI-анализ:</b>\n<i>Временно недоступен</i>"
                        await sent_message.edit_text(error_message, parse_mode="HTML", disable_web_page_preview=True)
                else:
                    await message.reply(f"❌ CVE {cve_id} не найден в базе данных.", disable_web_page_preview=True)
        else:
            # If no CVE patterns found, send help message
            await message.answer(
                "🤖 Привет! Я CVE Info Bot.\n\n"
                "Используйте команды:\n"
                "• /start - Начать работу\n"
                "• /help - Справка\n"
                "• /cve CVE-YYYY-NNNNN - Информация о CVE\n"
                "• /vendor <название> - Поиск по вендору\n"
                "• /top - Топ критических CVE\n"
                "• /stats - Статистика базы данных\n\n"
                "Бот показывает CVSS и EPSS оценки для оценки рисков.\n\n"
                "Или просто напишите CVE ID в сообщении!",
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        await message.answer("❌ Ошибка при обработке сообщения.", disable_web_page_preview=True)

async def main():
    try:
        # Start bot
        logger.info("CVE Bot starting...")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
