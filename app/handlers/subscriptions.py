"""
Обробники розділу «Підписки».
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional, Any

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.core.states import SubscriptionState
from app.services.sheets_service import sheets_service
from app.keyboards.inline import get_subscriptions_menu
from app.keyboards.reply import get_main_menu_keyboard
from app.utils.validators import validate_amount, validate_date, validate_category
from app.utils.formatters import format_currency, format_date, split_long_message
from app.utils.helpers import build_sheet_context

router = Router()
logger = logging.getLogger(__name__)

SUBSCRIPTION_NOTE_PREFIX = "Підписка: "
CANCEL_COMMANDS = {"0", "відміна", "скасувати", "cancel", "стоп"}


# ----------------------- ДОПОМІЖНІ ФУНКЦІЇ ----------------------- #

def _subscription_name(sub: Dict) -> str:
    name = (sub.get("subscription_name") or "").strip()
    if name:
        return name
    note = (sub.get("note") or "").strip()
    if note.startswith(SUBSCRIPTION_NOTE_PREFIX):
        return note[len(SUBSCRIPTION_NOTE_PREFIX):].strip() or "Без назви"
    return note or "Без назви"


def _subscription_currency(sub: Dict) -> str:
    return sub.get("currency") or "UAH"


def _build_subscription_summary(sub: Dict) -> str:
    amount = abs(float(sub.get("amount", 0) or 0))
    currency = _subscription_currency(sub)
    category = sub.get("category", "Інше")
    due_raw = sub.get("subscription_due_date") or sub.get("date")
    due_date = format_date(due_raw) if due_raw else "Не вказано"
    return (
        f"📝 Назва: <b>{_subscription_name(sub)}</b>\n"
        f"💰 Сума: <b>{format_currency(amount, currency)}</b>\n"
        f"📂 Категорія: <b>{category}</b>\n"
        f"📅 Дата списання: <b>{due_date}</b>"
    )


def _edit_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Назва", callback_data="edit_sub_field:name"),
                InlineKeyboardButton(text="💰 Сума", callback_data="edit_sub_field:amount"),
            ],
            [
                InlineKeyboardButton(text="📂 Категорія", callback_data="edit_sub_field:category"),
                InlineKeyboardButton(text="📅 Дата", callback_data="edit_sub_field:date"),
            ],
            [
                InlineKeyboardButton(text="🗑️ Видалити", callback_data="edit_sub_field:delete"),
                InlineKeyboardButton(text="✅ Готово", callback_data="edit_sub_field:finish"),
            ],
            [InlineKeyboardButton(text="↩️ До списку", callback_data="edit_sub_field:back")],
        ]
    )


def _build_list_text(subscriptions: List[Dict]) -> str:
    lines = ["📄 <b>Оберіть підписку для редагування:</b>"]
    for idx, sub in enumerate(subscriptions, start=1):
        amount = abs(float(sub.get("amount", 0) or 0))
        currency = _subscription_currency(sub)
        due_raw = sub.get("subscription_due_date") or sub.get("date")
        due = format_date(due_raw) if due_raw else "Не вказано"
        lines.append(
            f"\n{idx}. { _subscription_name(sub) }\n"
            f"   💰 {format_currency(amount, currency)} | 📅 {due}"
        )
    lines.append("\nНадішліть номер або 0 для скасування.")
    return "\n".join(lines)


# ----------------------- ДОДАВАННЯ ПІДПИСОК ----------------------- #

@router.message(F.text == "📝 Підписки")
async def show_subscriptions_menu(message: Message):
    await message.answer(
        "📝 <b>Управління підписками</b>\n\n"
        "• Додавайте регулярні витрати\n"
        "• Переглядайте та редагуйте активні підписки\n"
        "• Дозволяйте боту автоматично списувати кошти в день платежу",
        reply_markup=get_subscriptions_menu(),
    )


@router.callback_query(F.data == "add_subscription")
async def add_subscription_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    msg = await callback.message.answer(
        "🆕 <b>Додавання підписки</b>\n\n"
        "Крок 1/4: введіть назву підписки\n"
        "Наприклад: <code>Netflix</code>"
    )
    await state.update_data(last_bot_message_id=msg.message_id)
    await state.set_state(SubscriptionState.add_name)
    await callback.answer()


@router.message(SubscriptionState.add_name)
async def process_subscription_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) > 50:
        await message.reply("❌ Назва не може перевищувати 50 символів.")
        return
    await state.update_data(name=name)
    data = await state.get_data()
    try:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=data.get("last_bot_message_id"),
            text=(
                f"🆕 <b>Додавання підписки</b>\n\n"
                f"Назва: <b>{name}</b>\n\n"
                "Крок 2/4: введіть суму платежу\n"
                "Наприклад: <code>199</code>"
            ),
        )
    except Exception:
        pass
    await state.set_state(SubscriptionState.add_amount)


@router.message(SubscriptionState.add_amount)
async def process_subscription_amount(message: Message, state: FSMContext):
    is_valid, amount, error = validate_amount(message.text)
    if not is_valid:
        await message.reply(f"❌ {error}")
        return
    data = await state.get_data()
    await state.update_data(amount=amount)
    try:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=data.get("last_bot_message_id"),
            text=(
                "🆕 <b>Додавання підписки</b>\n\n"
                f"Назва: <b>{data.get('name')}</b>\n"
                f"Сума: <b>{format_currency(amount)}</b>\n\n"
                "Крок 3/4: введіть категорію\n"
                "Наприклад: <code>Розваги</code>"
            ),
        )
    except Exception:
        pass
    await state.set_state(SubscriptionState.add_category)


@router.message(SubscriptionState.add_category)
async def process_subscription_category(message: Message, state: FSMContext):
    is_valid, category, error = validate_category(message.text)
    if not is_valid:
        await message.reply(f"❌ {error}")
        return
    await state.update_data(category=category)
    data = await state.get_data()
    try:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=data.get("last_bot_message_id"),
            text=(
                "🆕 <b>Додавання підписки</b>\n\n"
                f"Назва: <b>{data.get('name')}</b>\n"
                f"Сума: <b>{format_currency(data.get('amount'))}</b>\n"
                f"Категорія: <b>{category}</b>\n\n"
                "Крок 4/4: введіть дату наступного списання (ДД.ММ.РРРР)"
            ),
        )
    except Exception:
        pass
    await state.set_state(SubscriptionState.add_date)


@router.message(SubscriptionState.add_date)
async def process_subscription_date(message: Message, state: FSMContext):
    is_valid, date_obj, error = validate_date(message.text)
    if not is_valid:
        await message.reply(f"❌ {error}")
        return
    if date_obj.date() < datetime.now().date():
        await message.reply("❌ Дата не може бути в минулому.")
        return

    data = await state.get_data()
    ctx = build_sheet_context(message.from_user)
    formatted_date = date_obj.strftime("%d.%m.%Y")
    await state.update_data(subscription_date=formatted_date)

    try:
        sheets_service.append_transaction(
            user_id=message.from_user.id,
            nickname=ctx.sheet_title,
            amount=-abs(data.get("amount")),
            category=data.get("category"),
            note=f"{SUBSCRIPTION_NOTE_PREFIX}{data.get('name')}",
            is_subscription=True,
            subscription_name=data.get("name"),
            subscription_due_date=formatted_date,
            legacy_titles=ctx.legacy_titles,
            user_display_name=ctx.display_name,
        )
        await message.answer(
            "✅ <b>Підписку додано!</b>\n\n" + _build_subscription_summary({
                "subscription_name": data.get("name"),
                "amount": -abs(data.get("amount")),
                "currency": "UAH",
                "category": data.get("category"),
                "subscription_due_date": formatted_date,
            })
        )
        await message.answer("Обирай наступну дію:", reply_markup=get_main_menu_keyboard())
        await state.clear()
    except Exception as exc:
        logger.error("Error adding subscription: %s", exc, exc_info=True)
        await message.reply("❌ Сталася помилка при додаванні підписки.")


# ----------------------- ПЕРЕГЛЯД ----------------------- #

@router.callback_query(F.data == "view_subscriptions")
async def view_subscriptions(callback: CallbackQuery):
    ctx = build_sheet_context(callback.from_user)
    try:
        subscriptions = sheets_service.get_subscriptions(ctx.sheet_title, ctx.legacy_titles)
    except Exception as exc:
        logger.error("Error loading subscriptions: %s", exc, exc_info=True)
        await callback.answer("❌ Не вдалося завантажити підписки", show_alert=True)
        return

    if not subscriptions:
        await callback.message.edit_text(
            "📝 У тебе поки що немає збережених підписок.\n\n"
            "Скористайся кнопкою «Додати», щоб я міг нагадувати про платежі!",
            reply_markup=get_subscriptions_menu(),
        )
        await callback.answer()
        return

    lines = ["📄 <b>Твої підписки:</b>"]
    totals: Dict[str, float] = {}
    for idx, sub in enumerate(subscriptions, start=1):
        amount = abs(float(sub.get("amount", 0) or 0))
        currency = _subscription_currency(sub)
        category = sub.get("category", "Інше")
        due_raw = sub.get("subscription_due_date") or sub.get("date")
        due_date = format_date(due_raw) if due_raw else "Не вказано"
        totals[currency] = totals.get(currency, 0) + amount
        lines.append(
            f"\n{idx}. <b>{_subscription_name(sub)}</b>\n"
            f"   💰 {format_currency(amount, currency)} | 📂 {category}\n"
            f"   📅 Наступне списання: {due_date}"
        )

    if totals:
        lines.append("\n💳 <b>Сумарна вартість:</b>")
        for currency, total in totals.items():
            lines.append(f"   • {format_currency(total, currency)}")

    chunks = split_long_message("\n".join(lines))
    await callback.message.edit_text(chunks[0], reply_markup=get_subscriptions_menu())
    for chunk in chunks[1:]:
        await callback.message.answer(chunk)
    await callback.answer()


# ----------------------- РЕДАГУВАННЯ ----------------------- #

@router.callback_query(F.data == "edit_subscriptions")
async def edit_subscriptions_menu(callback: CallbackQuery, state: FSMContext):
    ctx = build_sheet_context(callback.from_user)
    try:
        subscriptions = sheets_service.get_subscriptions(ctx.sheet_title, ctx.legacy_titles)
    except Exception as exc:
        logger.error("Error loading subscriptions for edit: %s", exc, exc_info=True)
        await callback.answer("❌ Не вдалося завантажити підписки", show_alert=True)
        return

    if not subscriptions:
        await callback.answer("Спочатку додай хоча б одну підписку.", show_alert=True)
        return

    await state.update_data(
        editable_subscriptions=subscriptions,
        selected_subscription_index=None,
        sheet_title=ctx.sheet_title,
        legacy_titles=ctx.legacy_titles,
    )
    await state.set_state(SubscriptionState.select_to_edit)
    await callback.message.answer(_build_list_text(subscriptions))
    await callback.answer()


@router.message(SubscriptionState.select_to_edit)
async def select_subscription_to_edit(message: Message, state: FSMContext):
    text = message.text.strip()
    if text.lower() in CANCEL_COMMANDS:
        await state.clear()
        await message.answer("Редагування скасовано.", reply_markup=get_main_menu_keyboard())
        return
    if not text.isdigit():
        await message.reply("Введи номер зі списку або 0 для скасування.")
        return

    idx = int(text) - 1
    data = await state.get_data()
    subscriptions = data.get("editable_subscriptions") or []
    if idx < 0 or idx >= len(subscriptions):
        await message.reply("Такої підписки немає. Спробуй ще раз.")
        return

    await state.update_data(selected_subscription_index=idx)
    await message.answer(
        "Що змінюємо?\n\n" + _build_subscription_summary(subscriptions[idx]),
        reply_markup=_edit_keyboard(),
    )


@router.callback_query(F.data.startswith("edit_sub_field:"))
async def handle_edit_action(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":", 1)[1]
    data = await state.get_data()
    subscriptions = data.get("editable_subscriptions") or []
    idx = data.get("selected_subscription_index")
    if idx is None or idx < 0 or idx >= len(subscriptions):
        await callback.answer("Спершу обери підписку зі списку.", show_alert=True)
        return

    if action == "back":
        await state.set_state(SubscriptionState.select_to_edit)
        await callback.message.answer(_build_list_text(subscriptions))
        await callback.answer()
        return

    if action == "finish":
        await state.clear()
        await callback.message.answer("Редагування завершено.", reply_markup=get_main_menu_keyboard())
        await callback.answer()
        return

    if action == "delete":
        ctx_title = data.get("sheet_title")
        legacy = data.get("legacy_titles")
        row_index = subscriptions[idx].get("_row")
        try:
            sheets_service.delete_transaction(ctx_title, row_index, legacy)
            updated = sheets_service.get_subscriptions(ctx_title, legacy)
        except Exception as exc:
            logger.error("Error deleting subscription: %s", exc, exc_info=True)
            await callback.answer("❌ Не вдалося видалити.", show_alert=True)
            return
        if updated:
            await state.update_data(
                editable_subscriptions=updated,
                selected_subscription_index=None,
            )
            await state.set_state(SubscriptionState.select_to_edit)
            await callback.message.answer("Підписку видалено.\n\n" + _build_list_text(updated))
        else:
            await state.clear()
            await callback.message.answer("Підписок більше немає.", reply_markup=get_main_menu_keyboard())
        await callback.answer("Підписку видалено")
        return

    prompts = {
        "name": "Введи нову назву або 0 для скасування.",
        "amount": "Введи нову суму (лише число). 0 для скасування.",
        "category": "Введи нову категорію. 0 — скасувати.",
        "date": "Введи нову дату у форматі ДД.ММ.РРРР або 0 для скасування.",
    }
    state_map = {
        "name": SubscriptionState.edit_name,
        "amount": SubscriptionState.edit_amount,
        "category": SubscriptionState.edit_category,
        "date": SubscriptionState.edit_date,
    }
    next_state = state_map.get(action)
    if not next_state:
        await callback.answer()
        return
    await state.set_state(next_state)
    await callback.message.answer(prompts[action])
    await callback.answer()


async def _apply_subscription_updates(
    state: FSMContext,
    updates: Dict[str, Any],
    recalc: bool,
) -> Optional[Dict]:
    data = await state.get_data()
    subscriptions = data.get("editable_subscriptions") or []
    idx = data.get("selected_subscription_index")
    sheet_title = data.get("sheet_title")
    legacy = data.get("legacy_titles")
    if idx is None or idx < 0 or idx >= len(subscriptions):
        return None
    row_index = subscriptions[idx].get("_row")
    if not row_index:
        return None

    sheets_service.update_transaction_fields(
        sheet_title,
        int(row_index),
        updates,
        legacy_titles=legacy,
        recalculate=recalc,
    )
    updated = sheets_service.get_subscriptions(sheet_title, legacy)
    new_idx = min(idx, len(updated) - 1) if updated else None
    await state.update_data(
        editable_subscriptions=updated,
        selected_subscription_index=new_idx,
    )
    if new_idx is None or not updated:
        return None
    return updated[new_idx]


@router.message(SubscriptionState.edit_name)
async def edit_subscription_name(message: Message, state: FSMContext):
    text = message.text.strip()
    if text.lower() in CANCEL_COMMANDS:
        await state.set_state(SubscriptionState.select_to_edit)
        await message.answer("Зміну назви скасовано.")
        return
    if not text:
        await message.reply("Назва не може бути порожньою.")
        return
    if len(text) > 50:
        await message.reply("Максимум 50 символів.")
        return
    updated = await _apply_subscription_updates(
        state,
        {'subscription_name': text, 'note': f"{SUBSCRIPTION_NOTE_PREFIX}{text}"},
        recalc=False,
    )
    if updated:
        await state.set_state(SubscriptionState.select_to_edit)
        await message.answer("Назву оновлено.\n\n" + _build_subscription_summary(updated), reply_markup=_edit_keyboard())


@router.message(SubscriptionState.edit_amount)
async def edit_subscription_amount(message: Message, state: FSMContext):
    text = message.text.strip()
    if text.lower() in CANCEL_COMMANDS:
        await state.set_state(SubscriptionState.select_to_edit)
        await message.answer("Зміну суми скасовано.")
        return
    is_valid, amount, error = validate_amount(text)
    if not is_valid:
        await message.reply(f"❌ {error}")
        return
    normalized = -abs(amount)
    updated = await _apply_subscription_updates(
        state,
        {'amount': normalized},
        recalc=True,
    )
    if updated:
        await state.set_state(SubscriptionState.select_to_edit)
        await message.answer("Суму оновлено.\n\n" + _build_subscription_summary(updated), reply_markup=_edit_keyboard())


@router.message(SubscriptionState.edit_category)
async def edit_subscription_category(message: Message, state: FSMContext):
    text = message.text.strip()
    if text.lower() in CANCEL_COMMANDS:
        await state.set_state(SubscriptionState.select_to_edit)
        await message.answer("Зміну категорії скасовано.")
        return
    is_valid, category, error = validate_category(text)
    if not is_valid:
        await message.reply(f"❌ {error}")
        return
    updated = await _apply_subscription_updates(
        state,
        {'category': category},
        recalc=False,
    )
    if updated:
        await state.set_state(SubscriptionState.select_to_edit)
        await message.answer("Категорію оновлено.\n\n" + _build_subscription_summary(updated), reply_markup=_edit_keyboard())


@router.message(SubscriptionState.edit_date)
async def edit_subscription_date(message: Message, state: FSMContext):
    text = message.text.strip()
    if text.lower() in CANCEL_COMMANDS:
        await state.set_state(SubscriptionState.select_to_edit)
        await message.answer("Зміну дати скасовано.")
        return
    is_valid, date_obj, error = validate_date(text)
    if not is_valid:
        await message.reply(f"❌ {error}")
        return
    if date_obj.date() < datetime.now().date():
        await message.reply("❌ Дата не може бути в минулому.")
        return
    formatted = date_obj.strftime("%d.%m.%Y")
    updated = await _apply_subscription_updates(
        state,
        {'subscription_due_date': formatted},
        recalc=False,
    )
    if updated:
        await state.set_state(SubscriptionState.select_to_edit)
        await message.answer("Дату оновлено.\n\n" + _build_subscription_summary(updated), reply_markup=_edit_keyboard())
