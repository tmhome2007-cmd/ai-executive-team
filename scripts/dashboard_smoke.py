"""Dashboard navigation/privacy smoke test with synthetic API responses only.
Start the production dashboard on localhost:3000 before running this script.
"""
import os
import json
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

API = 'http://127.0.0.1:8001'


def main():
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        page.set_default_timeout(8000)
        failures = []
        page.on('pageerror', lambda error: failures.append(str(error)))
        treasury_down = [False]
        requests = []
        decision = {'id': 105, 'topic': 'Synthetic landing page experiment',
                    'timestamp': '2026-10-08T12:00:00', 'meeting_type': 'strategy',
                    'agents_involved': 'ceo', 'task_description': 'Synthetic evidence',
                    'decision_outcome': '**Expected vs Actual**\n\n* Four checks passed.\n<script>alert(1)</script>',
                    'sandbox_mode': 1, 'approval_status': 'pending', 'preparation_status': 'not_started'}
        action = {'id': 60, 'timestamp': '2026-10-08T12:01:00', 'proposed_by': 'cto',
                  'action_description': 'Synthetic experiment', 'action_detail': 'Test only',
                  'status': 'executed', 'reviewed_at': None, 'actual_outcome': 'Four checks passed',
                  'outcome_status': 'partial', 'source_decision_id': 105}
        fixtures = {
            '/system/sandbox-status': {'sandbox_mode': True},
            '/system/health': {'status': 'healthy', 'uptime_seconds': 120, 'components': {
                'ollama': {'ok': True, 'message': 'Local inference ready'},
                'database': {'ok': True, 'message': 'Writable'},
                'telegram_configured': {'ok': False, 'message': 'Optional; disabled'}}},
            '/workflows/daily-research/status': {'success': None, 'last_run_time': None, 'message': 'Not run'},
            '/decisions/history': [decision], '/actions/pending': [], '/actions/history': [action],
            '/resources/pending': [], '/goals': [], '/followups/open': [],
            '/organization/office-roster': [],
            '/workflows/autonomous-followup/status': {'success': None, 'message': 'No run recorded', 'last_run_time': None, 'scanned_goal_count': 0, 'created_event_ids': [], 'generated_decision_ids': [], 'resolved_event_ids': [], 'errors': []},
            '/memory/ceo': [], '/memory/cfo': [], '/meeting-types': {},
            '/treasury/summary': {'currencies': {'EUR': {'available': 15, 'reserved': 5, 'cash_balance': 20}}},
        }

        fixtures['/executives/profiles'] = {
            'ceo': {'name': 'Kai Akira', 'role': 'CEO', 'goal': 'Strategic alignment', 'backstory': 'Synthetic strategic personality'},
            'cfo': {'name': 'Maya Chen', 'role': 'CFO', 'goal': 'Capital efficiency', 'backstory': 'Synthetic financial personality'},
            'cto': {'name': 'Priya Raman', 'role': 'CTO', 'goal': 'Technical feasibility', 'backstory': 'Synthetic engineering personality'},
        }
        fixtures['/company/activity'] = {'items': [
            {'event_key': 'outcome:60', 'timestamp': '2026-10-08T12:05:00', 'category': 'result', 'title': 'Outcome measured: partial', 'detail': 'Four checks passed', 'decision_id': 105, 'action_id': 60, 'resource_id': None, 'goal_id': None},
        ]}
        fixtures['/decisions/105/conversations'] = {'contributions': [
            {'id': 1, 'executive_key': 'ceo', 'phase': 'decision', 'sequence': 1, 'captured_at': '2026-10-08T12:00:00', 'body': 'Published CEO recommendation <script>alert(1)</script>', 'profile': {'name': 'Kai Akira', 'role': 'CEO'}},
            {'id': 2, 'executive_key': 'cto', 'phase': 'preparation', 'sequence': 1, 'captured_at': '2026-10-08T12:02:00', 'body': 'Published technical preparation', 'profile': {'name': 'Priya Raman', 'role': 'CTO'}},
        ]}

        def respond(route):
            request = route.request
            requests.append(request.method)
            path = urlsplit(request.url).path
            if path == '/treasury/summary' and treasury_down[0]:
                route.fulfill(status=503, headers={'Access-Control-Allow-Origin': os.environ.get('DASHBOARD_SMOKE_URL','http://127.0.0.1:3000/').rstrip('/')}, content_type='application/json', body='{}')
                return
            assert request.method == 'GET', 'Navigation must never approve or execute an action'
            assert request.headers.get('x-api-key') == 'synthetic-dashboard-key-1234567890'
            route.fulfill(status=200, headers={'Access-Control-Allow-Origin': os.environ.get('DASHBOARD_SMOKE_URL','http://127.0.0.1:3000/').rstrip('/')}, content_type='application/json', body=json.dumps(fixtures.get(path, {})))

        page.route(API + '/**', respond)
        page.goto(os.environ.get('DASHBOARD_SMOKE_URL','http://127.0.0.1:3000/'))
        page.get_by_placeholder('API Key').fill('synthetic-dashboard-key-1234567890')
        page.get_by_role('button', name='Confirm').click()
        page.get_by_role('heading', name='Company command center').wait_for()
        page.get_by_text('15 available · 5 reserved').wait_for()
        nav = page.get_by_role('navigation', name='Company views')
        for name, heading in [('Goals', 'Company Goals / Missions'), ('Treasury', 'Company Treasury'),
                              ('Resources', 'Resource & Capability Requests (0)'),
                              ('Actions & results', 'Action History'),
                              ('Executive activity', 'Executive Memory'), ('System health', 'System health')]:
            nav.get_by_role('button', name=name, exact=True).click()
            assert page.get_by_role('heading', name=heading, exact=True).is_visible()
        nav.get_by_role('button', name='Decisions', exact=True).click()
        assert page.get_by_text('<script>alert(1)</script>', exact=True).filter(visible=True).first.is_visible()
        report = page.get_by_role('region', name='AI report short review').filter(visible=True)
        assert report.get_by_role('heading', name='Reported findings', exact=True).is_visible()
        report.get_by_text('Full report and evidence details', exact=True).click()
        assert report.get_by_text(decision['decision_outcome'], exact=True).is_visible()
        assert report.locator('script').count() == 0
        nav.get_by_role('button', name='Overview', exact=True).click()
        nav.get_by_role('button', name='Virtual office', exact=True).click()
        page.get_by_role('heading', name='Virtual office', exact=True).wait_for()
        assert page.get_by_role('button', name='Inspect ', exact=False).count() == 11
        page.get_by_role('button', name='Inspect CTO', exact=True).click()
        inspector = page.get_by_role('complementary', name='Executive inspector')
        assert inspector.get_by_text('Observed: Four checks passed', exact=True).is_visible()
        assert inspector.get_by_text('executed · Decision #105', exact=True).is_visible()
        page.get_by_role('button', name='Build floor', exact=True).click()
        assert page.get_by_role('button', name='Inspect CEO', exact=True).count() == 0
        page.get_by_role('button', name='Inspect CTO', exact=True).wait_for()
        page.get_by_role('button', name='All floors', exact=True).click()
        page.get_by_role('button', name='Inspect CFO', exact=True).click()
        assert inspector.get_by_text('No actions for this executive in the loaded records.', exact=True).is_visible()
        page.get_by_role('button', name='Review CFO memory →', exact=True).click()
        assert page.get_by_role('heading', name='Executive Memory', exact=True).is_visible()
        assert page.get_by_role('combobox').filter(visible=True).first.input_value() == 'cfo'
        nav.get_by_role('button', name='Virtual office', exact=True).click()
        page.screenshot(path='/private/tmp/virtual-office-desktop.png', full_page=True)
        page.set_viewport_size({'width': 390, 'height': 844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path='/private/tmp/virtual-office-mobile.png', full_page=True)
        page.set_viewport_size({'width': 1440, 'height': 1000})
        nav.get_by_role('button', name='Overview', exact=True).click()
        nav.get_by_role('button', name='Conversations & activity', exact=True).click()
        page.get_by_text('Outcome measured: partial', exact=True).wait_for()
        page.get_by_role('combobox', name='Meeting for contributions').select_option('105')
        page.get_by_role('heading', name='Kai Akira', exact=True).wait_for()
        page.locator('.contribution').filter(has=page.get_by_role('heading', name='Kai Akira', exact=True)).get_by_text('Full report and evidence details', exact=True).click()
        assert page.get_by_text('Published CEO recommendation <script>alert(1)</script>', exact=True).is_visible()
        assert page.locator('.contribution script').count() == 0
        page.get_by_role('combobox', name='Contribution phase').select_option('preparation')
        page.locator('.contribution').get_by_text('Full report and evidence details', exact=True).click()
        assert page.get_by_text('Published technical preparation', exact=True).is_visible()
        assert page.get_by_role('heading', name='Kai Akira', exact=True).count() == 0
        page.get_by_role('combobox', name='Contribution phase').select_option('all')
        page.screenshot(path='/private/tmp/company-conversations-desktop.png', full_page=True)
        page.set_viewport_size({'width': 390, 'height': 844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.set_viewport_size({'width': 1440, 'height': 1000})
        nav.get_by_role('button', name='Overview', exact=True).click()
        treasury_down[0] = True
        page.get_by_role('button', name='Refresh company data').click()
        page.get_by_role('alert').filter(has_text='Could not fetch treasury').wait_for()
        assert page.get_by_text('Treasury unavailable.', exact=True).is_visible()
        treasury_down[0] = False
        page.get_by_role('button', name='Refresh company data').click()
        page.get_by_text('15 available · 5 reserved').wait_for()
        assert page.evaluate('Object.keys(localStorage).length + Object.keys(sessionStorage).length') == 0
        page.screenshot(path='/private/tmp/company-dashboard-v2-desktop.png', full_page=True)
        page.set_viewport_size({'width': 390, 'height': 844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path='/private/tmp/company-dashboard-v2-mobile.png', full_page=True)
        page.reload()
        page.get_by_role('heading', name='Access Required').wait_for()
        assert all(method == 'GET' for method in requests)
        assert not failures, failures
        browser.close()
        print('PASS: all ten views, executive names and published contributions, office profiles/floors and record linkage, safe report formatting, unavailable/recovered data, mobile layout, memory-only authentication, and no mutations.')


if __name__ == '__main__':
    main()
