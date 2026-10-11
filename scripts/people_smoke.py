"""People dashboard/owner API smoke on disposable SQLite; speech is stubbed, never transmitted."""

from browser_navigation import open_view

import os
import sys
import tempfile
import wave
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import config
from memory.database import init_db, get_company_activity
from memory.agile import create_board, create_task
from memory.character_profiles import get_character
from memory.organization import employees, assignments
from workflows import local_voice_samples
from memory.personal_simulation import events, relationship
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright


def main():
    with (
        tempfile.TemporaryDirectory(prefix="people-browser-") as raw,
        patch.object(config, "DATABASE_PATH", str(Path(raw).resolve() / "company.db")),
        patch.object(
            config, "API_SECRET_KEY", "synthetic-people-browser-key-1234567890"
        ),
        patch.object(local_voice_samples, "ASSET_ROOT", Path(raw) / "voices"),
    ):
        local_voice_samples.ASSET_ROOT.mkdir()
        with wave.open(
            str(local_voice_samples.ASSET_ROOT / "am_michael.wav"), "wb"
        ) as recording:
            recording.setnchannels(1)
            recording.setsampwidth(2)
            recording.setframerate(24000)
            recording.writeframes(b"\0\0" * 24000)
        init_db()
        board = create_board("Synthetic company work", "company")
        task = create_task(
            board,
            title="Synthetic staff task",
            acceptance_criteria="Owner reviews work",
            status="ready",
        )["id"]
        from main import app

        client = TestClient(app)
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.set_default_timeout(15000)
            errors = []
            requests = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.add_init_script("""window.__spoken=[];window.__cancelled=0;
                Object.defineProperty(window,'speechSynthesis',{value:{
                  getVoices:()=>[{name:'Synthetic local',lang:'en-US',localService:true,voiceURI:'local'},{name:'Synthetic second',lang:'en-GB',localService:true,voiceURI:'second'},{name:'Forbidden remote',lang:'en-US',localService:false,voiceURI:'remote'}],
                  addEventListener:()=>{},removeEventListener:()=>{},cancel:()=>window.__cancelled++,speak:u=>window.__spoken.push({name:u.voice.name,text:u.text,pitch:u.pitch,rate:u.rate})}});
                window.SpeechSynthesisUtterance=function(text){this.text=text;};""")

            def respond(route):
                request = route.request
                requests.append(request.url)
                path = request.url.removeprefix("http://127.0.0.1:8001")
                if request.method != "GET":
                    assert path.startswith(
                        ("/characters/", "/organization/", "/simulation/")
                    ), path
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
                    content_type=response.headers.get(
                        "content-type", "application/json"
                    ),
                    body=response.content,
                )

            page.route("http://127.0.0.1:8001/**", respond)
            page.goto(os.environ.get("DASHBOARD_SMOKE_URL", "http://127.0.0.1:3000/"))
            page.get_by_placeholder("API Key").fill(config.API_SECRET_KEY)
            page.get_by_role("button", name="Confirm", exact=True).click()
            open_view(page, "Organizational work")
            page.get_by_role("button", name="People & simulation", exact=True).click()
            page.get_by_label("Voice pace", exact=True).fill("1.05")
            page.get_by_role(
                "button", name="Save character version", exact=True
            ).click()
            page.get_by_text("190 cm · well built · version 2", exact=True).wait_for()
            assert get_character("executive:ceo")["appearance"]["beard"] is False
            assert (
                page.get_by_label("Compare installed local voice", exact=True)
                .locator("option")
                .filter(has_text="Forbidden remote")
                .count()
                == 0
            )
            page.get_by_label(
                "Compare installed local voice", exact=True
            ).select_option("local")
            page.get_by_role("button", name="Preview natural voice", exact=True).click()
            assert page.evaluate("window.__spoken[0].name") == "Synthetic local"
            assert page.evaluate("window.__spoken[0].pitch") == 1
            assert page.evaluate("window.__spoken[0].rate") == 1
            page.get_by_role(
                "button", name="Compare saved pitch / pace", exact=True
            ).click()
            assert page.evaluate("window.__spoken[1].rate") == 1.05
            page.get_by_label(
                "Compare installed local voice", exact=True
            ).select_option("second")
            page.get_by_role("button", name="Preview natural voice", exact=True).click()
            assert page.evaluate("window.__spoken[2].name") == "Synthetic second"
            page.get_by_role("button", name="Stop voice", exact=True).click()
            page.get_by_role(
                "button", name="Save selected voice at natural pitch", exact=True
            ).click()
            page.get_by_text("190 cm · well built · version 3", exact=True).wait_for()
            assert (
                get_character("executive:ceo")["voice"]["voice_name"]
                == "Synthetic second"
            )
            assert get_character("executive:ceo")["voice"]["language"] == "en-GB"
            assert get_character("executive:ceo")["voice"]["rate"] == 1
            page.get_by_label("Installed voice name (optional)", exact=True).fill(
                "Forbidden remote"
            )
            page.get_by_role(
                "button", name="Save character version", exact=True
            ).click()
            page.get_by_text("190 cm · well built · version 4", exact=True).wait_for()
            assert page.get_by_role(
                "button", name="Preview natural voice", exact=True
            ).is_disabled()
            page.get_by_text(
                "Your saved voice is unavailable on this device.", exact=False
            ).wait_for()
            assert page.evaluate("window.__spoken.length") == 3
            page.get_by_label("Neural audition voice", exact=True).select_option(
                "am_michael"
            )
            page.get_by_role("button", name="Load neural audition", exact=True).click()
            page.get_by_label("Neural audition playback", exact=True).wait_for(
                state="visible"
            )
            assert (
                page.get_by_label("Neural audition playback", exact=True)
                .get_attribute("src")
                .startswith("blob:")
            )
            page.wait_for_function(
                "() => {const a=document.querySelector('audio[aria-label=\"Neural audition playback\"]');return a && Number.isFinite(a.duration) && a.duration > .9 && a.readyState >= 2;}"
            )
            page.get_by_label("Neural audition playback", exact=True).evaluate(
                "(audio) => audio.play()"
            )
            page.wait_for_function(
                "() => document.querySelector('audio[aria-label=\"Neural audition playback\"]').currentTime > .05"
            )
            page.get_by_role("button", name="Stop neural audition", exact=True).click()
            assert page.get_by_label("Neural audition playback", exact=True).evaluate(
                "(audio) => audio.paused"
            )
            blocked_requests = []
            page.route(
                "https://example.test/blocked-audio.wav",
                lambda route: (
                    blocked_requests.append(route.request.url),
                    route.abort(),
                ),
            )
            page.evaluate(
                "() => {window.__mediaViolations=[];document.addEventListener('securitypolicyviolation',e => {if(e.effectiveDirective==='media-src')window.__mediaViolations.push(e.blockedURI)});window.__blockedAudio=new Audio('https://example.test/blocked-audio.wav');window.__blockedAudio.load();}"
            )
            page.wait_for_function(
                "() => window.__mediaViolations.includes('https://example.test/blocked-audio.wav')"
            )
            assert not blocked_requests, blocked_requests
            page.get_by_role(
                "button", name="Save neural voice preference", exact=True
            ).click()
            page.get_by_text("190 cm · well built · version 5", exact=True).wait_for()
            assert get_character("executive:ceo")["voice"]["provider"] == "kokoro_local"
            assert get_character("executive:ceo")["voice"]["voice_name"] == "am_michael"
            page.get_by_role(
                "button", name="Show character history", exact=True
            ).click()
            page.get_by_text("Version 1:", exact=False).wait_for()
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate(
                "document.documentElement.scrollWidth <= window.innerWidth + 1"
            )
            page.set_viewport_size({"width": 1440, "height": 1000})
            for key in (
                "ceo",
                "cfo",
                "general_counsel",
                "cmo",
                "board_director",
                "cto",
                "chro",
            ):
                page.get_by_label("Character", exact=True).select_option(
                    "executive:" + key
                )
                page.get_by_label("Portrait presentation", exact=True).wait_for()
                expected = get_character("executive:" + key)["appearance"][
                    "portrait_style"
                ]
                page.wait_for_function(
                    "(expected) => document.querySelector('[name=portrait_style]')?.value === expected",
                    arg=expected,
                )
                assert (
                    page.get_by_role("img", name="character:", exact=False).count() >= 2
                )
            page.get_by_label("Character", exact=True).select_option("executive:cfo")
            page.get_by_role("heading", name="Maya Chen", exact=True).wait_for()
            page.screenshot(
                path="/private/tmp/sprint2-character-review.png", full_page=True
            )
            page.get_by_role("button", name="Workforce", exact=True).click()

            def fill(values):
                for label, value in values.items():
                    page.get_by_label(label, exact=True).fill(str(value))

            fill(
                {
                    "Unique employee creation key": "smoke-worker",
                    "Employee name": "Synthetic adult worker",
                    "Employee job title": "Test assistant",
                    "Employee department ID": 1,
                    "Employee capacity hours": 8,
                }
            )
            page.get_by_role(
                "button", name="Create virtual employee", exact=True
            ).click()
            page.get_by_text(
                "Synthetic adult worker · Test assistant", exact=True
            ).wait_for()
            fill(
                {
                    "Employee ID to update": 1,
                    "Current employee version": 1,
                    "Updated department ID": 1,
                    "Updated employee capacity": 8,
                }
            )
            page.get_by_label("Employee status", exact=True).select_option("active")
            page.get_by_role("button", name="Update employee", exact=True).click()
            page.get_by_text("Employee #1", exact=False).filter(
                has_text="version 2"
            ).wait_for()
            fill(
                {
                    "Assigned employee ID": 1,
                    "Ready company task ID": task,
                    "Assignment hours": 5,
                }
            )
            page.get_by_role("button", name="Assign company work", exact=True).click()
            page.get_by_text("Assignment #1", exact=False).wait_for()
            fill(
                {
                    "Assignment ID to review": 1,
                    "Current assignment version": 1,
                    "Assignment review note": "Owner records synthetic work start",
                }
            )
            page.get_by_label("Assignment status", exact=True).select_option(
                "in_progress"
            )
            page.get_by_role(
                "button", name="Record assignment progress", exact=True
            ).click()
            page.get_by_text("Assignment #1", exact=False).filter(
                has_text="version 2"
            ).wait_for()
            fill(
                {
                    "Current assignment version": 2,
                    "Assignment review note": "Owner confirms synthetic completion",
                }
            )
            page.get_by_label("Assignment status", exact=True).select_option(
                "completed"
            )
            page.get_by_role(
                "button", name="Record assignment progress", exact=True
            ).click()
            page.get_by_text("Assignment #1", exact=False).filter(
                has_text="completed"
            ).wait_for()
            assert employees()[0]["allocated_hours"] == 0
            assert assignments()[0]["status"] == "completed"
            before = get_company_activity(100)
            page.get_by_role("button", name="Personal lives", exact=True).click()
            page.get_by_label("Enable personal simulation", exact=True).check()
            fill({"Simulation policy note": "Owner enables fictional test only"})
            page.get_by_role(
                "button", name="Save simulation settings", exact=True
            ).click()
            page.get_by_role(
                "button", name="Record fictional event", exact=True
            ).wait_for(state="visible")
            for kind, version in [("dating", 0), ("marriage", 1), ("divorce", 2)]:
                fill(
                    {
                        "Unique personal event key": "smoke-" + kind,
                        "Personal event character key": "executive:ceo",
                        "Partner key for relationship events": "executive:cfo",
                        "Current relationship version (0 for new)": version,
                        "Fictional event time": "2026-10-09T20:00",
                        "Fictional event narrative": "Fictional "
                        + kind
                        + " <script>alert(1)</script>",
                    }
                )
                page.get_by_label("Event type", exact=True).select_option(kind)
                page.get_by_role(
                    "button", name="Record fictional event", exact=True
                ).click()
                page.get_by_text(
                    "Fictional " + kind + " <script>alert(1)</script>", exact=True
                ).wait_for()
            assert len(events()) == 3
            assert relationship("executive:ceo", "executive:cfo")["state"] == "divorced"
            assert get_company_activity(100) == before
            assert page.locator("article script").count() == 0
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate(
                "document.documentElement.scrollWidth <= window.innerWidth + 1"
            )
            assert page.evaluate("localStorage.length") == 0
            assert page.evaluate("sessionStorage.length") == 0
            assert all(config.API_SECRET_KEY not in url for url in requests)
            assert page.evaluate("window.__cancelled") > 0
            assert not errors, errors
            browser.close()
        print(
            "PASS: character versions, local-only speech selection, employee allocation/lifecycle, fictional relationships, evidence isolation, mobile layout and key privacy"
        )


if __name__ == "__main__":
    main()
