import aiohttp
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class OllamaService:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = None):
        self.base_url = base_url
        if model is None:
            from config import Config
            self.model = Config.OLLAMA_MODEL
        else:
            self.model = model
    
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
Ты - эксперт по кибербезопасности. Проанализируй CVE и дай структурированный анализ на русском языке.

CVE: {cve_id}
Описание: {description}
CVSS: {cvss_v3}
Продукт: {vendor} {product}

ОБЯЗАТЕЛЬНО следуй этому формату (каждый раздел с новой строки и пустой строкой между разделами):

🔍 Суть:
[Объясни что это за уязвимость в 1-2 предложениях]

⚠️ Риски:
[Опиши основные угрозы и последствия]

🛠️ Действия:
[Конкретные шаги: обновить до версии X, применить патч, отключить функцию и т.д.]

⏰ Приоритет:
[критический/высокий/средний/низкий]

ВАЖНО:
- Будь конкретным и практичным
- Укажи конкретные версии если знаешь
- Дай четкие инструкции по исправлению
- НЕ используй HTML теги (<b>, <i>, <br>, <p> и т.д.)
- НЕ используй Markdown разметку (звездочки, подчеркивания)
- Используй ТОЛЬКО обычный текст с эмодзи
- Максимум 200 слов
- НЕ добавляй лишние фразы типа "Я готов помочь!"
- ОБЯЗАТЕЛЬНО добавляй пустую строку между разделами
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
                "temperature": 0.1,  # Очень детерминированные ответы
                "top_p": 0.9,
                "top_k": 40,
                "repeat_penalty": 1.1,
                "max_tokens": 300,   # Увеличиваем лимит для более полных ответов
                "num_predict": 300,
                "stop": ["\n\n\n", "---", "==="]  # Останавливаем на разделителях
            }
        }
        
        timeout = aiohttp.ClientTimeout(total=30)  # 30 секунд таймаут
        async with aiohttp.ClientSession(timeout=timeout) as session:
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
        
        return f"""🔍 Суть: Уязвимость {cve_id} в продукте {vendor} {product} с оценкой CVSS {cvss_v3}

⚠️ Риски: {severity} уровень угрозы. Требует немедленного внимания для предотвращения компрометации системы.

🛠️ Действия: {priority}. Проверьте наличие обновлений безопасности и примените патчи. Отключите неиспользуемые функции если возможно.

⏰ Приоритет: {severity.lower()}"""
