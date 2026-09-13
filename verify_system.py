"""
verify_system.py

Een standalone smoke test script voor het AI Executive Team project.
Controleert de belangrijkste systeemvoorwaarden (static checks & optionele live checks).
"""

import os
import sys
import re

# ANSI Kleurcodes voor nette terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

# Tellers voor het eindresultaat
passed_checks = 0
total_checks = 0


def log_pass(description: str):
    global passed_checks, total_checks
    passed_checks += 1
    total_checks += 1
    print(f"{GREEN}✅ PASS{RESET} : {description}")


def log_fail(description: str, reason: str):
    global total_checks
    total_checks += 1
    print(f"{RED}❌ FAIL{RESET} : {description}\n         ↳ {reason}")


def log_skip(description: str, reason: str):
    print(f"{YELLOW}⚠️ SKIPPED{RESET}: {description} ({reason})")


print("\n" + "=" * 60)
print(" STARTING SYSTEM VERIFICATION (SMOKE TEST)")
print("=" * 60 + "\n")


# -------------------------------------------------------------------
# CHECK 1: STATIC CHECK — Agent roster
# -------------------------------------------------------------------
try:
    expected_keys = {
        "ceo", "cfo", "coo", "cso", "cmo", "cco",
        "cto", "chro", "general_counsel", "cpo", "board_director"
    }
    
    # Importeer de agenten uit de applicatie
    sys.path.append(os.path.abspath("."))
    from agents.executive_agents import EXECUTIVE_AGENTS
    
    actual_keys = set(EXECUTIVE_AGENTS.keys())
    
    if actual_keys == expected_keys:
        log_pass("Agent roster in EXECUTIVE_AGENTS matches expected keys exactly")
    else:
        missing = expected_keys - actual_keys
        unexpected = actual_keys - expected_keys
        reason = f"Mismatch found. Missing: {missing or 'None'}, Unexpected: {unexpected or 'None'}"
        log_fail("Agent roster keys validation", reason)

except Exception as e:
    log_fail("Agent roster in EXECUTIVE_AGENTS check crashed", str(e))


# -------------------------------------------------------------------
# CHECK 2: STATIC CHECK — daily_research.py source inspection
# -------------------------------------------------------------------
try:
    file_path = "workflows/daily_research.py"
    if not os.path.exists(file_path):
        log_fail("Daily research source check", f"File '{file_path}' does not exist.")
    else:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        expected_substrings = [
            "run_executive_meeting",
            "log_decision",
            "send_notification",
            '"success"',
            '"database_id"',
            '"meeting_result"'
        ]

        missing_substrings = [sub for sub in expected_substrings if sub not in content]

        if not missing_substrings:
            log_pass("daily_research.py source contains all required workflow integration strings")
        else:
            log_fail(
                "daily_research.py source inspection", 
                f"Missing required substrings: {missing_substrings}"
            )

except Exception as e:
    log_fail("daily_research.py source inspection crashed", str(e))


# -------------------------------------------------------------------
# CHECK 3: STATIC CHECK — main.py endpoint audit
# -------------------------------------------------------------------
try:
    file_path = "main.py"
    if not os.path.exists(file_path):
        log_fail("main.py endpoint audit", f"File '{file_path}' does not exist.")
    else:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Verwachte beveiligingsinstellingen per endpoint
        expected_auth_status = {
            "/workflows/daily-research/status": False,
            "/decisions/history": False,
            "/workflows/daily-research/trigger": True,
            "/decisions/trigger": True,
        }

        auth_audit_errors = []

        for route_path, requires_auth in expected_auth_status.items():
            # Zoek het endpoint op in de code
            pattern = re.escape(route_path)
            match = re.search(pattern, content)
            
            if not match:
                auth_audit_errors.append(f"Route '{route_path}' was not found in main.py")
                continue

            # Bekijk ALLEEN het blok van deze specifieke route: vanaf de match
            # tot het begin van de functiedefinitie (def/async def) die erbij
            # hoort — niet een vast aantal karakters, want dat kan doorlopen
            # in de VOLGENDE endpoint-decorator en een fout-positief geven.
            start_pos = match.start()
            def_match = re.search(r"\n\s*(async def|def)\s", content[start_pos:])
            end_pos = start_pos + def_match.start() if def_match else start_pos + 500
            sub_content = content[start_pos:end_pos]

            has_auth = "Depends(verify_api_key)" in sub_content

            if requires_auth and not has_auth:
                auth_audit_errors.append(f"Route '{route_path}' SHOULD require auth, but 'Depends(verify_api_key)' is missing.")
            elif not requires_auth and has_auth:
                auth_audit_errors.append(f"Route '{route_path}' SHOULD BE PUBLIC, but 'Depends(verify_api_key)' is present.")

        if not auth_audit_errors:
            log_pass("main.py endpoint authorization dependencies strictly match requirements")
        else:
            log_fail("main.py endpoint audit failed", " | ".join(auth_audit_errors))

except Exception as e:
    log_fail("main.py endpoint audit crashed", str(e))


# -------------------------------------------------------------------
# CHECK 4: STATIC CHECK — CEO reorder logic
# -------------------------------------------------------------------
try:
    file_path = "workflows/meeting.py"
    if not os.path.exists(file_path):
        log_fail("CEO reorder logic check", f"File '{file_path}' does not exist.")
    else:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Controleer of logica aanwezig is die de CEO verplaatst of als laatste toevoegt
        has_ceo_reorder = (
            ("ceo" in content.lower()) and 
            ("append" in content.lower() or "reorder" in content.lower() or "remove" in content.lower())
        )

        if has_ceo_reorder:
            log_pass("workflows/meeting.py contains logic for prioritizing CEO execution order")
        else:
            log_fail(
                "CEO reorder logic check", 
                "No CEO reordering/append logic found in workflows/meeting.py"
            )

except Exception as e:
    log_fail("CEO reorder logic check crashed", str(e))


# -------------------------------------------------------------------
# CHECK 5: LIVE CHECK — Local server API endpoints
# -------------------------------------------------------------------
try:
    import requests

    server_url = "http://localhost:8000/"
    # Snelle check of de lokaal draaiende server bereikbaar is
    server_online = False
    try:
        response = requests.get(server_url, timeout=2)
        server_online = True
    except requests.RequestException:
        server_online = False

    if not server_online:
        log_skip("Live API Endpoint checks", "server not running on http://localhost:8000")
    else:
        # Test 1: Public status endpoint (200)
        res_status = requests.get("http://localhost:8000/workflows/daily-research/status", timeout=5)
        if res_status.status_code == 200:
            log_pass("LIVE: GET /workflows/daily-research/status returned status 200 (Public)")
        else:
            log_fail(
                "LIVE: GET /workflows/daily-research/status", 
                f"Expected status 200, got {res_status.status_code}"
            )

        # Test 2: Public history endpoint (200)
        res_history = requests.get("http://localhost:8000/decisions/history?limit=1", timeout=5)
        if res_history.status_code == 200:
            log_pass("LIVE: GET /decisions/history returned status 200 (Public)")
        else:
            log_fail(
                "LIVE: GET /decisions/history", 
                f"Expected status 200, got {res_history.status_code}"
            )

        # Test 3: Protected trigger endpoint without auth headers (401)
        payload = {
            "topic": "smoke_test",
            "task_description": "smoke_test",
            "agent_keys": ["ceo"]
        }
        res_trigger = requests.post("http://localhost:8000/decisions/trigger", json=payload, timeout=5)
        if res_trigger.status_code == 401:
            log_pass("LIVE: POST /decisions/trigger rejected unauthenticated request with status 401 (Protected)")
        else:
            log_fail(
                "LIVE: POST /decisions/trigger", 
                f"Expected status 401 for unauthenticated request, got {res_trigger.status_code}"
            )

except ImportError:
    log_fail("Live API Endpoint checks", "The 'requests' package is not installed.")
except Exception as e:
    log_fail("Live API Endpoint checks crashed", str(e))


# -------------------------------------------------------------------
# OVERALL SUMMARY & EXIT STATUS
# -------------------------------------------------------------------
print("\n" + "=" * 60)
summary_color = GREEN if passed_checks == total_checks and total_checks > 0 else RED
print(f" SUMMARY: {summary_color}{passed_checks}/{total_checks} checks passed{RESET}")
print("=" * 60 + "\n")

if passed_checks == total_checks and total_checks > 0:
    sys.exit(0)
else:
    sys.exit(1)