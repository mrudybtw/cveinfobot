import logging
from aiogram import types
from ..services.bot_service import BotService

logger = logging.getLogger(__name__)

class ChannelHandler:
    def __init__(self, bot_service: BotService):
        self.bot_service = bot_service
    
    async def handle_channel_post(self, message: types.Message):
        """Handle channel posts and look for CVE patterns"""
        try:
            if not message.text:
                return
            
            # Find CVE patterns in the post
            cve_patterns = self.bot_service.find_cve_patterns(message.text)
            
            if not cve_patterns:
                return
            
            logger.info(f"Found CVE patterns in channel post: {cve_patterns}")
            
            # Process each CVE found
            for cve_id in cve_patterns:
                cve_data = self.bot_service.get_cve_info(cve_id)
                
                if cve_data:
                    # Send initial CVE information + loading indicator
                    initial_message = self.bot_service.format_cve_message(cve_data, include_ai=False)
                    loading_message = self.bot_service.format_cve_message(cve_data, include_ai=True, loading_animation="🔄 <i>Анализирую уязвимость...</i>")
                    sent_message = await message.reply(loading_message, parse_mode="HTML")
                    
                    # Generate AI explanation and edit the message
                    try:
                        ai_explanation = await self.bot_service.generate_ai_explanation(cve_data)
                        
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
                    await message.reply(f"❌ CVE {cve_id} не найден в базе данных.")
                    
        except Exception as e:
            logger.error(f"Error handling channel post: {e}")
            await message.reply("❌ Ошибка при обработке сообщения.")
