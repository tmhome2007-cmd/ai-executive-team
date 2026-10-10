"""Immutable approved specifications and assessment bindings; no competence authority."""
import datetime
import hashlib
import json
import re
from memory.experiments import _text

TEMPLATES = [
    dict(key='task_guide', service_key='documentation', audience='A beginner using a fictional task app',
         supplied_facts='The fictional app supports creating, editing and completing tasks. Interface controls and reminders are unspecified. For the example, create the task text “Read chapter one”, edit it to “Read chapter two”, then mark that task complete. Separate task-name and description fields are not specified.',
         deliverable_kind='guide', exercise='Write a beginner task guide with three numbered steps and three FAQ answers. Explain how to choose a task, update it and record completion. Interface controls and reminder functionality are unknown.',
         checks=['Explains the create, edit and complete sequence with a concrete fictional task example.', 'Keeps interface controls and reminder functionality explicitly unknown.', 'Includes three numbered steps and three FAQ answers.', 'Does not claim testing or owner approval.']),
    dict(key='evidence_summary', service_key='documentation', audience='An owner deciding what to investigate next',
         supplied_facts='Fictional test TEST-001: five checks expected; four passed; the reminder did not appear. Cause, due time and original reproduction steps are unknown.',
         deliverable_kind='evidence_summary', exercise='Write a concise evidence summary with Findings, Unknowns and Next Action. Preserve the fictional test counts; request missing reproduction details before another test. Do not invent a cause.',
         checks=['Preserves five expected, four passed and one reminder failure.', 'Separates the observed failure from its unknown cause.', 'Requests missing reproduction details instead of inventing test conditions.']),
    dict(key='support_draft', service_key='support_drafts', audience='A customer asking about a fictional return',
         supplied_facts='Fictional policy: unused items may be reviewed for return within 14 days. The purchase date and item condition are unknown. No refund has been approved or issued.',
         deliverable_kind='reply', exercise='Draft a polite private customer reply based only on the supplied fictional return policy. Ask for purchase date and item condition, explain review, and do not promise or claim a refund.',
         checks=['States the supplied 14-day unused-item policy accurately.', 'Requests purchase date and item condition.', 'Does not promise or claim approval, refund or customer contact.']),
]


def init_quality(cursor):
    cursor.execute('''CREATE TABLE IF NOT EXISTS practice_specifications (
        id INTEGER PRIMARY KEY, brief_id INTEGER NOT NULL UNIQUE, specification_json TEXT NOT NULL,
        rubric_digest TEXT NOT NULL, structured INTEGER NOT NULL, created_at TEXT NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS practice_sample_specifications (
        sample_id INTEGER PRIMARY KEY, specification_id INTEGER NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS practice_review_specifications (
        review_id INTEGER PRIMARY KEY, specification_id INTEGER NOT NULL)''')
    for table in ('practice_specifications', 'practice_sample_specifications', 'practice_review_specifications'):
        for op in ('UPDATE', 'DELETE'):
            cursor.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{op.lower()} BEFORE {op} ON {table} BEGIN SELECT RAISE(ABORT,'Practice specifications and bindings are immutable'); END")  # nosec B608 # Literal identifiers.


def save_specification(cursor, brief_id, *, service_key, audience, supplied_facts, deliverable_kind, exercise, checks):
    if service_key not in {'documentation','editing','support_drafts','legacy'}:
        raise ValueError('Choose a supported practice service')
    structured = service_key != 'legacy'
    values = dict(service_key=service_key, audience=_text(audience,'audience',1000,structured),
                  supplied_facts=_text(supplied_facts,'supplied facts',6000,structured),
                  deliverable_kind=_text(deliverable_kind,'deliverable format',200,structured),
                  exercise=exercise, checks=checks, rubric_version=1)
    digest=hashlib.sha256(json.dumps({k:values[k] for k in ('service_key','deliverable_kind','checks','rubric_version')},sort_keys=True).encode()).hexdigest()
    cursor.execute('INSERT INTO practice_specifications(brief_id,specification_json,rubric_digest,structured,created_at) VALUES(?,?,?,?,?)',
                   (brief_id,json.dumps(values),digest,int(structured),datetime.datetime.now(datetime.timezone.utc).isoformat()))


def specification(cursor, brief_id):
    row=cursor.execute('SELECT * FROM practice_specifications WHERE brief_id=?',(brief_id,)).fetchone()
    if not row: return None
    item=dict(row);item['specification']=json.loads(item.pop('specification_json'));item['structured']=bool(item['structured'])
    return item


def bind_sample(cursor, brief_id, sample_id):
    spec=specification(cursor,brief_id)
    if spec: cursor.execute('INSERT INTO practice_sample_specifications VALUES(?,?)',(sample_id,spec['id']))


def bind_review(cursor, sample_id, review_id):
    row=cursor.execute('SELECT specification_id FROM practice_sample_specifications WHERE sample_id=?',(sample_id,)).fetchone()
    if row: cursor.execute('INSERT INTO practice_review_specifications VALUES(?,?)',(review_id,row['specification_id']))


def feedback_summary(cursor, brief_id):
    from memory.business_practice_history import history
    spec=specification(cursor,brief_id)
    samples=history(cursor,brief_id)
    pairs=[]
    for sample in samples:
        if not sample['parent_sample_id'] or not sample['reviews']: continue
        parent=next((s for s in samples if s['id']==sample['parent_sample_id']),None)
        if not parent or not parent['reviews']: continue
        before=next((r for r in parent['reviews'] if r['id']==sample['feedback_review_id']),None)
        after=sample['reviews'][-1]
        linked=cursor.execute('''SELECT s.specification_id FROM practice_sample_specifications s
            JOIN practice_review_specifications r ON r.specification_id=s.specification_id
            WHERE s.sample_id=? AND r.review_id=?''',(sample['id'],after['id'])).fetchone()
        parent_link=cursor.execute('''SELECT r.specification_id FROM practice_review_specifications r JOIN practice_sample_specifications s ON s.specification_id=r.specification_id WHERE r.review_id=? AND s.sample_id=?''',(before['id'],parent['id'])).fetchone() if before else None
        valid=bool(spec and spec['structured'] and linked and parent_link and linked[0]==parent_link[0]==spec['id'] and before and len(before['review']['results'])==len(after['review']['results'])==len(spec['specification']['checks']))
        improved=[];regressed=[];remaining=[]
        if valid:
            checks=spec['specification']['checks']
            improved=[checks[i] for i,(a,b) in enumerate(zip(before['review']['results'],after['review']['results'])) if not a and b]
            regressed=[checks[i] for i,(a,b) in enumerate(zip(before['review']['results'],after['review']['results'])) if a and not b]
            remaining=[checks[i] for i,r in enumerate(after['review']['results']) if not r]
        pairs.append(dict(sample_id=sample['id'],parent_sample_id=sample['parent_sample_id'],before_review_id=sample['feedback_review_id'],after_review_id=after['id'],comparable=valid,improved_checks=improved,regressed_checks=regressed,remaining_failures=remaining,
                          feedback_superseded=bool(before and parent['reviews'][-1]['id']!=before['id']),scope='Owner assessments of these samples, not verified competence or launch permission'))
    return dict(comparisons=pairs,scope='Compare exact feedback and current assessment under the same approved rubric; unbound legacy history is not comparable')


def practice_evidence(cursor):
    # Latest sample only per brief: repeated revisions are never separate examples.
    rows=cursor.execute('''SELECT p.*,s.id AS sample_id FROM practice_specifications p
        JOIN business_practice_samples s ON s.brief_id=p.brief_id
        JOIN practice_sample_specifications b ON b.sample_id=s.id AND b.specification_id=p.id
        WHERE p.structured=1 AND s.attempt=(SELECT MAX(attempt) FROM business_practice_samples WHERE brief_id=p.brief_id)
        ORDER BY p.id DESC LIMIT 501''').fetchall()
    if len(rows)>500: return dict(groups=[],truncated=True,scope='Too many examples; no aggregate claimed')
    groups={}
    seen_inputs=set()
    for row in rows:
        review=cursor.execute('''SELECT r.* FROM business_practice_reviews r JOIN practice_review_specifications b ON b.review_id=r.id
            WHERE r.sample_id=? AND b.specification_id=? ORDER BY r.id DESC LIMIT 1''',(row['sample_id'],row['id'])).fetchone()
        if not review: continue
        spec=json.loads(row['specification_json']);assessment=json.loads(review['review_json'])
        # Copies of the same input do not count as separate examples.
        signature=(row['rubric_digest'],tuple(re.findall(r'\w+',spec['supplied_facts'].casefold())))
        if signature in seen_inputs: continue
        seen_inputs.add(signature)
        group=groups.setdefault(row['rubric_digest'],dict(service_key=spec['service_key'],checks=spec['checks'],rubric_digest=row['rubric_digest'],assessed_examples=0,passing_examples=0,brief_ids=[]))
        group['assessed_examples']+=1;group['brief_ids'].append(row['brief_id'])
        if len(assessment['results'])==len(spec['checks']) and all(assessment['results']): group['passing_examples']+=1
    for group in groups.values():
        group['repeated_practice_evidence']=group['assessed_examples']>=2
    return dict(groups=list(groups.values()),truncated=False,scope='Distinct owner-assessed inputs only; not model training, independently verified competence, demand or launch authority')


def assert_specification(cursor, brief_id):
    """A changed mutable row cannot reinterpret the approved rubric."""
    spec=specification(cursor,brief_id)
    if not spec: return
    row=cursor.execute('SELECT exercise,checks_json FROM business_discovery WHERE id=?',(brief_id,)).fetchone()
    if not row or row['exercise']!=spec['specification']['exercise'] or json.loads(row['checks_json'])!=spec['specification']['checks']:
        raise RuntimeError('Approved practice specification changed; create a new brief')
