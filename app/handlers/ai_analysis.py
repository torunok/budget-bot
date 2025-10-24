#FILE: app/handlers/ai_analysis.py#

"""
Обробники для AI-аналізу
"""
import logging
from aiogram import Router, F
from aiogram.types import Message

from app.services.sheets_service import sheets_service
from app.services.ai_service import ai_service
from app.utils.formatters import split_long_message

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "🤖 AI Аналіз")
async def ai_analysis_handler(message: Message):
    """Виконує AI-аналіз фінансів"""
    nickname = message.from_user.username or "anonymous"
    
    waiting_msg = await message.answer(
        "🤖 <b>Аналізую твої фінанси...</b>\n\n"
        "Це може зайняти 10-30 секунд.\n"
        "Штучний інтелект вивчає всі твої транзакції 📊"
    )
    
    try:
        transactions = sheets_service.get_all_transactions(nickname)
        
        if not transactions or len(transactions) < 5:
            await waiting_msg.edit_text(
                "❌ Недостатньо даних для аналізу.\n\n"
                "Додай хоча б 5 транзакцій, щоб отримати якісний аналіз."
            )
            return
        
        # Отримуємо AI-аналіз
        analysis = await ai_service.analyze_finances(transactions)
        
        # Розбиваємо на частини, якщо довгий
        messages = split_long_message(analysis)
        
        await waiting_msg.delete()
        
        for idx, msg_text in enumerate(messages):
            if idx == 0:
                await message.answer(f"🤖 <b>AI Аналіз твоїх фінансів</b>\n\n{msg_text}")
            else:
                await message.answer(msg_text)
        
        logger.info(f"AI analysis completed for {nickname}")
        
    except Exception as e:
        logger.error(f"AI analysis error: {e}", exc_info=True)
        await waiting_msg.edit_text(
            "❌ На жаль, виникла помилка при аналізі.\n"
            "Спробуй пізніше або звернися в підтримку."
        )
