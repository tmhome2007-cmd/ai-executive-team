"""
notifications/telegram_bot.py

Module voor het versturen van Telegram-notificaties vanuit het AI Executive Team systeem.
Gebruikt de moderne asynchrone API van python-telegram-bot met een synchrone wrapper.
"""

import asyncio
import sys
from pathlib import Path
from telegram import Bot

# Zorg dat de hoofdmap van het project bereikbaar is voor imports
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from config import config


async def send_notification_async(message: str) -> None:
    """
    Verstuurt asynchroon een Telegram-bericht met behulp van de geconfigureerde bot token en chat ID.
    Vangt fouten op zodat de aanroepende code nooit crasht.
    """
    token = getattr(config, "TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = getattr(config, "TELEGRAM_CHAT_ID", "").strip()

    # 1. Controleer of de vereiste variabelen aanwezig zijn
    if not token or not chat_id:
        raise ValueError(
            "CRITICAL ERROR: TELEGRAM_BOT_TOKEN of TELEGRAM_CHAT_ID ontbreekt of is leeg. "
            "Controleer je .env bestand en zorg dat beide variabelen zijn ingesteld."
        )

    # 2. Verstuur het bericht via de Telegram Bot API
    try:
        bot = Bot(token=token)
        await bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode="Markdown"
        )
        print("Telegram notificatie succesvol verzonden!")
    except Exception as e:
        # Vang eventuele fouten op zonder de applicatie te laten crashen
        print(f"Failed to send Telegram notification: {e}")


def send_notification(message: str) -> None:
    """
    Synchrone wrapper om send_notification_async aan te roepen vanuit normale Python-code.
    """
    try:
        asyncio.run(send_notification_async(message))
    except Exception as e:
        print(f"Error running Telegram notification event loop: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("TELEGRAM NOTIFICATION TEST")
    print("=" * 60)
    
    test_message = (
        "✅ *Test message from the AI Executive Team system.*\n\n"
        "If you see this, notifications are working correctly!"
    )
    
    send_notification(test_message)
    print("=" * 60)
