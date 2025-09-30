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
                await message.answer("❌ Используйте: /cve CVE-YYYY-NNNNN", disable_web_page_preview=True)
                return
            
            # Extract CVE ID from command
            cve_patterns = self.bot_service.find_cve_patterns(text)
            if not cve_patterns:
                await message.answer("❌ CVE ID не найден. Используйте формат: CVE-YYYY-NNNNN", disable_web_page_preview=True)
                return
            
            cve_id = cve_patterns[0]  # Take first CVE found
            cve_data = self.bot_service.get_cve_info(cve_id)
            
            if cve_data:
                # Send initial message with basic info + loading indicator
                initial_message = self.bot_service.format_cve_message(cve_data, include_ai=False)
                loading_message = self.bot_service.format_cve_message(cve_data, include_ai=True, loading_animation="🔄 <i>Анализирую уязвимость...</i>")
                sent_message = await message.answer(loading_message, parse_mode="HTML", disable_web_page_preview=True)
                
                # Generate AI explanation and edit the message
                try:
                    ai_explanation = await self.bot_service.generate_ai_explanation(cve_data)
                    
                    # Create updated message with AI analysis
                    updated_message = f"{initial_message}\n\n🤖 <b>AI-анализ:</b>\n\n{ai_explanation}"
                    
                    # Edit the original message
                    await sent_message.edit_text(updated_message, parse_mode="HTML", disable_web_page_preview=True)
                    
                except Exception as e:
                    logger.error(f"Error generating AI explanation: {e}")
                    # Edit message to show AI error
                    error_message = f"{initial_message}\n\n🤖 <b>AI-анализ:</b>\n<i>Временно недоступен</i>"
                    await sent_message.edit_text(error_message, parse_mode="HTML", disable_web_page_preview=True)
            else:
                await message.answer(f"❌ CVE {cve_id} не найден в базе данных.", disable_web_page_preview=True)
                
        except Exception as e:
            logger.error(f"Error handling CVE command: {e}")
            await message.answer("❌ Ошибка при обработке команды.", disable_web_page_preview=True)
    
    async def handle_vendor_command(self, message: types.Message):
        """Handle /vendor command"""
        try:
            text = message.text
            if not text:
                await message.answer("❌ Используйте: /vendor <название вендора/продукта>", disable_web_page_preview=True)
                return
            
            # Extract vendor/product name
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                await message.answer("❌ Укажите название вендора/продукта: /vendor <название>", disable_web_page_preview=True)
                return
            
            vendor_name = parts[1]
            results = self.bot_service.search_by_vendor(vendor_name, limit=10)
            
            if results:
                response = self.bot_service.format_vendor_search_results(results)
                await message.answer(response, parse_mode="Markdown", disable_web_page_preview=True)
            else:
                await message.answer(f"❌ CVE для '{vendor_name}' не найдены.", disable_web_page_preview=True)
                
        except Exception as e:
            logger.error(f"Error handling vendor command: {e}")
            await message.answer("❌ Ошибка при обработке команды.", disable_web_page_preview=True)
    
    async def handle_top_command(self, message: types.Message):
        """Handle /top command - show top critical CVEs with interactive buttons"""
        try:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            results = self.bot_service.get_top_critical_cves(limit=10)
            
            if results:
                response = "🔴 <b>Топ-5 критических CVE:</b>\n\n"
                
                # Создаем кнопки для каждой CVE
                keyboard_buttons = []
                
                for i, cve in enumerate(results[:5], 1):  # Показываем только топ-5
                    cvss = cve.get('cvss_v3', 'N/A')
                    epss = cve.get('epss')
                    
                    # Определяем эмодзи серьезности
                    if cvss and cvss >= 9.0:
                        severity_emoji = "🔴"
                    elif cvss and cvss >= 7.0:
                        severity_emoji = "🟠"
                    else:
                        severity_emoji = "🟡"
                    
                    # EPSS информация (краткая)
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
                    
                    # Краткое описание
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
                    
                    # Компактный формат с вендором/продуктом
                    response += f"{i}. {severity_emoji} <b>{cve['id']}</b> (CVSS: {cvss}){epss_text}\n"
                    response += f"   <i>{vendor} {product}</i>\n"
                    response += f"   {description}\n\n"
                
                # Создаем кнопки в удобном формате (по 2 в ряду)
                for i in range(1, 6):
                    if i % 2 == 1:  # Нечетные номера - начало нового ряда
                        if i == 5:  # Последняя кнопка - отдельно
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
                
                # Добавляем кнопку "Показать еще" если есть больше CVE
                if len(results) > 5:
                    keyboard_buttons.append([
                        InlineKeyboardButton(
                            text="📋 Показать еще 5 CVE",
                            callback_data="top_more"
                        )
                    ])
                
                # Создаем клавиатуру
                keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
                
                await message.answer(
                    response, 
                    parse_mode="HTML", 
                    disable_web_page_preview=True,
                    reply_markup=keyboard
                )
            else:
                await message.answer("❌ Критические CVE не найдены.", disable_web_page_preview=True)
                
        except Exception as e:
            logger.error(f"Error handling top command: {e}")
            await message.answer("❌ Ошибка при обработке команды.", disable_web_page_preview=True)
    
    async def handle_start_command(self, message: types.Message):
        """Handle /start command"""
        # Check if start parameter contains CVE ID
        if message.text and 'cve_' in message.text:
            try:
                cve_id = message.text.split('cve_')[1].split()[0]
                # Get CVE data and send directly
                cve_data = self.bot_service.get_cve_info(cve_id)
                if cve_data:
                    # Send initial message with basic info + loading indicator
                    initial_message = self.bot_service.format_cve_message(cve_data, include_ai=False)
                    loading_message = self.bot_service.format_cve_message(cve_data, include_ai=True, loading_animation="🔄 <i>Анализирую уязвимость...</i>")
                    sent_message = await message.answer(loading_message, parse_mode="HTML", disable_web_page_preview=True)
                    
                    # Generate AI explanation and edit the message
                    try:
                        ai_explanation = await self.bot_service.generate_ai_explanation(cve_data)
                        
                        # Create updated message with AI analysis
                        updated_message = f"{initial_message}\n\n🤖 <b>AI-анализ:</b>\n\n{ai_explanation}"
                        
                        # Edit the original message
                        await sent_message.edit_text(updated_message, parse_mode="HTML", disable_web_page_preview=True)
                        
                    except Exception as e:
                        logger.error(f"Error generating AI explanation: {e}")
                        # Edit message to show AI error
                        error_message = f"{initial_message}\n\n🤖 <b>AI-анализ:</b>\n<i>Временно недоступен</i>"
                        await sent_message.edit_text(error_message, parse_mode="HTML", disable_web_page_preview=True)
                else:
                    await message.answer(f"❌ CVE {cve_id} не найден в базе данных.", disable_web_page_preview=True)
                return
            except Exception as e:
                logger.error(f"Error processing start parameter: {e}")
                pass
        
        welcome_text = """
🤖 **Добро пожаловать в CVE Info Bot!**

Этот бот поможет вам получить информацию о уязвимостях CVE с AI-анализом и EPSS оценками.

**Основные команды:**
• `/cve CVE-YYYY-NNNNN` - Информация о конкретной CVE
• `/vendor <название>` - Поиск CVE по вендору/продукту
• `/top` - Топ-5 критических CVE с интерактивными кнопками
• `/stats` - Статистика базы данных
• `/help` - Подробная справка

**Автоматические функции:**
• Бот автоматически комментирует посты в каналах, содержащие CVE
• Используйте @cveinfobot для inline-поиска
• Автоматическое обновление CVE каждый час

**Примеры:**
• `/cve CVE-2023-1234`
• `/vendor microsoft`
• `/vendor apache`
• `/stats`

**AI-анализ:**
Бот использует локальную модель Ollama для генерации объяснений и рекомендаций по CVE.

**EPSS оценки:**
Бот показывает EPSS (Exploit Prediction Scoring System) оценки для оценки вероятности эксплуатации уязвимостей в реальных атаках.

Начните с команды `/help` для получения подробной информации!
        """
        await message.answer(welcome_text, parse_mode="Markdown", disable_web_page_preview=True)

    async def handle_stats_command(self, message: types.Message):
        """Handle /stats command - show database statistics"""
        try:
            import sqlite3
            from datetime import datetime
            
            conn = sqlite3.connect('db/cve.db')
            cursor = conn.cursor()
            
            # Общее количество CVE
            cursor.execute("SELECT COUNT(*) FROM cve")
            total_cve = cursor.fetchone()[0]
            
            # Количество критических CVE
            cursor.execute("SELECT COUNT(*) FROM cve WHERE cvss_v3 IS NOT NULL AND cvss_v3 >= 9.0")
            critical_cve = cursor.fetchone()[0]
            
            # Количество высоких CVE
            cursor.execute("SELECT COUNT(*) FROM cve WHERE cvss_v3 IS NOT NULL AND cvss_v3 >= 7.0 AND cvss_v3 < 9.0")
            high_cve = cursor.fetchone()[0]
            
            # Количество средних CVE
            cursor.execute("SELECT COUNT(*) FROM cve WHERE cvss_v3 IS NOT NULL AND cvss_v3 >= 4.0 AND cvss_v3 < 7.0")
            medium_cve = cursor.fetchone()[0]
            
            # Количество низких CVE
            cursor.execute("SELECT COUNT(*) FROM cve WHERE cvss_v3 IS NOT NULL AND cvss_v3 < 4.0")
            low_cve = cursor.fetchone()[0]
            
            # CVE без CVSS оценки
            cursor.execute("SELECT COUNT(*) FROM cve WHERE cvss_v3 IS NULL")
            no_cvss = cursor.fetchone()[0]
            
            # EPSS статистика
            cursor.execute("SELECT COUNT(*) FROM cve WHERE epss IS NOT NULL")
            with_epss = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM cve WHERE epss > 0.5")
            high_epss = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM cve WHERE epss > 0.8")
            very_high_epss = cursor.fetchone()[0]
            
            cursor.execute("SELECT AVG(epss) FROM cve WHERE epss IS NOT NULL")
            avg_epss = cursor.fetchone()[0]
            
            # Последнее обновление
            cursor.execute("SELECT MAX(published_date) FROM cve")
            last_update = cursor.fetchone()[0]
            
            # Последний CVE (по дате публикации)
            cursor.execute("SELECT id, published_date FROM cve ORDER BY published_date DESC LIMIT 1")
            last_cve = cursor.fetchone()
            
            # Самый новый CVE ID (по номеру)
            cursor.execute("SELECT id FROM cve ORDER BY CAST(SUBSTR(id, 5, 4) AS INTEGER) DESC, CAST(SUBSTR(id, 10) AS INTEGER) DESC LIMIT 1")
            newest_cve = cursor.fetchone()
            
            # CVE за последние 24 часа
            cursor.execute("SELECT COUNT(*) FROM cve WHERE published_date >= datetime('now', '-1 day')")
            last_24h = cursor.fetchone()[0]
            
            # CVE за последнюю неделю
            cursor.execute("SELECT COUNT(*) FROM cve WHERE published_date >= datetime('now', '-7 days')")
            last_week = cursor.fetchone()[0]
            
            conn.close()
            
            # Форматируем дату последнего обновления
            if last_update:
                try:
                    last_update_dt = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
                    last_update_str = last_update_dt.strftime('%d.%m.%Y %H:%M UTC')
                except:
                    last_update_str = last_update
            else:
                last_update_str = "Неизвестно"
            
            # Форматируем средний EPSS
            avg_epss_str = f"{avg_epss:.4f}" if avg_epss is not None else "N/A"
            
            # Формируем ответ
            stats_text = f"""
📊 **Статистика базы данных CVE**

**Общая информация:**
• Всего CVE: {total_cve:,}
• Критических (9.0+): {critical_cve:,} 🔴
• Высоких (7.0-8.9): {high_cve:,} 🟠
• Средних (4.0-6.9): {medium_cve:,} 🟡
• Низких (<4.0): {low_cve:,} 🟢
• Без CVSS: {no_cvss:,} ⚪

**EPSS (Exploit Prediction):**
• С EPSS: {with_epss:,} ({with_epss/total_cve*100:.1f}%)
• Высокий EPSS (>0.5): {high_epss:,} 🚨
• Очень высокий EPSS (>0.8): {very_high_epss:,} ⚠️
• Средний EPSS: {avg_epss_str}

**Последние обновления:**
• Последнее обновление: {last_update_str}
• Последний CVE (по дате): {last_cve[0] if last_cve else 'Неизвестно'}
• Самый новый CVE ID: {newest_cve[0] if newest_cve else 'Неизвестно'}
• За 24 часа: {last_24h:,} новых CVE
• За неделю: {last_week:,} новых CVE
            """
            
            await message.answer(stats_text, parse_mode="Markdown", disable_web_page_preview=True)
            
        except Exception as e:
            logger.error(f"Error handling stats command: {e}")
            await message.answer("❌ Ошибка при получении статистики.", disable_web_page_preview=True)
    
    async def handle_help_command(self, message: types.Message):
        """Handle /help command"""
        help_text = """
🤖 **CVE Info Bot - Справка**

**Основные команды:**
• `/cve CVE-YYYY-NNNNN` - Информация о конкретной CVE
• `/vendor <название>` - Поиск CVE по вендору/продукту
• `/top` - Топ-5 критических CVE с интерактивными кнопками
• `/stats` - Статистика базы данных
• `/help` - Эта справка

**Автоматические функции:**
• Бот автоматически комментирует посты в каналах, содержащие CVE
• Используйте @cveinfobot для inline-поиска
• Автоматическое обновление CVE каждый час
• Интерактивные кнопки для детального просмотра CVE

**Примеры:**
• `/cve CVE-2023-1234`
• `/vendor microsoft`
• `/vendor apache`
• `/stats`

**AI-анализ:**
Бот использует локальную модель Ollama для генерации объяснений и рекомендаций по CVE.

**EPSS оценки:**
Бот показывает EPSS (Exploit Prediction Scoring System) оценки для оценки вероятности эксплуатации уязвимостей в реальных атаках.
        """
        await message.answer(help_text, parse_mode="Markdown", disable_web_page_preview=True)
