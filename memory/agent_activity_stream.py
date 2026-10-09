"""Bounded SSE replay of retained metadata; never publish prompts or tool output."""
import datetime
import json
from memory.database import get_connection
from workflows.capability_policy import ROLE_ALIASES

WINDOW_DAYS=30


def stream_page(after_id=0,limit=100):
    if type(after_id) is not int or after_id<0 or not 1<=limit<=100: raise ValueError('Invalid stream cursor')
    cutoff=(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(days=WINDOW_DAYS)).isoformat()
    with get_connection() as conn:
        minimum=conn.execute('SELECT MIN(id) FROM activity_events WHERE company_visible=1 AND julianday(timestamp)>=julianday(?)',(cutoff,)).fetchone()[0]
        maximum=conn.execute('SELECT COALESCE(MAX(id),0) FROM activity_events').fetchone()[0]
        reset=after_id>maximum or bool(after_id and minimum and after_id<minimum-1)
        if reset: after_id=max(0,(minimum or maximum+1)-1)
        rows=conn.execute('SELECT id,category,entity_table,entity_id,operation,new_state,timestamp FROM activity_events WHERE company_visible=1 AND id>? AND julianday(timestamp)>=julianday(?) ORDER BY id LIMIT ?',(after_id,cutoff,limit)).fetchall()
    return {'reset_required':reset,'after_id':after_id,'retention_days':WINDOW_DAYS,'items':[{**dict(r),'new_state':json.loads(r['new_state'])} for r in rows]}


def executive_states():
    keys=set(ROLE_ALIASES.values()); states={key:'unknown' for key in keys}
    now=datetime.datetime.now(datetime.timezone.utc)
    with get_connection() as conn:
        rows=conn.execute("SELECT executive_key,state,updated_at FROM agent_runtime ORDER BY updated_at DESC LIMIT 1001").fetchall()
    if len(rows)>1000: return states
    grouped={key:[] for key in keys}
    for row in rows:
        if row['executive_key'] in grouped: grouped[row['executive_key']].append(row)
    for role,items in grouped.items():
        if not items: continue
        running=[r for r in items if r['state']=='running']
        if running:
            states[role]='running' if all(0 <= (now-datetime.datetime.fromisoformat(r['updated_at'])).total_seconds()<900 for r in running) else 'unknown'
        else: states[role]=items[0]['state']
    return states
