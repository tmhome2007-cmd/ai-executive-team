"""Temporary owner playback test with synthetic WAV, no model/cloud calls."""

from browser_navigation import open_view

import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import config
from workflows import conversation_audio as speech
from tests.test_conversation_audio import wav
from memory.database import init_db, log_decision, get_connection
from memory.character_profiles import get_character, save_character
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright


def main():
    with (
        tempfile.TemporaryDirectory(prefix="spoken-ui-") as raw,
        patch.object(config, "DATABASE_PATH", str(Path(raw).resolve() / "company.db")),
        patch.object(config, "API_SECRET_KEY", "synthetic-speech-ui-key-1234567890"),
        patch.object(config, "CONVERSATION_AUDIO_RETENTION_DAYS", 30),
        patch.object(speech, "synthesize", return_value=wav()) as engine,
    ):
        init_db()
        profile = get_character("executive:ceo")
        save_character(
            "executive:ceo",
            profile["version"],
            profile["appearance"],
            profile["body"],
            dict(
                profile["voice"],
                provider="kokoro_local",
                voice_name="am_michael",
                language="en-US",
                pitch=1,
                rate=1,
            ),
        )
        decision = log_decision(
            "Fictional speech review", ["ceo"], "Synthetic input", "Synthetic result"
        )
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO decision_contributions(decision_id,phase,sequence,executive_key,body,profile_json,captured_at) VALUES(?,'decision',1,'ceo','Fictional published contribution. No approval is recorded.','{}','2026-10-10')",
                (decision,),
            )
            conn.commit()
        from main import app

        client = TestClient(app)
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            requests = []
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))

            def respond(route):
                request = route.request
                requests.append(request.url)
                path = request.url.removeprefix("http://127.0.0.1:8001")
                response = client.request(
                    request.method,
                    path,
                    headers={
                        "X-API-Key": config.API_SECRET_KEY,
                        "Content-Type": "application/json",
                    },
                    content=request.post_data,
                )
                route.fulfill(
                    status=response.status_code,
                    headers={
                        "content-type": response.headers.get(
                            "content-type", "application/json"
                        ),
                        "cache-control": "no-store",
                    },
                    body=response.content,
                )

            page.route("http://127.0.0.1:8001/**", respond)
            page.goto(os.environ.get("DASHBOARD_SMOKE_URL", "http://127.0.0.1:3001"))
            page.get_by_placeholder("API Key").fill(config.API_SECRET_KEY)
            page.get_by_role("button", name="Confirm", exact=True).click()
            open_view(page, "Conversations & activity")
            page.get_by_label("Meeting for contributions", exact=True).select_option(
                str(decision)
            )
            page.get_by_role(
                "button", name="Load spoken contribution", exact=True
            ).click()
            page.get_by_text("Generated audio", exact=False).wait_for()
            audio = page.get_by_label("Spoken contribution playback", exact=True)
            page.wait_for_function(
                "document.querySelector('audio[aria-label=\"Spoken contribution playback\"]').duration > 0"
            )
            assert audio.evaluate('(node)=>node.src.startsWith("blob:")')
            audio.evaluate("(node)=>node.play()")
            page.get_by_role(
                "button", name="Stop conversation voice", exact=True
            ).click()
            assert audio.evaluate("(node)=>node.paused")
            page.get_by_role(
                "button", name="Load spoken contribution", exact=True
            ).click()
            page.get_by_text("Loaded saved audio", exact=False).wait_for()
            engine.assert_called_once()
            page.get_by_role("button", name="Delete saved audio", exact=True).click()
            page.get_by_text(
                "Audio deleted. Published text and history remain intact.", exact=True
            ).wait_for()
            page.get_by_role(
                "button", name="Load spoken contribution", exact=True
            ).click()
            page.get_by_text("Generated audio", exact=False).wait_for()
            assert engine.call_count == 2
            page.set_viewport_size({"width": 390, "height": 844})
            page.screenshot(
                path="/private/tmp/be23-conversation-mobile.png", full_page=True
            )
            assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
            assert all(config.API_SECRET_KEY not in url for url in requests)
            assert page.evaluate("localStorage.length") == 0
            assert not errors, errors
            browser.close()
        with get_connection() as conn:
            assert conn.execute("SELECT COUNT(*) FROM action_queue").fetchone()[0] == 0
        print(
            "PASS local conversation UI: explicit generation, duration/play/stop, cache reuse, deletion/regeneration, private key and mobile layout",
            flush=True,
        )


if __name__ == "__main__":
    main()
