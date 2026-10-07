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

        # Verwachte beveiligingsinstellingen per endpoint. Na de security-
        # hardeningsronde zijn /workflows/daily-research/status en
        # /decisions/history bewust NIET meer publiek — ze konden bedrijfs-
        # gevoelige inhoud tonen zonder sleutel.
        expected_auth_status = {
            "/workflows/daily-research/status": True,
            "/decisions/history": True,
            "/workflows/daily-research/trigger": True,
            "/decisions/trigger": True,
            "/screenshots/{filename}": True,
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
        # Test 1: daily-research/status now requires auth — expect 401 without a key
        res_status = requests.get("http://localhost:8000/workflows/daily-research/status", timeout=5)
        if res_status.status_code == 401:
            log_pass("LIVE: GET /workflows/daily-research/status rejected unauthenticated request with status 401 (Protected)")
        else:
            log_fail(
                "LIVE: GET /workflows/daily-research/status", 
                f"Expected status 401 for unauthenticated request, got {res_status.status_code}"
            )

        # Test 2: decisions/history now requires auth — expect 401 without a key
        res_history = requests.get("http://localhost:8000/decisions/history?limit=1", timeout=5)
        if res_history.status_code == 401:
            log_pass("LIVE: GET /decisions/history rejected unauthenticated request with status 401 (Protected)")
        else:
            log_fail(
                "LIVE: GET /decisions/history", 
                f"Expected status 401 for unauthenticated request, got {res_history.status_code}"
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
# CHECK 6: STATIC CHECK — Danger pattern blocklist hasn't silently gone empty
# -------------------------------------------------------------------
# The single most dangerous silent failure for this whole pipeline would be
# DANGEROUS_PATTERNS quietly becoming an empty list during some future edit —
# execution would then run completely unguarded with no error or warning.
try:
    from workflows.action_executor import DANGEROUS_PATTERNS, is_dangerous_command

    if not DANGEROUS_PATTERNS or len(DANGEROUS_PATTERNS) < 5:
        log_fail(
            "action_executor.py danger pattern blocklist",
            f"Expected at least 5 dangerous patterns, found {len(DANGEROUS_PATTERNS)}. "
            "This list may have been accidentally emptied or truncated."
        )
    else:
        # Confirm it actually catches a known-bad command, not just that the
        # list is non-empty (a list of harmless/wrong patterns would still
        # pass a bare length check).
        test_result = is_dangerous_command("rm -rf /")
        if test_result:
            log_pass(f"action_executor.py blocklist has {len(DANGEROUS_PATTERNS)} patterns and correctly flags 'rm -rf /'")
        else:
            log_fail(
                "action_executor.py danger pattern blocklist",
                "'rm -rf /' was NOT flagged as dangerous — patterns may be broken or too narrow."
            )
except Exception as e:
    log_fail("Danger pattern blocklist check crashed", str(e))


# -------------------------------------------------------------------
# CHECK 7: STATIC CHECK — Workspace confinement actually blocks out-of-bounds paths
# -------------------------------------------------------------------
try:
    from workflows.action_executor import check_workspace_confinement

    outside_path_result = check_workspace_confinement("cat ../../../../etc/passwd")
    inside_path_result = check_workspace_confinement("echo hello > notes.txt")

    if outside_path_result and inside_path_result is None:
        log_pass("workspace confinement correctly blocks paths outside WORKSPACE_ROOT while allowing paths inside it")
    elif not outside_path_result:
        log_fail(
            "workspace confinement check",
            "A path traversal to /etc/passwd was NOT blocked — confinement logic may be broken."
        )
    else:
        log_fail(
            "workspace confinement check",
            f"A harmless relative path inside the workspace was incorrectly blocked: {inside_path_result}"
        )
except Exception as e:
    log_fail("Workspace confinement check crashed", str(e))


# -------------------------------------------------------------------
# CHECK 8: STATIC CHECK — /actions/execute is auth-protected
# -------------------------------------------------------------------
try:
    with open("main.py", "r", encoding="utf-8") as f:
        main_content = f.read()

    match = re.search(r'"/actions/\{action_id\}/execute"', main_content)
    if not match:
        log_fail("main.py /actions/execute endpoint check", "Route '/actions/{action_id}/execute' not found in main.py at all.")
    else:
        start_pos = match.start()
        def_match = re.search(r"\n\s*(async def|def)\s", main_content[start_pos:])
        end_pos = start_pos + def_match.start() if def_match else start_pos + 500
        block = main_content[start_pos:end_pos]

        if "Depends(verify_api_key)" in block:
            log_pass("main.py POST /actions/{action_id}/execute is correctly auth-protected")
        else:
            log_fail(
                "main.py /actions/execute endpoint check",
                "POST /actions/{action_id}/execute is MISSING Depends(verify_api_key) — this endpoint can run real commands and must be protected."
            )
except Exception as e:
    log_fail("/actions/execute auth check crashed", str(e))


# -------------------------------------------------------------------
# CHECK 9: STATIC CHECK — URL safety guard blocks dangerous schemes
# -------------------------------------------------------------------
try:
    from workflows.action_executor import check_url_safety

    js_result = check_url_safety("javascript:alert(document.cookie)")
    file_result = check_url_safety("file:///etc/passwd")
    https_result = check_url_safety("https://en.wikipedia.org")

    if js_result and file_result and https_result is None:
        log_pass("check_url_safety() correctly blocks javascript:/file: schemes while allowing https")
    else:
        problems = []
        if not js_result:
            problems.append("javascript: URL was NOT blocked")
        if not file_result:
            problems.append("file: URL was NOT blocked")
        if https_result is not None:
            problems.append(f"a legitimate https URL was incorrectly blocked: {https_result}")
        log_fail("check_url_safety() guard", "; ".join(problems))
except Exception as e:
    log_fail("URL safety check crashed", str(e))


# -------------------------------------------------------------------
# CHECK 10: STATIC CHECK — file_operation and browser_action still call
# their respective safety guards (source inspection, not just behavior)
# -------------------------------------------------------------------
try:
    with open("workflows/action_executor.py", "r", encoding="utf-8") as f:
        executor_content = f.read()

    file_op_match = re.search(
        r"def _execute_file_operation.*?(?=\ndef |\Z)", executor_content, re.DOTALL
    )
    browser_match = re.search(
        r"def _execute_browser_action.*?(?=\ndef |\Z)", executor_content, re.DOTALL
    )

    problems = []
    if not file_op_match or "check_workspace_confinement" not in file_op_match.group(0):
        problems.append("_execute_file_operation no longer calls check_workspace_confinement")
    if not browser_match or "check_url_safety" not in browser_match.group(0):
        problems.append("_execute_browser_action no longer calls check_url_safety")

    if problems:
        log_fail("action_executor.py guard wiring check", "; ".join(problems))
    else:
        log_pass("_execute_file_operation and _execute_browser_action both still call their safety guards")
except Exception as e:
    log_fail("Guard wiring check crashed", str(e))


# -------------------------------------------------------------------
# CHECK 11: STATIC CHECK — action_queue schema has action_type + sync_uuid + result_detail
# -------------------------------------------------------------------
try:
    with open("memory/database.py", "r", encoding="utf-8") as f:
        db_content = f.read()

    required_columns = ["action_type", "sync_uuid", "result_detail"]
    missing = [c for c in required_columns if c not in db_content]

    if not missing:
        log_pass("action_queue schema includes action_type, sync_uuid, and result_detail columns")
    else:
        log_fail(
            "database.py schema check",
            f"Missing expected column(s) in database.py: {missing}"
        )
except Exception as e:
    log_fail("Schema check crashed", str(e))


# -------------------------------------------------------------------
# CHECK 12: STATIC CHECK — cross-machine sync functions exist
# -------------------------------------------------------------------
try:
    from memory.database import export_history_to_jsonl, import_history_from_jsonl
    log_pass("export_history_to_jsonl and import_history_from_jsonl are both importable")
except ImportError as e:
    log_fail("Cross-machine sync functions check", f"Could not import sync functions: {e}")
except Exception as e:
    log_fail("Sync functions check crashed", str(e))


# -------------------------------------------------------------------
# CHECK 13: STATIC CHECK — shell variable expansion bypass stays closed
# -------------------------------------------------------------------
# Found via adversarial testing: "rm -rf $HOME" bypassed BOTH the danger
# blocklist and workspace confinement entirely, since $HOME is not
# recognized as a path-like token and no literal pattern matches it. Fixed
# by blocking any $VAR/${VAR} reference outright. This check ensures a
# future refactor can't silently reopen that exact gap.
try:
    from workflows.action_executor import is_dangerous_command, check_workspace_confinement

    bypass_attempt = "rm -rf $HOME"
    danger = is_dangerous_command(bypass_attempt)
    confinement = None if danger else check_workspace_confinement(bypass_attempt)

    if danger or confinement:
        log_pass("Shell variable expansion ($HOME) is correctly blocked, not a silent bypass")
    else:
        log_fail(
            "Shell variable expansion bypass check",
            "'rm -rf $HOME' was NOT blocked by either guard — this is a known, previously-fixed bypass that has reopened."
        )
except Exception as e:
    log_fail("Variable expansion bypass check crashed", str(e))


# -------------------------------------------------------------------
# CHECK 14: STATIC CHECK — Telegram callback verifies sender's chat_id
# -------------------------------------------------------------------
# CRITICAL: without this check, any Telegram user who finds the bot could
# approve/reject/EXECUTE real actions. Source-inspection confirms the check
# is still wired into the actual callback handler, not just present
# somewhere unused in the file.
try:
    with open("notifications/telegram_interactive.py", "r", encoding="utf-8") as f:
        ti_content = f.read()

    callback_match = re.search(
        r"async def handle_button_callback.*?(?=\nasync def |\ndef |\Z)", ti_content, re.DOTALL
    )
    if callback_match and "TELEGRAM_CHAT_ID" in callback_match.group(0) and "effective_chat" in callback_match.group(0):
        log_pass("handle_button_callback() verifies sender's chat_id against TELEGRAM_CHAT_ID")
    else:
        log_fail(
            "Telegram callback authorization check",
            "handle_button_callback() does not appear to verify the sender's chat_id — CRITICAL: any Telegram user could control real actions."
        )
except Exception as e:
    log_fail("Telegram callback auth check crashed", str(e))


# -------------------------------------------------------------------
# CHECK 15: STATIC CHECK — server does not default to binding 0.0.0.0
# -------------------------------------------------------------------
try:
    with open("main.py", "r", encoding="utf-8") as f:
        main_content = f.read()

    if 'host="0.0.0.0"' in main_content and "BIND_HOST" not in main_content:
        log_fail(
            "Server bind address check",
            "main.py hardcodes host=\"0.0.0.0\" — exposes the API to the whole local network by default."
        )
    else:
        log_pass("Server does not hardcode an open 0.0.0.0 bind (uses a safe default or BIND_HOST override)")
except Exception as e:
    log_fail("Bind address check crashed", str(e))


# -------------------------------------------------------------------
# CHECK 16: STATIC CHECK — subprocess execution uses a sanitized environment
# -------------------------------------------------------------------
try:
    with open("workflows/action_executor.py", "r", encoding="utf-8") as f:
        exec_content = f.read()

    subprocess_match = re.search(r"subprocess\.run\(\s*action_detail.*?\n\s*\)", exec_content, re.DOTALL)
    if subprocess_match and "env=" in subprocess_match.group(0):
        log_pass("subprocess.run() passes a sanitized env= — secrets are not inherited by executed commands")
    else:
        log_fail(
            "Subprocess environment sanitization check",
            "subprocess.run() does not pass env= — executed commands inherit the full process environment, including secrets from .env."
        )
except Exception as e:
    log_fail("Subprocess env check crashed", str(e))


# -------------------------------------------------------------------
# CHECK 17: STATIC CHECK — subprocess has resource limits beyond the timeout
# -------------------------------------------------------------------
try:
    if "preexec_fn" in exec_content and "RLIMIT" in exec_content:
        log_pass("subprocess execution has CPU/memory resource limits (RLIMIT) beyond the wall-clock timeout")
    else:
        log_fail(
            "Subprocess resource limit check",
            "No RLIMIT/preexec_fn found — a runaway command could consume unlimited CPU/memory until the timeout fires."
        )
except Exception as e:
    log_fail("Subprocess resource limit check crashed", str(e))


# -------------------------------------------------------------------
# CHECK 18: STATIC CHECK — API key check uses constant-time comparison and rate limiting
# -------------------------------------------------------------------
try:
    verify_key_match = re.search(r"def verify_api_key.*?(?=\ndef |\Z)", main_content, re.DOTALL)
    if verify_key_match:
        block = verify_key_match.group(0)
        has_constant_time = "compare_digest" in block
        has_rate_limit = "_MAX_FAILED_ATTEMPTS" in block or "429" in block

        if has_constant_time and has_rate_limit:
            log_pass("verify_api_key() uses constant-time comparison and rate-limits failed attempts")
        else:
            missing = []
            if not has_constant_time:
                missing.append("constant-time comparison (hmac.compare_digest)")
            if not has_rate_limit:
                missing.append("rate limiting / lockout on repeated failures")
            log_fail("API key hardening check", f"Missing: {', '.join(missing)}")
    else:
        log_fail("API key hardening check", "verify_api_key() function not found in main.py")
except Exception as e:
    log_fail("API key hardening check crashed", str(e))


# -------------------------------------------------------------------
# CHECK 19: STATIC CHECK — decisions/history, daily-research/status, and
# screenshots are now all auth-protected (were previously open)
# -------------------------------------------------------------------
try:
    with open("main.py", "r", encoding="utf-8") as f:
        main_content_check19 = f.read()

    routes_to_check = [
        '"/decisions/history"',
        '"/workflows/daily-research/status"',
        '"/screenshots/{filename}"',
    ]
    problems = []
    for route in routes_to_check:
        m = re.search(re.escape(route), main_content_check19)
        if not m:
            problems.append(f"{route} not found in main.py at all")
            continue
        start_pos = m.start()
        def_match = re.search(r"\n\s*(async def|def)\s", main_content_check19[start_pos:])
        end_pos = start_pos + def_match.start() if def_match else start_pos + 500
        block = main_content_check19[start_pos:end_pos]
        if "Depends(verify_api_key)" not in block:
            problems.append(f"{route} is missing auth")

    if problems:
        log_fail("Newly-protected endpoints check", "; ".join(problems))
    else:
        log_pass("/decisions/history, /workflows/daily-research/status, and /screenshots/{filename} are all auth-protected")
except Exception as e:
    log_fail("Newly-protected endpoints check crashed", str(e))


# -------------------------------------------------------------------
# CHECK 20: STATIC CHECK — research tool blocks internal/SSRF-style URLs
# -------------------------------------------------------------------
# PageReaderTool executes immediately with NO human approval step (unlike
# propose_browser_action) — this was found completely unvalidated: an agent
# could be tricked into fetching internal services (the backend itself,
# Ollama's API, anything on the local network) with zero protection.
try:
    from tools.research_tool import _is_safe_research_url

    localhost_result = _is_safe_research_url("http://localhost:8000/decisions/history")
    ollama_result = _is_safe_research_url("http://127.0.0.1:11434/api/tags")
    https_result = _is_safe_research_url("https://en.wikipedia.org/wiki/AI")

    if localhost_result and ollama_result and https_result is None:
        log_pass("research_tool.py blocks internal/loopback URLs (SSRF protection) while allowing real external sites")
    else:
        problems = []
        if not localhost_result:
            problems.append("localhost URL was NOT blocked")
        if not ollama_result:
            problems.append("127.0.0.1 (Ollama) URL was NOT blocked")
        if https_result is not None:
            problems.append(f"a legitimate https URL was incorrectly blocked: {https_result}")
        log_fail("Research tool SSRF protection", "; ".join(problems))
except Exception as e:
    log_fail("Research tool SSRF check crashed", str(e))


# -------------------------------------------------------------------
# CHECK 21: STATIC CHECK — every blocked/failed action branch persists
# its reason via record_execution_result (not just success paths)
# -------------------------------------------------------------------
# Found via a real incident: a blocked/failed action's reason was only ever
# sent to Telegram/the API response and discarded — Action History showed
# "Execution Failed" with zero indication of why. Count must match: every
# execution_failed/blocked_dangerous status update needs a paired call.
try:
    with open("workflows/action_executor.py", "r", encoding="utf-8") as f:
        exec_content_check21 = f.read()

    status_update_count = len(re.findall(
        r'update_action_status\(action_id, "(execution_failed|blocked_dangerous)"\)', exec_content_check21
    ))
    record_result_count = exec_content_check21.count("record_execution_result(")

    if record_result_count >= status_update_count and status_update_count > 0:
        log_pass(f"All {status_update_count} failure/block branches persist their reason via record_execution_result")
    else:
        log_fail(
            "Failure persistence check",
            f"{status_update_count} failure/block status updates but only {record_result_count} record_execution_result calls — some failures won't show a reason in history."
        )
except Exception as e:
    log_fail("Failure persistence check crashed", str(e))


# -------------------------------------------------------------------
# CHECK 22: STATIC CHECK — Telegram listener startup failures are logged,
# not silently lost
# -------------------------------------------------------------------
try:
    with open("notifications/telegram_interactive.py", "r", encoding="utf-8") as f:
        ti_content_check22 = f.read()

    has_conflict_handling = "TelegramConflictError" in ti_content_check22 or "Conflict" in ti_content_check22
    has_logger = "logger.error" in ti_content_check22
    has_alive_check = "def is_telegram_listener_alive" in ti_content_check22

    if has_conflict_handling and has_logger and has_alive_check:
        log_pass("Telegram listener startup failures are caught, logged, and queryable via is_telegram_listener_alive()")
    else:
        missing = []
        if not has_conflict_handling:
            missing.append("Conflict error detection")
        if not has_logger:
            missing.append("structured error logging")
        if not has_alive_check:
            missing.append("is_telegram_listener_alive()")
        log_fail("Telegram listener hardening check", f"Missing: {', '.join(missing)}")
except Exception as e:
    log_fail("Telegram listener hardening check crashed", str(e))


# -------------------------------------------------------------------
# CHECK 23: STATIC CHECK — blocking startup checks stay off asyncio loop
# -------------------------------------------------------------------
try:
    with open("main.py", "r", encoding="utf-8") as f:
        main_content_check23 = f.read()

    lifespan_match = re.search(
        r"async def lifespan\(app: FastAPI\):.*?(?=\n\n# 5\. FastAPI App Instantie)",
        main_content_check23,
        re.DOTALL,
    )
    if lifespan_match and "await asyncio.to_thread(run_startup_checks)" in lifespan_match.group(0):
        log_pass("startup checks are offloaded from the asyncio event loop before Playwright sync API runs")
    else:
        log_fail(
            "Async startup blocking-call check",
            "lifespan() must call 'await asyncio.to_thread(run_startup_checks)' so Playwright sync API does not run inside the asyncio event loop."
        )
except Exception as e:
    log_fail("Async startup blocking-call check crashed", str(e))


# -------------------------------------------------------------------
# CHECK 24: STATIC CHECK — Telegram shutdown handles a closed event loop
# -------------------------------------------------------------------
try:
    with open("notifications/telegram_interactive.py", "r", encoding="utf-8") as f:
        ti_content_check24 = f.read()

    has_closed_guard = "loop.is_closed()" in ti_content_check24
    clears_loop_state = '_state["loop"] = None' in ti_content_check24 and '_state["stop_event"] = None' in ti_content_check24
    handles_shutdown_race = "except RuntimeError" in ti_content_check24

    if has_closed_guard and clears_loop_state and handles_shutdown_race:
        log_pass("Telegram shutdown safely handles startup failure / already-closed event loop")
    else:
        missing = []
        if not has_closed_guard:
            missing.append("loop.is_closed() guard")
        if not clears_loop_state:
            missing.append("listener loop/stop-event state cleanup")
        if not handles_shutdown_race:
            missing.append("RuntimeError shutdown-race handling")
        log_fail("Telegram closed-loop shutdown check", f"Missing: {', '.join(missing)}")
except Exception as e:
    log_fail("Telegram closed-loop shutdown check crashed", str(e))


# -------------------------------------------------------------------
# CHECK 25: STATIC CHECK — database health check tests write capability
# -------------------------------------------------------------------
try:
    with open("system_checks.py", "r", encoding="utf-8") as f:
        system_checks_content_25 = f.read()

    db_check_match = re.search(
        r"def check_database_writable.*?(?=\ndef |\Z)",
        system_checks_content_25,
        re.DOTALL,
    )
    if db_check_match and "BEGIN IMMEDIATE" in db_check_match.group(0) and "rollback()" in db_check_match.group(0):
        log_pass("database health check verifies real SQLite write access without persisting changes")
    else:
        log_fail(
            "Database write-health check",
            "check_database_writable() must acquire a write transaction (BEGIN IMMEDIATE) and roll it back; SELECT-only checks can falsely report a read-only DB as writable."
        )
except Exception as e:
    log_fail("Database write-health check crashed", str(e))


# -------------------------------------------------------------------
# CHECK 28: STATIC/DYNAMIC CHECK — meeting evidence guard rejects invented figures
# -------------------------------------------------------------------
try:
    from workflows.meeting import find_unsupported_quantitative_claims

    source = "The supplied evidence says the pilot budget is €500 and the target margin is 20%."
    clean_output = "Use the €500 pilot budget and evaluate whether the 20% target margin is realistic."
    bad_output = "We project $10 million revenue, 200% ROI, and a 1.5 years payback period."

    clean_claims = find_unsupported_quantitative_claims(source, clean_output)
    bad_claims = find_unsupported_quantitative_claims(source, bad_output)

    if not clean_claims and len(bad_claims) == 3:
        log_pass("meeting evidence guard allows supplied figures and flags newly invented quantitative claims")
    else:
        log_fail(
            "Meeting quantitative evidence guard",
            f"Expected 0 supported-claim warnings and 3 invented-claim warnings; got clean={clean_claims}, bad={bad_claims}"
        )
except Exception as e:
    log_fail("Meeting quantitative evidence guard check crashed", str(e))


# -------------------------------------------------------------------
# CHECK 29: STATIC CHECK — executive meeting prompts enforce evidence discipline
# -------------------------------------------------------------------
try:
    with open("workflows/meeting.py", "r", encoding="utf-8") as f:
        meeting_content_29 = f.read()

    required_evidence_phrases = [
        "Unknown — evidence required",
        "Never invent or present as factual",
        "Do not inherit an unsupported claim",
        "Evidence needed before committing money or taking real-world action",
    ]
    missing = [p for p in required_evidence_phrases if p not in meeting_content_29]

    if not missing:
        log_pass("executive meeting prompts enforce evidence/assumption separation and reject inherited unsupported claims")
    else:
        log_fail("Meeting evidence-discipline prompt check", f"Missing required guardrail text: {missing}")
except Exception as e:
    log_fail("Meeting evidence-discipline prompt check crashed", str(e))


# -------------------------------------------------------------------
# CHECK 30: STATIC CHECK — API exposes decision-quality warnings
# -------------------------------------------------------------------
try:
    with open("main.py", "r", encoding="utf-8") as f:
        main_content_30 = f.read()

    has_model_field = "quality_warnings: dict = Field(default_factory=dict)" in main_content_30
    has_response_mapping = 'quality_warnings=meeting_result.get("quality_warnings", {})' in main_content_30

    if has_model_field and has_response_mapping:
        log_pass("ad-hoc decision API exposes meeting quality warnings to callers")
    else:
        missing = []
        if not has_model_field:
            missing.append("DecisionResponse.quality_warnings field")
        if not has_response_mapping:
            missing.append("quality_warnings response mapping")
        log_fail("Decision quality warning API check", f"Missing: {', '.join(missing)}")
except Exception as e:
    log_fail("Decision quality warning API check crashed", str(e))


# -------------------------------------------------------------------
# CHECK 31: STATIC CHECK — CFO/COO/CEO role prompts no longer force invented business facts
# -------------------------------------------------------------------
try:
    with open("agents/executive_agents.py", "r", encoding="utf-8") as f:
        agents_content_31 = f.read()

    required_role_guards = [
        "Unknown — evidence required; never invent figures",
        "do not invent operational infrastructure",
        "Do not inherit unsupported facts or figures from another executive",
    ]
    missing = [p for p in required_role_guards if p not in agents_content_31]

    if not missing:
        log_pass("CFO/COO/CEO prompts explicitly reject invented figures and unsupported company assumptions")
    else:
        log_fail("Executive role evidence guard check", f"Missing role guard(s): {missing}")
except Exception as e:
    log_fail("Executive role evidence guard check crashed", str(e))


# -------------------------------------------------------------------
# CHECK 32: STATIC/DYNAMIC CHECK — repeated executive analysis is surfaced
# -------------------------------------------------------------------
try:
    from workflows.meeting import find_repeated_analysis

    repeated_sentence = (
        "This recommendation should not be treated as independent corroboration because it repeats "
        "the exact same long evidence statement already supplied by another executive."
    )
    sample_outputs = {
        "cfo": repeated_sentence,
        "coo": repeated_sentence,
        "ceo": "A distinct synthesis that does not repeat the sentence above verbatim.",
    }
    repeated = find_repeated_analysis(sample_outputs, min_chars=80)

    if "coo" in repeated and "cfo" not in repeated:
        log_pass("meeting quality guard detects repeated long-form analysis across executives")
    else:
        log_fail("Repeated executive analysis guard", f"Unexpected result: {repeated}")
except Exception as e:
    log_fail("Repeated executive analysis guard check crashed", str(e))


# -------------------------------------------------------------------
# CHECK 33: STATIC CHECK — CEO has dedicated final-synthesis/approval-gate rules
# -------------------------------------------------------------------
try:
    with open("workflows/meeting.py", "r", encoding="utf-8") as f:
        meeting_content_33 = f.read()

    required_ceo_rules = [
        "CEO FINAL-SYNTHESIS RULES",
        "Do not copy or concatenate previous executives' answers",
        "Approval Gate",
        "recommend the next research/validation step instead of pretending the decision is ready",
    ]
    missing = [p for p in required_ceo_rules if p not in meeting_content_33]

    if not missing:
        log_pass("CEO meeting task has dedicated synthesis, evidence-gap, and human approval-gate rules")
    else:
        log_fail("CEO final-synthesis rules check", f"Missing: {missing}")
except Exception as e:
    log_fail("CEO final-synthesis rules check crashed", str(e))


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