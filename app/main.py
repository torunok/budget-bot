"""
Точка входу додатку
Налаштування webhook та запуск бота
"""

import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from app.config.settings import config, logger
from app.core.bot import dp, bot # Припускається, що dp та bot тут вже ініціалізовані
from app.handlers import register_all_handlers
from app.scheduler.tasks import setup_scheduler
from app.middlewares import setup_middlewares # Припускається, що ви його використовуєте


async def on_startup(app: web.Application) -> None:
    """Дії при запуску бота: встановлення Webhook та запуск планувальника"""

    # Налаштування webhook
    try:
        webhook_result = await bot.set_webhook(
            url=config.WEBHOOK_URL,
            secret_token=config.WEBHOOK_SECRET_TOKEN,
            drop_pending_updates=True
        )
        if webhook_result:
            logger.info(f"✅ Webhook set to: {config.WEBHOOK_URL}")
        else:
            logger.critical(f"❌ Webhook set returned False from aiogram!") 
            raise Exception("Telegram API returned non-success on set_webhook") 
            
    except Exception as e: 
        logger.critical(f"❌ Failed to set webhook! {e}", exc_info=True)
        raise

    # Запуск планувальника задач
    scheduler = setup_scheduler(bot)
    app['scheduler'] = scheduler
    logger.info("✅ Scheduler started")


async def on_shutdown(app: web.Application) -> None:
    """Дії при зупинці бота"""
    logger.info("⏹️ Shutting down bot...")
    
    # Зупинка планувальника
    if 'scheduler' in app:
        app['scheduler'].shutdown()
    
    # Видалення webhook
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.session.close()
    
    logger.info("✅ Bot shutdown complete")


async def health_check(request: web.Request) -> web.Response:
    """Health check endpoint для Render.com"""
    return web.Response(text="OK", status=200)


def create_app() -> web.Application:
    """Створення aiohttp додатку"""
    
    # 🔥 ВИПРАВЛЕНО 🔥: Передаємо 'logger' як другий аргумент, відповідно до змін у __init__.py
    register_all_handlers(dp, logger)
    logger.info("✅ All handlers successfully registered in Dispatcher.")
    
    app = web.Application()
    
    # Webhook handler
    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=config.WEBHOOK_SECRET_TOKEN,
    )
    # WEBHOOK_PATH повинен відповідати шляху, який ви використовуєте у WEBHOOK_URL
    webhook_handler.register(app, path=config.WEBHOOK_PATH) 
    
    # Health check endpoints
    app.router.add_get("/health", health_check)
    app.router.add_get("/", health_check)
    
    # Startup/shutdown hooks
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    
    # Налаштування aiogram
    setup_application(app, dp, bot=bot)
    
    return app


def main():
    """Запуск додатку"""
    try:
        logger.info(f"🌍 Environment: {config.SENTRY_ENVIRONMENT}")
        logger.info(f"🔧 Starting web server on {config.WEB_SERVER_HOST}:{config.WEB_SERVER_PORT}")
        
        app = create_app()
        web.run_app(
            app,
            host=config.WEB_SERVER_HOST,
            port=config.WEB_SERVER_PORT,
            print=None  # Вимкнути стандартний вивід aiohttp
        )
    except Exception as e:
        logger.critical(f"❌ Failed to start bot: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
