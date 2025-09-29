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
                logger.debug("No text in message, skipping")
                return
            
            # Find CVE patterns in the post
            cve_patterns = self.bot_service.find_cve_patterns(message.text)
            
            if not cve_patterns:
                logger.debug(f"No CVE patterns found in message: {message.text[:100]}...")
                return
            
            logger.info(f"Found CVE patterns in channel post: {cve_patterns}")
            logger.info(f"Message ID: {message.message_id}, Chat ID: {message.chat.id}")
            logger.info(f"Has linked chat: {hasattr(message.chat, 'linked_chat') and message.chat.linked_chat is not None}")
            if hasattr(message, 'message_thread_id'):
                logger.info(f"Message thread ID: {message.message_thread_id}")
            
            # Check if channel has linked discussion group for comments
            if hasattr(message.chat, 'linked_chat') and message.chat.linked_chat:
                # Send comments to discussion group
                await self._handle_channel_comments(message, cve_patterns)
            else:
                # Fallback to replying in the channel
                await self._handle_channel_replies(message, cve_patterns)
                    
        except Exception as e:
            logger.error(f"Error handling channel post: {e}")
            try:
                if hasattr(message.chat, 'linked_chat') and message.chat.linked_chat:
                    await message.bot.send_message(
                        chat_id=message.chat.linked_chat.id,
                        text="❌ Ошибка при обработке сообщения.",
                        disable_web_page_preview=True,
                        reply_to_message_id=message.message_id
                    )
                else:
                    await message.reply("❌ Ошибка при обработке сообщения.", disable_web_page_preview=True)
            except Exception as send_error:
                logger.error(f"Error sending error message: {send_error}")
    
    async def _handle_channel_comments(self, message: types.Message, cve_patterns: list):
        """Handle CVE comments in discussion group"""
        discussion_group_id = message.chat.linked_chat.id
        logger.info(f"Found discussion group: {discussion_group_id}")
        
        # Process each CVE found
        for cve_id in cve_patterns:
            cve_data = self.bot_service.get_cve_info(cve_id)
            
            if cve_data:
                # Send initial CVE information + loading indicator
                initial_message = self.bot_service.format_cve_message(cve_data, include_ai=False)
                loading_message = self.bot_service.format_cve_message(cve_data, include_ai=True, loading_animation="🔄 <i>Анализирую уязвимость...</i>")
                
                # Send comment to discussion group using message_thread_id for proper commenting
                try:
                    sent_message = await message.bot.send_message(
                        chat_id=discussion_group_id,
                        text=loading_message,
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                        message_thread_id=message.message_thread_id if hasattr(message, 'message_thread_id') and message.message_thread_id else None
                    )
                except Exception as e:
                    logger.warning(f"Failed to send with message_thread_id, trying with reply_to_message_id: {e}")
                    # Fallback to reply_to_message_id
                    sent_message = await message.bot.send_message(
                        chat_id=discussion_group_id,
                        text=loading_message,
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                        reply_to_message_id=message.message_id
                    )
                
                # Generate AI explanation and edit the message
                try:
                    ai_explanation = await self.bot_service.generate_ai_explanation(cve_data)
                    
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
                # Send error comment to discussion group
                try:
                    await message.bot.send_message(
                        chat_id=discussion_group_id,
                        text=f"❌ CVE {cve_id} не найден в базе данных.",
                        disable_web_page_preview=True,
                        message_thread_id=message.message_thread_id if hasattr(message, 'message_thread_id') and message.message_thread_id else None
                    )
                except Exception as e:
                    logger.warning(f"Failed to send error with message_thread_id, trying with reply_to_message_id: {e}")
                    await message.bot.send_message(
                        chat_id=discussion_group_id,
                        text=f"❌ CVE {cve_id} не найден в базе данных.",
                        disable_web_page_preview=True,
                        reply_to_message_id=message.message_id
                    )
    
    async def _handle_channel_replies(self, message: types.Message, cve_patterns: list):
        """Handle CVE replies in channel (fallback when no discussion group)"""
        logger.warning(f"Channel {message.chat.id} has no linked discussion group, using replies")
        
        # Process each CVE found
        for cve_id in cve_patterns:
            cve_data = self.bot_service.get_cve_info(cve_id)
            
            if cve_data:
                # Send initial CVE information + loading indicator
                initial_message = self.bot_service.format_cve_message(cve_data, include_ai=False)
                loading_message = self.bot_service.format_cve_message(cve_data, include_ai=True, loading_animation="🔄 <i>Анализирую уязвимость...</i>")
                sent_message = await message.reply(loading_message, parse_mode="HTML", disable_web_page_preview=True)
                
                # Generate AI explanation and edit the message
                try:
                    ai_explanation = await self.bot_service.generate_ai_explanation(cve_data)
                    
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
