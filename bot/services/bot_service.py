import sqlite3
import re
import logging
from typing import List, Dict, Optional, Tuple
from .ollama_service import OllamaService

logger = logging.getLogger(__name__)

class BotService:
    def __init__(self, db_path: str = "db/cve.db"):
        self.db_path = db_path
        self.ollama = OllamaService()
    
    def find_cve_patterns(self, text: str) -> List[str]:
        """Find all CVE patterns in text"""
        pattern = r'CVE-\d{4}-\d+'
        return re.findall(pattern, text, re.IGNORECASE)
    
    def get_cve_info(self, cve_id: str) -> Optional[Dict]:
        """Get CVE information from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, description, cvss_v3, published_date, vendor, product, epss
                FROM cve WHERE id = ?
            """, (cve_id.upper(),))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'id': row[0],
                    'description': row[1],
                    'cvss_v3': row[2],
                    'published_date': row[3],
                    'vendor': row[4],
                    'product': row[5],
                    'epss': row[6]
                }
            return None
        except Exception as e:
            logger.error(f"Error getting CVE info: {e}")
            return None
    
    def search_by_vendor(self, vendor: str, limit: int = 10) -> List[Dict]:
        """Search CVEs by vendor/product"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, description, cvss_v3, published_date, vendor, product
                FROM cve 
                WHERE vendor LIKE ? OR product LIKE ?
                ORDER BY cvss_v3 DESC NULLS LAST, published_date DESC
                LIMIT ?
            """, (f"%{vendor}%", f"%{vendor}%", limit))
            rows = cursor.fetchall()
            conn.close()
            
            return [{
                'id': row[0],
                'description': row[1],
                'cvss_v3': row[2],
                'published_date': row[3],
                'vendor': row[4],
                'product': row[5]
            } for row in rows]
        except Exception as e:
            logger.error(f"Error searching by vendor: {e}")
            return []
    
    def get_top_critical_cves(self, limit: int = 10) -> List[Dict]:
        """Get top critical CVEs by CVSS score"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, description, cvss_v3, published_date, vendor, product
                FROM cve 
                WHERE cvss_v3 IS NOT NULL
                ORDER BY cvss_v3 DESC, published_date DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            conn.close()
            
            return [{
                'id': row[0],
                'description': row[1],
                'cvss_v3': row[2],
                'published_date': row[3],
                'vendor': row[4],
                'product': row[5]
            } for row in rows]
        except Exception as e:
            logger.error(f"Error getting top CVEs: {e}")
            return []
    
    async def format_cve_message_with_ai(self, cve_data: Dict) -> str:
        """Format CVE message with AI analysis included"""
        cve_id = cve_data.get('id', 'Unknown')
        description = cve_data.get('description', 'No description available')
        cvss_v3 = cve_data.get('cvss_v3', 'N/A')
        vendor = cve_data.get('vendor', 'Unknown')
        product = cve_data.get('product', 'Unknown')
        published_date = cve_data.get('published_date', 'Unknown')
        
        # Escape Markdown special characters
        def escape_markdown(text):
            if not text:
                return text
            special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
            for char in special_chars:
                text = text.replace(char, f'\\{char}')
            return text
        
        # Clean and escape description
        clean_description = escape_markdown(description[:300])  # Короче для inline
        if len(description) > 300:
            clean_description += '...'
        
        # Determine severity emoji and text
        if cvss_v3 and isinstance(cvss_v3, (int, float)):
            if cvss_v3 >= 9.0:
                severity_emoji = "🔴"
                severity_text = "КРИТИЧЕСКИЙ"
            elif cvss_v3 >= 7.0:
                severity_emoji = "🟠"
                severity_text = "ВЫСОКИЙ"
            elif cvss_v3 >= 4.0:
                severity_emoji = "🟡"
                severity_text = "СРЕДНИЙ"
            else:
                severity_emoji = "🟢"
                severity_text = "НИЗКИЙ"
        else:
            severity_emoji = "⚪"
            severity_text = "НЕИЗВЕСТНО"
        
        # Generate AI analysis
        try:
            ai_analysis = await self.generate_ai_explanation(cve_data)
            # Ограничиваем длину AI анализа
            if len(ai_analysis) > 300:
                ai_analysis = ai_analysis[:300] + "..."
        except Exception as e:
            logger.error(f"Error generating AI analysis: {e}")
            ai_analysis = "🤖 AI\\-анализ временно недоступен\\."
        
        message = f"""{severity_emoji} *{cve_id}* - {severity_text}

*Продукт:* {escape_markdown(vendor)} {escape_markdown(product)}
*CVSS v3:* {cvss_v3}
*Дата:* {escape_markdown(published_date)}

*Описание:*
{clean_description}

🤖 *AI\\-анализ:*
{ai_analysis}

*Ссылки:*
• [NVD](https://nvd.nist.gov/vuln/detail/{cve_id})
• [CVE Details](https://www.cvedetails.com/cve/{cve_id}/)"""
        
        return message

    def format_cve_message(self, cve_data: Dict, include_ai: bool = True, loading_animation: str = None) -> str:
        """Format CVE information for Telegram message"""
        cve_id = cve_data.get('id', 'Unknown')
        description = cve_data.get('description', 'No description available')
        cvss_v3 = cve_data.get('cvss_v3', 'N/A')
        vendor = cve_data.get('vendor', 'Unknown')
        product = cve_data.get('product', 'Unknown')
        published_date = cve_data.get('published_date', 'Unknown')

        # Clean text for HTML - minimal escaping
        def clean_html_text(text):
            if not text:
                return text
            text = str(text)
            # Only escape HTML special characters
            text = text.replace('&', '&amp;')
            text = text.replace('<', '&lt;')
            text = text.replace('>', '&gt;')
            return text

        # Clean and truncate description
        clean_description = description[:500]
        if len(description) > 500:
            clean_description += '...'

        # Determine severity emoji and text
        if cvss_v3 and isinstance(cvss_v3, (int, float)):
            if cvss_v3 >= 9.0:
                severity_emoji = "🔴"
                severity_text = "КРИТИЧЕСКИЙ"
            elif cvss_v3 >= 7.0:
                severity_emoji = "🟠"
                severity_text = "ВЫСОКИЙ"
            elif cvss_v3 >= 4.0:
                severity_emoji = "🟡"
                severity_text = "СРЕДНИЙ"
            else:
                severity_emoji = "🟢"
                severity_text = "НИЗКИЙ"
        else:
            severity_emoji = "⚪"
            severity_text = "НЕИЗВЕСТНО"

        # Format date nicely
        try:
            from datetime import datetime
            if published_date and published_date != 'Unknown':
                dt = datetime.fromisoformat(published_date.replace('Z', '+00:00'))
                formatted_date = dt.strftime('%d.%m.%Y')
            else:
                formatted_date = published_date
        except:
            formatted_date = published_date

        message = f"""{severity_emoji} <b>{cve_id}</b> - {severity_text}

<b>Продукт:</b> {clean_html_text(vendor)} {clean_html_text(product)}
<b>CVSS v3:</b> {cvss_v3}
<b>Дата:</b> {clean_html_text(formatted_date)}

<b>Описание:</b>
{clean_html_text(clean_description)}

<b>Ссылки:</b>
• <a href="https://nvd.nist.gov/vuln/detail/{cve_id}">NVD</a>
• <a href="https://www.cvedetails.com/cve/{cve_id}/">CVE Details</a>"""

        if include_ai:
            if loading_animation:
                message += f"\n\n🤖 <b>AI-анализ:</b>\n{loading_animation}"
            else:
                message += "\n\n🤖 <b>AI-анализ:</b>\n<i>Генерация объяснения...</i>"

        return message
    
    def get_loading_animation(self, step: int = 0) -> str:
        """Get loading animation step"""
        animations = [
            "🔄 _Анализирую уязвимость..._",
            "🧠 _Обрабатываю данные..._", 
            "⚡ _Генерирую рекомендации..._",
            "🔍 _Формирую отчет..._",
            "✨ _Завершаю анализ..._"
        ]
        return animations[step % len(animations)]
    
    async def generate_ai_explanation(self, cve_data: Dict) -> str:
        """Generate AI explanation for CVE"""
        try:
            return await self.ollama.generate_cve_explanation(cve_data)
        except Exception as e:
            logger.error(f"Error generating AI explanation: {e}")
            return "🤖 AI-анализ временно недоступен."
    
    def format_vendor_search_results(self, results: List[Dict]) -> str:
        """Format vendor search results for Telegram message"""
        if not results:
            return "❌ CVE для указанного вендора/продукта не найдены\\."
        
        message = f"🔍 *Найдено {len(results)} CVE:*\n\n"
        
        for i, cve in enumerate(results[:5], 1):  # Limit to 5 results
            cvss = cve.get('cvss_v3', 'N/A')
            severity_emoji = "🔴" if cvss and cvss >= 9.0 else "🟠" if cvss and cvss >= 7.0 else "🟡" if cvss and cvss >= 4.0 else "🟢"
            
            # Escape special characters
            cve_id = cve['id'].replace('_', '\\_').replace('*', '\\*')
            vendor = cve.get('vendor', 'Unknown').replace('_', '\\_').replace('*', '\\*')
            product = cve.get('product', 'Unknown').replace('_', '\\_').replace('*', '\\*')
            description = cve.get('description', 'No description')[:100].replace('_', '\\_').replace('*', '\\*')
            
            message += f"{i}\\. {severity_emoji} *{cve_id}* \\(CVSS: {cvss}\\)\n"
            message += f"   {vendor} {product}\n"
            message += f"   {description}\\.\\.\\.\n\n"
        
        if len(results) > 5:
            message += f"\\.\\.\\. и еще {len(results) - 5} CVE"
        
        return message
    
    def format_inline_result(self, cve_data: Dict) -> str:
        """Format CVE data for inline query result"""
        cve_id = cve_data.get('id', 'Unknown')
        description = cve_data.get('description', 'No description available')
        cvss_v3 = cve_data.get('cvss_v3', 'N/A')
        vendor = cve_data.get('vendor', 'Unknown')
        product = cve_data.get('product', 'Unknown')
        
        # Truncate description for inline results
        short_desc = description[:100] + "..." if len(description) > 100 else description
        
        return f"🔍 {cve_id} (CVSS: {cvss_v3})\n{vendor} {product}\n{short_desc}"
