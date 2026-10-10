"""Private speech on disposable SQLite and synthetic audio; no company data or downloads."""
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
import wave
from unittest.mock import patch
from config import config
from memory.database import init_db,get_connection,log_decision
from memory.character_profiles import get_character,save_character
from workflows import conversation_audio as speech


def wav():
    out=io.BytesIO()
    with wave.open(out,'wb') as stream:
        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(24000);stream.writeframes(b'\0\0'*2400)
    return out.getvalue()


class ConversationAudioTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
        self.patch=patch.object(config,'DATABASE_PATH',str(self.root/'company.db'));self.patch.start()
        self.retention=patch.object(config,'CONVERSATION_AUDIO_RETENTION_DAYS',30);self.retention.start()
        init_db()
        profile=get_character('executive:ceo')
        save_character('executive:ceo',profile['version'],profile['appearance'],profile['body'],dict(profile['voice'],provider='kokoro_local',voice_name='am_michael',language='en-US',pitch=1,rate=1))
        self.decision=log_decision('Fictional speech test',['ceo'],'Synthetic input','Synthetic output')
        with get_connection() as conn:
            conn.execute("INSERT INTO decision_contributions(decision_id,phase,sequence,executive_key,body,profile_json,captured_at) VALUES(?,'decision',1,'ceo',?, '{}','2026-10-10')",(self.decision,'**Findings**\nThis is a fictional speech test. No customer contact or approval is recorded.'))
            self.ident=conn.execute('SELECT MAX(id) FROM decision_contributions').fetchone()[0]
            conn.execute("INSERT INTO discussion_messages(decision_id,round_number,phase,executive_key,body,profile_json,captured_at) VALUES(999,1,'proposal','ceo','Fictional published discussion contribution.','{}','2026-10-10')")
            conn.commit()
    def tearDown(self): self.retention.stop();self.patch.stop();self.temp.cleanup()
    def generate(self,token='a'*32): return speech.generate('contribution',self.ident,token)

    def test_cache_voice_version_and_missing_file_recovery(self):
        with patch.object(speech,'synthesize',return_value=wav()) as engine:
            first=self.generate();self.assertFalse(first['cached'])
            self.assertEqual(speech.audio_bytes(first['cache_key']),wav())
            self.assertEqual(self.generate('b'*32)['cache_key'],first['cache_key']);engine.assert_called_once()
            self.assertAlmostEqual(first['expires_at']-time.time(),30*86400,delta=5)
            speech.delete_audio(first['cache_key']);self.assertFalse(self.generate('c'*32)['cached'])
            profile=get_character('executive:ceo')
            save_character('executive:ceo',profile['version'],profile['appearance'],profile['body'],dict(profile['voice'],voice_name='am_fenrir'))
            second=self.generate('d'*32);self.assertNotEqual(second['cache_key'],first['cache_key']);self.assertEqual(second['voice'],'am_fenrir')
            with get_connection() as conn:
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM action_queue').fetchone()[0],0)
                with self.assertRaises(Exception): conn.execute('UPDATE conversation_audio SET voice=\'af_heart\'')

    def test_scope_limits_links_corruption_and_expiry(self):
        for invalid in ('../file','https://cloud.example', 'bad'):
            with self.assertRaises(ValueError): speech.audio_bytes(invalid)
        with self.assertRaises(ValueError): speech.spoken_text('x'*1201)
        self.assertEqual(speech.spoken_text('**Hello** [evidence](https://site.test/path)'), 'Hello evidence')
        with patch.object(speech,'synthesize',return_value=wav()): record=self.generate()
        target=self.root/'conversation-audio'/(record['cache_key']+'.wav')
        self.assertEqual(target.stat().st_mode & 0o777,0o600)
        target.write_bytes(wav()[:-20])
        with self.assertRaises(ValueError): speech.audio_bytes(record['cache_key'])
        target.unlink();target.symlink_to(self.root/'company.db')
        with self.assertRaises(ValueError): speech.audio_bytes(record['cache_key'])
        self.assertEqual(speech.prune_audio(now=record['expires_at']+1),0)
        self.assertTrue(target.is_symlink());target.unlink();target.write_bytes(wav());target.chmod(0o600)
        self.assertEqual(speech.prune_audio(now=record['expires_at']+1),1)
        with patch.object(speech,'time') as clock:
            clock.time.return_value=record['expires_at']+1
            with self.assertRaises(LookupError): speech.audio_bytes(record['cache_key'])

    def test_cancel_and_busy_do_not_publish_or_start_duplicate_work(self):
        entered=threading.Event();release=threading.Event();errors=[]
        def engine(text,voice,job): entered.set();release.wait(5);return wav()
        def worker():
            try: self.generate()
            except RuntimeError as error: errors.append(str(error))
        with patch.object(speech,'synthesize',side_effect=engine) as synth:
            thread=threading.Thread(target=worker);thread.start();self.assertTrue(entered.wait(5))
            with self.assertRaisesRegex(RuntimeError,'busy'): self.generate('b'*32)
            self.assertTrue(speech.cancel('a'*32)['cancel_requested']);release.set();thread.join(5)
            self.assertFalse(thread.is_alive());synth.assert_called_once();self.assertIn('cancelled',errors[0])
        with get_connection() as conn: self.assertEqual(conn.execute('SELECT COUNT(*) FROM conversation_audio').fetchone()[0],0)
        self.assertEqual(list((self.root/'conversation-audio').glob('*.wav')),[])

    def test_cross_process_lock_cache_capacity_and_disabled_voice(self):
        import fcntl
        directory=speech._directory();lock=os.open('.writer-lock',os.O_RDWR|os.O_CREAT,0o600,dir_fd=directory);fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            with patch.object(speech,'synthesize') as engine:
                with self.assertRaisesRegex(RuntimeError,'writer is busy'): self.generate()
                engine.assert_not_called()
        finally: os.close(lock);os.close(directory)
        with patch.object(speech,'MAX_FILES',0),patch.object(speech,'synthesize') as engine:
            with self.assertRaisesRegex(RuntimeError,'cache is full'): self.generate()
            engine.assert_not_called()
        with patch.object(config,'CONVERSATION_AUDIO_RETENTION_DAYS',0):
            with self.assertRaisesRegex(RuntimeError,'disabled'): self.generate()
        profile=get_character('executive:ceo')
        save_character('executive:ceo',profile['version'],profile['appearance'],profile['body'],dict(profile['voice'],provider='browser_local',voice_name=''))
        with self.assertRaisesRegex(RuntimeError,'No voice is substituted'): self.generate()

    def test_api_auth_binary_headers_discussion_and_identifier_bounds(self):
        from main import app
        from fastapi.testclient import TestClient
        with patch.object(config,'API_SECRET_KEY','synthetic-speech-api-key-1234567890'),patch.object(speech,'synthesize',return_value=wav()):
            client=TestClient(app);headers={'X-API-Key':config.API_SECRET_KEY}
            body=dict(source_kind='contribution',source_id=self.ident,request_id='a'*32)
            self.assertEqual(client.post('/conversation-audio',json=body).status_code,401)
            response=client.post('/conversation-audio',json=body,headers=headers);self.assertEqual(response.status_code,200,response.text)
            key=response.json()['cache_key']
            self.assertEqual(client.get('/conversation-audio/'+key).status_code,401)
            media=client.get('/conversation-audio/'+key,headers=headers);self.assertEqual(media.headers['content-type'],'audio/wav');self.assertEqual(media.headers['cache-control'],'no-store');self.assertEqual(media.content,wav())
            self.assertEqual(client.delete('/conversation-audio/requests/'+'a'*32).status_code,401)
            self.assertEqual(client.post('/conversation-audio',json=dict(body,source_id=2**80),headers=headers).status_code,422)
            self.assertEqual(client.post('/conversation-audio',json=dict(body,source_kind='discussion',source_id=1,request_id='b'*32),headers=headers).status_code,200)
            self.assertEqual(client.delete('/conversation-audio/'+key,headers=headers).status_code,200)
            self.assertEqual(client.get('/conversation-audio/'+key,headers=headers).status_code,404)

    def test_synthesis_timeout_kills_worker_and_strips_credentials(self):
        import subprocess
        from unittest.mock import Mock
        worker=Mock();worker.communicate.side_effect=[subprocess.TimeoutExpired('local-speech',90),(b'',b'')]
        with patch.object(speech,'verify_runtime',return_value=Path('/synthetic/python')),patch.object(speech.subprocess,'Popen',return_value=worker) as popen,patch.dict(os.environ,{'API_SECRET_KEY':'never-transmit-this','OPENAI_API_KEY':'never-transmit-this'}):
            job={'cancelled':threading.Event(),'process':None}
            with self.assertRaisesRegex(RuntimeError,'timed out'): speech.synthesize('Fictional test','am_michael',job)
            worker.kill.assert_called_once();env=popen.call_args.kwargs['env'];self.assertNotIn('API_SECRET_KEY',env);self.assertNotIn('OPENAI_API_KEY',env)
            self.assertNotIn('Fictional test',str(popen.call_args.args))
