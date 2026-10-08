"""
notifications/telegram_interactive.py

Maakt Telegram-notificaties over voorgestelde acties interactief: elk bericht
krijgt echte, aantikbare Approve / Reject / Execute knoppen, die rechtstreeks
dezelfde onderliggende functies aanroepen die de dashboard-knoppen ook
gebruiken (update_action_status, execute_action) — geen aparte, afwijkende
logica, gewoon een ander aanroeppunt voor exact hetzelfde gedrag, inclusief
alle veiligheidscontroles (danger patterns, workspace confinement) uit
workflows/action_executor.py.

BELANGRIJK — eigen thread, eigen event loop:
python-telegram-bot's Application (polling) wil zijn eigen event loop
beheren. Dit project draait al een event loop via uvicorn/FastAPI
(en de AsyncIOScheduler daarbinnen), dus de listener hier draait bewust in
een aparte OS-thread met een eigen, nieuw aangemaakte asyncio event loop —
zo kunnen de twee elkaar nooit in de weg zitten.
"""

import asyncio
import threading
import sys
import json
from pathlib import Path
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes
from telegram.error import Conflict as TelegramConflictError

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from config import config
from notifications.telegram_bot import send_notification_with_keyboard, escape_html
from memory.database import get_action_by_id
from workflows.action_control import (
    ActionControlError,
    approve_action_control,
    reject_action_control,
    execute_action_control,
)
from logging_config import get_logger

logger = get_logger(__name__)

# ------------------------------------------------------------------
# GEDEELDE STATE VOOR DE ACHTERGROND-THREAD
# ------------------------------------------------------------------
# Eén dictionary in plaats van losse globals, zodat start/stop elkaar netjes
# kunnen vinden zonder rommelige module-level `global` statements overal.
_state: dict = {
    "thread": None,
    "loop": None,
    "application": None,
    "stop_event": None,  # een asyncio.Event, aangemaakt BINNEN de eigen loop
    "started_successfully": False,  # wordt pas True NA een geslaagde start_polling()
    "last_error": None,  # laatste opstartfout, voor /system/health
}


def is_telegram_listener_alive() -> tuple[bool, Optional[str]]:
    """
    Retourneert (True, None) als de listener-thread leeft EN start_polling()
    daadwerkelijk is gelukt, anders (False, laatste_foutmelding). Gebruikt
    door /system/health, zodat een mislukte start (bijv. 'Conflict: terminated
    by other getUpdates request' — een ANDERE actieve proces pollt al met
    deze bot-token) zichtbaar is zonder in logs/app.log te hoeven graven.
    """
    thread = _state.get("thread")
    alive = thread is not None and thread.is_alive() and _state.get("started_successfully", False)
    return alive, _state.get("last_error")


# ------------------------------------------------------------------
# BERICHT- EN TOETSENBORD-OPBOUW
# ------------------------------------------------------------------
def build_action_keyboard(action_id: int, status: str) -> Optional[InlineKeyboardMarkup]:
    """
    Bouwt de juiste set knoppen voor de huidige status van een actie.
    - pending    -> Approve / Reject
    - approved   -> Execute / Reject
    - alles anders (rejected/executed/blocked/...) -> geen knoppen (eindstatus)
    """
    if status == "pending":
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Approve", callback_data=f"approve:{action_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject:{action_id}"),
        ]])
    elif status == "approved":
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("⚡ Execute", callback_data=f"execute:{action_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject:{action_id}"),
        ]])
    return None


def _telegram_safe_action_detail(action: dict) -> str:
    """Return enough detail for remote review without exporting file contents."""
    action_type = action.get("action_type", "shell")
    raw = action.get("action_detail", "") or ""
    if action_type == "file_operation":
        try:
            detail = json.loads(raw)
            operation = str(detail.get("operation", "unknown"))
            path = str(detail.get("file_path", "unknown"))
            content = detail.get("content", "")
            if operation in {"write", "append"}:
                return (
                    f"[{operation}] {path} — file body hidden from Telegram "
                    f"({len(content) if isinstance(content, str) else 0} characters); "
                    "review locally before approval"
                )
            return f"[{operation}] {path}"
        except Exception:
            return "[file_operation] details hidden from Telegram; review locally"
    if action_type == "browser_action":
        try:
            detail = json.loads(raw)
            url = str(detail.get("url", ""))
            selector = detail.get("click_selector")
            return f"[navigate] {url}" + (f" [click] {selector}" if selector else "")
        except Exception:
            return "[browser_action] malformed details; review locally"
    # Shell commands need exact remote review, but cap message size.
    return raw[:1000] + ("… [truncated; review locally]" if len(raw) > 1000 else "")


def format_action_message(action: dict, footer: str = "") -> str:
    """
    Build Telegram control text from DB state without exporting file bodies or
    command output. Telegram is a control surface, not a data-export channel.
    """
    safe_detail = _telegram_safe_action_detail(action)
    text = (
        f"⏳ <b>ACTION PROPOSAL #{action['id']}</b>\n\n"
        f"<b>Proposed By:</b> {escape_html(action['proposed_by'])}\n"
        f"<b>Description:</b> {escape_html(action['action_description'])}\n"
        f"<b>Detail:</b> <code>{escape_html(safe_detail)}</code>\n"
        f"<b>Status:</b> {escape_html(action['status'])}"
    )
    if footer:
        text += f"\n\n{footer}"
    return text


def send_proposal_notification(
    action_id: int, proposed_by: str, action_description: str, action_detail: str
) -> None:
    """
    Verstuurt de initiële voorstel-notificatie MET Approve/Reject knoppen.
    Wordt aangeroepen vanuit tools/action_proposal_tool.py in plaats van de
    oude platte send_notification() aanroep.
    """
    action = get_action_by_id(action_id) or {
        "id": action_id,
        "proposed_by": proposed_by,
        "action_description": action_description,
        "action_detail": action_detail,
        "action_type": "unknown",
        "status": "pending",
    }
    message = format_action_message(action)
    keyboard = build_action_keyboard(action_id, "pending")
    send_notification_with_keyboard(message, keyboard)


# ------------------------------------------------------------------
# KNOP-CALLBACK HANDLER
# ------------------------------------------------------------------
async def handle_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query

    # KRITIEKE CONTROLE: verifieer dat dit bericht ECHT van de eigenaar komt.
    # Zonder deze check zou ELKE Telegram-gebruiker die deze bot vindt en een
    # bericht stuurt (of ooit een callback triggert) real-world acties kunnen
    # goedkeuren, afwijzen of UITVOEREN op deze machine. Een bot-username is
    # geen geheim — dit moet ALTIJD expliciet worden gecontroleerd.
    sender_chat_id = str(update.effective_chat.id) if update.effective_chat else None
    sender_user_id = str(update.effective_user.id) if update.effective_user else None
    chat_type = getattr(update.effective_chat, "type", None) if update.effective_chat else None
    owner_chat_id = str(getattr(config, "TELEGRAM_CHAT_ID", "")).strip()

    # Remote approvals are intentionally supported ONLY from a private chat
    # whose user ID matches the configured owner chat ID. In a Telegram group,
    # every member shares the same chat ID; checking chat ID alone would let
    # any group member approve/execute actions.
    if (
        not owner_chat_id
        or sender_chat_id != owner_chat_id
        or sender_user_id != owner_chat_id
        or chat_type != "private"
    ):
        # Bewust een generiek antwoord — geen details weggeven aan wie dan
        # ook die dit probeert, en niets loggen dat een aanvaller nuttig zou
        # vinden (geen actie-ID's, geen systeeminformatie).
        try:
            await query.answer("Unauthorized.", show_alert=True)
        except Exception:
            pass
        logger.warning(f"Blocked Telegram callback from unauthorized chat_id: {sender_chat_id}")
        return

    try:
        action_type, action_id_str = query.data.split(":")
        action_id = int(action_id_str)
    except (ValueError, AttributeError):
        await query.answer("Invalid button data.", show_alert=True)
        return

    # Haal de ACTUELE status uit de database op — nooit vertrouwen op wat er
    # toevallig in het bericht stond, voor het geval iemand al eerder op een
    # andere knop heeft getikt (of via de dashboard al iets heeft gedaan).
    action = get_action_by_id(action_id)
    if action is None:
        await query.answer("This action no longer exists.", show_alert=True)
        return

    current_status = action["status"]

    # ---- APPROVE ----
    if action_type == "approve":
        if current_status != "pending":
            await query.answer(f"Already '{current_status}' — cannot approve again.", show_alert=True)
            return
        try:
            approve_action_control(action_id)
        except ActionControlError as exc:
            await query.answer(str(exc)[:180], show_alert=True)
            return
        await query.answer("Approved ✅")
        action = get_action_by_id(action_id) or action
        action["status"] = "approved"
        new_text = format_action_message(action, footer="✅ <b>APPROVED</b> via Telegram.")
        new_keyboard = build_action_keyboard(action_id, "approved")

    # ---- REJECT ----
    elif action_type == "reject":
        if current_status not in ("pending", "approved"):
            await query.answer(f"Already '{current_status}' — cannot reject now.", show_alert=True)
            return
        try:
            reject_action_control(action_id)
        except ActionControlError as exc:
            await query.answer(str(exc)[:180], show_alert=True)
            return
        await query.answer("Rejected ❌")
        action = get_action_by_id(action_id) or action
        action["status"] = "rejected"
        new_text = format_action_message(action, footer="❌ <b>REJECTED</b> via Telegram.")
        new_keyboard = None

    # ---- EXECUTE ----
    elif action_type == "execute":
        if current_status != "approved":
            await query.answer(f"Must be 'approved' first (currently '{current_status}').", show_alert=True)
            return
        await query.answer("Executing...")
        # execute_action() is sync and may run a real subprocess (up to the
        # existing 30s timeout) — run it in a worker thread so this callback
        # handler never blocks the bot's own event loop while it waits.
        try:
            result = await asyncio.to_thread(execute_action_control, action_id)
        except ActionControlError as exc:
            await query.answer(str(exc)[:180], show_alert=True)
            return

        refreshed = get_action_by_id(action_id) or action
        if result.get("blocked"):
            footer = f"🚫 <b>BLOCKED</b>: {escape_html(result.get('error', 'Unknown reason'))}"
        elif result.get("success") and result.get("mode") == "dry_run":
            footer = f"🧪 <b>EXECUTED (DRY RUN)</b>\n{escape_html(result.get('detail', ''))}"
        elif result.get("success"):
            footer = (
                "⚡ <b>EXECUTED SUCCESSFULLY</b>\n"
                "Execution output is retained locally and is not copied to Telegram."
            )
        else:
            footer = f"❌ <b>EXECUTION FAILED</b>: {escape_html(result.get('error', 'Unknown error'))}"

        new_text = format_action_message(refreshed, footer=footer)
        new_keyboard = None

    else:
        await query.answer("Unknown action.", show_alert=True)
        return

    try:
        await query.edit_message_text(text=new_text, parse_mode="HTML", reply_markup=new_keyboard)
    except Exception as e:
        # Bewerken kan falen als het bericht al identiek is, of te oud is —
        # dit mag de bot nooit laten crashen.
        logger.warning(f"Could not edit Telegram message after button tap: {e}")


# ------------------------------------------------------------------
# START / STOP VAN DE ACHTERGROND-LISTENER
# ------------------------------------------------------------------
def _run_listener_in_thread() -> None:
    """Draait in een eigen OS-thread met een eigen, nieuwe event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _state["loop"] = loop

    async def _main() -> None:
        stop_event = asyncio.Event()
        _state["stop_event"] = stop_event

        application = None
        initialized = False
        started = False
        polling_started = False

        try:
            application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
            application.add_handler(CallbackQueryHandler(handle_button_callback))
            _state["application"] = application

            await application.initialize()
            initialized = True
            await application.start()
            started = True
            await application.updater.start_polling(drop_pending_updates=True)
            polling_started = True

            _state["started_successfully"] = True
            _state["last_error"] = None
            logger.info("Telegram interactive listener started (polling for button taps).")

            await stop_event.wait()
            logger.info("Telegram interactive listener shutting down...")

        except TelegramConflictError as e:
            _state["last_error"] = (
                f"Conflict: another process is already polling this bot token. "
                f"Stop any other running instance of this app (check for zombie "
                f"processes from a previous --reload restart) before retrying. ({e})"
            )
            logger.error(f"Telegram listener FAILED to start: {_state['last_error']}")

        except Exception as e:
            _state["last_error"] = f"Unexpected error during startup/runtime: {e}"
            logger.error(f"Telegram listener FAILED/crashed: {e}", exc_info=True)

        finally:
            # Ook bij een gedeeltelijke startup (initialize/start gelukt maar
            # start_polling gefaald) altijd de reeds geopende resources sluiten.
            _state["started_successfully"] = False
            if application is not None:
                if polling_started:
                    try:
                        await application.updater.stop()
                    except Exception as cleanup_err:
                        logger.warning(f"Telegram updater cleanup failed: {cleanup_err}")
                if started:
                    try:
                        await application.stop()
                    except Exception as cleanup_err:
                        logger.warning(f"Telegram application stop failed: {cleanup_err}")
                if initialized:
                    try:
                        await application.shutdown()
                    except Exception as cleanup_err:
                        logger.warning(f"Telegram application shutdown failed: {cleanup_err}")

    try:
        loop.run_until_complete(_main())
    except Exception as e:
        _state["last_error"] = f"Listener thread crashed: {e}"
        logger.error(f"Telegram listener thread crashed unexpectedly: {e}", exc_info=True)
    finally:
        _state["started_successfully"] = False
        _state["application"] = None
        _state["stop_event"] = None
        _state["loop"] = None
        loop.close()


def start_telegram_listener() -> None:
    """
    Start de interactieve listener in een achtergrond-thread. Doet niets
    (met een duidelijke waarschuwing) als er geen bot token is geconfigureerd,
    zodat het systeem prima blijft werken zonder Telegram als dat gewenst is.
    """
    if not getattr(config, "TELEGRAM_BOT_TOKEN", "").strip():
        logger.warning("Telegram interactive listener NOT started: TELEGRAM_BOT_TOKEN is not set.")
        return

    if _state["thread"] is not None and _state["thread"].is_alive():
        logger.info("Telegram interactive listener is already running.")
        return

    thread = threading.Thread(target=_run_listener_in_thread, daemon=True, name="telegram-listener")
    _state["thread"] = thread
    thread.start()


def stop_telegram_listener() -> None:
    """Signaleert de achtergrond-thread om netjes te stoppen, en wacht erop."""
    loop = _state.get("loop")
    stop_event = _state.get("stop_event")

    thread = _state.get("thread")

    if loop is None or stop_event is None or loop.is_closed():
        # De listener kan tijdens startup al gefaald en zijn event loop gesloten
        # hebben. In dat geval is er niets meer te signaleren; alleen eventueel
        # de thread kort joinen zodat shutdown deterministisch blijft.
        if thread is not None and thread.is_alive():
            thread.join(timeout=10)
        return

    try:
        loop.call_soon_threadsafe(stop_event.set)
    except RuntimeError as e:
        # Race: de listener-thread kan precies tussen de state-read hierboven
        # en deze call zijn gestopt. Dat mag application shutdown niet breken.
        logger.warning(f"Telegram listener loop was already closed during shutdown: {e}")

    if thread is not None:
        thread.join(timeout=10)