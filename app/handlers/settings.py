#File: app/handlers/settings.py

"""
Обробники для налаштувань
"""
import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile

from app.keyboards.inline import (
    get_settings_menu,
    get_reminder_settings,
    get_currency_keyboard,
    get_export_format_keyboard
)
from app.services.sheets_service import sheets_service
from app.services.export_service import export_service
from app.utils.helpers import filter_transactions_by_period

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "⚙️ Налаштування")
async def show_settings(message: Message):
    """Показує меню налаштувань"""
    await message.answer(
        "⚙️ <b>Налаштування бота</b>\n\n"
        "Обери, що хочеш налаштувати:",
        reply_markup=get_settings_menu()
    )


@router.callback_query(F.data == "how_it_works")
async def show_how_it_works(callback: CallbackQuery):
    """Показує інформацію про роботу бота"""
    text = (
        "📚 <b>Як працює бот</b>\n\n"

        "<b>1. Додавання транзакцій</b>\n"
        "Просто пиши суму та опис:\n"
        "<code>150 їжа</code> або <code>5000 зарплата</code>\n\n"

        "<b>2. Автоматична категоризація</b>\n"
        "Бот автоматично визначає категорію з твого опису\n\n"

        "<b>3. Статистика та аналітика</b>\n"
        "Переглядай витрати за різні періоди,\n"
        "отримуй детальні звіти з графіками\n\n"

        "<b>4. AI-аналіз</b>\n"
        "Штучний інтелект аналізує твої фінанси\n"
        "та дає персональні рекомендації\n\n"

        "<b>5. Підписки</b>\n"
        "Додавай регулярні платежі та\n"
        "отримуй нагадування вчасно\n\n"

        "<b>6. Експорт даних</b>\n"
        "Завантажуй свої дані у CSV, Excel або PDF\n\n"

        "Всі дані зберігаються в Google Sheets\n"
        "і доступні тільки тобі! 🔒"
    )

    await callback.message.edit_text(text, reply_markup=get_settings_menu())
    await callback.answer()


@router.callback_query(F.data == "reminders_menu")
async def show_reminders_menu(callback: CallbackQuery):
    """Показує меню нагадувань"""
    user_id = callback.from_user.id
    enabled_users = sheets_service.get_reminder_users()

    status = "✅ Увімкнено" if user_id in enabled_users else "❌ Вимкнено"

    text = (
        "🔔 <b>Налаштування нагадувань</b>\n\n"
        f"<b>Статус:</b> {status}\n\n"
        "Нагадування допоможуть не забувати\n"
        "записувати витрати щодня.\n\n"
        "Ти отримаєш 3 нагадування:\n"
        "• 09:00 - Ранок\n"
        "• 13:00 - Обід\n"
        "• 20:00 - Вечір"
    )

    await callback.message.edit_text(text, reply_markup=get_reminder_settings())
    await callback.answer()


@router.callback_query(F.data == "enable_reminders")
async def enable_reminders(callback: CallbackQuery):
    """Вмикає нагадування"""
    sheets_service.add_reminder_user(callback.from_user.id)

    await callback.answer("✅ Нагадування увімкнено!", show_alert=True)
    await show_reminders_menu(callback)


@router.callback_query(F.data == "disable_reminders")
async def disable_reminders(callback: CallbackQuery):
    """Вимикає нагадування"""
    sheets_service.remove_reminder_user(callback.from_user.id)

    await callback.answer("❌ Нагадування вимкнено", show_alert=True)
    await show_reminders_menu(callback)


@router.callback_query(F.data == "export_data")
async def show_export_menu(callback: CallbackQuery):
    """Показує меню експорту"""
    await callback.message.edit_text(
        "📥 <b>Експорт даних</b>\n\n"
        "Обери формат для завантаження своїх даних:",
        reply_markup=get_export_format_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("export_"))
async def process_export(callback: CallbackQuery):
    """Обробляє експорт даних"""
    format_type = callback.data.split("_")[1]
    nickname = callback.from_user.username or "anonymous"

    await callback.message.edit_text("⏳ Готую файл для завантаження...")

    try:
        transactions = sheets_service.get_all_transactions(nickname)
        balance, currency = sheets_service.get_current_balance(nickname)

        if not transactions:
            await callback.message.edit_text(
                "❌ Немає даних для експорту",
                reply_markup=get_settings_menu()
            )
            return

        if format_type == "csv":
            file_buffer = export_service.export_to_csv(transactions)
            filename = f"budget_{nickname}_{datetime.now().strftime('%Y%m%d')}.csv"

        elif format_type == "excel":
            file_buffer = export_service.export_to_excel(transactions)
            filename = f"budget_{nickname}_{datetime.now().strftime('%Y%m%d')}.xlsx"

        elif format_type == "pdf":
            file_buffer = export_service.export_to_pdf(
                transactions, nickname, balance, currency
            )
            filename = f"budget_{nickname}_{datetime.now().strftime('%Y%m%d')}.pdf"
        else:
            await callback.answer("❌ Невідомий формат", show_alert=True)
            return

        # Створюємо BufferedInputFile для відправки
        document = BufferedInputFile(file_buffer.getvalue(), filename=filename)

        await callback.message.answer_document(
            document=document,
            caption=f"📊 Твій фінансовий звіт у форматі {format_type.upper()}"
        )

        await callback.message.edit_text(
            "✅ Файл успішно створено!",
            reply_markup=get_settings_menu()
        )

        logger.info(f"Exported {format_type} for {nickname}")

    except Exception as e:
        logger.error(f"Export error: {e}", exc_info=True)
        await callback.message.edit_text(
            "❌ Помилка при створенні файлу",
            reply_markup=get_settings_menu()
        )


@router.callback_query(F.data == "back_to_settings")
async def back_to_settings(callback: CallbackQuery):
    """Повернення до налаштувань"""
    await show_settings(callback.message)
    await callback.answer()


def register_handlers(router_main):
    """Реєструє хендлери налаштувань"""
    router_main.include_router(router)