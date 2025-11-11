#File: app/scheduler/tasks.py

"""
Заплановані задачі (cron jobs)
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config.settings import config
from app.services.sheets_service import sheets_service

logger = logging.getLogger(__name__)


async def send_daily_reminders(bot: Bot):
    """Надсилає щоденні нагадування"""
    logger.info("📅 Running scheduled task: daily reminders")
    
    try:
        user_ids = sheets_service.get_reminder_users()
        
        reminder_text = (
            "🔔 <b>Нагадування</b>\n\n"
            "Не забудьте записати сьогоднішні витрати та доходи!"
        )
        
        success_count = 0
        for user_id in user_ids:
            try:
                await bot.send_message(chat_id=user_id, text=reminder_text)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to send reminder to {user_id}: {e}")
        
        logger.info(f"✅ Sent reminders to {success_count}/{len(user_ids)} users")
        
    except Exception as e:
        logger.error(f"Error in daily reminders task: {e}", exc_info=True)


def _parse_subscription_date(value: str) -> Optional[date]:
    """Повертає дату підписки з різних форматів"""
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


async def check_subscription_renewals(bot: Bot):
    """Перевіряє підписки, що мають бути поновлені"""
    logger.info("📅 Running scheduled task: subscription renewals")
    
    try:
        # Отримуємо всі аркуші користувачів
        worksheets = [
            ws.title for ws in sheets_service.spreadsheet.worksheets()
            if ws.title not in ["feedback_and_suggestions", "Sheet1", "reminder_settings"]
        ]
        
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        notifications_sent = 0
        
        for nickname in worksheets:
            try:
                subscriptions = sheets_service.get_subscriptions(nickname)
                transactions = sheets_service.get_all_transactions(nickname)
                
                if not transactions:
                    continue
                
                user_id = int(transactions[0].get('user_id', 0))
                
                for sub in subscriptions:
                    try:
                        due_date_str = sub.get('date', '')
                        due_date = _parse_subscription_date(due_date_str)
                        
                        if not due_date:
                            continue
                        
                        notification_text = None
                        if due_date == today:
                            sub_name = sub.get('note', 'Підписка')
                            sub_amount = abs(float(sub.get('amount', 0)))
                            
                            notification_text = (
                                f"🔔 <b>Нагадування про підписку</b>\n\n"
                                f"Сьогодні має бути списання за: <b>{sub_name}</b>\n"
                                f"Сума: <b>{sub_amount:.2f} UAH</b>\n\n"
                                f"Чи продовжити підписку?"
                            )
                        elif due_date == tomorrow:
                            sub_name = sub.get('note', 'Підписка')
                            sub_amount = abs(float(sub.get('amount', 0)))
                            due_str = due_date.strftime("%d.%m.%Y")
                            
                            notification_text = (
                                f"⏰ <b>Підписка завтра</b>\n\n"
                                f"Вже завтра ({due_str}) буде списання за: <b>{sub_name}</b>\n"
                                f"Сума: <b>{sub_amount:.2f} UAH</b>\n\n"
                                f"Переконайся, що кошти на рахунку!"
                            )
                        
                        if notification_text:
                            await bot.send_message(chat_id=user_id, text=notification_text)
                            notifications_sent += 1
                            
                    except (ValueError, TypeError) as e:
                        logger.error(f"Error processing subscription date: {e}")
                        
            except Exception as e:
                logger.error(f"Error checking subscriptions for {nickname}: {e}")
        
        logger.info(f"✅ Sent {notifications_sent} subscription notifications")
        
    except Exception as e:
        logger.error(f"Error in subscription renewals task: {e}", exc_info=True)


async def cleanup_old_data(bot: Bot):
    """Очищає старі дані (опціонально)"""
    logger.info("📅 Running scheduled task: data cleanup")
    # TODO: Реалізувати очищення даних старших N місяців
    pass


async def generate_weekly_report(bot: Bot):
    """Генерує щотижневий звіт для користувачів"""
    logger.info("📅 Running scheduled task: weekly report")
    
    try:
        worksheets = [
            ws.title for ws in sheets_service.spreadsheet.worksheets()
            if ws.title not in ["feedback_and_suggestions", "Sheet1", "reminder_settings"]
        ]
        
        for nickname in worksheets[:5]:  # Обмежуємо для тесту
            try:
                transactions = sheets_service.get_all_transactions(nickname)
                
                if not transactions:
                    continue
                
                user_id = int(transactions[0].get('user_id', 0))
                
                # Фільтруємо за останній тиждень
                week_ago = datetime.now().timestamp() - (7 * 24 * 60 * 60)
                week_transactions = [
                    t for t in transactions
                    if datetime.fromisoformat(t['date']).timestamp() > week_ago
                ]
                
                if not week_transactions:
                    continue
                
                total_income = sum(
                    float(t['amount']) for t in week_transactions
                    if float(t.get('amount', 0)) > 0
                )
                total_expense = sum(
                    abs(float(t['amount'])) for t in week_transactions
                    if float(t.get('amount', 0)) < 0
                )
                
                report = (
                    f"📊 <b>Твій тижневий звіт</b>\n\n"
                    f"📈 Доходи: {total_income:.2f} UAH\n"
                    f"📉 Витрати: {total_expense:.2f} UAH\n"
                    f"💰 Різниця: {total_income - total_expense:.2f} UAH\n\n"
                    f"Транзакцій за тиждень: {len(week_transactions)}"
                )
                
                await bot.send_message(chat_id=user_id, text=report)
                
            except Exception as e:
                logger.error(f"Error generating report for {nickname}: {e}")
        
        logger.info("✅ Weekly reports sent")
        
    except Exception as e:
        logger.error(f"Error in weekly report task: {e}", exc_info=True)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Налаштовує всі заплановані задачі"""
    scheduler = AsyncIOScheduler(timezone='Europe/Kiev')
    
    # Щоденні нагадування
    for reminder_time in config.REMINDER_TIMES:
        scheduler.add_job(
            send_daily_reminders,
            trigger=CronTrigger(
                hour=reminder_time['hour'],
                minute=reminder_time['minute']
            ),
            kwargs={'bot': bot},
            id=f"reminder_{reminder_time['hour']}_{reminder_time['minute']}"
        )
    
    # Перевірка підписок щодня о 9:00
    scheduler.add_job(
        check_subscription_renewals,
        trigger=CronTrigger(hour=10, minute=0),
        kwargs={'bot': bot},
        id='subscription_check'
    )
    
    # Тижневий звіт у неділю о 18:00
    scheduler.add_job(
        generate_weekly_report,
        trigger=CronTrigger(day_of_week='sun', hour=18, minute=0),
        kwargs={'bot': bot},
        id='weekly_report'
    )
    
    # Очищення даних щомісяця
    scheduler.add_job(
        cleanup_old_data,
        trigger=CronTrigger(day=1, hour=3, minute=0),
        kwargs={'bot': bot},
        id='data_cleanup'
    )
    
    scheduler.start()
    logger.info("✅ Scheduler configured with all tasks")
    
    return scheduler
