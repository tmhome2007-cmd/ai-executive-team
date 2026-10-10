"""Owner review UI -> authenticated API -> disposable SQLite. No company runtime writes."""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
os.environ['CREWAI_DISABLE_TELEMETRY'] = 'true'
os.environ['CREWAI_TRACING_ENABLED'] = 'false'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import config
from memory.database import init_db, create_company_goal, propose_resource_request, transition_resource_request_status, get_connection, propose_action, get_action_by_id
from memory.agile import create_board
from memory.evidence import list_sources
from memory.planning import create_plan, list_plans
from memory.capabilities import list_capabilities
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright


def main():
    with tempfile.TemporaryDirectory(prefix='organizational-browser-') as raw:
        config.DATABASE_PATH = str(Path(raw).resolve() / 'company.db')
        config.API_SECRET_KEY = 'synthetic-organizational-browser-key-1234567890'
        config.TELEGRAM_BOT_TOKEN = ''
        config.TELEGRAM_CHAT_ID = ''
        config.SANDBOX_MODE = True
        init_db()
        goal = create_company_goal('Synthetic mission', 'Collect synthetic evidence', 'Dated evidence', status='active')
        board = create_board('Synthetic company work', 'company')
        resource = propose_resource_request('CTO', 'access', 'Synthetic dataset', 'Synthetic only')
        transition_resource_request_status(resource, 'approved', ('pending',))
        action = propose_action('CTO', 'Synthetic pending file', 'printf synthetic')
        def generate(**fields):
            return create_plan(**fields, tasks=[dict(key='research', title='Synthetic research', acceptance_criteria='List evidence gaps', assignee='cfo', depends_on=[], expected_cost=0, currency='EUR')])
        def meeting(**fields):
            roles = fields['agent_keys']
            return {'participants': roles, 'individual_outputs': {key: 'Synthetic published analysis <script>alert(1)</script>. The owner approved this.' for key in roles}, 'final_decision': 'Evidence required. The owner agreed to execute.'}
        from main import app
        client = TestClient(app)
        with patch('foundation_api.generate_plan', side_effect=generate), patch('workflows.executive_planning.run_executive_meeting', side_effect=meeting), patch('workflows.discussion_rounds.run_executive_meeting', side_effect=meeting), sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page(viewport={'width': 1440, 'height': 1000})
            page.set_default_timeout(15000)
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            def respond(route):
                request = route.request
                path = request.url.replace('http://127.0.0.1:8001', '')
                if request.method != 'GET':
                    assert path.startswith(('/evidence','/plans','/planned-work','/discussions','/capabilities',f'/actions/{action}/capabilities')), 'Unexpected business mutation: ' + path
                response = client.request(request.method, path, headers={'X-API-Key': config.API_SECRET_KEY, 'Content-Type': 'application/json'}, content=request.post_data)
                route.fulfill(status=response.status_code, content_type='application/json', headers={'Access-Control-Allow-Origin': os.environ.get('DASHBOARD_SMOKE_URL','http://127.0.0.1:3000/').rstrip('/')}, body=response.content)
            page.route('http://127.0.0.1:8001/**', respond)
            page.goto(os.environ.get('DASHBOARD_SMOKE_URL','http://127.0.0.1:3000/'))
            page.get_by_placeholder('API Key').fill(config.API_SECRET_KEY)
            page.get_by_role('button', name='Confirm', exact=True).click()
            page.get_by_role('navigation', name='Company views').get_by_role('button', name='Organizational work', exact=True).click()
            page.get_by_text('No sources recorded yet.', exact=True).wait_for()
            for label, value in {'Source title':'Synthetic dated source','Source reference':'Disposable test counter','Source observation date':'2000-01-01T12:00','Source expiry date (optional)':'2030-01-01T12:00','Source summary':'Synthetic record <script>alert(1)</script>'}.items():
                page.get_by_label(label, exact=True).fill(value)
            page.get_by_role('button', name='Register source', exact=True).click()
            source = None
            page.get_by_text('Source #1 · Synthetic dated source', exact=True).wait_for()
            source = list_sources()[0]
            page.get_by_role('button', name=f"Confirm source #{source['id']}", exact=True).click()
            page.get_by_text('Observed', exact=False).filter(has_text='owner confirmed').wait_for()
            page.get_by_role('button', name='Plans', exact=True).click()
            page.get_by_text('No work plans proposed yet.', exact=True).wait_for()
            for label, value in {'Plan title':'Synthetic work plan','Active goal ID':str(goal),'Company board ID':str(board)}.items():
                page.get_by_label(label, exact=True).fill(value)
            page.get_by_role('button', name='Generate plan proposal', exact=True).click()
            page.get_by_role('button', name='Approve plan #1', exact=True).wait_for()
            page.get_by_label('Owner review note', exact=True).fill('Owner reviewed synthetic plan')
            page.get_by_role('button', name='Approve plan #1', exact=True).click()
            page.get_by_role('button', name='Approve plan #1', exact=True).wait_for(state='detached')
            page.get_by_role('button', name='Run approved planning tasks', exact=True).click()
            page.get_by_role('button', name='Accept work #1', exact=True).wait_for()
            page.get_by_role('button', name='Accept work #1', exact=True).click()
            page.get_by_role('button', name='Accept work #1', exact=True).wait_for(state='detached')
            assert list_plans()[0]['work'][0]['status'] == 'done'
            page.get_by_role('button', name='Discussion rounds', exact=True).click()
            for label, value in {'Discussion topic':'Synthetic structured debate','Discussion evidence and question':'No verified outcomes supplied','Discussion source IDs (optional, comma separated)':str(source['id'])}.items():
                page.get_by_label(label, exact=True).fill(value)
            page.get_by_role('button', name='Start discussion rounds', exact=True).click()
            page.get_by_text('Round 4 · synthesis', exact=False).wait_for()
            assert page.locator('article script').count() == 0
            assert 'The owner approved' not in page.locator('section[aria-label="Organizational work"]').inner_text()
            page.get_by_role('button', name='Access inventory', exact=True).click()
            page.get_by_text('No scoped access provided yet.', exact=False).wait_for()
            page.get_by_label('Access provider', exact=True).select_option('manual')
            for label, value in {'Approved resource request ID':str(resource),'Exact target (owner/repository or browser host)':'Synthetic dataset','Scopes (repo.read, repo.write, page.read or page.interact)':'data.read','Executive keys (comma separated)':'cto'}.items():
                page.get_by_label(label, exact=True).fill(value)
            page.get_by_role('button', name='Provide access', exact=True).click()
            page.get_by_role('button', name='Verify access #1', exact=True).wait_for()
            page.get_by_role('button', name='Verify access #1', exact=True).click()
            page.get_by_text('Resource #1 · provided · unverified', exact=False).wait_for()
            for label, value in {'Pending action ID':str(action),'Required access ID':'1','Required action scope':'data.read'}.items():
                page.get_by_label(label, exact=True).fill(value)
            page.get_by_role('button', name='Bind action access requirement', exact=True).click()
            page.get_by_role('button', name='Revoke access #1', exact=True).click()
            page.get_by_text('Resource #1 · revoked · revoked', exact=False).wait_for()
            assert list_capabilities()[0]['status'] == 'revoked'
            assert get_action_by_id(action)['status'] == 'pending'
            with get_connection() as conn:
                assert conn.execute("SELECT COUNT(*) FROM decision_approvals WHERE status != 'pending'").fetchone()[0] == 0
                assert conn.execute('SELECT COUNT(*) FROM treasury_entries').fetchone()[0] == 0
                assert conn.execute("SELECT COUNT(*) FROM action_queue WHERE status != 'pending'").fetchone()[0] == 0
                assert conn.execute('SELECT COUNT(*) FROM discussion_messages').fetchone()[0] == 7
            for tab in ('Evidence','Plans','Discussion rounds','Access inventory'):
                page.get_by_role('button', name=tab, exact=True).click()
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), tab
                page.set_viewport_size({'width':1440,'height':1000})
            page.screenshot(path='/private/tmp/backend-organizational-work.png', full_page=True)
            assert page.evaluate('Object.keys(localStorage).length + Object.keys(sessionStorage).length') == 0
            assert not errors, errors
            browser.close()
            print('PASS: source registration/review, owner-approved plan/task review, published persona rounds, scoped manual access/revocation, safe model text, mobile width and no business execution/spending.')


if __name__ == '__main__':
    main()
