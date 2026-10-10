"""Cross-process locking for action execution claims.

Eén gedeelde, systeembrede lock die voorkomt dat er ooit twee zware CrewAI-runs
tegelijk draaien — bijvoorbeeld de geplande dagelijkse research die toevallig
start terwijl je zelf handmatig een ad-hoc vraag stelt via /decisions/trigger.
Zonder deze lock zouden zulke overlappende runs de CPU/GPU-belasting (en dus
de warmteontwikkeling) simpelweg optellen, zonder dat je dat ziet aankomen.

Gebruik:
- Vanuit SYNCHRONE code (zoals workflows/meeting.py, dat vanuit een sync
  FastAPI-endpoint of via asyncio.to_thread draait): gebruik gewoon
  `with EXECUTION_LOCK:` rond de kickoff-aanroep.
- Vanuit ASYNCHRONE code die rechtstreeks kickoff_async() aanroept (zoals
  workflows/daily_research.py): gebruik de meegeleverde helper
  `acquire_execution_lock_async()` / `release_execution_lock()`, zodat het
  wachten op de lock de event loop niet blokkeert.
"""

import asyncio
import threading

# EEN enkele, proces-brede lock. Bewust een threading.Lock (niet asyncio.Lock),
# omdat zowel sync code (meeting.py, direct aangeroepen vanuit een sync
# FastAPI-endpoint) als async code (daily_research.py) hem moeten kunnen
# gebruiken zonder twee aparte, niet-compatibele lock-werelden te krijgen.
EXECUTION_LOCK = threading.Lock()


async def acquire_execution_lock_async() -> None:
    """
    Wacht (indien nodig) tot de lock vrij is, vanuit async code — zonder de
    event loop te blokkeren terwijl er gewacht wordt. Gebruik dit in plaats
    van EXECUTION_LOCK.acquire() rechtstreeks binnen een async functie.
    """
    await asyncio.to_thread(EXECUTION_LOCK.acquire)


def release_execution_lock() -> None:
    """Geeft de lock vrij. release() blokkeert nooit, dus geen to_thread nodig."""
    if EXECUTION_LOCK.locked():
        EXECUTION_LOCK.release()
