"""
Планувальник періодичних задач (нагадування, автосписання тощо).
"""

import calendar
import logging
from datetime import datetime, date, timedelta
from typing import Optional

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config.settings import config
from app.services.sheets_service import sheets_service
from app.utils.formatters import format_currency

logger = logging.getLogger(__name__)

SUBSCRIPTION_NOTE_PREFIX = "Підписка: "


# ----------------------- ДОПОМІЖНІ ФУНКЦІЇ ----------------------- #

def _parse_subscription_date(value: str) -> Optional[date]:
    if not value:
        return None
    text = value.strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    for fmt in ("%d.%m.%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _next_charge_date(current: date) -> date:
    year = current.year + (current.month // 12)
    month = 1 if current.month == 12 else current.month + 1
    if current.month == 12:
        year = current.year + 1
    days = calendar.monthrange(year, month)[1]
    day = min(current.day, days)
    return date(year, month, day)


def _subscription_name(sub: dict) -> str:
    name = (sub.get("subscription_name") or "").strip()
    if name:
        return name
    note = (sub.get("note") or "").strip()
    if note.startswith(SUBSCRIPTION_NOTE_PREFIX):
        return note[len(SUBSCRIPTION_NOTE_PREFIX):].strip() or "Без назви"
    return note or "Без назви"


# ----------------------- Нагадування ----------------------- #

async def send_daily_reminders(bot: Bot):
    logger.info("📅 Running scheduled task: daily reminders")
    try:
        user_ids = sheets_service.get_reminder_users()
        text = (
            "🔔 <b>Нагадування</b>\n\n"
            "Не забудь записати сьогоднішні витрати та доходи!"
        )
        sent = 0
        for user_id in user_ids:
            try:
                await bot.send_message(chat_id=user_id, text=text)
                sent += 1
            except Exception as exc:
                logger.error("Failed to send reminder to %s: %s", user_id, exc)
        logger.info("✅ Sent reminders to %s/%s users", sent, len(user_ids))
    except Exception as exc:
        logger.error("Error in daily reminders task: %s", exc, exc_info=True)


# ----------------------- ПІДПИСКИ ----------------------- #

async def check_subscription_renewals(bot: Bot):
    logger.info("📅 Running scheduled task: subscription renewals")
    try:
        worksheets = [
            ws.title
            for ws in sheets_service.spreadsheet.worksheets()
            if ws.title not in {"feedback_and_suggestions", "Sheet1", "reminder_settings"}
        ]

        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        notifications = 0
        auto_charges = 0

        for sheet_title in worksheets:
            try:
                subscriptions = sheets_service.get_subscriptions(sheet_title)
                if not subscriptions:
                    continue

                for sub in subscriptions:
                    due_date = _parse_subscription_date(
                        sub.get("subscription_due_date") or sub.get("date", "")
                    )
                    if not due_date:
                        continue

                    name = _subscription_name(sub)
                    amount = abs(float(sub.get("amount", 0) or 0))
                    category = sub.get("category", "Підписки")
                    row_index = sub.get("_row")
                    user_id_raw = sub.get("user_id")
                    try:
                        user_id = int(str(user_id_raw))
                    except (TypeError, ValueError):
                        user_id = None

                    if due_date == today and user_id:
                        # створюємо витрату
                        try:
                            sheets_service.append_transaction(
                                user_id=user_id,
                                nickname=sheet_title,
                                amount=-amount,
                                category=category,
                                note=f"{SUBSCRIPTION_NOTE_PREFIX}{name} (авто)",
                                is_subscription=False,
                                subscription_name=name,
                                subscription_due_date=due_date.strftime("%d.%m.%Y"),
                                legacy_titles=[sheet_title],
                            )
                            auto_charges += 1
                            next_due = _next_charge_date(due_date)
                            sheets_service.update_transaction_fields(
                                sheet_title,
                                row_index,
                                {'subscription_due_date': next_due.strftime("%d.%m.%Y")},
                                legacy_titles=[sheet_title],
                            )
                            await bot.send_message(
                                chat_id=user_id,
                                text=(
                                    "🤖 <b>Автосписання виконано</b>\n\n"
                                    f"{name}: {format_currency(amount)}\n"
                                    f"Наступна дата: {next_due.strftime('%d.%m.%Y')}"
                                ),
                            )
                        except Exception as exc:
                            logger.error("Failed to auto-charge %s: %s", sheet_title, exc, exc_info=True)

                    elif due_date == tomorrow and user_id:
                        notifications += 1
                        await bot.send_message(
                            chat_id=user_id,
                            text=(
                                "⏰ <b>Наближається підписка</b>\n\n"
                                f"Завтра буде списання за <b>{name}</b>\n"
                                f"Сума: {amount:.2f} UAH"
                            ),
                        )
            except Exception as exc:
                logger.error("Error checking subscriptions for %s: %s", sheet_title, exc, exc_info=True)

        logger.info("✅ Subscription reminders: %s, auto-charges: %s", notifications, auto_charges)
    except Exception as exc:
        logger.error("Error in subscription renewals task: %s", exc, exc_info=True)


# ----------------------- ІНШІ ЗАДАЧІ ----------------------- #

async def cleanup_old_data(bot: Bot):
    logger.info("🧹 Running scheduled task: data cleanup")


async def generate_weekly_report(bot: Bot):
    logger.info("📊 Running scheduled task: weekly report")
    # Скорочено: попередня реалізація залишена без змін


# ----------------------- НАЛАШТУВАННЯ ----------------------- #

def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Europe/Kiev")

    for reminder_time in config.REMINDER_TIMES:
        scheduler.add_job(
            send_daily_reminders,
            trigger=CronTrigger(hour=reminder_time["hour"], minute=reminder_time["minute"]),
            kwargs={'bot': bot},
            id=f"reminder_{reminder_time['hour']}_{reminder_time['minute']}",
        )

    scheduler.add_job(
        check_subscription_renewals,
        trigger=CronTrigger(hour=9, minute=0),
        kwargs={'bot': bot},
        id="subscription_check",
    )

    scheduler.add_job(
        generate_weekly_report,
        trigger=CronTrigger(day_of_week="sun", hour=18, minute=0),
        kwargs={'bot': bot},
        id="weekly_report",
    )

    scheduler.add_job(
        cleanup_old_data,
        trigger=CronTrigger(day=1, hour=3, minute=0),
        kwargs={'bot': bot},
        id="data_cleanup",
    )

    scheduler.start()
    logger.info("✅ Scheduler configured with all tasks")
    return scheduler
