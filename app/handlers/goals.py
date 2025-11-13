# ============================================
# FILE: app/handlers/goals.py (NEW)
# ============================================
"""
Обробники для управління цілями заощаджень
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.core.states import BudgetGoalState
from app.services.sheets_service import sheets_service
from app.keyboards.reply import get_main_menu_keyboard
from app.utils.validators import validate_amount, validate_date
from app.utils.formatters import format_currency, format_date

logger = logging.getLogger(__name__)
router = Router()


# ==================== ГОЛОВНЕ МЕНЮ ЦІЛЕЙ ====================

def get_goals_menu() -> InlineKeyboardMarkup:
    """Меню управління цілями"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Додати ціль", callback_data="add_goal"),
            InlineKeyboardButton(text="📊 Мої цілі", callback_data="view_goals")
        ],
        [
            InlineKeyboardButton(text="💰 Внести гроші", callback_data="contribute_to_goal"),
            InlineKeyboardButton(text="📈 Прогрес", callback_data="goals_progress")
        ],
        [
            InlineKeyboardButton(text="✏️ Редагувати", callback_data="edit_goals"),
            InlineKeyboardButton(text="🗑️ Видалити", callback_data="delete_goals")
        ]
    ])


@router.message(F.text == "🎯 Цілі")
async def show_goals_menu(message: Message):
    """Показує меню цілей"""
    nickname = message.from_user.username or "anonymous"
    
    try:
        goals = sheets_service.get_goals(nickname)
        active_goals = len([g for g in goals if not is_goal_completed(g)])
        
        text = (
            "🎯 <b>Цілі заощаджень</b>\n\n"
            f"📊 Активних цілей: {active_goals}\n\n"
            "Тут ти можеш:\n"
            "• Встановлювати фінансові цілі\n"
            "• Відстежувати прогрес\n"
            "• Робити внески\n"
            "• Отримувати мотивацію!\n\n"
            "Обирай дію:"
        )
        
        await message.answer(text, reply_markup=get_goals_menu())
        
    except Exception as e:
        logger.error(f"Error showing goals menu: {e}", exc_info=True)
        await message.answer("❌ Помилка завантаження цілей")


# ==================== ДОДАВАННЯ НОВОЇ ЦІЛІ ====================

@router.callback_query(F.data == "add_goal")
async def add_goal_start(callback: CallbackQuery, state: FSMContext):
    """Початок додавання цілі"""
    await callback.message.edit_text(
        "🎯 <b>Додавання нової цілі</b>\n\n"
        "Крок 1/3: Введи назву цілі\n\n"
        "Наприклад:\n"
        "• <code>Відпустка в Європі</code>\n"
        "• <code>Новий ноутбук</code>\n"
        "• <code>Подушка безпеки</code>"
    )
    await state.set_state(BudgetGoalState.set_goal_name)
    await callback.answer()


@router.message(BudgetGoalState.set_goal_name)
async def process_goal_name(message: Message, state: FSMContext):
    """Обробка назви цілі"""
    name = message.text.strip()
    
    if len(name) > 100:
        await message.reply("❌ Назва занадто довга. Максимум 100 символів.")
        return
    
    await state.update_data(goal_name=name)
    
    await message.answer(
        f"🎯 <b>Додавання цілі: {name}</b>\n\n"
        f"Крок 2/3: Яка сума потрібна?\n\n"
        f"Введи ціль у гривнях:\n"
        f"Наприклад: <code>50000</code>"
    )
    
    await state.set_state(BudgetGoalState.set_goal_amount)


@router.message(BudgetGoalState.set_goal_amount)
async def process_goal_amount(message: Message, state: FSMContext):
    """Обробка суми цілі"""
    is_valid, amount, error = validate_amount(message.text)
    
    if not is_valid:
        await message.reply(f"❌ {error}")
        return
    
    data = await state.get_data()
    goal_name = data.get('goal_name')
    
    await state.update_data(goal_amount=amount)
    
    await message.answer(
        f"🎯 <b>Ціль: {goal_name}</b>\n"
        f"💰 Сума: {format_currency(amount)}\n\n"
        f"Крок 3/3: До якої дати хочеш досягти?\n\n"
        f"Введи дату у форматі <code>день.місяць.рік</code>\n"
        f"Наприклад: <code>31.12.2025</code>\n\n"
        f"Або відправ <code>-</code>, якщо дедлайн не важливий"
    )
    
    await state.set_state(BudgetGoalState.set_goal_deadline)


@router.message(BudgetGoalState.set_goal_deadline)
async def process_goal_deadline(message: Message, state: FSMContext):
    """Обробка дедлайну цілі"""
    deadline_str = message.text.strip()
    deadline = None
    
    if deadline_str != "-":
        is_valid, date_obj, error = validate_date(deadline_str)
        
        if not is_valid:
            await message.reply(f"❌ {error}")
            return
        
        if date_obj < datetime.now():
            await message.reply("❌ Дата не може бути в минулому")
            return
        
        deadline = date_obj.strftime("%Y-%m-%d")
    
    data = await state.get_data()
    goal_name = data.get('goal_name')
    goal_amount = data.get('goal_amount')
    nickname = message.from_user.username or "anonymous"
    
    try:
        # Додаємо ціль
        sheets_service.add_goal(
            nickname=nickname,
            goal_name=goal_name,
            target_amount=goal_amount,
            deadline=deadline,
            current_amount=0
        )
        
        # Розраховуємо скільки днів залишилось
        days_left = ""
        if deadline:
            deadline_date = datetime.strptime(deadline, "%Y-%m-%d")
            days = (deadline_date - datetime.now()).days
            days_left = f"\n⏰ Залишилось днів: {days}"
        
        human_deadline = human_goal_deadline(deadline)
        await message.answer(
            f"✅ <b>Ціль створена!</b>\n\n"
            f"🎯 Назва: {goal_name}\n"
            f"💰 Сума: {format_currency(goal_amount)}\n"
            f"📅 Дедлайн: {human_deadline}"
            f"{days_left}\n\n"
            f"Тримайся плану і все вийде! 💪",
            reply_markup=get_main_menu_keyboard()
        )
        
        await state.clear()
        
        logger.info(f"Goal created: {goal_name} for {nickname}")
        
    except Exception as e:
        logger.error(f"Error creating goal: {e}", exc_info=True)
        await message.reply("❌ Помилка при створенні цілі")


# ==================== ПЕРЕГЛЯД ЦІЛЕЙ ====================

@router.callback_query(F.data == "view_goals")
async def view_goals(callback: CallbackQuery):
    """Показує всі цілі користувача"""
    nickname = callback.from_user.username or "anonymous"
    
    try:
        goals = sheets_service.get_goals(nickname)
        _, currency = sheets_service.get_current_balance(nickname)
        currency = currency or "UAH"
        
        if not goals:
            await callback.message.edit_text(
                "🎯 У тебе поки немає цілей.\n\n"
                "Створи першу ціль, щоб почати заощаджувати!",
                reply_markup=get_goals_menu()
            )
            await callback.answer()
            return
        
        text_lines = ["🎯 <b>Твої фінансові цілі:</b>"]
        
        for goal in goals:
            text_lines.append(format_goal_display(goal, currency))
        
        await callback.message.edit_text(
            "\n\n".join(text_lines),
            reply_markup=get_goals_menu()
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error viewing goals: {e}", exc_info=True)
        await callback.answer("❌ Помилка", show_alert=True)


def create_progress_bar(percentage: float, length: int = 10) -> str:
    """Створює прогрес-бар"""
    capped = max(0.0, min(percentage, 100.0))
    filled = int(round(capped / 100 * length))
    filled = min(length, filled)
    empty = length - filled
    return "▪️" * filled + "▫️" * empty


def is_goal_completed(goal: Dict) -> bool:
    """Повертає True, якщо ціль позначена виконаною"""
    value = goal.get('completed', False)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y", "completed"}


def get_goal_amounts(goal: Dict) -> tuple:
    """Повертає (target, current, remaining, percentage)"""
    target = float(goal.get('target_amount', 0) or 0)
    current = float(goal.get('current_amount', 0) or 0)
    remaining = max(target - current, 0)
    percentage = (current / target * 100) if target > 0 else 0
    return target, current, remaining, percentage


def parse_goal_deadline(goal: Dict) -> Optional[datetime]:
    """Парсить дедлайн цілі"""
    deadline = goal.get('deadline')
    if not deadline or deadline in {"Без дедлайну", "-"}:
        return None
    try:
        return datetime.strptime(deadline, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def format_deadline_hint(goal: Dict) -> str:
    """Формує текст про дедлайн"""
    deadline = parse_goal_deadline(goal)
    if not deadline:
        return "⏰ Без дедлайну"
    days_left = (deadline - datetime.now()).days
    if days_left > 1:
        return f"⏰ До дедлайну: {days_left} дн."
    if days_left == 1:
        return "⏰ Залишився 1 день!"
    if days_left == 0:
        return "⏰ Дедлайн сьогодні!"
    return "⏰ Дедлайн прострочено"


def goal_deadline_sort_key(goal: Dict) -> datetime:
    """Ключ сортування по дедлайну"""
    deadline = parse_goal_deadline(goal)
    return deadline or datetime.max


def human_goal_deadline(deadline: Optional[str]) -> str:
    """Повертає людинозрозуміле значення дедлайну"""
    if not deadline or deadline in {"Без дедлайну", "-", "без обмежень"}:
        return "без обмежень"
    return format_date(deadline) or deadline


def get_goal_days_left(goal: Dict) -> str:
    """Повертає текст із залишком днів"""
    deadline = parse_goal_deadline(goal)
    if not deadline:
        return "без дедлайну"
    days_left = (deadline - datetime.now()).days
    if days_left > 1:
        return f"{days_left} днів"
    if days_left == 1:
        return "1 день"
    if days_left == 0:
        return "дедлайн сьогодні"
    return "просрочено"


def format_goal_display(goal: Dict, currency: str) -> str:
    """Форматує відображення цілі у списку"""
    name = goal.get('goal_name', 'Без назви')
    target, current, _, percentage = get_goal_amounts(goal)
    progress_bar = create_progress_bar(percentage)
    days_left_text = get_goal_days_left(goal)
    deadline_text = human_goal_deadline(goal.get('deadline'))
    
    lines = [
        f"🎯 Ціль: {name}",
        f"💰 Прогрес: {format_currency(current, currency)} / {format_currency(target, currency)} ({percentage:.0f}%)",
        f"📊 Прогрес-бар: {progress_bar}",
        f"⏰ Залишилось: {days_left_text}",
        f"📅 Дедлайн: {deadline_text}"
    ]
    
    if is_goal_completed(goal):
        lines.append("✅ Ціль досягнуто!")
    
    return "\n".join(lines)


def build_goal_details_text(goal: Dict, currency: str = "UAH") -> str:
    """Формує опис цілі для редагування"""
    target, current, remaining, percentage = get_goal_amounts(goal)
    status = "✅ Досягнуто" if is_goal_completed(goal) else "🔄 В процесі"
    lines = [
        f"✏️ <b>Редагування: {goal.get('goal_name', 'Без назви')}</b>\n",
        f"Статус: {status}",
        f"Прогрес: {format_currency(current, currency)} / {format_currency(target, currency)} ({percentage:.1f}%)",
        f"📊 Бар: {create_progress_bar(percentage)}",
        f"Залишилось накопичити: {format_currency(remaining, currency)}",
        f"⏰ Залишилось часу: {get_goal_days_left(goal)}",
        f"Дедлайн: {human_goal_deadline(goal.get('deadline'))}",
        f"{format_deadline_hint(goal)}"
    ]
    return "\n".join(lines)


def get_goal_action_keyboard(goal: Dict) -> InlineKeyboardMarkup:
    """Клавіатура дій над окремою ціллю"""
    toggle_text = "✅ Позначити виконаною" if not is_goal_completed(goal) else "🔄 Повернути в роботу"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Назва", callback_data="goal_action_rename"),
            InlineKeyboardButton(text="💰 Сума", callback_data="goal_action_amount")
        ],
        [
            InlineKeyboardButton(text="💳 Змінити внесення", callback_data="goal_action_progress")
        ],
        [
            InlineKeyboardButton(text="📅 Дедлайн", callback_data="goal_action_deadline"),
            InlineKeyboardButton(text=toggle_text, callback_data="goal_action_toggle")
        ],
        [
            InlineKeyboardButton(text="⬅️ До списку", callback_data="edit_goals")
        ]
    ])


# ==================== ВНЕСОК ДО ЦІЛІ ====================

@router.callback_query(F.data == "contribute_to_goal")
async def contribute_to_goal_start(callback: CallbackQuery, state: FSMContext):
    """Вибір цілі для внеску"""
    nickname = callback.from_user.username or "anonymous"
    
    try:
        goals = sheets_service.get_goals(nickname)
        active_goals = [g for g in goals if not is_goal_completed(g)]
        
        if not active_goals:
            await callback.answer("Немає активних цілей", show_alert=True)
            return
        
        # Створюємо клавіатуру з цілями
        buttons = []
        for idx, goal in enumerate(active_goals):
            name = goal.get('goal_name', f'Ціль {idx+1}')
            buttons.append([
                InlineKeyboardButton(
                    text=name,
                    callback_data=f"contribute_{idx}"
                )
            ])
        
        buttons.append([
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_goals")
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await callback.message.edit_text(
            "💰 <b>Внесок до цілі</b>\n\n"
            "Обери ціль, до якої хочеш додати гроші:",
            reply_markup=keyboard
        )
        
        await state.update_data(active_goals=active_goals)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error in contribute start: {e}", exc_info=True)
        await callback.answer("❌ Помилка", show_alert=True)


@router.callback_query(F.data.startswith("contribute_"))
async def contribute_amount_request(callback: CallbackQuery, state: FSMContext):
    """Запит суми внеску"""
    goal_idx = int(callback.data.split("_")[1])
    data = await state.get_data()
    goals = data.get('active_goals', [])
    
    if goal_idx >= len(goals):
        await callback.answer("❌ Ціль не знайдено", show_alert=True)
        return
    
    goal = goals[goal_idx]
    await state.update_data(selected_goal_idx=goal_idx)
    
    target = float(goal.get('target_amount', 0))
    current = float(goal.get('current_amount', 0))
    remaining = target - current
    
    await callback.message.edit_text(
        f"💰 <b>Внесок до: {goal.get('goal_name')}</b>\n\n"
        f"Поточний прогрес: {format_currency(current)} / {format_currency(target)}\n"
        f"Залишилось: {format_currency(remaining)}\n\n"
        f"Скільки хочеш додати?\n"
        f"Введи суму:"
    )
    
    await state.set_state(BudgetGoalState.awaiting_contribution)
    await callback.answer()


@router.message(BudgetGoalState.awaiting_contribution)
async def process_contribution(message: Message, state: FSMContext):
    """Обробка внеску"""
    is_valid, amount, error = validate_amount(message.text)
    
    if not is_valid:
        await message.reply(f"❌ {error}")
        return
    
    data = await state.get_data()
    goals = data.get('active_goals', [])
    goal_idx = data.get('selected_goal_idx', 0)
    nickname = message.from_user.username or "anonymous"
    _, currency = sheets_service.get_current_balance(nickname)
    currency = currency or "UAH"
    
    try:
        goal = goals[goal_idx]
        goal_name = goal.get('goal_name')
        current = float(goal.get('current_amount', 0))
        target = float(goal.get('target_amount', 0))
        
        new_amount = current + amount
        completed = new_amount >= target
        
        # Оновлюємо ціль
        sheets_service.update_goal_progress(
            nickname=nickname,
            goal_name=goal_name,
            new_amount=new_amount,
            completed=completed
        )
        
        # Віднімаємо з балансу
        sheets_service.append_transaction(
            user_id=message.from_user.id,
            nickname=nickname,
            amount=-amount,
            category="Заощадження",
            note=f"Внесок до цілі: {goal_name}"
        )
        
        progress_pct = (new_amount / target * 100) if target > 0 else 0
        
        if completed:
            await message.answer(
                f"🎉🎉🎉 <b>ВІТАЄМО!</b> 🎉🎉🎉\n\n"
                f"Ти досяг цілі: <b>{goal_name}</b>\n"
                f"💰 Накопичено: {format_currency(new_amount, currency)}\n\n"
                f"Продовжуй в тому ж дусі! 🚀"
            )
        else:
            remaining = target - new_amount
            await message.answer(
                f"✅ <b>Внесок додано!</b>\n\n"
                f"🎯 Ціль: {goal_name}\n"
                f"💰 Додано: {format_currency(amount, currency)}\n"
                f"📊 Прогрес: {progress_pct:.1f}%\n"
                f"📉 Залишилось: {format_currency(remaining, currency)}\n\n"
                f"Так тримати! 💪"
            )
        
        await state.clear()
        
        await message.answer(
            "Обирай наступну дію:",
            reply_markup=get_main_menu_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Error processing contribution: {e}", exc_info=True)
        await message.reply("❌ Помилка при внеску")


# ==================== ПРОГРЕС ЦІЛЕЙ ====================

@router.callback_query(F.data == "goals_progress")
async def show_goals_progress(callback: CallbackQuery):
    """Показує зведення по цілях"""
    nickname = callback.from_user.username or "anonymous"
    
    try:
        goals = sheets_service.get_goals(nickname)
        _, currency = sheets_service.get_current_balance(nickname)
        currency = currency or "UAH"
        
        if not goals:
            await callback.message.edit_text(
                "🎯 Поки що немає жодної цілі.\n\n"
                "Створи першу, щоб побачити прогрес!",
                reply_markup=get_goals_menu()
            )
            await callback.answer()
            return
        
        active_goals = [g for g in goals if not is_goal_completed(g)]
        completed_count = len(goals) - len(active_goals)
        
        total_target = sum(get_goal_amounts(g)[0] for g in goals)
        total_saved = sum(get_goal_amounts(g)[1] for g in goals)
        avg_progress = (total_saved / total_target * 100) if total_target > 0 else 0
        
        text_lines = [
            "📈 <b>Прогрес по цілях</b>\n",
            f"🎯 Всього цілей: {len(goals)} (активних: {len(active_goals)}, завершених: {completed_count})",
            f"💰 Накопичено: {format_currency(total_saved, currency)} / {format_currency(total_target, currency)}",
            f"🚀 Середній прогрес: {avg_progress:.1f}%"
        ]
        
        if active_goals:
            sorted_goals = sorted(active_goals, key=goal_deadline_sort_key)
            text_lines.append("\n<b>Найближчі цілі:</b>")
            for goal in sorted_goals[:3]:
                name = goal.get('goal_name', 'Без назви')
                target, current, remaining, percentage = get_goal_amounts(goal)
                text_lines.append(
                    f"\n<b>{name}</b>\n"
                    f"   {create_progress_bar(percentage)} {percentage:.1f}%\n"
                    f"   Залишилось: {format_currency(remaining, currency)}\n"
                    f"   📅 До: {human_goal_deadline(goal.get('deadline'))}\n"
                    f"   {format_deadline_hint(goal)}"
                )
            
            # Рекомендація для найближчої цілі
            first_goal = sorted_goals[0]
            deadline = parse_goal_deadline(first_goal)
            if deadline:
                _, _, remaining, _ = get_goal_amounts(first_goal)
                days_left = max((deadline - datetime.now()).days, 1)
                daily_need = remaining / days_left if remaining > 0 else 0
                text_lines.append(
                    f"\n💡 Щоб встигнути з ціллю <b>{first_goal.get('goal_name')}</b>, "
                    f"відкладай приблизно {format_currency(daily_need, currency)} щодня."
                )
        
        await callback.message.edit_text(
            "\n".join(text_lines),
            reply_markup=get_goals_menu()
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error showing goals progress: {e}", exc_info=True)
        await callback.answer("❌ Помилка", show_alert=True)


# ==================== РЕДАГУВАННЯ ЦІЛЕЙ ====================

@router.callback_query(F.data == "edit_goals")
async def edit_goals(callback: CallbackQuery, state: FSMContext):
    """Меню вибору цілі для редагування"""
    nickname = callback.from_user.username or "anonymous"
    
    try:
        goals = sheets_service.get_goals(nickname)
        _, currency = sheets_service.get_current_balance(nickname)
        currency = currency or "UAH"
        
        if not goals:
            await callback.message.edit_text(
                "❌ Немає цілей для редагування.",
                reply_markup=get_goals_menu()
            )
            await callback.answer()
            return
        
        buttons = []
        for idx, goal in enumerate(goals):
            _, current, _, percentage = get_goal_amounts(goal)
            status = "✅" if is_goal_completed(goal) else f"{percentage:.0f}%"
            buttons.append([
                InlineKeyboardButton(
                    text=f"{idx + 1}. {goal.get('goal_name', 'Без назви')} ({status})",
                    callback_data=f"goal_edit_{idx}"
                )
            ])
        
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_goals")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await state.update_data(goals_cache=goals, user_currency=currency)
        await callback.message.edit_text(
            "✏️ <b>Вибери ціль для редагування</b>:",
            reply_markup=keyboard
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error showing edit goals menu: {e}", exc_info=True)
        await callback.answer("❌ Помилка", show_alert=True)


@router.callback_query(F.data.startswith("goal_edit_"))
async def select_goal_for_edit(callback: CallbackQuery, state: FSMContext):
    """Показує дії для конкретної цілі"""
    idx = int(callback.data.split("_")[2])
    data = await state.get_data()
    goals: List[Dict] = data.get('goals_cache', [])
    currency = data.get('user_currency', 'UAH')
    
    if idx >= len(goals):
        await callback.answer("❌ Ціль не знайдено", show_alert=True)
        return
    
    goal = goals[idx]
    await state.update_data(selected_goal=goal, selected_goal_name=goal.get('goal_name'))
    
    await callback.message.edit_text(
        build_goal_details_text(goal, currency),
        reply_markup=get_goal_action_keyboard(goal)
    )
    await callback.answer()


def ensure_goal_selected(data: Dict) -> Optional[str]:
    """Перевіряє, чи обрана ціль у стані"""
    goal_name = data.get('selected_goal_name')
    return goal_name


@router.callback_query(F.data == "goal_action_rename")
async def goal_action_rename(callback: CallbackQuery, state: FSMContext):
    """Запит на зміну назви"""
    data = await state.get_data()
    goal_name = ensure_goal_selected(data)
    
    if not goal_name:
        await callback.answer("Спочатку обери ціль", show_alert=True)
        return
    
    await callback.message.edit_text(
        f"✏️ <b>Зміна назви цілі</b>\n\n"
        f"Поточна назва: {goal_name}\n"
        f"Введи нову назву (до 100 символів):"
    )
    await state.set_state(BudgetGoalState.edit_goal_name)
    await callback.answer()


@router.callback_query(F.data == "goal_action_amount")
async def goal_action_amount(callback: CallbackQuery, state: FSMContext):
    """Запит на зміну суми"""
    data = await state.get_data()
    goal_name = ensure_goal_selected(data)
    currency = data.get('user_currency', 'UAH')
    
    if not goal_name:
        await callback.answer("Спочатку обери ціль", show_alert=True)
        return
    
    goal = data.get('selected_goal', {})
    _, current, _, _ = get_goal_amounts(goal)
    
    await callback.message.edit_text(
        f"💰 <b>Нова цільова сума</b>\n\n"
        f"Ціль: {goal_name}\n"
        f"Вже зібрано: {format_currency(current, currency)}\n\n"
        f"Введи нову суму (не менше поточної):"
    )
    await state.set_state(BudgetGoalState.edit_goal_amount)
    await callback.answer()


@router.callback_query(F.data == "goal_action_deadline")
async def goal_action_deadline(callback: CallbackQuery, state: FSMContext):
    """Запит на зміну дедлайну"""
    data = await state.get_data()
    goal_name = ensure_goal_selected(data)
    
    if not goal_name:
        await callback.answer("Спочатку обери ціль", show_alert=True)
        return
    
    await callback.message.edit_text(
        f"📅 <b>Новий дедлайн для '{goal_name}'</b>\n\n"
        f"Введи дату у форматі <code>день.місяць.рік</code>\n"
        f"Наприклад: <code>31.12.2025</code>\n"
        f"Щоб прибрати дедлайн, надішли <code>-</code>"
    )
    await state.set_state(BudgetGoalState.edit_goal_deadline)
    await callback.answer()


@router.callback_query(F.data == "goal_action_progress")
async def goal_action_progress(callback: CallbackQuery, state: FSMContext):
    """Запит на зміну накопиченої суми"""
    data = await state.get_data()
    goal = data.get('selected_goal')
    goal_name = ensure_goal_selected(data)
    currency = data.get('user_currency', 'UAH')
    
    if not goal or not goal_name:
        await callback.answer("Спочатку обери ціль", show_alert=True)
        return
    
    _, current, _, _ = get_goal_amounts(goal)
    
    await callback.message.edit_text(
        f"💳 <b>Змінити внесення для '{goal_name}'</b>\n\n"
        f"Зараз накопичено: {format_currency(current, currency)}\n"
        f"Введи нову суму накопиченого (від 0 до цілі):"
    )
    await state.set_state(BudgetGoalState.edit_goal_progress)
    await callback.answer()


@router.callback_query(F.data == "goal_action_toggle")
async def goal_action_toggle(callback: CallbackQuery, state: FSMContext):
    """Позначає/знімає виконання цілі"""
    data = await state.get_data()
    goal = data.get('selected_goal')
    goal_name = ensure_goal_selected(data)
    currency = data.get('user_currency', 'UAH')
    
    if not goal or not goal_name:
        await callback.answer("Спочатку обери ціль", show_alert=True)
        return
    
    nickname = callback.from_user.username or "anonymous"
    new_status = not is_goal_completed(goal)
    
    try:
        sheets_service.update_goal_details(
            nickname=nickname,
            goal_name=goal_name,
            completed=new_status
        )
        goal['completed'] = new_status  # Оновлюємо кеш
        
        await callback.message.edit_text(
            build_goal_details_text(goal, currency),
            reply_markup=get_goal_action_keyboard(goal)
        )
        status_text = "Ціль виконана! 🎉" if new_status else "Ціль повернена в роботу."
        await callback.answer(status_text, show_alert=True if new_status else False)
        
    except Exception as e:
        logger.error(f"Error toggling goal status: {e}", exc_info=True)
        await callback.answer("❌ Не вдалося оновити статус", show_alert=True)


@router.message(BudgetGoalState.edit_goal_name)
async def process_goal_rename(message: Message, state: FSMContext):
    """Обробляє нову назву"""
    new_name = message.text.strip()
    data = await state.get_data()
    old_name = data.get('selected_goal_name')
    nickname = message.from_user.username or "anonymous"
    
    if not old_name:
        await message.reply("Спочатку обери ціль у меню редагування.")
        await state.clear()
        return
    
    if not new_name:
        await message.reply("❌ Назва не може бути порожньою.")
        return
    
    if len(new_name) > 100:
        await message.reply("❌ Назва занадто довга. Максимум 100 символів.")
        return
    
    try:
        # Перевіряємо на дублікати
        existing = sheets_service.get_goals(nickname)
        if any(g.get('goal_name') == new_name for g in existing):
            await message.reply("❌ Ціль з такою назвою вже існує.")
            return
        
        sheets_service.update_goal_details(
            nickname=nickname,
            goal_name=old_name,
            new_name=new_name
        )
        
        await message.answer(
            f"✅ Назву змінено на <b>{new_name}</b>.",
            reply_markup=get_goals_menu()
        )
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error renaming goal: {e}", exc_info=True)
        await message.reply("❌ Не вдалося змінити назву.")


@router.message(BudgetGoalState.edit_goal_amount)
async def process_goal_amount_edit(message: Message, state: FSMContext):
    """Обробляє нову суму цілі"""
    is_valid, amount, error = validate_amount(message.text)
    data = await state.get_data()
    goal = data.get('selected_goal')
    goal_name = data.get('selected_goal_name')
    currency = data.get('user_currency', 'UAH')
    nickname = message.from_user.username or "anonymous"
    
    if not goal or not goal_name:
        await message.reply("Спочатку обери ціль у меню редагування.")
        await state.clear()
        return
    
    if not is_valid or not amount:
        await message.reply(f"❌ {error or 'Некоректна сума'}")
        return
    
    _, current, _, _ = get_goal_amounts(goal)
    if amount < current:
        await message.reply("❌ Нова сума не може бути меншою за вже накопичену.")
        return
    
    try:
        sheets_service.update_goal_details(
            nickname=nickname,
            goal_name=goal_name,
            target_amount=amount
        )
        await message.answer(
            f"✅ Нова цільова сума: {format_currency(amount, currency)}",
            reply_markup=get_goals_menu()
        )
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error updating goal amount: {e}", exc_info=True)
        await message.reply("❌ Не вдалося оновити суму.")


@router.message(BudgetGoalState.edit_goal_deadline)
async def process_goal_deadline_edit(message: Message, state: FSMContext):
    """Обробляє новий дедлайн"""
    deadline_str = message.text.strip()
    data = await state.get_data()
    goal_name = data.get('selected_goal_name')
    nickname = message.from_user.username or "anonymous"
    
    if not goal_name:
        await message.reply("Спочатку обери ціль у меню редагування.")
        await state.clear()
        return
    
    if deadline_str == "-":
        new_deadline = "Без дедлайну"
    else:
        is_valid, date_obj, error = validate_date(deadline_str)
        
        if not is_valid or not date_obj:
            await message.reply(f"❌ {error}")
            return
        
        if date_obj.date() < datetime.now().date():
            await message.reply("❌ Дата не може бути в минулому.")
            return
        
        new_deadline = date_obj.strftime("%Y-%m-%d")
    
    try:
        sheets_service.update_goal_details(
            nickname=nickname,
            goal_name=goal_name,
            deadline=new_deadline
        )
        human_deadline = human_goal_deadline(new_deadline)
        await message.answer(
            f"✅ Дедлайн оновлено: {human_deadline}",
            reply_markup=get_goals_menu()
        )
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error updating goal deadline: {e}", exc_info=True)
        await message.reply("❌ Не вдалося оновити дедлайн.")


@router.message(BudgetGoalState.edit_goal_progress)
async def process_goal_progress_edit(message: Message, state: FSMContext):
    """Оновлює поточну суму накопиченого"""
    data = await state.get_data()
    goal = data.get('selected_goal')
    goal_name = data.get('selected_goal_name')
    currency = data.get('user_currency', 'UAH')
    nickname = message.from_user.username or "anonymous"
    
    if not goal or not goal_name:
        await message.reply("Спочатку обери ціль у меню редагування.")
        await state.clear()
        return
    
    raw_value = message.text.strip().replace(",", ".")
    try:
        new_amount = float(raw_value)
    except ValueError:
        await message.reply("❌ Некоректна сума. Введи число, наприклад: 1500 або 1500.50")
        return
    
    if new_amount < 0:
        await message.reply("❌ Сума не може бути від'ємною.")
        return
    
    target, _, _, _ = get_goal_amounts(goal)
    if new_amount > target:
        await message.reply("❌ Сума не може перевищувати цільову.")
        return
    
    completed = new_amount >= target and target > 0
    
    try:
        sheets_service.update_goal_progress(
            nickname=nickname,
            goal_name=goal_name,
            new_amount=new_amount,
            completed=completed
        )
        
        goal['current_amount'] = new_amount
        goal['completed'] = completed
        
        pct = (new_amount / target * 100) if target > 0 else 0
        
        await message.answer(
            f"✅ Внесення оновлено!\n\n"
            f"🎯 Ціль: {goal_name}\n"
            f"💰 Накопичено: {format_currency(new_amount, currency)}\n"
            f"📊 Прогрес: {pct:.1f}%\n"
            f"{create_progress_bar(pct)}",
            reply_markup=get_goals_menu()
        )
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error updating goal progress: {e}", exc_info=True)
        await message.reply("❌ Не вдалося оновити внесення.")


# ==================== ВИДАЛЕННЯ ЦІЛЕЙ ====================

@router.callback_query(F.data == "delete_goals")
async def delete_goals_menu(callback: CallbackQuery, state: FSMContext):
    """Показує цілі для видалення"""
    nickname = callback.from_user.username or "anonymous"
    
    try:
        goals = sheets_service.get_goals(nickname)
        
        if not goals:
            await callback.message.edit_text(
                "🗑️ Немає цілей для видалення.",
                reply_markup=get_goals_menu()
            )
            await callback.answer()
            return
        
        buttons = []
        for idx, goal in enumerate(goals):
            buttons.append([
                InlineKeyboardButton(
                    text=f"{idx + 1}. {goal.get('goal_name', 'Без назви')}",
                    callback_data=f"goal_delete_{idx}"
                )
            ])
        
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_goals")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await state.update_data(goals_cache=goals)
        await callback.message.edit_text(
            "🗑️ <b>Оберіть ціль для видалення</b>:",
            reply_markup=keyboard
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error showing delete goals menu: {e}", exc_info=True)
        await callback.answer("❌ Помилка", show_alert=True)


@router.callback_query(F.data.regexp(r"^goal_delete_\d+$"))
async def confirm_goal_delete(callback: CallbackQuery, state: FSMContext):
    """Підтвердження видалення цілі"""
    idx = int(callback.data.split("_")[2])
    data = await state.get_data()
    goals: List[Dict] = data.get('goals_cache', [])
    
    if idx >= len(goals):
        await callback.answer("❌ Ціль не знайдено", show_alert=True)
        return
    
    goal = goals[idx]
    goal_name = goal.get('goal_name', 'Без назви')
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Видалити", callback_data="goal_delete_confirm"),
            InlineKeyboardButton(text="❌ Скасувати", callback_data="goal_delete_cancel")
        ]
    ])
    
    await state.update_data(goal_to_delete=goal_name)
    await state.set_state(BudgetGoalState.delete_goal_confirmation)
    
    await callback.message.edit_text(
        f"🗑️ <b>Видалити ціль?</b>\n\n"
        f"Ціль: {goal_name}\n"
        f"Цю дію не можна скасувати.",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(BudgetGoalState.delete_goal_confirmation, F.data == "goal_delete_confirm")
async def process_goal_delete(callback: CallbackQuery, state: FSMContext):
    """Видаляє ціль"""
    data = await state.get_data()
    goal_name = data.get('goal_to_delete')
    nickname = callback.from_user.username or "anonymous"
    
    if not goal_name:
        await callback.answer("Ціль не вибрано", show_alert=True)
        return
    
    try:
        sheets_service.delete_goal(nickname, goal_name)
        await callback.message.edit_text(
            f"✅ Ціль <b>{goal_name}</b> видалена.",
            reply_markup=get_goals_menu()
        )
        await state.clear()
        await callback.answer("Видалено")
        
    except Exception as e:
        logger.error(f"Error deleting goal: {e}", exc_info=True)
        await callback.answer("❌ Не вдалося видалити ціль", show_alert=True)


@router.callback_query(BudgetGoalState.delete_goal_confirmation, F.data == "goal_delete_cancel")
async def cancel_goal_delete(callback: CallbackQuery, state: FSMContext):
    """Скасовує видалення"""
    await state.clear()
    await callback.message.edit_text(
        "Операцію скасовано.",
        reply_markup=get_goals_menu()
    )
    await callback.answer()


# ==================== НАЗАД ====================

@router.callback_query(F.data == "back_to_goals")
async def back_to_goals(callback: CallbackQuery):
    """Повернення до меню цілей"""
    await show_goals_menu(callback.message)
    await callback.answer()
