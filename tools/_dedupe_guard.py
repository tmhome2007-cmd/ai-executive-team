"""
tools/_dedupe_guard.py

Gedeelde, in-memory bescherming tegen een agent die dezelfde tool-aanroep
herhaaldelijk achter elkaar doet (waargenomen incident: CFO riep
propose_file_operation 13x aan voor hetzelfde bestand binnen één taak,
wat 13 losse database-rijen en 13 Telegram-notificaties genereerde voordat
de gebruiker de server hard moest killen).

Dit is een TWEEDE, onafhankelijke beveiligingslaag naast max_iter op de
Agent zelf: zelfs als max_iter om wat voor reden dan ook te hoog zou staan,
stopt dit een identieke herhaalde aanroep binnen hetzelfde korte tijdvenster
alsnog vóórdat er weer een nieuwe database-rij en Telegram-bericht ontstaat.
"""

import time
from typing import Optional

# key -> laatste timestamp waarop dezelfde aanroep werd gezien
_recent_proposals: dict[str, float] = {}

DEDUPE_WINDOW_SECONDS = 90


def check_and_register_proposal(dedupe_key: str) -> Optional[str]:
    """
    Controleert of dezelfde aanroep (via dedupe_key) al binnen het
    tijdvenster is voorgesteld. Als dat zo is, retourneert het een
    duidelijke boodschap voor de agent (om te helpen de loop te doorbreken)
    ZONDER opnieuw te registreren. Als het een nieuwe aanroep is, registreert
    het de aanroep en retourneert het None.
    """
    now = time.time()

    # Ruim oude entries op zodat deze dict niet onbeperkt blijft groeien
    stale_keys = [k for k, ts in _recent_proposals.items() if now - ts > DEDUPE_WINDOW_SECONDS]
    for k in stale_keys:
        del _recent_proposals[k]

    last_seen = _recent_proposals.get(dedupe_key)
    if last_seen is not None and (now - last_seen) < DEDUPE_WINDOW_SECONDS:
        return (
            "DUPLICATE CALL DETECTED: You already proposed this exact action moments ago. "
            "Do NOT call this tool again for the same action — it has already been logged and "
            "is pending human review. Provide your final written answer now instead."
        )

    _recent_proposals[dedupe_key] = now
    return None
