"""
notifications/telegram_bot.py

Module voor het versturen van Telegram-notificaties vanuit het AI Executive Team systeem.
Gebruikt de moderne asynchrone API van python-telegram-bot met een synchrone wrapper.

BELANGRIJK — parse_mode="HTML", niet "Markdown":
Legacy Telegram "Markdown" parse mode is erg fragiel: het begrijpt alleen
*enkele* sterretjes voor vet, en breekt zodra tekst dubbele sterretjes
("**vet**"), losse onderstrepingstekens, of andere markdown-achtige tekens
bevat — wat onvermijdelijk gebeurt zodra we vrije tekst van een LLM-agent of
een bestandspad in een bericht plakken. HTML mode is veel toleranter: alleen
&, < en > moeten worden ge-escaped in dynamische inhoud (zie escape_html()),
en onze eigen opmaak gebruikt expliciete tags (<b>, <code>) in plaats van
sterretjes, dus er is geen dubbelzinnigheid meer over waar opmaak begint/eindigt.
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


def escape_html(text: str) -> str:
    """
    Escaped &, < en > in willekeurige dynamische tekst (bestandspaden,
    agent-output, shell-commando's) voordat die in een HTML-bericht wordt
    geplakt. Gebruik dit ALTIJD voor dynamische inhoud — nooit voor je eigen
    letterlijke <b>/<code> tags in het bericht-template zelf.
    """
    if not isinstance(text, str):
        text = str(text)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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
            parse_mode="HTML"
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
        "✅ <b>Test message from the AI Executive Team system.</b>\n\n"
        "If you see this, notifications are working correctly!"
    )

    send_notification(test_message)
    print("=" * 60)
