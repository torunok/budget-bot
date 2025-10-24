"""
Точка входу додатку з повною діагностикою
"""

import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.types import Update
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from app.config.settings import config, logger
from app.core.bot import dp, bot
from app.handlers import register_all_handlers
from app.scheduler.tasks import setup_scheduler


# ======================================
# ДІАГНОСТИЧНИЙ MIDDLEWARE
# ======================================
class DiagnosticMiddleware(BaseMiddleware):
    """Детальне логування всіх оновлень"""
    
    async def __call__(self, handler, event: Update, data: dict):
        logger.info("=" * 60)
        logger.info(f"📥 INCOMING UPDATE: {event.update_id}")
        logger.info(f"📋 Event type: {event.event_type}")
        
        if event.message:
            msg = event.message
            logger.info(f"💬 Message ID: {msg.message_id}")
            logger.info(f"👤 From: @{msg.from_user.username} (ID: {msg.from_user.id})")
            logger.info(f"📝 Text: {msg.text}")
            logger.info(f"📅 Date: {msg.date}")
        
        if event.callback_query:
            cb = event.callback_query
            logger.info(f"🔘 Callback ID: {cb.id}")
            logger.info(f"👤 From: @{cb.from_user.username}")
            logger.info(f"📝 Data: {cb.data}")
        
        try:
            logger.info("🔄 Processing update...")
            result = await handler(event, data)
            logger.info(f"✅ Update {event.update_id} processed successfully!")
            logger.info("=" * 60)
            return result
        except Exception as e:
            logger.error(f"❌ ERROR processing update {event.update_id}:", exc_info=True)
            logger.info("=" * 60)
            raise


# ======================================
# WEBHOOK HANDLER З ЛОГУВАННЯМ
# ======================================
async def webhook_handler(request: web.Request) -> web.Response:
    """Обробка вхідних webhook запитів з детальним логуванням"""
    logger.info("🌐 Webhook request received!")
    logger.info(f"   Method: {request.method}")
    logger.info(f"   Path: {request.path}")
    logger.info(f"   Headers: {dict(request.headers)}")
    
    # Перевірка secret token
    secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    logger.info(f"🔐 Received token: {secret_token}")
    logger.info(f"🔐 Expected token: {config.WEBHOOK_SECRET_TOKEN}")
    
    if secret_token != config.WEBHOOK_SECRET_TOKEN:
        logger.warning(f"⚠️  Invalid secret token! Received: {secret_token}, Expected: {config.WEBHOOK_SECRET_TOKEN}")
        return web.Response(status=403, text="Forbidden")
    
    logger.info("✅ Secret token valid")
    
    try:
        # Читаємо body
        body = await request.read()
        logger.info(f"📦 Body length: {len(body)} bytes")
        
        # Передаємо в aiogram handler
        update = Update.model_validate_json(body)
        logger.info(f"✅ Update parsed: {update.update_id}")
        
        await dp.feed_update(bot, update)
        logger.info("✅ Update fed to dispatcher")
        
        return web.Response(status=200, text="OK")
    except Exception as e:
        logger.error(f"❌ Webhook handler error: {e}", exc_info=True)
        return web.Response(status=500, text="Internal Server Error")


# ======================================
# STARTUP / SHUTDOWN
# ======================================
async def on_startup(app: web.Application) -> None:
    """Дії при запуску бота"""
    
    logger.info("🚀 Starting bot...")
    
    # Видаляємо старий webhook
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("🗑️  Old webhook deleted")
    except Exception as e:
        logger.warning(f"⚠️  Could not delete old webhook: {e}")
    
    await asyncio.sleep(1)
    
    # Встановлюємо новий webhook
    try:
        webhook_url = config.WEBHOOK_URL
        logger.info(f"🔧 Setting webhook to: {webhook_url}")
        logger.info(f"🔐 Secret token: {config.WEBHOOK_SECRET_TOKEN[:10]}...")
        
        webhook_result = await bot.set_webhook(
            url=webhook_url,
            secret_token=config.WEBHOOK_SECRET_TOKEN,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"]
        )
        
        if webhook_result:
            logger.info(f"✅ Webhook set successfully!")
            logger.info(f"Secret token being used: {config.WEBHOOK_SECRET_TOKEN}")
            
            # Перевірка
            webhook_info = await bot.get_webhook_info()
            logger.info(f"📋 Webhook URL: {webhook_info.url}")
            logger.info(f"📋 Pending updates: {webhook_info.pending_update_count}")
            logger.info(f"📋 Last error: {webhook_info.last_error_date}")
            
            if webhook_info.last_error_message:
                logger.error(f"⚠️  Last error message: {webhook_info.last_error_message}")
            
            if webhook_info.url != webhook_url:
                raise Exception(f"Webhook URL mismatch! Expected: {webhook_url}, Got: {webhook_info.url}")
        else:
            raise Exception("set_webhook returned False")
            
    except Exception as e:
        logger.critical(f"❌ Failed to set webhook: {e}", exc_info=True)
        raise

    # Запуск планувальника
    scheduler = setup_scheduler(bot)
    app['scheduler'] = scheduler
    logger.info("✅ Scheduler started")
    
    logger.info("🎉 Bot startup complete!")


async def on_shutdown(app: web.Application) -> None:
    """Дії при зупинці бота"""
    logger.info("⏹️  Shutting down bot...")
    
    if 'scheduler' in app:
        app['scheduler'].shutdown()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.session.close()
    
    logger.info("✅ Bot shutdown complete")


async def health_check(request: web.Request) -> web.Response:
    """Health check endpoint"""
    return web.Response(text="OK", status=200)


# ======================================
# CREATE APP
# ======================================
def create_app() -> web.Application:
    """Створення aiohttp додатку"""
    
    logger.info("🔧 Creating application...")
    
    # Додаємо діагностичний middleware
    dp.update.middleware(DiagnosticMiddleware())
    logger.info("✅ Diagnostic middleware registered")
    
    # Реєстрація хендлерів
    register_all_handlers(dp, logger)
    logger.info("✅ All handlers registered")
    
    app = web.Application()
    
    # Ручний webhook handler (для більшого контролю)
    app.router.add_post(config.WEBHOOK_PATH, webhook_handler)
    logger.info(f"✅ Webhook handler registered at {config.WEBHOOK_PATH}")
    
    # Health checks
    app.router.add_get("/health", health_check)
    app.router.add_get("/", health_check)
    
    # Lifecycle
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    
    return app


# ======================================
# MAIN
# ======================================
def main():
    """Запуск додатку"""
    try:
        logger.info("=" * 60)
        logger.info("🤖 BUDGET BOT STARTING")
        logger.info("=" * 60)
        logger.info(f"🌍 Environment: {config.SENTRY_ENVIRONMENT}")
        logger.info(f"🔧 Host: {config.WEB_SERVER_HOST}")
        logger.info(f"🔧 Port: {config.WEB_SERVER_PORT}")
        logger.info(f"🔧 Webhook path: {config.WEBHOOK_PATH}")
        logger.info(f"🔧 Full webhook URL: {config.WEBHOOK_URL}")
        logger.info("=" * 60)
        
        app = create_app()
        web.run_app(
            app,
            host=config.WEB_SERVER_HOST,
            port=config.WEB_SERVER_PORT,
            print=None
        )
    except Exception as e:
        logger.critical(f"❌ Failed to start bot: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()