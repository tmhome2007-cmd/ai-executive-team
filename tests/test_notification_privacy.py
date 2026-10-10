"""Regression checks for notification privacy."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from config import config
from notifications.telegram_bot import (
    send_notification_async,
    send_notification_with_keyboard_async,
)


class NotificationPrivacyTests(unittest.TestCase):
    def test_transport_receives_no_business_details_and_errors_do_not_reveal_token(
        self,
    ):
        saved = (
            config.TELEGRAM_BOT_TOKEN,
            config.TELEGRAM_CHAT_ID,
            config.TELEGRAM_INCLUDE_SENSITIVE_DETAILS,
        )
        config.TELEGRAM_BOT_TOKEN = "123456:synthetic-only"
        config.TELEGRAM_CHAT_ID = "synthetic-chat"
        config.TELEGRAM_INCLUDE_SENSITIVE_DETAILS = False
        try:
            bot = SimpleNamespace(
                send_message=AsyncMock(return_value=SimpleNamespace(message_id=1))
            )
            with patch("notifications.telegram_bot.Bot", return_value=bot):
                asyncio.run(
                    send_notification_async("Private synthetic budget and file path")
                )
                asyncio.run(
                    send_notification_with_keyboard_async("Private synthetic action")
                )
                for call in bot.send_message.call_args_list:
                    self.assertEqual(
                        call.kwargs["text"],
                        "AI Executive Team update. Review the local dashboard for details.",
                    )
                bot.send_message.side_effect = RuntimeError(
                    "Secret token: 123456:synthetic-only"
                )
                with self.assertRaisesRegex(
                    RuntimeError, "^Telegram transport failed; details suppressed$"
                ):
                    asyncio.run(send_notification_async("Private synthetic budget"))
        finally:
            (
                config.TELEGRAM_BOT_TOKEN,
                config.TELEGRAM_CHAT_ID,
                config.TELEGRAM_INCLUDE_SENSITIVE_DETAILS,
            ) = saved
