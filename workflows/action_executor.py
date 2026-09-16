"""
workflows/action_executor.py

Module voor het veilig uitvoeren van goedgekeurde acties uit de action_queue.
Ondersteunt zowel een live-uitvoering via subprocess als een veilige dry-run modus.
"""

import subprocess
from memory.database import get_action_by_id, update_action_status
from notifications.telegram_bot import send_notification
from config import config


def execute_action(action_id: int) -> dict:
    """
    Voert een goedgekeurde actie uit op basis van het action_id.
    
    Als config.SANDBOX_MODE True is, wordt er een dry-run uitgevoerd.
    Als config.SANDBOX_MODE False is, wordt het commando daadwerkelijk gestart.
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

    # 3. SANDBOX / DRY RUN MODUS
    if config.SANDBOX_MODE:
        print(f"[DRY RUN] Would execute: {action_detail}")
        update_action_status(action_id, "executed_dry_run")

        try:
            notification_text = (
                f"🧪 **DRY RUN — no real action was taken**\n\n"
                f"**Action ID:** #{action_id}\n"
                f"**Command:** `{action_detail}`"
            )
            send_notification(notification_text)
        except Exception as e:
            print(f"Warning: Failed to send Telegram dry-run notification: {e}")

        return {
            "success": True,
            "mode": "dry_run",
            "action_id": action_id,
            "detail": action_detail,
        }

    # 4. LIVE UITVOERING (SANDBOX_MODE == False)
    try:
        completed_process = subprocess.run(
            action_detail,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Succesvolle uitvoering (exit code 0)
        if completed_process.returncode == 0:
            update_action_status(action_id, "executed")

            try:
                notification_text = (
                    f"✅ **ACTION EXECUTED**\n\n"
                    f"**Action ID:** #{action_id}\n"
                    f"**Command:** `{action_detail}`\n"
                    f"**Output:**\n```\n{completed_process.stdout}\n```"
                )
                send_notification(notification_text)
            except Exception as e:
                print(f"Warning: Failed to send Telegram execution notification: {e}")

            return {
                "success": True,
                "mode": "live",
                "action_id": action_id,
                "stdout": completed_process.stdout,
                "stderr": completed_process.stderr,
            }

        # Mislukte uitvoering (non-zero exit code)
        else:
            update_action_status(action_id, "execution_failed")
            error_msg = completed_process.stderr or f"Process failed with return code {completed_process.returncode}"

            try:
                notification_text = (
                    f"❌ **EXECUTION FAILED**\n\n"
                    f"**Action ID:** #{action_id}\n"
                    f"**Command:** `{action_detail}`\n"
                    f"**Error:**\n```\n{error_msg}\n```"
                )
                send_notification(notification_text)
            except Exception as e:
                print(f"Warning: Failed to send Telegram failure notification: {e}")

            return {
                "success": False,
                "mode": "live",
                "action_id": action_id,
                "error": error_msg,
            }

    except Exception as e:
        # Afvangen van uitzonderingen zoals subprocess.TimeoutExpired
        update_action_status(action_id, "execution_failed")
        error_msg = str(e)

        try:
            notification_text = (
                f"❌ **EXECUTION FAILED (EXCEPTION)**\n\n"
                f"**Action ID:** #{action_id}\n"
                f"**Command:** `{action_detail}`\n"
                f"**Exception:** {error_msg}"
            )
            send_notification(notification_text)
        except Exception as notify_err:
            print(f"Warning: Failed to send Telegram exception notification: {notify_err}")

        return {
            "success": False,
            "mode": "live",
            "action_id": action_id,
            "error": error_msg,
        }