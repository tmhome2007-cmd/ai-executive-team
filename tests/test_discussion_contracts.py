"""Real CrewAI prompt contracts distinguish discussion phases from generic strategy."""
import tempfile
import unittest
from pathlib import Path
from config import config
from crewai import Agent
from memory.database import init_db
from workflows.meeting import run_executive_meeting
from workflows.discussion_contracts import round_contract, CONTRACTS
from test_workflow_recovery import SyntheticLLM


class ContractLLM(SyntheticLLM):
    prompts: list = []
    def call(self, messages, **kwargs):
        self.prompts.append(str(messages))
        return super().call(messages, **kwargs)


class DiscussionContractTests(unittest.TestCase):
    def test_real_tasks_use_phase_contract_without_generic_strategy_template(self):
        with tempfile.TemporaryDirectory() as raw:
            previous = config.DATABASE_PATH
            config.DATABASE_PATH = str(Path(raw).resolve() / 'contracts.db')
            try:
                init_db()
                for phase in CONTRACTS:
                    llm = ContractLLM(model='synthetic-only', prompts=[])
                    agent = Agent(role='CEO', goal='Review evidence', backstory='Synthetic CEO', llm=llm, tools=[], allow_delegation=False, verbose=False)
                    run_executive_meeting(topic='Synthetic reminder test', task_description='Fictional fixture: four checks passed, reminder failed; cause unknown.', agent_keys=['ceo'], agents_source={'ceo': agent}, memory_context={'enabled': False}, workflow_run_id='contract:' + phase, discussion_round=(phase, True))
                    prompt = '\n'.join(llm.prompts)
                    self.assertIn(CONTRACTS[phase], prompt)
                    self.assertIn('single-executive self-review', prompt)
                    self.assertIn('No tools, spending', prompt)
                    self.assertNotIn('Use this meeting-type response structure exactly', prompt)
                    self.assertNotIn('CEO FINAL-SYNTHESIS RULES', prompt)
                    self.assertIn('one reproducible next test', prompt)
            finally:
                config.DATABASE_PATH = previous

    def test_multi_executive_disagreement_requires_actual_conflicting_views(self):
        self.assertIn('actual incompatible recommendations', round_contract('critique', False))
        with self.assertRaises(ValueError):
            round_contract('fake-round', True)
