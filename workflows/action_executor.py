"""
workflows/action_executor.py

Module voor het veilig uitvoeren van goedgekeurde acties uit de action_queue.
Ondersteunt patrooncontroles voor gevaarlijke commando's, een echte confinement-
check die elk pad-achtig token in het commando herleidt tot een absoluut pad en
blokkeert als dat buiten WORKSPACE_ROOT valt, een live-uitvoering via subprocess,
en een veilige dry-run modus.
"""

import json
import os
import re
import shlex
import subprocess
from urllib.parse import urlparse
from memory.database import get_action_by_id, update_action_status
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
    """Heuristiek: is dit token vermoedelijk een bestands-/mappad, in
    plaats van een losse vlag (-rf) of commandonaam (echo, ls)?"""
    if not token or token.startswith("-"):
        return False
    return "/" in token or token in (".", "..") or token.startswith("~") or token.startswith(".")


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

    if not parsed.netloc:
        return f"URL has no valid domain: '{url}'"

    # Optionele allowlist: als config.ALLOWED_BROWSER_DOMAINS is ingesteld
    # (komma-gescheiden lijst), mag alleen naar die domeinen genavigeerd
    # worden. Leeg/niet ingesteld = geen beperking (alle http/https toegestaan).
    allowlist_raw = getattr(config, "ALLOWED_BROWSER_DOMAINS", "").strip()
    if allowlist_raw:
        allowed_domains = [d.strip().lower() for d in allowlist_raw.split(",") if d.strip()]
        domain = parsed.netloc.lower()
        if not any(domain == d or domain.endswith("." + d) for d in allowed_domains):
            return f"Domain '{domain}' is not in the allowed browser domains list: {allowed_domains}"

    return None


# ------------------------------------------------------------------
# DANGEROUS COMMAND PATTERNS
# ------------------------------------------------------------------
DANGEROUS_PATTERNS: list[tuple[str, str]] = [
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
        operation = detail["operation"]
        file_path = detail["file_path"]
        content = detail.get("content", "")
    except (json.JSONDecodeError, KeyError) as e:
        update_action_status(action_id, "execution_failed")
        return {
            "success": False,
            "action_id": action_id,
            "error": f"Malformed file_operation action_detail: {e}",
        }

    # Confinement-check op het pad zelf — dezelfde functie als voor shell-
    # commando's, want die tokenizeert en herleidt elk pad-achtig token toch
    # al; een kale padstring werkt daar prima als enkel token.
    confinement_reason = check_workspace_confinement(file_path)
    if confinement_reason:
        update_action_status(action_id, "blocked_dangerous")
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
            return {"success": False, "action_id": action_id, "error": f"Unknown operation: {operation}"}

    except Exception as e:
        update_action_status(action_id, "execution_failed")
        error_msg = f"File operation failed: {e}"
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
        url = detail["url"]
        click_selector = detail.get("click_selector") or None
        if click_selector is not None and str(click_selector).strip().lower() in ("null", "none", "n/a"):
            click_selector = None
    except (json.JSONDecodeError, KeyError) as e:
        update_action_status(action_id, "execution_failed")
        return {
            "success": False,
            "action_id": action_id,
            "error": f"Malformed browser_action action_detail: {e}",
        }

    url_block_reason = check_url_safety(url)
    if url_block_reason:
        update_action_status(action_id, "blocked_dangerous")
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

    # 2. Controleer of de status op 'approved' staat
    status = action.get("status")
    if status != "approved":
        return {
            "success": False, 
            "error": f"Action status is '{status}', must be 'approved' to execute."
        }

    action_detail = action.get("action_detail", "")
    action_type = action.get("action_type", "shell")

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
            cwd=_get_workspace_root()
        )

        if completed_process.returncode == 0:
            update_action_status(action_id, "executed")

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