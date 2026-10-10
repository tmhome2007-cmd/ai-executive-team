"""Fixed rubrics, exact source attribution and representative useful deliverables."""
import datetime
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from config import config
from memory.database import init_db, get_connection
from memory.evidence import create_source, get_source, review_source
from memory.business_discovery import create_brief, claim_stage, finish_stage, select_practice, review_practice, get_brief
from memory.business_evidence import classify_source, business_sources
from memory.practice_quality import TEMPLATES, practice_evidence
from workflows.practice_deliverables import validate_deliverable
from workflows.business_research_contract import SERVICES, render_research

NOW=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()


class SprintThreeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=patch.object(config,'DATABASE_PATH',str(Path(self.temp.name)/'test.db'));self.db.start();init_db()
        self.ids=[]
        for i in range(3):
            source=create_source(source_key=f'buyer-{i}',title='Fictional buyer fixture',reference=f'https://publisher{i}.example/request',summary='Fictional buyer requested documentation for a task application. This is test data, not real demand.',observed_at=NOW(),expires_at=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(days=7)).isoformat())
            self.ids.append(source['id'])

    def tearDown(self):
        self.db.stop();self.temp.cleanup()

    def payload(self,**fields):
        return json.dumps(dict(options=[dict(key=k,skills=['Writing'],exercise='Private fictional text sample',checks=['Preserves supplied facts','Labels unknowns']) for k in SERVICES],practice_choice='documentation',**fields))

    def brief(self,facts='Fictional input A',checks=None,structured=True):
        b=create_brief('Private research','No spending or external action',self.ids)
        b=claim_stage(b['id'],b['version'],'research')
        b=finish_stage(b['id'],'research',render_research(self.payload(),b['research_sources']),b['version'])
        return select_practice(b['id'],b['version'],'Documentation','Draft a private summary',checks or ['Preserves facts','Labels unknowns'],(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(days=1)).isoformat(),**(dict(service_key='documentation',audience='Owner',supplied_facts=facts,deliverable_kind='other_text') if structured else {}))

    def sample(self,b,revision=False):
        b=claim_stage(b['id'],b['version'],'revision' if revision else 'practice')
        return finish_stage(b['id'],'revision' if revision else 'practice','Fictional private sample with unknowns; owner review remains pending.',b['version'])

    def assess(self,b,results,correction=False):
        return review_practice(b['id'],b['version'],results,'Owner assessed the exact displayed private sample.',NOW(),correction)

    def aggregate(self):
        with get_connection() as conn: return practice_evidence(conn.cursor())

    def test_api_auth_bounds_and_structured_plan_required_fields(self):
        from fastapi.testclient import TestClient
        from main import app
        with patch.object(config, 'API_SECRET_KEY', 'synthetic-sprint3-owner-key-1234567890'):
            client=TestClient(app);headers={'X-API-Key':config.API_SECRET_KEY}
            self.assertEqual(client.get('/business-discovery/practice-evidence').status_code,401)
            response=client.get('/business-discovery/practice-templates',headers=headers)
            self.assertEqual(response.status_code,200);self.assertEqual(response.headers['Cache-Control'],'no-store')
            self.assertEqual(client.get(f'/business-discovery/source-context/{2**80}',headers=headers).status_code,422)
            self.assertEqual(client.get(f'/business-discovery/{2**80}',headers=headers).status_code,422)
            fields=dict(expected_version=0,category='buyer',services=['documentation'],publication_date=datetime.date.today().isoformat(),note='Synthetic buyer fixture')
            url=f'/business-discovery/source-context/{self.ids[0]}'
            self.assertEqual(client.post(url,json=fields,headers=headers).status_code,200)
            self.assertEqual(client.post(url,json=fields,headers=headers).status_code,409)
            b=create_brief('API fixture','Private only',self.ids)
            b=claim_stage(b['id'],b['version'],'research');b=finish_stage(b['id'],'research',render_research(self.payload(),b['research_sources']),b['version'])
            fields=dict(expected_version=b['version'],selected_option='Documentation',service_key='documentation',exercise='Draft a private summary',checks=['Preserves facts','Labels unknowns'],observation_due_at=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(days=1)).isoformat())
            response=client.post(f"/business-discovery/{b['id']}/practice-plan",json=fields,headers=headers)
            self.assertEqual(response.status_code,400);self.assertEqual(get_brief(b['id'])['state'],'research_ready')
            fields.update(audience='Owner',supplied_facts='Fictional input',deliverable_kind='other_text')
            self.assertEqual(client.post(f"/business-discovery/{b['id']}/practice-plan",json=fields,headers=headers).status_code,200)
            self.assertEqual(client.post(f"/business-discovery/{b['id']}/practice-plan",json=fields,headers=headers).status_code,409)

    def test_exact_feedback_and_correction_history(self):
        b=self.assess(self.sample(self.brief()),[False,True])
        original=b['attempts'][0]['reviews'][0]['id']
        b=self.assess(b,[False,False],True)
        used=b['attempts'][0]['reviews'][-1]['id']
        b=self.assess(self.sample(b,True),[True,False])
        pair=b['feedback_summary']['comparisons'][0]
        self.assertTrue(pair['comparable']);self.assertEqual(pair['before_review_id'],used)
        self.assertNotEqual(used,original);self.assertEqual(pair['improved_checks'],['Preserves facts']);self.assertEqual(pair['remaining_failures'],['Labels unknowns'])
        self.assertEqual(len(b['attempts'][0]['reviews']),2)
        self.assertEqual(self.aggregate()['groups'][0]['assessed_examples'],1)
        with get_connection() as conn:
            for query in ('UPDATE practice_specifications SET rubric_digest="x"','DELETE FROM practice_review_specifications','DELETE FROM business_research_contexts'):
                with self.assertRaises(sqlite3.IntegrityError): conn.execute(query)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM action_queue').fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM treasury_entries').fetchone()[0],0)

    def test_changed_rubric_rejected_and_new_rubric_separate(self):
        b=self.sample(self.brief())
        with get_connection() as conn:
            conn.execute('UPDATE business_discovery SET checks_json=? WHERE id=?',(json.dumps(['Easier check','Other check']),b['id']));conn.commit()
        with self.assertRaises(RuntimeError): self.assess(b,[True,True])
        self.assertEqual(get_brief(b['id'])['state'],'sample_ready')
        self.assess(self.sample(self.brief(checks=['Different check','Other check'])),[True,True])
        self.assertEqual(self.aggregate()['groups'][0]['assessed_examples'],1)

    def test_copies_revisions_and_legacy_do_not_count_as_distinct_examples(self):
        first=self.assess(self.sample(self.brief()),[True,True])
        self.assess(self.sample(self.brief()),[True,True])
        self.assess(self.sample(self.brief(structured=False)),[True,True])
        self.assertEqual(self.aggregate()['groups'][0]['assessed_examples'],1)
        second=self.assess(self.sample(self.brief(facts='Fictional input B')),[True,False])
        group=self.aggregate()['groups'][0]
        self.assertEqual(group['assessed_examples'],2);self.assertTrue(group['repeated_practice_evidence']);self.assertEqual(group['passing_examples'],1)
        self.sample(second,True) # unreviewed latest sample removes old assessment from current aggregate
        self.assertEqual(self.aggregate()['groups'][0]['assessed_examples'],1)
        self.assertEqual(first['risk_limit'],0)

    def test_owner_classification_is_versioned_and_report_context_is_frozen(self):
        context=classify_source(self.ids[0],0,'buyer',['documentation'],datetime.date.today().isoformat(),'Fictional classification')
        self.assertEqual(context['version'],1)
        with self.assertRaises(RuntimeError): classify_source(self.ids[0],0,'platform',[])
        b=self.brief()
        classify_source(self.ids[0],1,'platform',[])
        self.assertEqual(get_brief(b['id'])['research_sources'][0]['business_context']['category'],'buyer')
        self.assertEqual(business_sources(self.ids)[0]['business_context']['category'],'platform')
        with self.assertRaises(ValueError): classify_source(self.ids[1],0,'buyer',['documentation'],'2999-01-01')

    def test_platform_records_cannot_select_business_and_fabricated_quotes_rejected(self):
        claims=[dict(source_id=i,service='documentation',quote='Fictional buyer requested documentation for a task application.',relation='supports') for i in self.ids[:2]]
        for ident in self.ids:
            classify_source(ident,0,'platform',['documentation'],datetime.date.today().isoformat())
            review_source(ident,1,'owner_confirmed')
        report=render_research(self.payload(claims=claims),business_sources(self.ids))
        self.assertIn('Selection blocked',report);self.assertIn('0 distinct source-site',report)
        claims[0]['quote']='Invented evidence that does not appear in the record.'
        rejected=render_research(self.payload(claims=claims),business_sources(self.ids))
        self.assertIn('Withheld unsupported quotation',rejected)
        self.assertNotIn(claims[0]['quote'],rejected)
        self.assertIn('Selection blocked',rejected)

    def test_candidate_requires_coverage_and_contradictions_block(self):
        claims=[dict(source_id=i,service='documentation',quote='Fictional buyer requested documentation for a task application.',relation='supports') for i in self.ids[:2]]
        for ident in self.ids:
            classify_source(ident,0,'buyer',['documentation'],datetime.date.today().isoformat())
            review_source(ident,1,'owner_confirmed')
        report=render_research(self.payload(claims=claims),business_sources(self.ids))
        self.assertIn('Research candidate with greatest',report);self.assertIn('not established',report)
        claims.append(dict(source_id=self.ids[2],service='documentation',quote='This is test data, not real demand.',relation='contradicts'))
        self.assertIn('Selection blocked',render_research(self.payload(claims=claims),business_sources(self.ids)))
        classify_source(self.ids[2],1,'contradiction',['documentation'],datetime.date.today().isoformat())
        self.assertIn('Selection blocked',render_research(self.payload(claims=claims[:2]),business_sources(self.ids)))
        # Same publisher and unknown freshness cannot establish distinct current coverage.
        sources=business_sources(self.ids);sources[1]['reference']='https://docs.publisher0.example/request';sources[0]['reference']='https://support.publisher0.example/request';sources[0]['freshness']='unknown'
        self.assertIn('Selection blocked',render_research(self.payload(claims=claims[:2]),sources))

    def test_proposals_are_bounded_and_sensitive_urls_rejected(self):
        for url in ('http://127.0.0.1/private','http://localhost/x','https://site.example/x?token=abc','https://user:password@site.example/x','http://[::1]/x'):
            with self.assertRaises(ValueError): render_research(self.payload(next_sources=[dict(url=url,purpose='Buyer evidence')]),[get_source(i) for i in self.ids])
        report=render_research(self.payload(next_sources=[dict(url='https://github.com/orgs/community/discussions',purpose='Investigate missing demand evidence')]),[get_source(i) for i in self.ids])
        self.assertIn('Proposed public source (not read)',report)
        for url in ('https://example.org/public-page','https://docs.example.com/x','https://public.example/x'):
            report=render_research(self.payload(next_sources=[dict(url=url,purpose='Unknown contents')]),[get_source(i) for i in self.ids])
            self.assertIn('Withheld placeholder source URL',report)
            self.assertNotIn('Proposed public source (not read)',report)

    def test_local_guide_adapter_accepts_native_structured_model_result(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from workflows.task_guide_contract import TaskGuideDraft
        from workflows.business_discovery import _reason
        value=TaskGuideDraft(initial_task_text='Read chapter one',revised_task_text='Read chapter two',faqs=[dict(question='How to create?',answer='Use the create function.'),dict(question='How to edit?',answer='Use the edit function.'),dict(question='How to complete?',answer='Use the complete function.')],unknowns=['Interface controls and reminder functionality are unknown.'])
        agent=SimpleNamespace(llm=SimpleNamespace(model='llama3.1',base_url='http://localhost:11434'),role='Synthetic agent',backstory='Fictional test')
        for native in (value,value.model_dump()):
            with patch('workflows.business_discovery._local_agent',return_value=agent),patch('crewai.LLM',return_value=SimpleNamespace(call=Mock(return_value=native))):
                from workflows.task_guide_contract import render_task_guide
                rendered=render_task_guide(_reason('Fictional task guide',structured='task_guide'),TEMPLATES[0]['supplied_facts'])
                self.assertIn('1. Use the create function',rendered)
                self.assertTrue(validate_deliverable(rendered,dict(structured=True,specification=TEMPLATES[0])))

    def test_structured_guide_keeps_unknown_ui_out_of_instructions(self):
        from workflows.task_guide_contract import render_task_guide
        draft=dict(initial_task_text='Read chapter one',revised_task_text='Read chapter two',faqs=[dict(question='How do I start?',answer='Use the create function with the supplied fictional task text.'),dict(question='How do I update it?',answer='Use the edit function on that same task.'),dict(question='How do I finish?',answer='Use the complete function on the task you finished.')],unknowns=['Interface controls and reminder functionality are unknown.'])
        draft['faqs'][0]['answer']='A: A: '+draft['faqs'][0]['answer']
        rendered=render_task_guide(json.dumps(draft))
        self.assertNotIn('A: A:',rendered)
        self.assertTrue(validate_deliverable(rendered,dict(structured=True,specification=TEMPLATES[0])))
        for invalid in ('Click the Create Task button for the fictional example (interface control unknown).', 'Create the fictional task by entering its text into the task text field.'):
            draft['faqs'][0]['answer']=invalid
            with self.assertRaises(ValueError): validate_deliverable(render_task_guide(json.dumps(draft)),dict(structured=True,specification=TEMPLATES[0]))

    def test_three_representative_deliverables_and_observed_failure(self):
        samples=[
            '**Task guide**\n1. Create a task for the fictional example “Read chapter one” using the create function; exact controls are unknown.\n2. Edit that same task to “Read chapter two” using the edit function; keep the revised text with that task.\n3. Complete that task using the complete function after the fictional reading activity; check its recorded completion.\n**FAQ**\nQ: How do I start?\nA: Choose a short task description and use the create function.\nQ: How do I change it?\nA: Update the chosen task using the edit function.\nQ: How do I finish it?\nA: Use the complete function for the task you finished.\nInterface controls and reminder functionality are unknown.',
            '**Findings**\nFictional TEST-001 expected five checks; four passed and the reminder did not appear.\n**Unknowns**\nThe cause is unknown; reminder due time and original reproduction steps are unknown.\n**Next Action**\nRequest the reproduction steps and due time before defining another test.',
            'Thank you for asking about the fictional return policy. Unused items may be reviewed for return within 14 days. Please provide your purchase date and describe the item condition so it can be reviewed against the policy. No refund is approved or promised; this is a private draft and no customer has been contacted.'
        ]
        for template,sample in zip(TEMPLATES,samples):
            with self.subTest(template=template['key']):
                result=validate_deliverable(sample,dict(structured=True,specification=template))
                self.assertTrue(result)
                if template['key']=='evidence_summary': self.assertNotIn('Reminder functionality is unknown',result)
        with self.assertRaises(ValueError): validate_deliverable('1. Create using the create function.\n2. Edit using the edit function.\n3. Complete using the complete function.\nQ: Create?\nA: Create.\nQ: Edit?\nA: Edit.\nQ: Complete?\nA: Complete.\nReminder functionality is unknown.',dict(structured=True,specification=TEMPLATES[0]))
        with self.assertRaises(ValueError): validate_deliverable(samples[2]+' Your refund will be processed today.',dict(structured=True,specification=TEMPLATES[2]))
