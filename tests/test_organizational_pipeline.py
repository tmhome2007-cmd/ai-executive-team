"""Real CrewAI and durable checkpoints, without network/provider/model side effects."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from crewai import Agent
from crewai.llms.base_llm import BaseLLM
from config import config
from agents.executive_agents import EXECUTIVE_AGENTS_NO_TOOLS
from memory.database import init_db, create_company_goal, get_connection
from memory.agile import create_board
from workflows.executive_planning import generate_plan
from workflows.discussion_rounds import run_discussion


class PlanLLM(BaseLLM):
    calls: int = 0
    def call(self, messages, **kwargs):
        self.calls += 1
        return 'Final Answer: ' + json.dumps({'tasks': [{'key': 'research', 'title': 'Collect evidence', 'acceptance_criteria': 'List dated records and gaps', 'assignee': 'cso', 'depends_on': [], 'expected_cost': 0, 'currency': 'EUR'}]})
    def supports_function_calling(self):
        return False


class DiscussionLLM(PlanLLM):
    def call(self, messages, **kwargs):
        self.calls += 1
        return 'Final Answer: Evidence-Supported Findings: No verified outcomes supplied. Assumptions: Unknown. Recommendation: Collect dated records. Approval Gate: Pending owner review.'


class OrganizationalPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.saved = config.DATABASE_PATH
        config.DATABASE_PATH = str(Path(self.temp.name).resolve() / 'pipeline.db')
        init_db()
        self.goal = create_company_goal('Synthetic goal', 'Collect synthetic evidence', 'Dated records', status='active')
        self.board = create_board('Synthetic tasks', 'company')
    def tearDown(self):
        config.DATABASE_PATH = self.saved
        self.temp.cleanup()
    def agents(self, llm):
        result = {key: Agent(role=EXECUTIVE_AGENTS_NO_TOOLS[key].role, goal=EXECUTIVE_AGENTS_NO_TOOLS[key].goal, backstory=EXECUTIVE_AGENTS_NO_TOOLS[key].backstory, llm=llm, tools=[], allow_delegation=False, verbose=False, max_iter=2) for key in ('ceo', 'coo', 'cfo')}
        return result
    def test_actual_plan_pipeline_preserves_persona_and_reuses_saved_plan(self):
        llm = PlanLLM(model='synthetic-only')
        agents = self.agents(llm)
        with patch('workflows.executive_planning.EXECUTIVE_AGENTS_NO_TOOLS', agents):
            first = generate_plan(run_key='pipeline-plan', goal_id=self.goal, board_id=self.board, title='Synthetic research', proposer='coo')
            with get_connection() as conn:
                step = conn.execute("SELECT result_json FROM workflow_step_checkpoints WHERE run_id = 'plan:pipeline-plan' AND step_id = 'proposal'").fetchone()
                self.assertIsNotNone(step)
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM agile_tasks').fetchone()[0], 0)
            with patch('workflows.executive_planning.Crew', side_effect=AssertionError('Repeated inference')):
                self.assertEqual(generate_plan(run_key='pipeline-plan', goal_id=self.goal, board_id=self.board, title='Synthetic research', proposer='coo')['id'], first['id'])
            with self.assertRaises(RuntimeError):
                generate_plan(run_key='pipeline-plan', goal_id=self.goal, board_id=self.board, title='Changed scope', proposer='coo')
        self.assertEqual(first['status'], 'proposed')
        self.assertEqual(agents['coo'].backstory, EXECUTIVE_AGENTS_NO_TOOLS['coo'].backstory)
    def test_actual_round_pipeline_persists_speakers_and_replays_without_inference(self):
        llm = DiscussionLLM(model='synthetic-only')
        agents = self.agents(llm)
        fields = dict(run_key='pipeline-rounds', topic='Synthetic debate', task_description='No outcomes supplied', agent_keys=['cfo','ceo'], goal_id=self.goal)
        with patch('workflows.discussion_rounds.EXECUTIVE_AGENTS_NO_TOOLS', agents):
            first = run_discussion(**fields)
            self.assertEqual(len(first['messages']), 7)
            with patch('workflows.discussion_rounds.run_executive_meeting', side_effect=AssertionError('Repeated inference')):
                self.assertEqual(run_discussion(**fields)['messages'], first['messages'])
            with self.assertRaises(RuntimeError):
                run_discussion(**{**fields, 'task_description': 'Changed scope'})
        with get_connection() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM workflow_step_checkpoints WHERE run_id LIKE 'discussion:pipeline-rounds:%' AND status = 'succeeded'").fetchone()[0], 7)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM action_queue').fetchone()[0], 0)
        self.assertTrue(all(message['profile']['backstory'] == EXECUTIVE_AGENTS_NO_TOOLS[message['executive_key']].backstory for message in first['messages']))


if __name__ == '__main__':
    unittest.main()
