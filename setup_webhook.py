# File: setup_webhook.py

"""
Скрипт для встановлення та перевірки webhook
Запустіть: python setup_webhook.py
"""

import requests
import json

# Ваші дані
BOT_TOKEN = "8211488233:AAFLVqxx24zwrdOiCMA_iEWhP6H4fDfOQ5s"
WEBHOOK_URL = "https://budget-telegram-bot-jfuh.onrender.com/webhook"

def set_webhook():
    """Встановлення webhook"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    
    payload = {
        "url": WEBHOOK_URL,
        "drop_pending_updates": True,
        "allowed_updates": ["message", "callback_query"]
    }
    
    print("🔧 Setting webhook...")
    print(f"📍 URL: {WEBHOOK_URL}")
    
    response = requests.post(url, json=payload)
    result = response.json()
    
    print("\n📋 Response:")
    print(json.dumps(result, indent=2))
    
    if result.get("ok"):
        print("\n✅ Webhook set successfully!")
    else:
        print(f"\n❌ Error: {result.get('description')}")
    
    return result.get("ok")


def get_webhook_info():
    """Перевірка статусу webhook"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
    
    print("\n🔍 Checking webhook status...")
    
    response = requests.get(url)
    result = response.json()
    
    if result.get("ok"):
        info = result.get("result", {})
        print("\n📋 Webhook Info:")
        print(f"  URL: {info.get('url', 'NOT SET')}")
        print(f"  Pending updates: {info.get('pending_update_count', 0)}")
        print(f"  Last error date: {info.get('last_error_date', 0)}")
        
        if info.get('last_error_message'):
            print(f"  ⚠️  Last error: {info.get('last_error_message')}")
        
        if info.get('url') == WEBHOOK_URL:
            print("\n✅ Webhook is configured correctly!")
        elif info.get('url'):
            print(f"\n⚠️  Webhook URL mismatch!")
            print(f"     Expected: {WEBHOOK_URL}")
            print(f"     Current:  {info.get('url')}")
        else:
            print("\n❌ Webhook is NOT set!")
    else:
        print(f"\n❌ Error: {result.get('description')}")
    
    return result


def delete_webhook():
    """Видалення webhook"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
    
    print("\n🗑️  Deleting webhook...")
    
    response = requests.post(url, json={"drop_pending_updates": True})
    result = response.json()
    
    if result.get("ok"):
        print("✅ Webhook deleted!")
    else:
        print(f"❌ Error: {result.get('description')}")
    
    return result.get("ok")


def main():
    """Головна функція"""
    print("=" * 60)
    print("🤖 Telegram Webhook Setup Tool")
    print("=" * 60)
    
    # Спочатку перевіряємо поточний стан
    get_webhook_info()
    
    # Видаляємо старий webhook
    delete_webhook()
    
    # Чекаємо секунду
    import time
    time.sleep(1)
    
    # Встановлюємо новий webhook
    success = set_webhook()
    
    if success:
        # Перевіряємо результат
        time.sleep(1)
        get_webhook_info()
        
        print("\n" + "=" * 60)
        print("✅ Setup complete! Try sending /start to your bot")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("❌ Setup failed! Check the errors above")
        print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()