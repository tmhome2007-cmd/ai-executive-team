"""Privacy defaults must override saved tracing consent and interactive prompts."""
import os
import subprocess
import sys
import unittest
from unittest.mock import patch
from crewai import Agent, Crew, Task, Process
from crewai.events.listeners.tracing.utils import should_enable_tracing
from test_workflow_recovery import SyntheticLLM


class TracePrivacyTests(unittest.TestCase):
    def test_bootstrap_overrides_environment_tracing_before_framework_import(self):
        environment = dict(os.environ, CREWAI_TRACING_ENABLED='true')
        result = subprocess.run([sys.executable, '-c', 'import privacy_bootstrap, os; assert os.environ["CREWAI_TRACING_ENABLED"] == "false"'], env=environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_real_crew_does_not_prompt_or_upload_despite_saved_consent(self):
        with patch.dict(os.environ, {'CREWAI_TRACING_ENABLED': 'false'}), patch('crewai.events.listeners.tracing.utils._load_user_data', return_value={'trace_consent': True, 'first_execution_done': True}), patch('crewai.telemetry.tracing.ephemeral.EphemeralSpanBuffer.share', side_effect=AssertionError('Trace sharing invoked')), patch('builtins.input', side_effect=AssertionError('Server prompted for input')):
            self.assertFalse(should_enable_tracing(override=False))
            agent = Agent(role='Synthetic role', goal='Synthetic task', backstory='Synthetic only', llm=SyntheticLLM(model='synthetic'), tools=[], verbose=False, allow_delegation=False)
            result = Crew(agents=[agent], tasks=[Task(description='Return a synthetic test result', expected_output='Synthetic result', agent=agent)], process=Process.sequential, tracing=False, verbose=False).kickoff()
            self.assertTrue(result.raw)
