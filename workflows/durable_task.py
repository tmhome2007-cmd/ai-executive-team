"""CrewAI task persistence without replaying an interrupted tool invocation."""
import hashlib
import json
from crewai import Task
from crewai.tasks.task_output import TaskOutput
from workflows.step_checkpoints import run_json_step


class DurableTask(Task):
    checkpoint_run_id: str
    quality_evidence: str = ''
    quality_enabled: bool = False
    quality_phase: str = ''
    quality_proposals: dict[str, str] = {}
    checkpoint_step_id: str

    def execute_sync(self, agent=None, context=None, tools=None):
        chosen_agent = agent or self.agent
        from memory.operating_policies import policy_context
        operating_context = policy_context()
        # Bind result reuse to actual prompt, predecessor outputs and role.
        digest = hashlib.sha256(json.dumps({
            'operating_context': operating_context,
            'quality_policy': 1 if self.quality_enabled else None,
            'quality_evidence': self.quality_evidence,
            'quality_phase': self.quality_phase, 'quality_proposals': self.quality_proposals,
            'description': self.description, 'expected_output': self.expected_output,
            'context': context, 'role': chosen_agent.role,
            'goal': chosen_agent.goal, 'backstory': chosen_agent.backstory,
            'base_url': getattr(chosen_agent.llm, 'base_url', None),
            'model': getattr(chosen_agent.llm, 'model', None),
            'tools': [tool.name for tool in (tools or self.tools or [])],
        }, sort_keys=True).encode()).hexdigest()

        from memory.database import _current_action_provenance
        provenance = _current_action_provenance()

        def execute_task():
            before_actions = set(provenance['created_action_ids']) if provenance else set()
            before_resources = set(provenance['created_resource_request_ids']) if provenance else set()
            output = super(DurableTask, self).execute_sync(agent, context, tools)
            if self.quality_enabled:
                from workflows.output_quality import assess_output, review_notice, QUALITY_POLICY
                def check(candidate):
                    issues = assess_output(candidate, self.quality_evidence)
                    if self.quality_phase:
                        from workflows.discussion_contracts import assess_round, guard_critique_references
                        issues.extend(assess_round(candidate, self.quality_phase, self.quality_evidence)['warnings'])
                        if self.quality_phase == 'critique' and guard_critique_references(candidate, self.quality_proposals) != candidate:
                            issues.append('Cite the exact prior published claim using Claim quote: executive_key | verbatim text. Do not invent challenges; acknowledge existing stop conditions.')
                    return list(dict.fromkeys(issues))[:30]
                issues = check(output.raw)
                # Repair language once, never repeat a task with tool authority.
                if issues and not (tools or self.tools or chosen_agent.tools):
                    repaired = chosen_agent.llm.call(messages=[{'role': 'user', 'content':
                        QUALITY_POLICY + '\nRepair this draft only; no tools or new facts. Keep the required output format.\n'
                        + 'Role: ' + chosen_agent.role + '\nGoal: ' + chosen_agent.goal[:2000] + '\nPersona: ' + chosen_agent.backstory[:4000] + '\nTask: ' + self.description[:30000]
                        + '\nRequired format: ' + self.expected_output[:10000]
                        + '\nSource evidence: ' + self.quality_evidence[:30000]
                        + '\nIssues: ' + '\n'.join(issues) + '\nDraft: ' + output.raw[:30000]}])
                    if isinstance(repaired, str) and repaired.strip():
                        output.raw = repaired.removeprefix('Final Answer: ').strip()
                        issues = check(output.raw)
                output.raw = review_notice(output.raw, issues)
            # Avoid copying token-bearing trace/messages into durable results.
            return {
                'output': output.model_dump(mode='json', exclude={'messages', 'pydantic'}),
                'action_ids': [item for item in provenance['created_action_ids'] if item not in before_actions] if provenance else [],
                'resource_ids': [item for item in provenance['created_resource_request_ids'] if item not in before_resources] if provenance else [],
            }

        def execute():
            from workflows.capability_policy import normalize_executive_role
            from memory.agent_runtime import record_state
            role = normalize_executive_role(chosen_agent.role.split(" (", 1)[0])
            if role:
                record_state(self.checkpoint_run_id, self.checkpoint_step_id, role, 'running')
            try:
                original_description = self.description
                self.description = original_description + "\n" + operating_context
                try:
                    result = execute_task()
                finally:
                    self.description = original_description
            except BaseException:
                if role:
                    record_state(self.checkpoint_run_id, self.checkpoint_step_id, role, 'unknown')
                raise
            if role:
                record_state(self.checkpoint_run_id, self.checkpoint_step_id, role, 'idle')
            return result

        saved = run_json_step(self.checkpoint_run_id, self.checkpoint_step_id, digest, execute)
        if provenance:
            for field, items in (('created_action_ids', saved['action_ids']), ('created_resource_request_ids', saved['resource_ids'])):
                for item in items:
                    if item not in provenance[field]:
                        provenance[field].append(item)
        self.output = TaskOutput.model_validate(saved['output'])
        return self.output
