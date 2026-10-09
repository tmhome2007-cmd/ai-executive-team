"""Opt-in proposal -> critique -> revision -> CEO synthesis, with durable role steps."""
from agents.executive_agents import EXECUTIVE_AGENTS_NO_TOOLS, get_executive_profiles
from memory.database import log_decision, get_company_goal, get_decision_by_id, get_connection
from memory.evidence import source_context
from memory.discussions import consent_guard, get_discussion
from memory.experiments import _text
from workflows.meeting import run_executive_meeting
from workflows.output_quality import assess_output
from workflows.discussion_contracts import assess_round, guard_missing_prerequisites, guard_critique_references, guard_revision_changes


def run_discussion(*, run_key, topic, task_description, agent_keys, source_ids=None, goal_id=None):
    _text(run_key, 'discussion run key', 80)
    _text(topic, 'discussion topic', 200)
    _text(task_description, 'discussion task', 12000)
    if not isinstance(agent_keys, list) or not 1 <= len(agent_keys) <= 11 or len(set(agent_keys)) != len(agent_keys) or 'ceo' not in agent_keys or any(key not in EXECUTIVE_AGENTS_NO_TOOLS for key in agent_keys):
        raise ValueError('Discussion requires unique known executives and CEO synthesis')
    source_context(source_ids or [])  # Validate retries as well as new runs.
    with get_connection() as conn:
        saved = conn.execute('SELECT * FROM decisions WHERE workflow_key = ?', ('discussion:' + run_key,)).fetchone()
        if saved:
            links = conn.execute("SELECT s.id, s.source_key FROM evidence_links l JOIN evidence_sources s ON s.id = l.source_id WHERE l.entity_kind = 'decision' AND l.entity_id = ? AND l.relation = 'context'", (saved['id'],)).fetchall()
    if saved:
        expected = (topic, ','.join(agent_keys), task_description, goal_id)
        actual = tuple(saved[k] for k in ('topic', 'agents_involved', 'task_description', 'goal_id'))
        registered = {r['id'] for r in links if r['source_key'] != 'decision-context:' + saved['sync_uuid']}
        if actual != expected or registered != set(source_ids or []):
            raise RuntimeError('Discussion run key reused with different inputs or sources')
        return {'decision_id': saved['id'], 'final_decision': saved['decision_outcome'], 'messages': get_discussion(saved['id']), 'approval_status': get_decision_by_id(saved['id'])['approval_status']}
    if goal_id is not None:
        goal = get_company_goal(goal_id)
        if not goal or goal['status'] != 'active':
            raise ValueError('Discussion goal must be active')
    evidence = task_description + '\n' + source_context(source_ids or [])
    profiles = get_executive_profiles()
    messages = []
    previous = ''
    revised = {}
    proposals = {}
    for number, phase in enumerate(('proposal', 'critique', 'revision', 'synthesis'), 1):
        participants = ['ceo'] if phase == 'synthesis' else list(agent_keys)
        instruction = {
            'proposal': 'Publish a role-specific proposal with assumptions, source IDs and missing evidence.',
            'critique': 'Critique the published proposals from your own role. Identify unsupported claims and disagreements; prior speeches are not new evidence.',
            'revision': 'Revise your proposal after critique. State what changed and unresolved disagreement, preserving your personality.',
            'synthesis': 'Synthesize the revised views and unresolved disagreements. State evidence gaps and the exact owner review requested; never assert approval.',
        }[phase]
        original_context = ('\nORIGINAL PUBLISHED PROPOSALS (compare actual changes against these):\n' + '\n'.join(f'{r}: {b}' for r, b in proposals.items())) if phase == 'revision' else ''
        result = run_executive_meeting(topic=topic, task_description=evidence + '\nROUND: ' + phase + '\n' + instruction + '\nPUBLISHED PRIOR ROUND (unverified recommendations):\n' + previous + original_context,
            agent_keys=participants, agents_source=EXECUTIVE_AGENTS_NO_TOOLS, evidence_text=evidence,
            meeting_type='strategy', workflow_run_id=f'discussion:{run_key}:{phase}',
            discussion_round=(phase, len(agent_keys) == 1), discussion_proposals=proposals,
            memory_context={'enabled': True, 'goal_id': goal_id, 'limit': 5})
        outputs = result.get('individual_outputs', {})
        if set(outputs) != set(participants) or set(result['participants']) != set(participants) or len(result['participants']) != len(participants):
            raise ValueError('Discussion round lacks a published output for each participant')
        published = {}
        for role in result['participants']:
            raw_body = consent_guard(outputs[role])
            body = guard_missing_prerequisites(raw_body, phase)
            if phase == 'critique':
                body = guard_critique_references(body, proposals)
            elif phase == 'revision':
                body = guard_revision_changes(body, proposals.get(role, ''))
            published[role] = body
            quality = assess_round(body, phase, evidence)
            quality['warnings'].extend(assess_output(body, evidence))
            if quality['warnings']:
                quality['status'] = 'review_required'
            if body != raw_body:
                quality['warnings'].append('Backend corrected unverified discussion instructions or attribution; review the published output')
                quality['status'] = 'review_required'
            quality['warnings'] = list(dict.fromkeys(quality['warnings']))[:30]
            messages.append({'round_number': number, 'phase': phase, 'executive_key': role, 'body': body, 'profile': profiles[role], 'quality_checks': quality})
        if phase == 'proposal':
            proposals = published.copy()
        if phase == 'revision':
            revised = published
        previous = '\n'.join(f'{role}: {body}' for role, body in published.items())
        reviews = [f"{m['executive_key']}: {warning}" for m in messages if m['round_number'] == number for warning in m['quality_checks']['warnings']]
        if reviews:
            previous += '\nAUTOMATIC REVIEW CUES (not source evidence; address these in the next round):\n' + '\n'.join(reviews)
        if len(previous) > 300000:
            raise ValueError('Published discussion context exceeds the bounded round size')
    final = guard_missing_prerequisites(consent_guard(result['final_decision']), 'synthesis')
    unresolved = list(dict.fromkeys(warning for message in messages for warning in message['quality_checks']['warnings']))[:30]
    if unresolved:
        final += '\n\nDiscussion quality review required:\n' + '\n'.join('- ' + warning for warning in unresolved) + '\nThese checks do not approve the recommendation. Owner review remains pending.'
    revised['ceo'] = final
    ident = log_decision(topic, agent_keys, task_description, final, goal_id=goal_id,
        workflow_key='discussion:' + run_key, individual_outputs=revised, executive_profiles=profiles,
        source_ids=source_ids, discussion_messages=messages)
    return {'decision_id': ident, 'final_decision': final, 'messages': get_discussion(ident), 'approval_status': get_decision_by_id(ident)['approval_status']}
