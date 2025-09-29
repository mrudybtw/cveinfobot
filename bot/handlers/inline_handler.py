import logging
from aiogram import types
from aiogram.filters import Command
from ..services.bot_service import BotService

logger = logging.getLogger(__name__)

class InlineHandler:
    def __init__(self, bot_service: BotService):
        self.bot_service = bot_service
    
    async def handle_inline_query(self, query: types.InlineQuery):
        """Handle inline queries for CVE search"""
        try:
            query_text = query.query.strip()
            
            if not query_text:
                # Show recent critical CVEs if no query
                results = self.bot_service.get_top_critical_cves(limit=5)
                inline_results = []
                
                for cve in results:
                    # Use simple format for inline (no AI to keep it fast)
                    message_text = self.bot_service.format_cve_message(cve, include_ai=False)
                    inline_results.append(types.InlineQueryResultArticle(
                        id=cve['id'],
                        title=f"🔍 {cve['id']} (CVSS: {cve.get('cvss_v3', 'N/A')})",
                        description=f"{cve.get('vendor', 'Unknown')} {cve.get('product', 'Unknown')}",
                        input_message_content=types.InputTextMessageContent(
                            message_text=message_text,
                            parse_mode="Markdown"
                        )
                    ))
                
                await query.answer(inline_results, cache_time=300)
                return
            
            # Search for CVE by ID
            if query_text.upper().startswith('CVE-'):
                cve_data = self.bot_service.get_cve_info(query_text)
                if cve_data:
                    # Use simple format for inline (no AI to keep it fast)
                    message_text = self.bot_service.format_cve_message(cve_data, include_ai=False)
                    result = types.InlineQueryResultArticle(
                        id=cve_data['id'],
                        title=f"🔍 {cve_data['id']} (CVSS: {cve_data.get('cvss_v3', 'N/A')})",
                        description=f"{cve_data.get('vendor', 'Unknown')} {cve_data.get('product', 'Unknown')}",
                        input_message_content=types.InputTextMessageContent(
                            message_text=message_text,
                            parse_mode="Markdown"
                        )
                    )
                    await query.answer([result], cache_time=300)
                else:
                    await query.answer([], cache_time=300)
                return
            
            # Search by vendor/product
            results = self.bot_service.search_by_vendor(query_text, limit=10)
            
            if results:
                inline_results = []
                for cve in results:
                    # Use simple format for inline (no AI to keep it fast)
                    message_text = self.bot_service.format_cve_message(cve, include_ai=False)
                    inline_results.append(types.InlineQueryResultArticle(
                        id=cve['id'],
                        title=f"🔍 {cve['id']} (CVSS: {cve.get('cvss_v3', 'N/A')})",
                        description=f"{cve.get('vendor', 'Unknown')} {cve.get('product', 'Unknown')}",
                        input_message_content=types.InputTextMessageContent(
                            message_text=message_text,
                            parse_mode="Markdown"
                        )
                    ))
                
                await query.answer(inline_results, cache_time=300)
            else:
                await query.answer([], cache_time=300)
                
        except Exception as e:
            logger.error(f"Error handling inline query: {e}")
            await query.answer([], cache_time=300)
