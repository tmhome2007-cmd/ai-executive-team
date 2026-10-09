"""Restart-safe, owner-configured collectors. No unapproved provider execution."""
import datetime
import json
import hashlib
import sqlite3
from memory.database import get_connection
from memory.experiments import _date, _text


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def init_observation_jobs(cursor):
    cursor.execute('''CREATE TABLE IF NOT EXISTS observation_jobs (
        id INTEGER PRIMARY KEY, job_key TEXT NOT NULL UNIQUE, experiment_id INTEGER NOT NULL,
        collector TEXT NOT NULL, source_id INTEGER, collection_action_id INTEGER,
        due_at TEXT NOT NULL, next_run_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
        attempts INTEGER NOT NULL DEFAULT 0, version INTEGER NOT NULL DEFAULT 1,
        note TEXT NOT NULL DEFAULT '', observation_id INTEGER, created_at TEXT NOT NULL,
        claimed_at TEXT, collector_digest TEXT NOT NULL DEFAULT '')''')
    cursor.execute("CREATE TRIGGER IF NOT EXISTS observation_binding_immutable BEFORE UPDATE OF job_key,experiment_id,collector,source_id,collection_action_id,due_at,collector_digest ON observation_jobs BEGIN SELECT RAISE(ABORT,'Observation inputs are immutable; create a new job'); END")
    cursor.execute('CREATE INDEX IF NOT EXISTS observation_due ON observation_jobs(status,next_run_at,id)')


def schedule_observation(*, job_key, experiment_id, collector, due_at, source_id=None, collection_action_id=None):
    job_key=_text(job_key,'job key',80)
    due_at=_date(due_at,'observation due date')
    if collector not in {'owner_source','approved_file_read'}: raise ValueError('Unsupported observation collector')
    if (collector=='owner_source' and (type(source_id) is not int or source_id<1 or collection_action_id is not None)) or (collector=='approved_file_read' and (type(collection_action_id) is not int or collection_action_id<1 or source_id is not None)):
        raise ValueError('Provide exactly the collector source or read-action ID')
    with get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if not conn.execute('SELECT 1 FROM experiments WHERE id=?',(experiment_id,)).fetchone(): raise LookupError('Experiment not found')
        if source_id and not conn.execute('SELECT 1 FROM evidence_sources WHERE id=?',(source_id,)).fetchone(): raise LookupError('Source not found')
        collector_digest=''
        if collection_action_id:
            action=conn.execute('SELECT action_type,action_detail FROM action_queue WHERE id=?',(collection_action_id,)).fetchone()
            if not action: raise LookupError('Read action not found')
            try: detail=json.loads(action['action_detail'])
            except (ValueError,TypeError): raise ValueError('Collector requires a structured file-read action') from None
            if not isinstance(detail,dict) or action['action_type']!='file_operation' or detail.get('operation')!='read': raise ValueError('Collector cannot execute write, browser or shell actions')
            collector_digest=hashlib.sha256((action['action_type']+'\n'+action['action_detail']).encode()).hexdigest()
        row=conn.execute('SELECT * FROM observation_jobs WHERE job_key=?',(job_key,)).fetchone()
        expected=dict(experiment_id=experiment_id,collector=collector,source_id=source_id,collection_action_id=collection_action_id,due_at=due_at,collector_digest=collector_digest)
        if row:
            if any(row[k]!=v for k,v in expected.items()): raise RuntimeError('Job key reused with different inputs')
            return dict(row)
        ident=conn.execute('INSERT INTO observation_jobs(job_key,experiment_id,collector,source_id,collection_action_id,due_at,next_run_at,created_at,collector_digest) VALUES(?,?,?,?,?,?,?,?,?)',(job_key,experiment_id,collector,source_id,collection_action_id,due_at,due_at,utcnow(),collector_digest)).lastrowid
        conn.commit()
    return get_job(ident)


def get_job(ident):
    with get_connection() as conn:
        row=conn.execute('SELECT * FROM observation_jobs WHERE id=?',(ident,)).fetchone()
    return dict(row) if row else None


def list_jobs(limit=50,offset=0):
    if not 1<=limit<=100 or offset<0: raise ValueError('Invalid pagination')
    with get_connection() as conn:
        return [dict(r) for r in conn.execute('SELECT * FROM observation_jobs ORDER BY id DESC LIMIT ? OFFSET ?',(limit,offset))]


def review_job(ident,expected_version,operation):
    if operation not in {'retry','cancel'}: raise ValueError('Invalid job operation')
    with get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute('SELECT * FROM observation_jobs WHERE id=?',(ident,)).fetchone()
        if not row: raise LookupError('Observation job not found')
        if row['version']!=expected_version: raise RuntimeError('Job changed; refresh')
        if row['status'] in {'running','completed','cancelled'}: raise RuntimeError('Running/terminal jobs cannot be replayed')
        if operation=='retry' and row['collector']!='owner_source': raise ValueError('Interrupted tool collectors need a new reviewed read action and job')
        conn.execute('UPDATE observation_jobs SET status=?,next_run_at=?,attempts=0,version=version+1,note=? WHERE id=?',('pending' if operation=='retry' else 'cancelled',max(datetime.datetime.fromisoformat(row['due_at'].replace('Z','+00:00')),datetime.datetime.now(datetime.timezone.utc)).isoformat(),'Owner reviewed '+operation,ident))
        conn.commit()
    return get_job(ident)


def claim_job():
    now=utcnow()
    with get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute("SELECT * FROM observation_jobs WHERE status IN ('pending','retry') AND julianday(next_run_at)<=julianday(?) AND attempts<3 ORDER BY next_run_at,id LIMIT 1",(now,)).fetchone()
        if not row: return None
        conn.execute("UPDATE observation_jobs SET status='running',attempts=attempts+1,version=version+1,claimed_at=? WHERE id=?",(now,row['id']))
        conn.commit()
    return get_job(row['id'])


def recover_observations():
    # Called only by the existing exclusively locked server startup.
    with get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute("UPDATE observation_jobs SET status=CASE WHEN collector='owner_source' AND attempts<3 THEN 'retry' ELSE 'needs_review' END,next_run_at=?,version=version+1,note='Interrupted collector recovered; no external tool replay' WHERE status='running'",(utcnow(),))
        conn.commit()


def collect_job(job):
    from memory.evidence import get_source, create_source
    from memory.database import get_action_by_id
    from memory.experiments import get_experiment, record_observation
    source_ids=[]
    if job['collector']=='owner_source':
        source=get_source(job['source_id'])
        if not source or source['verification']!='owner_confirmed' or source['freshness']=='stale': raise ValueError('Collector source must be current and owner-confirmed')
        text=source['summary']; source_ids=[source['id']]
    else:
        action=get_action_by_id(job['collection_action_id'])
        if not action: raise LookupError('Collector action missing')
        digest=hashlib.sha256((action['action_type']+'\n'+action['action_detail']).encode()).hexdigest()
        if digest!=job['collector_digest']: raise ValueError('Read action changed since observation scheduling')
        detail=json.loads(action['action_detail'])
        if action['action_type']!='file_operation' or detail.get('operation')!='read': raise ValueError('Collector action changed; only structured reads are permitted')
        if action['status']=='approved':
            from workflows.action_control import execute_action_control
            result=execute_action_control(action['id'])
            if not result.get('success'): raise ValueError('Approved read did not complete; manual reconciliation required')
            text=result.get('stdout','')
        elif action['status']=='executed':
            result=json.loads(action.get('result_detail') or '{}'); text=result.get('stdout','')
        else: raise ValueError('Read requires independent action approval and a completed real read')
        if not isinstance(text,str) or len(text)>12000: raise ValueError('Read measurement must be a bounded JSON record')
    try: payload=json.loads(text)
    except (ValueError,TypeError): raise ValueError('Collector data must be a structured JSON measurement') from None
    if not isinstance(payload,dict) or set(payload)!={'experiment_id','metric_name','observed_at','value'} or type(payload['experiment_id']) is not int or payload['experiment_id']!=job['experiment_id']:
        raise ValueError('Measurement must identify this experiment and contain only the required fields')
    plan=get_experiment(job['experiment_id'])
    if payload['metric_name']!=plan['metric_name']: raise ValueError('Measurement metric does not match experiment')
    measured=_date(payload['observed_at'],'measured time')
    if datetime.datetime.fromisoformat(measured.replace('Z','+00:00'))<datetime.datetime.fromisoformat(job['due_at'].replace('Z','+00:00')): raise ValueError('Measurement predates scheduled observation')
    if not source_ids:
        source=create_source(source_key='collector-job:'+str(job['id']),title='Approved file-read observation',reference='Approved read action #'+str(job['collection_action_id']),summary=text,observed_at=measured,source_kind='observation')
        source_ids=[source['id']]
    return record_observation(job['experiment_id'],idempotency_key='observation-job:'+str(job['id']),observed_at=measured,value=payload['value'],evidence='Collector source record IDs: '+','.join(map(str,source_ids)),source_ids=source_ids)


def run_observation_jobs(max_items=5):
    if type(max_items) is not int or not 1<=max_items<=20: raise ValueError('Invalid collector batch size')
    completed=[]
    for _ in range(max_items):
        job=claim_job()
        if not job: break
        status='completed'; note='Source-backed observation recorded'; observation_id=None
        try:
            observation=collect_job(job)
            observation_id=observation['id']
        except sqlite3.OperationalError:
            status='retry' if job['collector']=='owner_source' and job['attempts']<3 else 'needs_review'
            note='Transient local collection failure; bounded retry' if status=='retry' else 'Collector requires owner review; tools are never replayed'
        except Exception:
            # Raw provider/file exceptions may contain private paths or credentials.
            status='needs_review'; note='Collector unavailable, invalid or interrupted; owner review required'
        next_run=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(seconds=30 * 2 ** min(job['attempts'],3))).isoformat()
        with get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute('UPDATE observation_jobs SET status=?,note=?,observation_id=?,next_run_at=?,version=version+1 WHERE id=? AND status=\'running\'',(status,note,observation_id,next_run,job['id']))
            conn.commit()
        completed.append(job['id'])
    return completed
