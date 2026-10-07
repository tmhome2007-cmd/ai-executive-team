"""
system_checks.py

Kleine, gedeelde diagnostische controles — gebruikt zowel bij het opstarten
(een duidelijke waarschuwing als Ollama niet bereikbaar is, in plaats van een
verwarrende timeout/crash pas midden in een crew-run) als door het
/system/health endpoint voor doorlopende zichtbaarheid.
"""

import os
import sqlite3
import time

import requests

from config import config
from logging_config import get_logger

logger = get_logger(__name__)

# Onthoudt het opstarttijdstip van het PROCES (niet van de request) voor de
# uptime-weergave in /system/stats.
_PROCESS_START_TIME = time.time()


def get_uptime_seconds() -> float:
    return time.time() - _PROCESS_START_TIME


def check_ollama_reachable(timeout: float = 3.0) -> tuple[bool, str]:
    """
    Controleert of Ollama daadwerkelijk bereikbaar is op OLLAMA_BASE_URL.
    Retourneert (True, "ok") of (False, reden). Faalt snel (korte timeout) —
    dit is bedoeld als preflight-check, niet als vervanging voor de echte
    aanroep zelf.
    """
    try:
        response = requests.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=timeout)
        if response.status_code == 200:
            return True, "ok"
        return False, f"Ollama antwoordde met status {response.status_code}"
    except requests.exceptions.ConnectionError:
        return False, f"Kan geen verbinding maken met Ollama op {config.OLLAMA_BASE_URL} — draait 'ollama serve'?"
    except requests.exceptions.Timeout:
        return False, f"Ollama reageerde niet binnen {timeout}s"
    except Exception as e:
        return False, f"Onverwachte fout bij Ollama-check: {e}"


def check_database_writable() -> tuple[bool, str]:
    """Controleert of de database daadwerkelijk beschrijfbaar is (niet alleen dat het bestand bestaat)."""
    try:
        db_path = config.DATABASE_PATH
        os.makedirs(os.path.dirname(os.path.abspath(db_path)) or ".", exist_ok=True)
        conn = sqlite3.connect(db_path, timeout=3.0)
        try:
            # SELECT 1 bewijst alleen dat de database leesbaar is. BEGIN
            # IMMEDIATE vraagt SQLite om een echte write-reservering; op een
            # read-only database faalt dit direct, zonder dat we data hoeven
            # te wijzigen. Daarna rollen we de lege transactie meteen terug.
            conn.execute("BEGIN IMMEDIATE")
            conn.rollback()
        finally:
            conn.close()
        return True, "ok"
    except Exception as e:
        return False, f"Database niet beschrijfbaar: {e}"


def check_telegram_configured() -> tuple[bool, str]:
    """Controleert alleen of de benodigde waarden aanwezig ZIJN — verstuurt geen testbericht (kost geen API-call)."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return False, "TELEGRAM_BOT_TOKEN of TELEGRAM_CHAT_ID ontbreekt"
    return True, "ok"


def check_playwright_browser_installed() -> tuple[bool, str]:
    """
    Lanceert daadwerkelijk een echte Chromium-instantie en sluit hem meteen
    weer — dit is de enige volledig betrouwbare manier om te weten of de
    browser-binary die het geïnstalleerde Playwright-pakket verwacht
    daadwerkelijk aanwezig is (gokken op een bestandspad is onbetrouwbaar
    gebleken: we hebben zelf gezien dat het pakket build '1243' verwachtte
    terwijl alleen '1234' gedownload was). Dit is een EENMALIGE check bij het
    opstarten. Omdat deze functie de synchrone Playwright API gebruikt, moet
    de async FastAPI lifespan haar via asyncio.to_thread() uitvoeren; gewone
    synchrone routes mogen haar rechtstreeks aanroepen via FastAPI's threadpool.
    """
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        return True, "ok"
    except Exception as e:
        return False, (
            f"Chromium kon niet gestart worden: {e}. Waarschijnlijk oplossing: "
            f"./venv/bin/playwright install chromium"
        )


def run_startup_checks() -> None:
    """
    Wordt één keer aangeroepen bij het opstarten (main.py lifespan). Logt
    duidelijke waarschuwingen voor problemen die de app niet per se moeten
    blokkeren, maar wel de moeite waard zijn om meteen te weten — in plaats
    van pas te ontdekken dat Ollama niet draait wanneer de eerste crew-run
    na minuten stil faalt.
    """
    ollama_ok, ollama_msg = check_ollama_reachable()
    if ollama_ok:
        logger.info("Startup check: Ollama is bereikbaar.")
    else:
        logger.warning(f"Startup check: Ollama NIET bereikbaar — {ollama_msg}")

    db_ok, db_msg = check_database_writable()
    if db_ok:
        logger.info("Startup check: database is beschrijfbaar.")
    else:
        logger.warning(f"Startup check: database probleem — {db_msg}")

    tg_ok, tg_msg = check_telegram_configured()
    if tg_ok:
        logger.info("Startup check: Telegram-configuratie aanwezig.")
    else:
        logger.warning(f"Startup check: Telegram probleem — {tg_msg}")

    pw_ok, pw_msg = check_playwright_browser_installed()
    if pw_ok:
        logger.info("Startup check: Playwright/Chromium is bruikbaar.")
    else:
        logger.warning(f"Startup check: Playwright probleem — {pw_msg}")