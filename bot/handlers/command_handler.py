import logging
from aiogram import types
from aiogram.filters import Command
from ..services.bot_service import BotService

logger = logging.getLogger(__name__)

class CommandHandler:
    def __init__(self, bot_service: BotService):
        self.bot_service = bot_service
    
    async def handle_cve_command(self, message: types.Message):
        """Handle /cve command"""
        try:
            text = message.text
            if not text:
                await message.answer("❌ Используйте: /cve CVE-YYYY-NNNNN")
                return
            
            # Extract CVE ID from command
            cve_patterns = self.bot_service.find_cve_patterns(text)
            if not cve_patterns:
                await message.answer("❌ CVE ID не найден. Используйте формат: CVE-YYYY-NNNNN")
                return
            
            cve_id = cve_patterns[0]  # Take first CVE found
            cve_data = self.bot_service.get_cve_info(cve_id)
            
            if cve_data:
                # Send initial message with basic info + loading indicator
                initial_message = self.bot_service.format_cve_message(cve_data, include_ai=False)
                loading_message = self.bot_service.format_cve_message(cve_data, include_ai=True, loading_animation="🔄 <i>Анализирую уязвимость...</i>")
                sent_message = await message.answer(loading_message, parse_mode="HTML")
                
                # Generate AI explanation and edit the message
                try:
                    ai_explanation = await self.bot_service.generate_ai_explanation(cve_data)
                    
                    # Create updated message with AI analysis
                    updated_message = f"{initial_message}\n\n🤖 <b>AI-анализ:</b>\n\n{ai_explanation}"
                    
                    # Edit the original message
                    await sent_message.edit_text(updated_message, parse_mode="HTML")
                    
                except Exception as e:
                    logger.error(f"Error generating AI explanation: {e}")
                    # Edit message to show AI error
                    error_message = f"{initial_message}\n\n🤖 <b>AI-анализ:</b>\n<i>Временно недоступен</i>"
                    await sent_message.edit_text(error_message, parse_mode="HTML")
            else:
                await message.answer(f"❌ CVE {cve_id} не найден в базе данных.")
                
        except Exception as e:
            logger.error(f"Error handling CVE command: {e}")
            await message.answer("❌ Ошибка при обработке команды.")
    
    async def handle_vendor_command(self, message: types.Message):
        """Handle /vendor command"""
        try:
            text = message.text
            if not text:
                await message.answer("❌ Используйте: /vendor <название вендора/продукта>")
                return
            
            # Extract vendor/product name
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                await message.answer("❌ Укажите название вендора/продукта: /vendor <название>")
                return
            
            vendor_name = parts[1]
            results = self.bot_service.search_by_vendor(vendor_name, limit=10)
            
            if results:
                response = self.bot_service.format_vendor_search_results(results)
                await message.answer(response, parse_mode="Markdown")
            else:
                await message.answer(f"❌ CVE для '{vendor_name}' не найдены.")
                
        except Exception as e:
            logger.error(f"Error handling vendor command: {e}")
            await message.answer("❌ Ошибка при обработке команды.")
    
    async def handle_top_command(self, message: types.Message):
        """Handle /top command - show top critical CVEs"""
        try:
            results = self.bot_service.get_top_critical_cves(limit=5)
            
            if results:
                response = "🔴 *Топ\\-5 критических CVE:*\n\n"
                for i, cve in enumerate(results, 1):
                    cvss = cve.get('cvss_v3', 'N/A')
                    severity_emoji = "🔴" if cvss and cvss >= 9.0 else "🟠" if cvss and cvss >= 7.0 else "🟡"
                    
                    # Escape special characters
                    cve_id = cve['id'].replace('_', '\\_').replace('*', '\\*')
                    vendor = cve.get('vendor', 'Unknown').replace('_', '\\_').replace('*', '\\*')
                    product = cve.get('product', 'Unknown').replace('_', '\\_').replace('*', '\\*')
                    description = cve.get('description', 'No description')[:100].replace('_', '\\_').replace('*', '\\*')
                    
                    response += f"{i}\\. {severity_emoji} *{cve_id}* \\(CVSS: {cvss}\\)\n"
                    response += f"   {vendor} {product}\n"
                    response += f"   {description}\\.\\.\\.\n\n"
                
                await message.answer(response, parse_mode="Markdown")
            else:
                await message.answer("❌ Критические CVE не найдены\\.")
                
        except Exception as e:
            logger.error(f"Error handling top command: {e}")
            await message.answer("❌ Ошибка при обработке команды\\.")
    
    async def handle_start_command(self, message: types.Message):
        """Handle /start command"""
        welcome_text = """
🤖 **Добро пожаловать в CVE Info Bot!**

Этот бот поможет вам получить информацию о уязвимостях CVE с AI-анализом.

**Основные команды:**
• `/cve CVE-YYYY-NNNNN` - Информация о конкретной CVE
• `/vendor <название>` - Поиск CVE по вендору/продукту
• `/top` - Топ-5 критических CVE
• `/help` - Подробная справка

**Автоматические функции:**
• Бот автоматически комментирует посты в каналах, содержащие CVE
• Используйте @cveinfobot для inline-поиска

**Примеры:**
• `/cve CVE-2023-1234`
• `/vendor microsoft`
• `/vendor apache`

**AI-анализ:**
Бот использует локальную модель Ollama для генерации объяснений и рекомендаций по CVE.

Начните с команды `/help` для получения подробной информации!
        """
        await message.answer(welcome_text, parse_mode="Markdown")

    async def handle_help_command(self, message: types.Message):
        """Handle /help command"""
        help_text = """
🤖 **CVE Info Bot - Справка**

**Основные команды:**
• `/cve CVE-YYYY-NNNNN` - Информация о конкретной CVE
• `/vendor <название>` - Поиск CVE по вендору/продукту
• `/top` - Топ-5 критических CVE
• `/help` - Эта справка

**Автоматические функции:**
• Бот автоматически комментирует посты в каналах, содержащие CVE
• Используйте @cveinfobot для inline-поиска

**Примеры:**
• `/cve CVE-2023-1234`
• `/vendor microsoft`
• `/vendor apache`

**AI-анализ:**
Бот использует локальную модель Ollama для генерации объяснений и рекомендаций по CVE.
        """
        await message.answer(help_text, parse_mode="Markdown")
