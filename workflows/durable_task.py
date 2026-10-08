"""CrewAI task persistence without replaying an interrupted tool invocation."""
import hashlib
import json
from crewai import Task
from crewai.tasks.task_output import TaskOutput
from workflows.step_checkpoints import run_json_step


class DurableTask(Task):
    checkpoint_run_id: str
    checkpoint_step_id: str

    def execute_sync(self, agent=None, context=None, tools=None):
        chosen_agent = agent or self.agent
        # Bind result reuse to actual prompt, predecessor outputs and role.
        digest = hashlib.sha256(json.dumps({
            'description': self.description, 'expected_output': self.expected_output,
            'context': context, 'role': chosen_agent.role,
            'goal': chosen_agent.goal, 'backstory': chosen_agent.backstory,
            'base_url': getattr(chosen_agent.llm, 'base_url', None),
            'model': getattr(chosen_agent.llm, 'model', None),
            'tools': [tool.name for tool in (tools or self.tools or [])],
        }, sort_keys=True).encode()).hexdigest()

        from memory.database import _current_action_provenance
        provenance = _current_action_provenance()

        def execute():
            before_actions = set(provenance['created_action_ids']) if provenance else set()
            before_resources = set(provenance['created_resource_request_ids']) if provenance else set()
            output = super(DurableTask, self).execute_sync(agent, context, tools)
            # Avoid copying token-bearing trace/messages into durable results.
            return {
                'output': output.model_dump(mode='json', exclude={'messages', 'pydantic'}),
                'action_ids': [item for item in provenance['created_action_ids'] if item not in before_actions] if provenance else [],
                'resource_ids': [item for item in provenance['created_resource_request_ids'] if item not in before_resources] if provenance else [],
            }

        saved = run_json_step(self.checkpoint_run_id, self.checkpoint_step_id, digest, execute)
        if provenance:
            for field, items in (('created_action_ids', saved['action_ids']), ('created_resource_request_ids', saved['resource_ids'])):
                for item in items:
                    if item not in provenance[field]:
                        provenance[field].append(item)
        self.output = TaskOutput.model_validate(saved['output'])
        return self.output
