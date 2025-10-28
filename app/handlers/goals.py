# ============================================
# FILE: app/handlers/goals.py (NEW)
# ============================================
"""
Обробники для управління цілями заощаджень
"""

import logging
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.core.states import BudgetGoalState
from app.services.sheets_service import sheets_service
from app.keyboards.reply import get_main_menu_keyboard
from app.utils.validators import validate_amount, validate_date
from app.utils.formatters import format_currency

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
        active_goals = len([g for g in goals if not g.get('completed', False)])
        
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
        f"Введи дату у форматі <code>день-місяць-рік</code>\n"
        f"Наприклад: <code>31-12-2025</code>\n\n"
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
        
        await message.answer(
            f"✅ <b>Ціль створена!</b>\n\n"
            f"🎯 Назва: {goal_name}\n"
            f"💰 Сума: {format_currency(goal_amount)}\n"
            f"📅 Дедлайн: {deadline or 'без обмежень'}"
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
        
        if not goals:
            await callback.message.edit_text(
                "🎯 У тебе поки немає цілей.\n\n"
                "Створи першу ціль, щоб почати заощаджувати!",
                reply_markup=get_goals_menu()
            )
            await callback.answer()
            return
        
        text_lines = ["🎯 <b>Твої фінансові цілі:</b>\n"]
        
        for idx, goal in enumerate(goals, 1):
            name = goal.get('goal_name', 'Без назви')
            target = float(goal.get('target_amount', 0))
            current = float(goal.get('current_amount', 0))
            deadline = goal.get('deadline', 'Без дедлайну')
            completed = goal.get('completed', False)
            
            # Прогрес
            progress_pct = (current / target * 100) if target > 0 else 0
            progress_bar = create_progress_bar(progress_pct)
            
            # Статус
            status = "✅ Досягнуто!" if completed else "🔄 В процесі"
            
            # Дедлайн
            deadline_text = ""
            if deadline and deadline != "Без дедлайну":
                try:
                    deadline_date = datetime.strptime(deadline, "%Y-%m-%d")
                    days_left = (deadline_date - datetime.now()).days
                    if days_left > 0:
                        deadline_text = f"\n   ⏰ {days_left} днів"
                    elif days_left == 0:
                        deadline_text = "\n   ⏰ Сьогодні!"
                    else:
                        deadline_text = "\n   ⏰ Прострочено"
                except:
                    pass
            
            text_lines.append(
                f"\n<b>{idx}. {name}</b> {status}\n"
                f"   💰 {format_currency(current)} / {format_currency(target)}\n"
                f"   {progress_bar} {progress_pct:.1f}%"
                f"{deadline_text}"
            )
        
        await callback.message.edit_text(
            "\n".join(text_lines),
            reply_markup=get_goals_menu()
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error viewing goals: {e}", exc_info=True)
        await callback.answer("❌ Помилка", show_alert=True)


def create_progress_bar(percentage: float, length: int = 10) -> str:
    """Створює прогрес-бар"""
    filled = int(percentage / 100 * length)
    empty = length - filled
    return "🟩" * filled + "⬜" * empty


# ==================== ВНЕСОК ДО ЦІЛІ ====================

@router.callback_query(F.data == "contribute_to_goal")
async def contribute_to_goal_start(callback: CallbackQuery, state: FSMContext):
    """Вибір цілі для внеску"""
    nickname = callback.from_user.username or "anonymous"
    
    try:
        goals = sheets_service.get_goals(nickname)
        active_goals = [g for g in goals if not g.get('completed', False)]
        
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
    
    await state.set_state(BudgetGoalState.view_progress)
    await callback.answer()


@router.message(BudgetGoalState.view_progress)
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
                f"💰 Накопичено: {format_currency(new_amount)}\n\n"
                f"Продовжуй в тому ж дусі! 🚀"
            )
        else:
            remaining = target - new_amount
            await message.answer(
                f"✅ <b>Внесок додано!</b>\n\n"
                f"🎯 Ціль: {goal_name}\n"
                f"💰 Додано: {format_currency(amount)}\n"
                f"📊 Прогрес: {progress_pct:.1f}%\n"
                f"📉 Залишилось: {format_currency(remaining)}\n\n"
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


# ==================== НАЗАД ====================

@router.callback_query(F.data == "back_to_goals")
async def back_to_goals(callback: CallbackQuery):
    """Повернення до меню цілей"""
    await show_goals_menu(callback.message)
    await callback.answer()