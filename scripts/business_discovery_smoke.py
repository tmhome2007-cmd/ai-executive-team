"""Full owner research/practice UI on disposable records and a supplied dashboard URL."""
import json
import datetime
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import config
from memory.database import init_db, get_connection
from memory.evidence import create_source
from memory.business_discovery import list_briefs
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright


def main():
    with tempfile.TemporaryDirectory(prefix='business-ui-') as raw, patch.object(config, 'DATABASE_PATH', str(Path(raw) / 'test.db')), patch.object(config, 'API_SECRET_KEY', 'synthetic-business-smoke-key-1234567890'):
        init_db()
        for i in range(3):
            create_source(source_key=f'synthetic-{i}', title=f'Synthetic source {i}', reference=f'fixture {i}', summary='Synthetic constraint only. No demand evidence.', observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        from main import app
        client = TestClient(app)
        assert client.get('/business-discovery').status_code == 401
        from workflows.business_research_contract import SERVICES
        research = json.dumps({'options': [{'key': key, 'skills': ['Clear writing'], 'exercise': 'Private sample <script>alert(1)</script>', 'checks': ['Clearly labels unknown demand', 'Does not claim launch approval']} for key in SERVICES], 'practice_choice': 'documentation'})
        with patch('workflows.business_discovery._reason', return_value=research) as reason, sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page(viewport={'width': 1440, 'height': 1000})
            page.set_default_timeout(10000)
            errors, urls = [], []
            page.on('pageerror', lambda error: errors.append(str(error)))
            def respond(route):
                req = route.request
                urls.append(req.url)
                response = client.request(req.method, req.url.removeprefix('http://127.0.0.1:8001'), headers={'X-API-Key': config.API_SECRET_KEY, 'Content-Type': 'application/json'}, content=req.post_data)
                if response.status_code >= 400:
                    print('Synthetic request failed:', req.method, req.url, response.text)
                route.fulfill(status=response.status_code, content_type='application/json', body=response.content)
            page.route('http://127.0.0.1:8001/**', respond)
            page.goto(os.environ.get('DASHBOARD_SMOKE_URL', 'http://127.0.0.1:3001'))
            page.get_by_placeholder('API Key').fill(config.API_SECRET_KEY)
            page.get_by_role('button', name='Confirm', exact=True).click()
            page.get_by_role('navigation', name='Company views').get_by_role('button', name='Business research', exact=True).click()
            page.get_by_text('Available evidence records (3)', exact=True).click()
            for checkbox in page.locator('input[type=checkbox]:visible').all():
                checkbox.check()
            page.get_by_role('button', name='Save research brief', exact=True).click()
            reason.side_effect = ValueError('Synthetic generation failure')
            page.get_by_role('button', name='Compare options with local AI', exact=True).click()
            page.get_by_text('Synthetic generation failure', exact=True).wait_for()
            page.get_by_role('button', name='Refresh record', exact=True).click()
            page.get_by_role('button', name='Create new attempt from this brief', exact=True).click()
            reason.side_effect = None
            page.get_by_role('button', name='Compare options with local AI', exact=True).click()
            page.get_by_label('Chosen option', exact=True).fill('Synthetic documentation')
            page.get_by_label('Practice deliverable', exact=True).fill('Draft a synthetic guide, with no external action.')
            page.get_by_label('Observable checks (2–10, one per line)', exact=True).fill('Clearly labels unknown demand\nDoes not claim launch approval')
            page.get_by_label('Review due (your local time)', exact=True).fill((datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'))
            page.get_by_role('button', name='Approve this practice plan only', exact=True).click()
            page.get_by_role('button', name='Generate private practice sample', exact=True).click()
            page.get_by_text('Practice sample — AI self-checks are unverified', exact=True).wait_for()
            page.get_by_label('Clearly labels unknown demand', exact=True).check()
            page.get_by_label('Does not claim launch approval', exact=True).check()
            page.get_by_label('What you checked and observed', exact=True).fill('Synthetic review of the displayed sample; both checks observed.')
            page.get_by_role('button', name='Record practice review', exact=True).click()
            page.get_by_text('practice passed', exact=False).wait_for()
            assert list_briefs()[0]['state'] == 'reviewed'
            with get_connection() as conn:
                assert conn.execute('SELECT COUNT(*) FROM action_queue').fetchone()[0] == 0
                assert conn.execute('SELECT COUNT(*) FROM treasury_entries').fetchone()[0] == 0
            assert page.locator('script').filter(has_text='alert(1)').count() == 0
            page.set_viewport_size({'width': 390, 'height': 844})
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1')
            page.screenshot(path='/private/tmp/business-discovery-mobile.png', full_page=True)
            assert not errors, errors
            assert all(config.API_SECRET_KEY not in url for url in urls)
            assert page.evaluate('localStorage.length') == 0
            browser.close()
        print('PASS business UI: authenticated research -> owner practice plan -> sample -> review, no actions/money, literal text and mobile/key safety')


if __name__ == '__main__':
    main()
