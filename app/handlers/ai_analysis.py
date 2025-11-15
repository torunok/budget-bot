# ============================================
# FILE: app/handlers/ai_analysis.py
# ============================================
"""
Обробники для AI-аналізу бюджету.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config.settings import config
from app.core.states import AIAnalysisState
from app.keyboards.inline import get_ai_analysis_period_keyboard
from app.services.ai_service import ai_service
from app.services.sheets_service import sheets_service
from app.utils.formatters import format_currency, format_date, split_long_message
from app.utils.helpers import SheetContext, build_sheet_context
from app.utils.validators import validate_date

logger = logging.getLogger(__name__)
router = Router()

MIN_TRANSACTIONS_REQUIRED = 5
AI_TRANSACTIONS_LIMIT = 200
PERIOD_LENGTHS = {"30": 30, "60": 60, "90": 90}


@router.message(F.text == "🤖 AI Аналіз")
async def ai_analysis_entry(message: Message, state: FSMContext):
    """Початковий запит AI-аналізу - показує вибір періоду."""
    await state.clear()
    await message.answer(
        "🤖 <b>AI Аналіз</b>\n\nОбери, за який період підготувати аналітику:",
        reply_markup=get_ai_analysis_period_keyboard(),
    )


@router.callback_query(F.data.startswith("ai_period_"))
async def handle_ai_period(callback: CallbackQuery, state: FSMContext):
    """Обробка вибору періоду через інлайн-клавіатуру."""
    period_key = callback.data.removeprefix("ai_period_")
    ctx = build_sheet_context(callback.from_user)

    if period_key == "custom":
        await state.set_state(AIAnalysisState.awaiting_start_date)
        await state.update_data(ai_ctx=_serialize_context(ctx))
        await callback.message.answer(
            "📅 Введи дату <b>від</b> у форматі <code>ДД.ММ.РРРР</code>."
        )
        await callback.answer()
        return

    start, end = _resolve_period_bounds(period_key)
    if start is None and end is None:
        await callback.answer("Невідомий період", show_alert=True)
        return

    await callback.answer()
    await _run_ai_analysis(callback.message, ctx, start, end, state)


@router.message(AIAnalysisState.awaiting_start_date)
async def handle_custom_start(message: Message, state: FSMContext):
    """Отримує дату 'від' для кастомного періоду."""
    is_valid, date_obj, error = validate_date(message.text)
    if not is_valid or not date_obj:
        await message.answer(error or "Не вдалося розпізнати дату. Спробуй ще раз.")
        return

    ctx = build_sheet_context(message.from_user)
    start_dt = datetime(
        date_obj.year, date_obj.month, date_obj.day, tzinfo=timezone.utc
    )
    await state.update_data(
        ai_ctx=_serialize_context(ctx),
        custom_start=start_dt.isoformat(),
    )
    await state.set_state(AIAnalysisState.awaiting_end_date)
    await message.answer(
        "Добре! Тепер введи дату <b>до</b> у форматі <code>ДД.ММ.РРРР</code>."
    )


@router.message(AIAnalysisState.awaiting_end_date)
async def handle_custom_end(message: Message, state: FSMContext):
    """Отримує дату 'до' і запускає аналітику."""
    data = await state.get_data()
    ctx = _deserialize_context(message.from_user, data)
    start_iso = data.get("custom_start")
    if not start_iso:
        await message.answer("Спочатку введи дату від.")
        await state.set_state(AIAnalysisState.awaiting_start_date)
        return

    try:
        start_dt = datetime.fromisoformat(start_iso)
    except ValueError:
        start_dt = datetime.now(timezone.utc) - timedelta(days=30)

    is_valid, date_obj, error = validate_date(message.text)
    if not is_valid or not date_obj:
        await message.answer(error or "Не вдалося розпізнати дату. Спробуй ще раз.")
        return

    end_dt = datetime(
        date_obj.year,
        date_obj.month,
        date_obj.day,
        23,
        59,
        59,
        tzinfo=timezone.utc,
    )

    if end_dt < start_dt:
        await message.answer("Дата 'до' не може бути раніше за дату 'від'.")
        return

    await _run_ai_analysis(message, ctx, start_dt, end_dt, state)


async def _run_ai_analysis(
    target_message: Message,
    ctx: SheetContext,
    start: Optional[datetime],
    end: Optional[datetime],
    state: FSMContext,
):
    """Завантажує дані, фільтрує і викликає AI."""
    waiting_msg = await target_message.answer(
        "🤖 Збираю транзакції та готую аналітику..."
    )
    try:
        rows = sheets_service.get_all_transactions(ctx.sheet_title, ctx.legacy_titles)
        filtered, actual_start, actual_end = _filter_transactions(rows, start, end)

        if len(filtered) < MIN_TRANSACTIONS_REQUIRED:
            await waiting_msg.edit_text(
                "Замало даних для AI-аналізу обраного періоду. Потрібно хоча б 5 транзакцій."
            )
            return

        analysis_context, ai_transactions, period_label = _build_analysis_payload(
            filtered, ctx, actual_start, actual_end
        )

        analysis_text = await ai_service.analyze_finances(
            ai_transactions, analysis_context
        )

        try:
            await waiting_msg.delete()
        except Exception:
            pass

        header = f"🤖 <b>AI Аналіз за {period_label}</b>\n\n"
        for chunk in split_long_message(header + analysis_text):
            await target_message.answer(chunk)

    except Exception as exc:
        logger.error("AI analysis error for %s: %s", ctx.sheet_title, exc, exc_info=True)
        await waiting_msg.edit_text(
            "⚠️ Сталася помилка під час підготовки AI-аналізу. Спробуй пізніше."
        )
    finally:
        await state.clear()


def _resolve_period_bounds(
    period_key: str,
) -> Tuple[Optional[datetime], Optional[datetime]]:
    now = datetime.now(timezone.utc)
    if period_key == "all":
        return None, now
    days = PERIOD_LENGTHS.get(period_key)
    if days is None:
        return now - timedelta(days=30), now
    return now - timedelta(days=days), now


def _filter_transactions(
    transactions: List[Dict[str, Any]],
    start: Optional[datetime],
    end: Optional[datetime],
) -> Tuple[List[Dict[str, Any]], datetime, datetime]:
    """Фільтрує транзакції по періоду та повертає список з parsed датами."""
    end_bound = end or datetime.now(timezone.utc)
    filtered: List[Dict[str, Any]] = []

    for tx in transactions:
        parsed = _parse_transaction_date(tx.get("date"))
        if not parsed:
            continue
        if start and parsed < start:
            continue
        if parsed > end_bound:
            continue
        tx_copy = dict(tx)
        tx_copy["_parsed_date"] = parsed
        filtered.append(tx_copy)

    filtered.sort(key=lambda item: item["_parsed_date"])
    if not filtered:
        return [], start or end_bound, end_bound

    return filtered, filtered[0]["_parsed_date"], filtered[-1]["_parsed_date"]


def _build_analysis_payload(
    transactions: List[Dict[str, Any]],
    ctx: SheetContext,
    period_start: datetime,
    period_end: datetime,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], str]:
    """Готує агрегати та контекст для AI."""
    currency = _detect_currency(transactions, config.DEFAULT_CURRENCY)
    aggregates = _calculate_aggregates(transactions, period_start, period_end)
    top_categories = _summarize_top_categories(transactions, currency)
    goals_summary = _summarize_goals(ctx, currency)
    budgets_summary = _summarize_budgets(ctx, currency)
    subscriptions_summary = _summarize_subscriptions(ctx, currency)

    limited = transactions[-AI_TRANSACTIONS_LIMIT:]
    ai_transactions = [
        {
            "date": tx["_parsed_date"].isoformat(),
            "amount": _safe_float(tx.get("amount")),
            "currency": tx.get("currency") or currency,
            "category": tx.get("category", "Без категорії"),
            "note": tx.get("note", ""),
        }
        for tx in limited
    ]

    period_display = (
        f"{period_start.strftime('%d.%m.%Y')} → {period_end.strftime('%d.%m.%Y')}"
    )
    period_note = (
        f"This analysis covers the period from {period_start.strftime('%Y-%m-%d')} "
        f"to {period_end.strftime('%Y-%m-%d')}. Only the last {len(ai_transactions)} "
        "transactions were included to optimize context."
    )

    analysis_context = {
        "period_start": period_start.strftime("%Y-%m-%d"),
        "period_end": period_end.strftime("%Y-%m-%d"),
        "transactions_count": len(transactions),
        "limited_count": len(ai_transactions),
        "currency": currency,
        "aggregates": aggregates,
        "top_categories": top_categories,
        "goals_summary": goals_summary,
        "budgets_summary": budgets_summary,
        "subscriptions_summary": subscriptions_summary,
        "period_note": period_note,
    }

    return analysis_context, ai_transactions, period_display


def _calculate_aggregates(
    transactions: List[Dict[str, Any]],
    period_start: datetime,
    period_end: datetime,
) -> Dict[str, float]:
    income = 0.0
    expenses = 0.0
    for tx in transactions:
        amount = _safe_float(tx.get("amount"))
        if amount >= 0:
            income += amount
        else:
            expenses += abs(amount)

    ratio = income / expenses if expenses else None
    savings_rate = ((income - expenses) / income * 100) if income else None
    days = max(1, (period_end - period_start).days + 1)
    avg_daily = expenses / days
    avg_monthly = avg_daily * 30

    return {
        "total_expenses": expenses,
        "total_income": income,
        "income_expense_ratio": ratio,
        "savings_rate": savings_rate,
        "average_daily_spend": avg_daily,
        "average_monthly_spend": avg_monthly,
    }


def _summarize_top_categories(transactions: List[Dict[str, Any]], currency: str) -> str:
    totals: Dict[str, float] = {}
    for tx in transactions:
        amount = _safe_float(tx.get("amount"))
        if amount >= 0:
            continue
        category = tx.get("category") or "Інше"
        totals[category] = totals.get(category, 0.0) + abs(amount)

    if not totals:
        return "Немає витрат для вибраного періоду."

    sorted_items = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:5]
    return "\n".join(
        f"- {name}: {format_currency(value, currency)}" for name, value in sorted_items
    )


def _summarize_goals(ctx: SheetContext, currency: str) -> str:
    goals = _load_with_fallback(ctx, sheets_service.get_goals)
    if not goals:
        return "Активних фінансових цілей немає."

    lines = []
    for goal in goals[:5]:
        name = goal.get("goal_name") or "Без назви"
        target = _safe_float(goal.get("target_amount"))
        current = _safe_float(goal.get("current_amount"))
        completed = str(goal.get("completed", "")).lower() in {"true", "1", "yes", "виконано"}
        progress = min(100, (current / target * 100)) if target else 0
        status = "✅ виконано" if completed else f"{progress:.0f}%"
        lines.append(
            f"- {name}: {format_currency(current, currency)} / {format_currency(target, currency)} ({status})"
        )

    return "\n".join(lines)


def _summarize_budgets(ctx: SheetContext, currency: str) -> str:
    budgets = _load_with_fallback(ctx, sheets_service.get_category_budgets)
    if not budgets:
        return "Бюджети ще не налаштовані."

    lines = []
    for budget in budgets[:5]:
        category = budget.get("category") or "Без категорії"
        limit_amount = _safe_float(budget.get("budget_amount"))
        spent = _safe_float(budget.get("current_spent"))
        if limit_amount:
            percent = spent / limit_amount * 100
            status = "перевищено" if spent > limit_amount else f"{percent:.0f}%"
        else:
            status = "без ліміту"
        lines.append(
            f"- {category}: {format_currency(spent, currency)} / {format_currency(limit_amount, currency)} ({status})"
        )

    return "\n".join(lines)


def _summarize_subscriptions(ctx: SheetContext, currency: str) -> str:
    try:
        subscriptions = sheets_service.get_subscriptions(
            ctx.sheet_title, ctx.legacy_titles
        )
    except Exception as exc:
        logger.warning("Could not load subscriptions for %s: %s", ctx.sheet_title, exc)
        return "Не вдалося завантажити інформацію про підписки."

    if not subscriptions:
        return "Активних підписок не знайдено."

    total_spent = sum(abs(_safe_float(sub.get("amount"))) for sub in subscriptions)
    lines = [
        f"- Активні підписки: {len(subscriptions)}, прогноз {format_currency(total_spent, currency)} на період"
    ]

    upcoming = []
    for sub in subscriptions:
        due_raw = sub.get("subscription_due_date") or sub.get("date")
        due = _parse_transaction_date(due_raw)
        if due:
            upcoming.append((due, sub))
    upcoming.sort(key=lambda item: item[0])
    if upcoming:
        preview = []
        for due, sub in upcoming[:3]:
            name = sub.get("subscription_name") or sub.get("category") or "Підписка"
            preview.append(f"{name} ({format_date(due)})")
        lines.append(f"- Найближчі списання: {', '.join(preview)}")

    return "\n".join(lines)


def _load_with_fallback(
    ctx: SheetContext, loader
) -> List[Dict[str, Any]]:  # pragma: no cover - simple helper
    candidates = [ctx.sheet_title, *ctx.legacy_titles]
    for title in candidates:
        try:
            data = loader(title)
        except Exception:
            continue
        if data:
            return data
    return []


def _detect_currency(transactions: List[Dict[str, Any]], default: str) -> str:
    for tx in reversed(transactions):
        currency = tx.get("currency")
        if currency:
            return str(currency)
    return default


def _parse_transaction_date(raw_value: Any) -> Optional[datetime]:
    if not raw_value or raw_value == "initial":
        return None

    raw = str(raw_value).strip()
    if not raw:
        return None

    raw = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        for fmt in ("%d.%m.%Y", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S"):
            try:
                parsed = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue
        else:
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _serialize_context(ctx: SheetContext) -> Dict[str, Any]:
    return {
        "sheet_title": ctx.sheet_title,
        "legacy_titles": ctx.legacy_titles,
        "display_name": ctx.display_name,
    }


def _deserialize_context(user, data: Dict[str, Any]) -> SheetContext:
    ctx_data = data.get("ai_ctx")
    if ctx_data:
        return SheetContext(
            sheet_title=ctx_data.get("sheet_title", ""),
            legacy_titles=ctx_data.get("legacy_titles", []),
            display_name=ctx_data.get("display_name", ""),
        )
    return build_sheet_context(user)
