import aiohttp
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class OllamaService:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.model = "llama3.1:8b"  # Default model, can be configured
    
    async def generate_cve_explanation(self, cve_data: dict) -> str:
        """Generate AI explanation and recommendations for a CVE"""
        try:
            prompt = self._create_cve_prompt(cve_data)
            response = await self._call_ollama(prompt)
            return response
        except Exception as e:
            logger.error(f"Error generating CVE explanation: {e}")
            return self._get_fallback_explanation(cve_data)
    
    def _create_cve_prompt(self, cve_data: dict) -> str:
        """Create a prompt for the LLM based on CVE data"""
        cve_id = cve_data.get('id', 'Unknown')
        description = cve_data.get('description', 'No description available')
        cvss_v3 = cve_data.get('cvss_v3', 'N/A')
        vendor = cve_data.get('vendor', 'Unknown')
        product = cve_data.get('product', 'Unknown')
        
        prompt = f"""
Проанализируй CVE и дай КРАТКИЙ анализ на русском (максимум 150 слов):

CVE: {cve_id}
Описание: {description}
CVSS: {cvss_v3}
Продукт: {vendor} {product}

Формат ответа (БЕЗ звездочек и подчеркиваний):
🔍 Суть: [краткое объяснение в 1-2 предложения]
⚠️ Риски: [основные угрозы]
🛠️ Действия: [что делать - обновить/патчить/мониторить]
⏰ Приоритет: [критический/высокий/средний/низкий]

Будь кратким и по делу! НЕ используй Markdown разметку!
"""
        return prompt
    
    async def _call_ollama(self, prompt: str) -> str:
        """Make API call to Ollama"""
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,  # Более детерминированные ответы
                "top_p": 0.8,
                "max_tokens": 200,   # Ограничиваем длину ответа
                "num_predict": 200   # Дополнительное ограничение
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get('response', 'Ошибка генерации ответа')
                else:
                    raise Exception(f"Ollama API error: {response.status}")
    
    def _get_fallback_explanation(self, cve_data: dict) -> str:
        """Fallback explanation when Ollama is not available"""
        cve_id = cve_data.get('id', 'Unknown')
        cvss_v3 = cve_data.get('cvss_v3', 'N/A')
        vendor = cve_data.get('vendor', 'Unknown')
        product = cve_data.get('product', 'Unknown')
        
        # Determine severity based on CVSS score
        if cvss_v3 and isinstance(cvss_v3, (int, float)):
            if cvss_v3 >= 9.0:
                severity = "КРИТИЧЕСКИЙ"
                priority = "Немедленно"
            elif cvss_v3 >= 7.0:
                severity = "ВЫСОКИЙ"
                priority = "В течение 24 часов"
            elif cvss_v3 >= 4.0:
                severity = "СРЕДНИЙ"
                priority = "В течение недели"
            else:
                severity = "НИЗКИЙ"
                priority = "При следующем плановом обновлении"
        else:
            severity = "НЕИЗВЕСТНО"
            priority = "Требует анализа"
        
        return f"""
🔍 **{cve_id}** - {severity}

**Продукт:** {vendor} {product}
**CVSS v3:** {cvss_v3}

**Рекомендации:**
• Приоритет обновления: {priority}
• Проверьте наличие обновлений безопасности
• Примените патчи как можно скорее
• Мониторьте системы на предмет компрометации

⚠️ *AI-анализ временно недоступен. Рекомендуется ручная проверка.*
"""
