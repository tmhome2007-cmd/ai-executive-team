"""Tool-free planning and durable, dependency-aware recommendation dispatch."""
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from agents.executive_agents import EXECUTIVE_AGENTS_NO_TOOLS, get_executive_profiles
from crewai import Agent, Crew, Process
from memory.database import get_company_goal, get_treasury_summary, log_decision, get_connection
from memory.planning import create_plan, claim_work, finish_work, get_plan
from memory.experiments import _text
from workflows.durable_task import DurableTask
from workflows.execution_lock import EXECUTION_LOCK
from workflows.meeting import run_executive_meeting


def generate_plan(*, run_key, goal_id, board_id, title, proposer='coo'):
    _text(run_key, 'plan run key', 80)
    _text(title, 'plan title', 200)
    if proposer not in EXECUTIVE_AGENTS_NO_TOOLS:
        raise ValueError('Unknown proposing executive')
    with get_connection() as conn:
        previous = conn.execute('SELECT * FROM executive_plans WHERE run_key = ?', (run_key,)).fetchone()
    if previous:
        if any(previous[k] != v for k, v in [('goal_id', goal_id), ('board_id', board_id), ('title', title), ('proposer', proposer)]):
            raise RuntimeError('Plan run key reused with different inputs')
        return get_plan(previous['id'])
    goal = get_company_goal(goal_id)
    if not goal or goal['status'] != 'active':
        raise ValueError('Plan generation requires an active goal')
    with get_connection() as conn:
        board = conn.execute("SELECT id FROM agile_boards WHERE id = ? AND kind = 'company'", (board_id,)).fetchone()
    if not board:
        raise ValueError('Company board not found')
    canonical = EXECUTIVE_AGENTS_NO_TOOLS[proposer]
    # Rebuild public configuration; live LLM clients contain non-copyable locks.
    agent = Agent(role=canonical.role, goal=canonical.goal, backstory=canonical.backstory,
                  llm=canonical.llm, tools=[], allow_delegation=False, verbose=False,
                  max_iter=canonical.max_iter)
    task = DurableTask(agent=agent, checkpoint_run_id='plan:' + run_key, checkpoint_step_id='proposal',
        description=(f'Propose a reviewed work plan: {title}. Preserve your role/personality. No tools, owner approval claims or real-world commitments. '
            'Return only JSON {"tasks":[{"key":"research","title":"...","acceptance_criteria":"...",'
            '"assignee":"cso","depends_on":[],"expected_cost":0,"currency":"EUR"}]}. '
            'Use known executive keys, at most 20 tasks, an acyclic graph, and distinguish estimated costs from measured facts. '
            'This is a proposal, not spending authority. Goal and treasury context: ' + json.dumps({'goal': goal, 'treasury': get_treasury_summary()}, sort_keys=True)),
        expected_output='Only the specified JSON object with tasks; no Markdown or invented evidence.')
    def worker():
        # The worker owns the lock even if the HTTP caller times out.
        with EXECUTION_LOCK:
            return Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False).kickoff()
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        executor.submit(worker).result(timeout=600)
    except FutureTimeoutError:
        raise RuntimeError('Plan reasoning timed out; review its checkpoint before retrying') from None
    finally:
        executor.shutdown(wait=False)
    try:
        proposal = json.loads(task.output.raw)
        if not isinstance(proposal, dict) or set(proposal) != {'tasks'}:
            raise ValueError()
    except (ValueError, AttributeError):
        raise ValueError('Executive did not return a valid structured plan; nothing was approved') from None
    return create_plan(run_key=run_key, goal_id=goal_id, board_id=board_id, title=title, proposer=proposer, tasks=proposal['tasks'])


async def dispatch_planned_work(max_items=2):
    if not 1 <= max_items <= 5:
        raise ValueError('Invalid dispatch batch size')
    # Scan by durable work ID, including blocked dependencies beyond the first page.
    cursor_id = 0
    dispatched = []
    while len(dispatched) < max_items:
        with get_connection() as conn:
            ids = [r[0] for r in conn.execute("SELECT id FROM planned_work WHERE id > ? AND status = 'waiting' ORDER BY id LIMIT 100", (cursor_id,))]
        if not ids:
            break
        for ident in ids:
            cursor_id = ident
            work = claim_work(ident)
            if work is None:
                continue
            try:
                goal = get_company_goal(work['goal_id'])
                result = await asyncio.to_thread(run_executive_meeting, topic=work['title'],
                    task_description='OWNER-REVIEWED TOOL-FREE WORK:\n' + work['acceptance_criteria'] + '\nProvide a recommendation only. Evidence gaps remain unknown.\nGoal: ' + goal['description'],
                    agent_keys=[work['assignee']], agents_source=EXECUTIVE_AGENTS_NO_TOOLS,
                    meeting_type='planning', workflow_run_id=f"plan:{work['plan_id']}:work:{ident}",
                    memory_context={'enabled': True, 'goal_id': work['goal_id'], 'limit': 5})
                decision_id = log_decision(work['title'], result['participants'], work['acceptance_criteria'], result['final_decision'],
                    goal_id=work['goal_id'], meeting_type='planning', workflow_key=f"plan:{work['plan_id']}:work:{ident}",
                    individual_outputs=result.get('individual_outputs'), executive_profiles=get_executive_profiles())
                finish_work(ident, decision_id=decision_id)
            except BaseException as error:
                finish_work(ident, error='failed or interrupted')
                if not isinstance(error, Exception):
                    raise
            dispatched.append(ident)
            if len(dispatched) >= max_items:
                break
    return {'dispatched_work_ids': dispatched, 'scope': 'Tool-free recommendations only; no direction/action approval or spending'}
