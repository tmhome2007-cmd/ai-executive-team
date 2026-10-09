"""Versioned fictional adult character presentation, separate from executive authority."""
import copy
import datetime
import json
import re
from agents.identities import EXECUTIVE_NAMES
from memory.database import get_connection
from memory.experiments import _text, _number

STYLES = {'dreadlocks', 'short', 'bob', 'long', 'curly', 'bun'}
PORTRAITS = {'masculine', 'feminine', 'androgynous'}
EXECUTIVE_PRESENTATIONS = {
    'ceo': 'masculine', 'cfo': 'feminine', 'cso': 'masculine',
    'chro': 'androgynous', 'general_counsel': 'feminine', 'coo': 'masculine',
    'cmo': 'feminine', 'cpo': 'masculine', 'board_director': 'feminine',
    'cco': 'masculine', 'cto': 'feminine',
}

BUILDS = {'slender', 'average', 'athletic', 'well_built'}


def default_presentation(key, index=0, *, legacy=False):
    palettes = [('#593725','#111111','#171717','#991b1b','#172535'),
                ('#ddb18e','#211b18','#342517','#342517','#334155'),
                ('#bd8461','#30251e','#294f42','#294f42','#1e3a5f'),
                ('#f1cbb0','#704d30','#465d7b','#465d7b','#36454f'),
                ('#784b36','#171717','#302016','#302016','#4c1d35')]
    skin,hair,eyes,tint,outfit=palettes[index % len(palettes)]
    presentation = dict(appearance=dict(description='Black man; clean-shaven; black dreadlocks; black eyes with a subtle red tint; tall and well-built.' if key=='ceo' else 'Original fictional adult character with a distinct professional appearance.', skin_tone=skin,hair_color=hair,eye_color=eyes,eye_tint=tint,hair_style='dreadlocks' if key=='ceo' else ['short','bob','long','curly','bun'][index % 5],beard=key in {'cso','coo','cpo','cco'} and index % 2==0),
                body=dict(height_cm=190 if key=='ceo' else 166+(index*7)%23,build='well_built' if key=='ceo' else ['slender','average','athletic'][index%3],outfit_color=outfit,asset_ref='builtin:character-v1'),
                voice=dict(provider='browser_local',language='en-US',voice_name='',pitch=.72 if key=='ceo' else round(.8+(index%5)*.12,2),rate=.9 if key=='ceo' else round(.88+(index%4)*.06,2),style='Calm, deep, deliberate leadership voice' if key=='ceo' else ['Clear and measured','Warm and steady','Bright and energetic','Low and thoughtful'][index%4]),
                adult=True,scope='Fictional presentation only; does not alter reasoning persona or authority')
    if not legacy:
        portrait = EXECUTIVE_PRESENTATIONS.get(key, 'androgynous')
        presentation['appearance']['portrait_style'] = portrait
        if key != 'ceo':
            identity = {'feminine': 'woman', 'masculine': 'man', 'androgynous': 'person with an androgynous presentation'}[portrait]
            presentation['appearance']['description'] = f"Original fictional adult {identity}; distinct professional appearance."
            if portrait != 'masculine': presentation['appearance']['beard'] = False
            presentation['voice']['pitch'] = 1.0
            presentation['voice']['rate'] = 1.0
        else:
            presentation['voice']['pitch'] = 1.0
    return presentation


def init_characters(cursor):
    cursor.execute('''CREATE TABLE IF NOT EXISTS character_profiles (
        id INTEGER PRIMARY KEY, character_key TEXT NOT NULL, version INTEGER NOT NULL,
        appearance TEXT NOT NULL, body TEXT NOT NULL, voice TEXT NOT NULL,
        created_at TEXT NOT NULL, UNIQUE(character_key,version))''')
    for index,key in enumerate(EXECUTIVE_NAMES):
        presentation=default_presentation(key,index)
        cursor.execute('INSERT OR IGNORE INTO character_profiles(character_key,version,appearance,body,voice,created_at) VALUES(?,1,?,?,?,?)', (f'executive:{key}',json.dumps(presentation['appearance']),json.dumps(presentation['body']),json.dumps(presentation['voice']),datetime.datetime.now(datetime.timezone.utc).isoformat()))
    for index,key in enumerate(EXECUTIVE_NAMES):
        row = cursor.execute('SELECT version,appearance,body,voice FROM character_profiles WHERE character_key=? ORDER BY version DESC LIMIT 1', (f'executive:{key}',)).fetchone()
        legacy = default_presentation(key,index,legacy=True)
        if row and row[0] == 1 and all(json.loads(row[index]) == legacy[field] for index,field in enumerate(('appearance','body','voice'),1)):
            updated = default_presentation(key,index)
            cursor.execute('INSERT INTO character_profiles(character_key,version,appearance,body,voice,created_at) VALUES(?,2,?,?,?,?)', (f'executive:{key}',json.dumps(updated['appearance']),json.dumps(updated['body']),json.dumps(updated['voice']),datetime.datetime.now(datetime.timezone.utc).isoformat()))
    for operation in ('UPDATE','DELETE'):
        cursor.execute(f"CREATE TRIGGER IF NOT EXISTS character_no_{operation.lower()} BEFORE {operation} ON character_profiles BEGIN SELECT RAISE(ABORT,'Character versions are retained'); END")  # nosec B608 # Literal operations.


def character_exists(cursor, key, require_active=False):
    if key in {f'executive:{k}' for k in EXECUTIVE_NAMES}: return True
    if isinstance(key,str) and re.fullmatch(r'employee:[1-9][0-9]{0,9}',key):
        row=cursor.execute('SELECT status FROM virtual_employees WHERE id=?',(int(key.split(':')[1]),)).fetchone()
        return bool(row and (not require_active or row['status']=='active'))
    return False


def _row(row):
    return dict(character_key=row['character_key'],version=row['version'],appearance=json.loads(row['appearance']),body=json.loads(row['body']),voice=json.loads(row['voice']),adult=True,scope='Fictional presentation only; reasoning persona and authority are unchanged')


def get_character(key):
    with get_connection() as conn:
        if not character_exists(conn.cursor(),key): raise LookupError('Character not found')
        row=conn.execute('SELECT * FROM character_profiles WHERE character_key=? ORDER BY version DESC LIMIT 1',(key,)).fetchone()
    if not row: raise LookupError('Character profile not initialized')
    return _row(row)


def validate_presentation(appearance, body, voice):
    appearance=copy.deepcopy(appearance)
    if isinstance(appearance,dict):
        portrait = appearance.pop('portrait_style', 'androgynous')
        if not isinstance(portrait,str) or portrait not in PORTRAITS: raise ValueError('Invalid portrait style')
    expected=[(appearance,{'description','skin_tone','hair_color','eye_color','eye_tint','hair_style','beard'}),(body,{'height_cm','build','outfit_color','asset_ref'}),(voice,{'provider','language','voice_name','pitch','rate','style'})]
    if any(not isinstance(obj,dict) or set(obj)!=fields for obj,fields in expected): raise ValueError('Use the exact appearance, body and voice fields')
    appearance=copy.deepcopy(appearance);body=copy.deepcopy(body);voice=copy.deepcopy(voice)
    appearance['portrait_style']=portrait
    appearance['description']=_text(appearance['description'],'appearance description',1000)
    for obj,fields in [(appearance,['skin_tone','hair_color','eye_color','eye_tint']),(body,['outfit_color'])]:
        for field in fields:
            if not isinstance(obj[field],str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',obj[field]): raise ValueError('Colors must be six-digit hex values')
    if not isinstance(appearance['hair_style'],str) or appearance['hair_style'] not in STYLES or type(appearance['beard']) is not bool: raise ValueError('Invalid hair style or beard setting')
    height=_number(body['height_cm'],'height')
    if not 140<=height<=220 or not isinstance(body['build'],str) or body['build'] not in BUILDS or body['asset_ref']!='builtin:character-v1': raise ValueError('Invalid body or unsupported asset reference')
    if voice['provider']!='browser_local' or not isinstance(voice['language'],str) or not re.fullmatch(r'[a-z]{2,3}-[A-Z]{2}',voice['language']): raise ValueError('Only local browser voices and supported locale syntax are allowed')
    voice['voice_name']=_text(voice['voice_name'],'voice name',120,required=False)
    voice['style']=_text(voice['style'],'voice style',400)
    for field in ('pitch','rate'):
        voice[field]=_number(voice[field],field)
        if not .5<=voice[field]<=1.5: raise ValueError('Voice pitch/rate must be between 0.5 and 1.5')
    return appearance,body,voice


def save_character(key,expected_version,appearance,body,voice):
    appearance,body,voice=validate_presentation(appearance,body,voice)
    with get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if not character_exists(conn.cursor(),key): raise LookupError('Character not found')
        row=conn.execute('SELECT MAX(version) FROM character_profiles WHERE character_key=?',(key,)).fetchone()
        if type(expected_version) is not int or row[0]!=expected_version: raise RuntimeError('Character changed; refresh')
        conn.execute('INSERT INTO character_profiles(character_key,version,appearance,body,voice,created_at) VALUES(?,?,?,?,?,?)',(key,expected_version+1,json.dumps(appearance),json.dumps(body),json.dumps(voice),datetime.datetime.now(datetime.timezone.utc).isoformat()))
        conn.commit()
    return get_character(key)


def character_history(key,limit=50,offset=0):
    if type(limit) is not int or not 1<=limit<=100 or type(offset) is not int or offset<0: raise ValueError('Invalid pagination')
    with get_connection() as conn:
        if not character_exists(conn.cursor(),key): raise LookupError('Character not found')
        return [_row(r) for r in conn.execute('SELECT * FROM character_profiles WHERE character_key=? ORDER BY version DESC LIMIT ? OFFSET ?',(key,limit,offset))]


def executive_presentations():
    with get_connection() as conn:
        rows=conn.execute("SELECT p.* FROM character_profiles p WHERE p.version=(SELECT MAX(version) FROM character_profiles newer WHERE newer.character_key=p.character_key) AND p.character_key LIKE 'executive:%'").fetchall()
    return {r['character_key'].split(':',1)[1]:_row(r) for r in rows}
