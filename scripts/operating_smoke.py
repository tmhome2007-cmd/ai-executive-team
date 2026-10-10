"""Operations dashboard -> owner API -> disposable SQLite, with browser privacy checks."""
import datetime
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from config import config
from memory.database import init_db, create_executive_memory, propose_action, add_treasury_entry, approve_action_with_treasury, claim_action_for_execution, update_action_status, get_executive_memories
from memory.evidence import create_source, review_source
from memory.experiments import create_experiment
from memory.operating_policies import get_policy
from memory.observation_jobs import list_jobs, run_observation_jobs
from memory.agent_runtime import record_state
from playwright.sync_api import sync_playwright
from fastapi.testclient import TestClient


def main():
    with tempfile.TemporaryDirectory(prefix='operating-browser-') as raw, patch.object(config,'DATABASE_PATH',str(Path(raw).resolve()/'company.db')), patch.object(config,'API_SECRET_KEY','synthetic-operating-browser-key-1234567890'):
        init_db()
        stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
        action=propose_action('CTO','Synthetic observation subject','printf synthetic',expected_cost_amount=0,currency='EUR')
        experiment=create_experiment(action,title='Synthetic experiment',hypothesis='Recorded counter increases',baseline_note='Disposable data',baseline_value=10,metric_name='requests',unit='count',target_value=20,direction='increase',expected_result='Twenty requests',budget_amount=0,risk_limit=0,currency='EUR',observation_due_at='2020-01-01T00:00:00Z')
        approve_action_with_treasury(action); assert claim_action_for_execution(action); update_action_status(action,'executed_dry_run')
        stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
        source=create_source(source_key='browser-source',title='Synthetic measurement',reference='Disposable test record',summary=json.dumps(dict(experiment_id=experiment['id'],metric_name='requests',observed_at=stamp,value=25)),observed_at=stamp)
        review_source(source['id'],1,'owner_confirmed')
        memory,_=create_executive_memory(executive_key='ceo',memory_kind='general_lesson',lesson='Synthetic old lesson',fingerprint='browser-memory')
        record_state('browser-run','task','ceo','idle')
        from main import app
        client=TestClient(app)
        with sync_playwright() as runtime:
            browser=runtime.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':1000});page.set_default_timeout(15000)
            errors=[];requests=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            def respond(route):
                request=route.request; requests.append(request.url)
                path=request.url.removeprefix('http://127.0.0.1:8001')
                if request.method!='GET': assert path.startswith(('/operating-policy','/memory-review','/observation-jobs')),path
                response=client.request(request.method,path,headers={'X-API-Key':config.API_SECRET_KEY,'Content-Type':'application/json'},content=request.post_data)
                route.fulfill(status=response.status_code,content_type='application/json',headers={'Access-Control-Allow-Origin':os.environ.get('DASHBOARD_SMOKE_URL','http://127.0.0.1:3000/').rstrip('/')},body=response.content)
            page.route('http://127.0.0.1:8001/**',respond)
            page.goto(os.environ.get('DASHBOARD_SMOKE_URL','http://127.0.0.1:3000/'))
            page.get_by_placeholder('API Key').fill(config.API_SECRET_KEY);page.get_by_role('button',name='Confirm',exact=True).click()
            page.get_by_role('navigation',name='Company views').get_by_role('button',name='Organizational work',exact=True).click()
            page.get_by_role('button',name='Operations',exact=True).click()
            page.get_by_text('Company operating policy',exact=True).wait_for()
            page.get_by_label('Maximum action cost',exact=True).fill('5')
            page.get_by_label('Policy review note',exact=True).fill('Synthetic owner policy')
            page.get_by_role('button',name='Save policy version',exact=True).click()
            page.get_by_text('Version 2.',exact=False).wait_for();assert get_policy()['max_action_cost']==5
            for label,value in {'Memory ID':str(memory),'Current memory version':'1','Source IDs, comma separated':str(source['id']),'Replacement lesson for corrections':'Synthetic corrected lesson <script>alert(1)</script>','Memory review note':'Owner-reviewed correction'}.items():page.get_by_label(label,exact=True).fill(value)
            page.get_by_label('Operation',exact=True).select_option('correct');page.get_by_role('button',name='Record memory review',exact=True).click()
            page.get_by_text('Synthetic corrected lesson <script>alert(1)</script>',exact=True).wait_for();assert len(get_executive_memories('ceo'))==1;assert page.locator('article script').count()==0
            for label,value in {'Unique observation job key':'browser-observation','Experiment ID':str(experiment['id']),'Source ID for source collector':str(source['id']),'Observation due (local time)':'2020-01-01T12:00'}.items():page.get_by_label(label,exact=True).fill(value)
            page.get_by_role('button',name='Schedule observation',exact=True).click();page.get_by_text('Job #1',exact=False).wait_for();assert len(list_jobs())==1
            run_observation_jobs();assert list_jobs()[0]['status']=='completed',list_jobs();page.get_by_role('button',name='Refresh records',exact=True).click();page.get_by_text('Observation #1',exact=False).wait_for()
            page.get_by_text('ceo: idle',exact=True).wait_for()
            page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1')
            assert page.evaluate('localStorage.length')==0;assert page.evaluate('sessionStorage.length')==0
            assert all(config.API_SECRET_KEY not in url for url in requests);assert not errors,errors
            browser.close()
        print('PASS: Operations browser/API policy, memory correction, observation result, activity, mobile layout, text safety and in-memory key privacy')


if __name__=='__main__':main()
