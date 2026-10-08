"""Real SQLite/FastAPI task-board UI checks, entirely on disposable data.
Requires the dashboard built for API port 8001 and served on localhost:3000.
API requests are intercepted and sent to an in-process test backend, never the
user's running backend. Scheduler lifespan and external actions are not started.
"""
import os
import tempfile
from pathlib import Path
os.environ['CREWAI_DISABLE_TELEMETRY'] = 'true'
os.environ['CREWAI_TRACING_ENABLED'] = 'false'
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import config
from memory.database import init_db, create_company_goal, log_decision, propose_action, get_connection, action_provenance_scope, get_decision_by_id, transition_decision_approval, claim_decision_for_preparation
from memory.agile import list_boards, list_tasks, update_task
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright


def main():
    with tempfile.TemporaryDirectory(prefix='agile-browser-') as raw:
        config.DATABASE_PATH = str(Path(raw).resolve() / 'agile.db')
        config.API_SECRET_KEY = 'synthetic-agile-browser-key-1234567890'
        config.TELEGRAM_BOT_TOKEN = ''
        config.TELEGRAM_CHAT_ID = ''
        config.SANDBOX_MODE = True
        init_db()
        goal = create_company_goal('Synthetic experiment', 'Test only', 'Record observed outcome', status='active')
        decision = log_decision('Synthetic direction', ['ceo'], 'Test evidence', 'Published direction', goal_id=goal)
        transition_decision_approval(decision, 'approved', ('pending',))
        claim_decision_for_preparation(decision)
        with action_provenance_scope(decision, get_decision_by_id(decision)['sync_uuid']):
            action = propose_action('CTO', 'Synthetic proposed action', 'printf synthetic')
        from main import app
        client = TestClient(app)
        writes = []
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page(viewport={'width': 1440, 'height': 1000})
            page.set_default_timeout(10000)
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))

            def respond(route):
                request = route.request
                path = request.url.replace('http://127.0.0.1:8001', '')
                if request.method != 'GET':
                    writes.append(path)
                    assert path.startswith(('/boards', '/tasks')), 'Unexpected business mutation'
                response = client.request(request.method, path, headers={'X-API-Key': config.API_SECRET_KEY, 'Content-Type': 'application/json'}, content=request.post_data)
                route.fulfill(status=response.status_code, content_type='application/json', headers={'Access-Control-Allow-Origin': 'http://127.0.0.1:3000'}, body=response.content)

            page.route('http://127.0.0.1:8001/**', respond)
            page.goto('http://127.0.0.1:3000/')
            page.get_by_placeholder('API Key').fill(config.API_SECRET_KEY)
            page.get_by_role('button', name='Confirm', exact=True).click()
            page.get_by_role('navigation', name='Company views').get_by_role('button', name='Agile boards', exact=True).click()
            page.get_by_role('button', name='Create development roadmap', exact=True).click()
            page.get_by_role('button', name='BE-02 · Append-only activity event ledger', exact=True).wait_for()
            roadmap = next(b for b in list_boards() if b['kind'] == 'development')
            assert len(list_tasks(roadmap['id'])) == 14
            page.screenshot(path='/private/tmp/backend-agile-roadmap.png', full_page=True)
            page.get_by_label('New board name', exact=True).fill('Synthetic company work')
            page.get_by_role('button', name='Create board', exact=True).click()
            page.get_by_role('button', name='New task', exact=True).click()
            page.get_by_label('Task title', exact=True).fill('Observe synthetic experiment')
            page.get_by_label('Task acceptance criteria', exact=True).fill('Record observed result and evidence')
            page.get_by_label('Task assignee', exact=True).select_option('cto')
            for field, value in [('goal_id', goal), ('decision_id', decision), ('action_id', action)]:
                page.get_by_label('Task ' + field, exact=True).fill(str(value))
            page.get_by_role('button', name='Save task', exact=True).click()
            card = page.get_by_role('button', name='Observe synthetic experiment', exact=True)
            card.wait_for()
            card.click()
            page.get_by_label('Task status', exact=True).select_option('blocked')
            page.get_by_label('Task blocked reason', exact=True).fill('Need owner evidence')
            page.get_by_role('button', name='Save task', exact=True).click()
            page.get_by_role('region', name='Tasks blocked').get_by_text('Need owner evidence', exact=True).wait_for()
            card.click()
            page.get_by_label('Task status', exact=True).select_option('done')
            page.get_by_role('button', name='Save task', exact=True).click()
            page.get_by_role('alert').filter(has_text='A done task needs a completion note').wait_for()
            page.get_by_label('Task completion note', exact=True).fill('Verified with synthetic observation')
            page.get_by_role('button', name='Save task', exact=True).click()
            page.get_by_role('region', name='Tasks done').get_by_text('Verified with synthetic observation', exact=True).wait_for()
            company = next(b for b in list_boards() if b['kind'] == 'company')
            task = list_tasks(company['id'])[0]
            card.click()
            update_task(task['id'], task['version'], title='Concurrent task update')
            page.get_by_label('Task title', exact=True).fill('Stale overwrite')
            page.get_by_role('button', name='Save task', exact=True).click()
            page.get_by_role('alert').filter(has_text='Task changed since it was loaded').wait_for()
            assert list_tasks(company['id'])[0]['title'] == 'Concurrent task update'
            page.get_by_role('button', name='Cancel edit', exact=True).click()
            page.get_by_role('button', name='Refresh board', exact=True).click()
            page.get_by_role('button', name='Concurrent task update', exact=True).wait_for()
            page.set_viewport_size({'width': 390, 'height': 844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert page.evaluate('Object.keys(localStorage).length + Object.keys(sessionStorage).length') == 0
            with get_connection() as conn:
                assert conn.execute('SELECT status FROM action_queue WHERE id = ?', (action,)).fetchone()[0] == 'pending'
            assert not errors, errors
            assert writes
            browser.close()
            print('PASS: development roadmap, company task CRUD, lineage, blocking/completion rules, concurrent-edit conflict, mobile layout, privacy and no business execution.')


if __name__ == '__main__':
    main()
