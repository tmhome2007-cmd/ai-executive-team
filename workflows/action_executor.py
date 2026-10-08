"""
workflows/action_executor.py

Module voor het veilig uitvoeren van goedgekeurde acties uit de action_queue.
Ondersteunt patrooncontroles voor gevaarlijke commando's, een echte confinement-
check die elk pad-achtig token in het commando herleidt tot een absoluut pad en
blokkeert als dat buiten WORKSPACE_ROOT valt, een live-uitvoering via subprocess,
en een veilige dry-run modus.
"""

import ipaddress
import json
import os
import re
import shlex
import socket
import subprocess

try:
    import resource  # Unix-only (macOS/Linux) — niet beschikbaar op Windows
    _RESOURCE_MODULE_AVAILABLE = True
except ImportError:
    _RESOURCE_MODULE_AVAILABLE = False
from urllib.parse import urlparse
from memory.database import (
    get_action_by_id,
    update_action_status,
    record_execution_result,
    claim_action_for_execution,
    mark_action_outcome_measurement_pending,
    mark_action_outcome_execution_failed,
    VALID_ACTION_TYPES,
)
from notifications.telegram_bot import send_notification, escape_html
from config import config

# ------------------------------------------------------------------
# WORKSPACE CONFINEMENT
# ------------------------------------------------------------------
# BELANGRIJK: cwd=... in subprocess.run() zet alleen de START-directory —
# het beperkt op geen enkele manier welke paden een commando daadwerkelijk
# mag aanraken. Een commando als "rm /Users/alpha/Documents/iets" of
# "cat ../../../etc/passwd" zou zonder deze check gewoon buiten de workspace
# kunnen werken, ongeacht cwd. Deze functie herleidt elk pad-achtig token in
# het commando naar een absoluut, symlink-opgelost pad en wijst het commando
# af zodra ook maar één zo'n pad buiten WORKSPACE_ROOT valt.

# Shell metakarakters die het commando in losse deelcommando's opsplitsen
_SHELL_CHAIN_SPLIT = re.compile(r"&&|\|\||;|\|")


def _limit_subprocess_resources() -> None:
    """
    Wordt uitgevoerd IN het kindproces, vlak vóór het echte commando start
    (via preexec_fn). Begrenst CPU-tijd en geheugen zodat een losgeslagen of
    kwaadaardig commando (bijv. "yes", of iets dat /dev/zero leest) niet
    onbeperkt CPU/RAM kan opslokken tijdens de 30 seconden wall-clock timeout
    — die timeout stopt het proces pas AAN HET EIND van 30s, dit begrenst wat
    het in de tussentijd kan verbruiken. Alleen actief op Unix (macOS/Linux).
    """
    if not _RESOURCE_MODULE_AVAILABLE:
        return
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (25, 25))  # max 25 CPU-seconden
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))  # max 512MB adresruimte
    except Exception:
        pass  # als het platform dit niet ondersteunt, ga gewoon door zonder limiet


def _get_safe_subprocess_env() -> dict:
    """
    Bouwt een MINIMALE environment voor subprocess.run() — NIET de volledige
    os.environ van dit proces. Zonder dit zou een goedgekeurd shell-commando
    zoals "env", "printenv" of "set" gewoon TELEGRAM_BOT_TOKEN, API_SECRET_KEY
    en OPENAI_API_KEY uit .env kunnen dumpen naar een bestand of de output —
    geen enkel dangerous-pattern zou dat opvangen, want die commando's zijn
    op zichzelf volkomen onschuldig. Alleen wat een normaal commando echt
    nodig heeft (PATH, HOME, taal-instellingen) wordt doorgegeven.
    """
    safe_keys = ("PATH", "HOME", "LANG", "LC_ALL", "TZ", "USER", "SHELL")
    return {k: os.environ[k] for k in safe_keys if k in os.environ}


def _get_workspace_root() -> str:
    """Retourneert het absolute, symlink-opgeloste WORKSPACE_ROOT pad, en
    zorgt dat de map bestaat zodat cwd= en de confinement-check altijd een
    concrete, echte directory hebben om tegen te vergelijken."""
    raw = config.WORKSPACE_ROOT or "./workspace"
    expanded = os.path.expanduser(raw)
    absolute = os.path.abspath(expanded)
    os.makedirs(absolute, exist_ok=True)
    return os.path.realpath(absolute)


def _looks_like_path(token: str) -> bool:
    """Conservatieve pad-detectie voor shellargumenten.

    Ook een kaal relatief token zoals notes.txt of outside kan een
    bestand/symlink in WORKSPACE_ROOT zijn. De oude heuristiek controleerde
    alleen tokens met slash, tilde of punt, waardoor een symlink met een
    simpele naam naar buiten de workspace confinement kon omzeilen.
    """
    if not token or token.startswith("-"):
        return False
    if token in {">", ">>", "<", "<<", "2>", "2>>", "2>&1"}:
        return False
    return True


def check_workspace_confinement(command: str) -> str | None:
    """
    Controleert of ELK pad-achtig token in het commando, na resolutie,
    binnen WORKSPACE_ROOT valt. Retourneert een reden-string zodra iets
    buiten de workspace valt of niet statisch te analyseren is, anders None.
    """
    # Command substitution (`...` of $(...)) kan een pad verbergen dat
    # statisch niet te herleiden is — dit blokkeren we bij voorbaat in
    # plaats van te doen alsof we het veilig kunnen controleren.
    if "`" in command or "$(" in command:
        return "Command substitution (` or $(...)) detected — cannot statically verify target paths, blocked for safety"

    # Shell variable expansie ($HOME, ${HOME}, $1, etc.) is precies zo
    # onvoorspelbaar als command substitution voor statische analyse: het
    # ECHTE pad is pas bekend op het moment dat de shell het daadwerkelijk
    # expandeert, niet nu. Een commando als "rm -rf $HOME" bevat geen enkel
    # token dat begint met /, ~ of . — dus _looks_like_path() zou het NOOIT
    # herkennen als een te controleren pad, en geen enkel DANGEROUS_PATTERNS
    # regex matcht de letterlijke tekst "$HOME" — waardoor dit commando
    # volledig langs BEIDE controles zou glippen en op het echte home-
    # folder zou uitvoeren zodra de shell het expandeert. Blokkeer daarom
    # elke variabele-referentie bij voorbaat, net als command substitution.
    if re.search(r"\$\{?\w+\}?", command):
        return "Shell variable expansion ($VAR or ${VAR}) detected — the real target path cannot be statically verified before the shell expands it, blocked for safety"

    workspace_root = _get_workspace_root()

    # Splits op shell-verbindingstekens zodat elk deelcommando apart
    # gecontroleerd wordt (anders zou "cd /safe && rm -rf /" de eerste,
    # onschuldige helft laten "meeliften" met de tweede).
    segments = [seg.strip() for seg in _SHELL_CHAIN_SPLIT.split(command) if seg.strip()]

    for segment in segments:
        try:
            tokens = shlex.split(segment)
        except ValueError:
            # Onbalans in aanhalingstekens o.i.d. — niet veilig te parsen.
            return f"Command segment could not be safely parsed: '{segment}'"

        for token in tokens:
            if not _looks_like_path(token):
                continue

            expanded = os.path.expanduser(token)
            if not os.path.isabs(expanded):
                expanded = os.path.join(workspace_root, expanded)
            resolved = os.path.realpath(expanded)

            # os.path.commonpath vergelijkt echte pad-prefixen (geen simpele
            # string-vergelijking, die "workspace2" zou laten matchen op
            # "workspace" als we alleen startswith() zouden gebruiken).
            try:
                if os.path.commonpath([resolved, workspace_root]) != workspace_root:
                    return (
                        f"Path '{token}' resolves to '{resolved}', which is outside "
                        f"the allowed workspace directory '{workspace_root}'"
                    )
            except ValueError:
                # Gebeurt op sommige platforms als paden op andere "drives"/
                # roots staan — per definitie dus buiten de workspace.
                return f"Path '{token}' resolves outside the allowed workspace directory '{workspace_root}'"

    return None


# ------------------------------------------------------------------
# URL SAFETY CHECK (voor browser_action)
# ------------------------------------------------------------------
# Analoog aan check_workspace_confinement, maar voor URLs in plaats van
# bestandspaden: blokkeert gevaarlijke schema's (javascript:, file:, data:)
# die browser-navigatie zouden kunnen misbruiken buiten "gewoon een pagina
# bezoeken", en staat alleen http/https toe.
_DANGEROUS_URL_SCHEMES = {"javascript", "file", "data", "vbscript", "about"}


def check_url_safety(url: str) -> str | None:
    """
    Controleert of een URL veilig genoeg is om te navigeren. Retourneert een
    reden-string als de URL geblokkeerd moet worden, anders None.
    """
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return f"Could not parse URL: '{url}'"

    scheme = (parsed.scheme or "").lower()

    if scheme in _DANGEROUS_URL_SCHEMES:
        return f"URL scheme '{scheme}:' is not allowed — only http/https navigation is permitted"

    if scheme not in ("http", "https"):
        return f"URL must use http or https (got '{scheme or 'no scheme'}')"

    if not parsed.hostname:
        return f"URL has no valid domain: '{url}'"

    hostname = parsed.hostname.lower()
    if hostname == "localhost" or hostname.endswith(".localhost") or hostname.endswith(".local"):
        return f"Local/internal hostname '{hostname}' is not allowed"

    try:
        resolved_addresses = {
            info[4][0]
            for info in socket.getaddrinfo(hostname, parsed.port or (443 if scheme == "https" else 80))
        }
    except socket.gaierror as e:
        return f"Could not resolve hostname '{hostname}': {e}"

    for resolved_ip in resolved_addresses:
        try:
            ip_obj = ipaddress.ip_address(resolved_ip)
        except ValueError:
            return f"Could not validate resolved address '{resolved_ip}' for '{hostname}'"
        if (
            ip_obj.is_loopback
            or ip_obj.is_private
            or ip_obj.is_link_local
            or ip_obj.is_reserved
            or ip_obj.is_unspecified
        ):
            return (
                f"URL resolves to a loopback/private/internal address ({resolved_ip}) — "
                "browser action blocked from reaching internal services"
            )

    # Optionele allowlist: als config.ALLOWED_BROWSER_DOMAINS is ingesteld
    # (komma-gescheiden lijst), mag alleen naar die domeinen genavigeerd
    # worden. Leeg/niet ingesteld = geen beperking (alle http/https toegestaan).
    allowlist_raw = getattr(config, "ALLOWED_BROWSER_DOMAINS", "").strip()
    if allowlist_raw:
        allowed_domains = [d.strip().lower() for d in allowlist_raw.split(",") if d.strip()]
        domain = hostname
        if not any(domain == d or domain.endswith("." + d) for d in allowed_domains):
            return f"Domain '{domain}' is not in the allowed browser domains list: {allowed_domains}"

    return None


# ------------------------------------------------------------------
# DANGEROUS COMMAND PATTERNS
# ------------------------------------------------------------------
DANGEROUS_PATTERNS: list[tuple[str, str]] = [
    (
        r"\b(?:bash|zsh|sh)\s+-c\b",
        "Nested shell interpreter (-c) can hide commands from static safety analysis"
    ),
    (
        r"\b(?:python(?:3)?|perl|ruby|node)\s+-(?:c|e)\b",
        "Inline interpreter code can hide filesystem/system actions from static safety analysis"
    ),
    (
        r"\beval\b",
        "Shell eval can dynamically construct commands that bypass static safety analysis"
    ),
    # Recursive/forced deletion of root, home, wildcards, or parent paths
    (
        r"rm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+(/\s*|~|/root|\*|\.\.)",
        "Forced recursive deletion of root, home, parent, or wildcard path detected"
    ),
    (
        r"rm\s+-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*\s+(/\s*|~|/root|\*|\.\.)",
        "Forced recursive deletion of root, home, parent, or wildcard path detected"
    ),
    # Disk-level destructive commands
    (
        r"\bdd\s+if=",
        "Low-level disk writing/formatting command (dd) detected"
    ),
    (
        r"\bmkfs",
        "Filesystem creation/formatting command (mkfs) detected"
    ),
    (
        r"\bdiskutil\s+erasedisk\b",
        "Disk erasure command (diskutil erasedisk) detected"
    ),
    # Piping remote downloads directly into shell interpreters
    (
        r"curl.*\|\s*(sh|bash|zsh)",
        "Piping remote download (curl) directly into shell execution detected"
    ),
    (
        r"wget.*\|\s*(sh|bash|zsh)",
        "Piping remote download (wget) directly into shell execution detected"
    ),
    # Fork bombs
    (
        r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:",
        "Fork bomb pattern detected"
    ),
    # Privilege escalation
    (
        r"\bsudo\b",
        "Privilege escalation attempt using 'sudo' detected"
    ),
    (
        r"\bsu\s+-",
        "Privilege escalation attempt using 'su -' detected"
    ),
    # macOS system-critical paths
    (
        r"/(System|Library)(/|\s|$)",
        "Access or modification attempt on macOS system-critical path (/System/ or /Library/) detected"
    ),
    # Overwriting shell history or configuration files
    (
        r">\s*~/\.(bash_history|zsh_history|bashrc|zshrc|profile)",
        "Attempt to overwrite shell history or configuration files detected"
    )
]


def is_dangerous_command(command: str) -> str | None:
    """
    Controleert de commandoreeks tegen alle patronen in DANGEROUS_PATTERNS.
    Retourneert de beschrijving/reden van het EERSTE overeenkomende patroon, 
    of None als er geen enkel risico gedetecteerd wordt.
    """
    for pattern, reason in DANGEROUS_PATTERNS:
        if re.search(pattern, command, flags=re.IGNORECASE):
            return reason
    return None


def _execute_file_operation(action_id: int, action: dict) -> dict:
    """
    Voert een gestructureerde bestandsoperatie uit (read/write/append) via
    gewone Python file I/O — GEEN subprocess, GEEN shell. Gebruikt dezelfde
    check_workspace_confinement() als shell-commando's, zodat een
    bestandspad net zo min buiten WORKSPACE_ROOT kan komen.
    """
    action_detail_raw = action.get("action_detail", "")

    try:
        detail = json.loads(action_detail_raw)
        if not isinstance(detail, dict):
            raise ValueError("action_detail must be a JSON object")
        operation = detail["operation"]
        file_path = detail["file_path"]
        content = detail.get("content", "")

        if operation not in ("read", "write", "append"):
            raise ValueError(f"unsupported file operation: {operation!r}")
        if not isinstance(file_path, str) or not file_path.strip():
            raise ValueError("file_path must be a non-empty string")
        if not isinstance(content, str):
            raise ValueError("content must be a string")
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        update_action_status(action_id, "execution_failed")
        error_msg = f"Malformed file_operation action_detail: {e}"
        record_execution_result(action_id, json.dumps({"error": error_msg}))
        mark_action_outcome_execution_failed(action_id, error_msg)
        return {
            "success": False,
            "action_id": action_id,
            "error": error_msg,
        }

    # Confinement-check op het pad zelf — dezelfde functie als voor shell-
    # commando's, want die tokenizeert en herleidt elk pad-achtig token toch
    # al; een kale padstring werkt daar prima als enkel token.
    confinement_reason = check_workspace_confinement(file_path)
    if confinement_reason:
        update_action_status(action_id, "blocked_dangerous")
        record_execution_result(action_id, json.dumps({"error": f"Blocked: {confinement_reason}"}))
        mark_action_outcome_execution_failed(action_id, f"Blocked before execution: {confinement_reason}")
        try:
            send_notification(
                f"🚫 <b>FILE OPERATION BLOCKED — path outside workspace</b>\n\n"
                f"<b>Action ID:</b> #{action_id}\n"
                f"<b>Operation:</b> {escape_html(operation)}\n"
                f"<b>Path:</b> <code>{escape_html(file_path)}</code>\n"
                f"<b>Reason:</b> {escape_html(confinement_reason)}"
            )
        except Exception as e:
            print(f"Warning: Failed to send Telegram block notification for action #{action_id}: {e}")
        return {
            "success": False,
            "action_id": action_id,
            "error": f"Blocked: {confinement_reason}",
            "blocked": True,
        }

    workspace_root = _get_workspace_root()
    resolved_path = file_path if os.path.isabs(os.path.expanduser(file_path)) else os.path.join(workspace_root, file_path)
    resolved_path = os.path.realpath(os.path.expanduser(resolved_path))

    # --- SANDBOX MODE: simuleer, raak het echte bestand niet aan ---
    if config.SANDBOX_MODE:
        update_action_status(action_id, "executed_dry_run")
        preview = f"Would {operation} '{resolved_path}'" + (f" with {len(content)} characters of content" if operation != "read" else "")
        record_execution_result(action_id, json.dumps({"detail": preview, "mode": "dry_run"}))
        try:
            send_notification(
                f"🧪 <b>DRY RUN — FILE OPERATION</b>\n\n"
                f"<b>Action ID:</b> #{action_id}\n"
                f"<b>Detail:</b> {escape_html(preview)}"
            )
        except Exception as e:
            print(f"Warning: Failed to send Telegram dry-run notification for action #{action_id}: {e}")
        return {"success": True, "mode": "dry_run", "action_id": action_id, "detail": preview}

    # --- LIVE MODE: echte file I/O ---
    try:
        if operation == "read":
            with open(resolved_path, "r", encoding="utf-8") as f:
                file_content = f.read()
            update_action_status(action_id, "executed")
            record_execution_result(action_id, json.dumps({"stdout": file_content[:2000]}))
            mark_action_outcome_measurement_pending(action_id)
            try:
                send_notification(
                    f"⚡ <b>FILE READ SUCCESSFUL</b>\n\n"
                    f"<b>Action ID:</b> #{action_id}\n"
                    f"<b>Path:</b> <code>{escape_html(resolved_path)}</code>\n"
                    f"<b>Content:</b>\n{escape_html(file_content[:500])}"
                )
            except Exception as e:
                print(f"Warning: Failed to send Telegram notification for action #{action_id}: {e}")
            return {"success": True, "mode": "live", "action_id": action_id, "stdout": file_content}

        elif operation in ("write", "append"):
            mode = "w" if operation == "write" else "a"
            with open(resolved_path, mode, encoding="utf-8") as f:
                f.write(content)
            update_action_status(action_id, "executed")
            record_execution_result(action_id, json.dumps({"stdout": f"Wrote {len(content)} characters to {resolved_path}"}))
            mark_action_outcome_measurement_pending(action_id)
            try:
                send_notification(
                    f"⚡ <b>FILE {operation.upper()} SUCCESSFUL</b>\n\n"
                    f"<b>Action ID:</b> #{action_id}\n"
                    f"<b>Path:</b> <code>{escape_html(resolved_path)}</code>\n"
                    f"<b>Bytes written:</b> {len(content)}"
                )
            except Exception as e:
                print(f"Warning: Failed to send Telegram notification for action #{action_id}: {e}")
            return {"success": True, "mode": "live", "action_id": action_id, "stdout": f"Wrote {len(content)} characters to {resolved_path}"}

        else:
            update_action_status(action_id, "execution_failed")
            error_msg = f"Unknown operation: {operation}"
            record_execution_result(action_id, json.dumps({"error": error_msg}))
            mark_action_outcome_execution_failed(action_id, error_msg)
            return {"success": False, "action_id": action_id, "error": error_msg}

    except Exception as e:
        update_action_status(action_id, "execution_failed")
        error_msg = f"File operation failed: {e}"
        record_execution_result(action_id, json.dumps({"error": error_msg}))
        mark_action_outcome_execution_failed(action_id, error_msg)
        try:
            send_notification(
                f"❌ <b>FILE OPERATION FAILED</b>\n\n"
                f"<b>Action ID:</b> #{action_id}\n"
                f"<b>Error:</b> {escape_html(error_msg)}"
            )
        except Exception as notify_err:
            print(f"Warning: Failed to send Telegram notification for action #{action_id}: {notify_err}")
        return {"success": False, "mode": "live", "action_id": action_id, "error": error_msg}


def _execute_browser_action(action_id: int, action: dict) -> dict:
    """
    Voert een gestructureerde browser-actie uit (navigeren + optioneel klikken)
    via Playwright's SYNCHRONE API. Dit is hier veilig — in tegenstelling tot
    tools/research_tool.py (dat vanuit async code draait en daarom naar
    requests+BeautifulSoup is overgestapt) — omdat execute_action() een
    gewone sync functie is die altijd in een echte worker thread draait
    (via asyncio.to_thread of FastAPI's threadpool), zonder actieve event loop.
    """
    action_detail_raw = action.get("action_detail", "")

    try:
        detail = json.loads(action_detail_raw)
        if not isinstance(detail, dict):
            raise ValueError("action_detail must be a JSON object")
        url = detail["url"]
        click_selector = detail.get("click_selector") or None

        if not isinstance(url, str) or not url.strip():
            raise ValueError("url must be a non-empty string")
        if click_selector is not None and not isinstance(click_selector, str):
            raise ValueError("click_selector must be a string or null")
        if click_selector is not None and click_selector.strip().lower() in ("null", "none", "n/a", ""):
            click_selector = None
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        update_action_status(action_id, "execution_failed")
        error_msg = f"Malformed browser_action action_detail: {e}"
        record_execution_result(action_id, json.dumps({"error": error_msg}))
        return {
            "success": False,
            "action_id": action_id,
            "error": error_msg,
        }

    url_block_reason = check_url_safety(url)
    if url_block_reason:
        update_action_status(action_id, "blocked_dangerous")
        record_execution_result(action_id, json.dumps({"error": f"Blocked: {url_block_reason}"}))
        mark_action_outcome_execution_failed(action_id, f"Blocked before execution: {url_block_reason}")
        try:
            send_notification(
                f"🚫 <b>BROWSER ACTION BLOCKED — unsafe URL</b>\n\n"
                f"<b>Action ID:</b> #{action_id}\n"
                f"<b>URL:</b> <code>{escape_html(url)}</code>\n"
                f"<b>Reason:</b> {escape_html(url_block_reason)}"
            )
        except Exception as e:
            print(f"Warning: Failed to send Telegram block notification for action #{action_id}: {e}")
        return {
            "success": False,
            "action_id": action_id,
            "error": f"Blocked: {url_block_reason}",
            "blocked": True,
        }

    # --- SANDBOX MODE: simuleer, open geen echte browser ---
    if config.SANDBOX_MODE:
        update_action_status(action_id, "executed_dry_run")
        preview = f"Would navigate to '{url}'" + (f" and click '{click_selector}'" if click_selector else "")
        record_execution_result(action_id, json.dumps({"detail": preview, "mode": "dry_run"}))
        try:
            send_notification(
                f"🧪 <b>DRY RUN — BROWSER ACTION</b>\n\n"
                f"<b>Action ID:</b> #{action_id}\n"
                f"<b>Detail:</b> {escape_html(preview)}"
            )
        except Exception as e:
            print(f"Warning: Failed to send Telegram dry-run notification for action #{action_id}: {e}")
        return {"success": True, "mode": "dry_run", "action_id": action_id, "detail": preview}

    # --- LIVE MODE: echte browser-navigatie via Playwright sync API ---
    try:
        from playwright.sync_api import sync_playwright

        workspace_root = _get_workspace_root()
        screenshots_dir = os.path.join(workspace_root, "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        screenshot_path = os.path.join(screenshots_dir, f"action_{action_id}.png")

        page_title = None
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Revalidate every navigation request, including redirects. Without
            # this, an initially-safe public URL could redirect Chromium to a
            # localhost/private-network target after the preflight check.
            def _guard_navigation(route):
                request = route.request
                if request.is_navigation_request():
                    reason = check_url_safety(request.url)
                    if reason:
                        route.abort()
                        return
                route.continue_()

            page.route("**/*", _guard_navigation)
            page.goto(url, timeout=15000)
            page_title = page.title()

            if click_selector:
                page.click(click_selector, timeout=10000)
                page.wait_for_timeout(1000)  # korte pauze zodat de klik-actie zichtbaar effect heeft voordat de screenshot wordt genomen

            page.screenshot(path=screenshot_path)
            browser.close()

        update_action_status(action_id, "executed")
        result_summary = f"Navigated to '{url}' (page title: '{page_title}')" + (
            f" and clicked '{click_selector}'" if click_selector else ""
        )
        record_execution_result(action_id, json.dumps({
            "stdout": result_summary,
            "screenshot_path": screenshot_path,
        }))
        mark_action_outcome_measurement_pending(action_id)
        try:
            send_notification(
                f"⚡ <b>BROWSER ACTION SUCCESSFUL</b>\n\n"
                f"<b>Action ID:</b> #{action_id}\n"
                f"<b>Detail:</b> {escape_html(result_summary)}\n"
                f"<b>Screenshot saved:</b> <code>{escape_html(screenshot_path)}</code>"
            )
        except Exception as e:
            print(f"Warning: Failed to send Telegram notification for action #{action_id}: {e}")

        return {
            "success": True,
            "mode": "live",
            "action_id": action_id,
            "stdout": result_summary,
            "screenshot_path": screenshot_path,
        }

    except Exception as e:
        update_action_status(action_id, "execution_failed")
        error_msg = f"Browser action failed: {e}"
        record_execution_result(action_id, json.dumps({"error": error_msg}))
        mark_action_outcome_execution_failed(action_id, error_msg)
        try:
            send_notification(
                f"❌ <b>BROWSER ACTION FAILED</b>\n\n"
                f"<b>Action ID:</b> #{action_id}\n"
                f"<b>Error:</b> {escape_html(error_msg)}"
            )
        except Exception as notify_err:
            print(f"Warning: Failed to send Telegram notification for action #{action_id}: {notify_err}")
        return {"success": False, "mode": "live", "action_id": action_id, "error": error_msg}


def execute_action(action_id: int) -> dict:
    """
    Voert een goedgekeurde actie uit op basis van het action_id.
    
    1. Controleert of de actie bestaat en de status 'approved' heeft.
    2. Controleert op gevaarlijke patronen en blokkeert zo nodig vóór sandbox/live branching.
    3. Als config.SANDBOX_MODE True is, wordt er een dry-run uitgevoerd.
    4. Als config.SANDBOX_MODE False is, wordt het commando daadwerkelijk gestart.
    """
    # 1. Haal de actie op uit de database
    action = get_action_by_id(action_id)
    if not action:
        return {"success": False, "error": "Action not found"}

    # 2. Reserveer de actie atomair voor precies één executor.
    status = action.get("status")
    if status != "approved":
        return {
            "success": False,
            "error": f"Action status is '{status}', must be 'approved' to execute."
        }
    if not claim_action_for_execution(action_id):
        current = get_action_by_id(action_id)
        current_status = current.get("status") if current else "unknown"
        return {
            "success": False,
            "error": f"Action could not be claimed for execution; current status is '{current_status}'.",
        }

    action_detail = action.get("action_detail", "")
    action_type = action.get("action_type", "shell")
    if action_type not in VALID_ACTION_TYPES:
        update_action_status(action_id, "execution_failed")
        error_msg = f"Unsupported action_type '{action_type}'"
        record_execution_result(action_id, json.dumps({"error": error_msg}))
        mark_action_outcome_execution_failed(action_id, error_msg)
        return {"success": False, "action_id": action_id, "error": error_msg}

    # Gestructureerde bestandsoperaties gaan een volledig eigen, veiligere pad
    # (gewone file I/O, geen shell) — de bestaande shell-logica hieronder
    # blijft ongewijzigd voor action_type == 'shell' (het standaardgedrag).
    if action_type == "file_operation":
        return _execute_file_operation(action_id, action)

    if action_type == "browser_action":
        return _execute_browser_action(action_id, action)

    # 3. SAFETY GUARD CHECKS (vóór sandbox/live modus keuzes)
    # (a) Bekende gevaarlijke commandopatronen
    danger_reason = is_dangerous_command(action_detail)
    # (b) Echte confinement-check: raakt dit commando iets buiten WORKSPACE_ROOT?
    confinement_reason = None if danger_reason else check_workspace_confinement(action_detail)
    block_reason = danger_reason or confinement_reason

    if block_reason:
        update_action_status(action_id, "blocked_dangerous")
        record_execution_result(action_id, json.dumps({"error": f"Blocked: {block_reason}"}))
        mark_action_outcome_execution_failed(action_id, f"Blocked before execution: {block_reason}")

        try:
            notification_text = (
                f"🚫 <b>EXECUTION BLOCKED — dangerous command detected</b>\n\n"
                f"<b>Action ID:</b> #{action_id}\n"
                f"<b>Command:</b> <code>{escape_html(action_detail)}</code>\n"
                f"<b>Reason:</b> {escape_html(block_reason)}"
            )
            send_notification(notification_text)
        except Exception as e:
            print(f"Warning: Failed to send Telegram block notification for action #{action_id}: {e}")

        return {
            "success": False,
            "action_id": action_id,
            "error": f"Blocked: {block_reason}",
            "blocked": True
        }

    # 4. SANDBOX / DRY RUN MODUS
    if config.SANDBOX_MODE:
        print(f"[DRY RUN] Would execute: {action_detail}")
        update_action_status(action_id, "executed_dry_run")
        record_execution_result(
            action_id,
            json.dumps({"detail": f"[DRY RUN] Command simulated: {action_detail}", "mode": "dry_run"}),
        )

        try:
            notification_text = (
                f"🧪 <b>DRY RUN EXECUTED</b>\n\n"
                f"<b>Action ID:</b> #{action_id}\n"
                f"<b>Command:</b> <code>{escape_html(action_detail)}</code>\n"
                f"<b>Mode:</b> Sandbox (Dry-Run)"
            )
            send_notification(notification_text)
        except Exception as e:
            print(f"Warning: Failed to send Telegram dry-run notification: {e}")

        return {
            "success": True,
            "mode": "dry_run",
            "action_id": action_id,
            "detail": f"[DRY RUN] Command simulated: {action_detail}",
        }

    # 5. LIVE EXECUTIE MODUS (Inclusief Time-out & Subprocess error handling)
    try:
        completed_process = subprocess.run(
            action_detail,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,  # 30 seconden time-out ter beveiliging
            cwd=_get_workspace_root(),
            env=_get_safe_subprocess_env(),  # GEEN secrets (.env) doorgeven aan het kindproces
            preexec_fn=_limit_subprocess_resources if _RESOURCE_MODULE_AVAILABLE else None,
        )

        if completed_process.returncode == 0:
            update_action_status(action_id, "executed")
            record_execution_result(action_id, json.dumps({
                "stdout": completed_process.stdout,
                "stderr": completed_process.stderr,
            }))
            mark_action_outcome_measurement_pending(action_id)

            try:
                notification_text = (
                    f"⚡ <b>LIVE EXECUTION SUCCESSFUL</b>\n\n"
                    f"<b>Action ID:</b> #{action_id}\n"
                    f"<b>Command:</b> <code>{escape_html(action_detail)}</code>\n"
                    f"<b>Output:</b>\n{escape_html(completed_process.stdout[:500]) if completed_process.stdout else '(no output)'}"
                )
                send_notification(notification_text)
            except Exception as e:
                print(f"Warning: Failed to send Telegram success notification for action #{action_id}: {e}")

            return {
                "success": True,
                "mode": "live",
                "action_id": action_id,
                "stdout": completed_process.stdout,
                "stderr": completed_process.stderr,
            }
        else:
            update_action_status(action_id, "execution_failed")
            error_msg = completed_process.stderr or f"Command exited with return code {completed_process.returncode}"
            record_execution_result(action_id, json.dumps({"error": error_msg, "stdout": completed_process.stdout, "stderr": completed_process.stderr}))
            mark_action_outcome_execution_failed(action_id, error_msg)

            try:
                notification_text = (
                    f"❌ <b>EXECUTION FAILED</b>\n\n"
                    f"<b>Action ID:</b> #{action_id}\n"
                    f"<b>Command:</b> <code>{escape_html(action_detail)}</code>\n"
                    f"<b>Error:</b>\n{escape_html(error_msg[:500])}"
                )
                send_notification(notification_text)
            except Exception as e:
                print(f"Warning: Failed to send Telegram failure notification for action #{action_id}: {e}")

            return {
                "success": False,
                "mode": "live",
                "action_id": action_id,
                "error": error_msg,
                "stdout": completed_process.stdout,
                "stderr": completed_process.stderr,
            }

    except subprocess.TimeoutExpired:
        update_action_status(action_id, "execution_failed")
        error_msg = "Command timed out after 30 seconds."
        record_execution_result(action_id, json.dumps({"error": error_msg}))
        mark_action_outcome_execution_failed(action_id, error_msg)

        try:
            send_notification(
                f"❌ <b>EXECUTION FAILED (TIMEOUT)</b>\n\n"
                f"<b>Action ID:</b> #{action_id}\n"
                f"<b>Command:</b> <code>{escape_html(action_detail)}</code>\n"
                f"<b>Error:</b> {escape_html(error_msg)}"
            )
        except Exception as e:
            print(f"Warning: Failed to send Telegram timeout notification for action #{action_id}: {e}")

        return {
            "success": False,
            "mode": "live",
            "action_id": action_id,
            "error": error_msg,
        }

    except Exception as e:
        update_action_status(action_id, "execution_failed")
        error_msg = f"Unexpected error during execution: {e}"
        record_execution_result(action_id, json.dumps({"error": error_msg}))
        mark_action_outcome_execution_failed(action_id, error_msg)

        try:
            send_notification(
                f"❌ <b>EXECUTION FAILED (UNEXPECTED ERROR)</b>\n\n"
                f"<b>Action ID:</b> #{action_id}\n"
                f"<b>Command:</b> <code>{escape_html(action_detail)}</code>\n"
                f"<b>Error:</b> {escape_html(error_msg)}"
            )
        except Exception as notify_err:
            print(f"Warning: Failed to send Telegram error notification for action #{action_id}: {notify_err}")

        return {
            "success": False,
            "mode": "live",
            "action_id": action_id,
            "error": error_msg,
        }