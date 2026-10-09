"""Launcher safety: existing credentials/data/processes are never replaced."""
import contextlib
import io
import signal
import unittest
from unittest.mock import Mock,patch
from scripts import company_cli as cli


class CompanyCliTests(unittest.TestCase):
    def test_environment_preserves_existing_values_and_enforces_local_sandbox(self):
        with patch.dict('os.environ',{'API_SECRET_KEY':'owner-secret','DATABASE_PATH':'/existing/company.db','SANDBOX_MODE':'false'},clear=True):
            env=cli.environment()
        self.assertEqual(env['API_SECRET_KEY'],'owner-secret');self.assertEqual(env['DATABASE_PATH'],'/existing/company.db')
        self.assertEqual(env['SANDBOX_MODE'],'true');self.assertEqual(env['ALLOW_REMOTE_LLM'],'false');self.assertEqual(env['TELEGRAM_BOT_TOKEN'],'')

    def test_ollama_probe_rejects_remote_credentials_redirect_paths_and_invalid_urls(self):
        for value in ['https://remote.example','http://127.0.0.1@evil.example','http://secret:password@localhost:11434','http://localhost:11434/path','http://localhost:11434/?api_key=private','http://[invalid']:
            with self.subTest(value=value),self.assertRaises(RuntimeError):cli.local_url(value)
        self.assertEqual(cli.local_url('http://127.0.0.1:11434/'),'http://127.0.0.1:11434')

    def test_key_copy_never_prints_or_changes_key(self):
        env={'API_SECRET_KEY':'existing-private-key-'+'x'*32};output=io.StringIO()
        with patch.object(cli.sys,'platform','darwin'),patch.object(cli.shutil,'which',return_value='/usr/bin/pbcopy'),patch.object(cli.subprocess,'run') as run,contextlib.redirect_stdout(output):cli.copy_key(env)
        self.assertEqual(run.call_args.kwargs['input'],env['API_SECRET_KEY']);self.assertNotIn(env['API_SECRET_KEY'],output.getvalue())
        self.assertEqual(run.call_args.args[0],['pbcopy'])

    def test_missing_key_is_not_generated_and_occupied_ports_are_not_killed(self):
        with self.assertRaises(RuntimeError):cli.copy_key({'API_SECRET_KEY':''})
        with patch.object(cli,'doctor',return_value=True),patch.object(cli,'available',return_value=False),patch.object(cli.subprocess,'Popen') as spawn,patch.object(cli.os,'killpg') as kill:
            with self.assertRaises(RuntimeError):cli.start({})
        spawn.assert_not_called();kill.assert_not_called()

    def test_cleanup_stops_only_children_it_created(self):
        alive=Mock(pid=12345);alive.poll.return_value=None;stopped=Mock(pid=54321);stopped.poll.return_value=0
        with patch.object(cli.os,'killpg') as kill:cli.stop_children([alive,stopped])
        kill.assert_called_once_with(12345,signal.SIGTERM)

    def test_probe_uses_no_proxy_and_disallows_redirects(self):
        with patch.object(cli.urllib.request,'build_opener') as opener:
            opener.return_value.open.side_effect=cli.urllib.error.HTTPError('http://127.0.0.1/',302,'Redirect',{},None)
            self.assertFalse(cli.reachable('http://127.0.0.1/'))
        self.assertEqual(opener.call_args.args[0].proxies,{})
        self.assertIsNone(opener.call_args.args[1].redirect_request(None,None,None,None,None,None))

    def test_start_readiness_interrupt_cleans_only_owned_servers(self):
        env={'API_SECRET_KEY':'synthetic-key-'+'x'*32};backend=Mock(pid=123);frontend=Mock(pid=456)
        backend.poll.return_value=None;frontend.poll.return_value=None
        with patch.object(cli,'doctor',return_value=True),patch.object(cli,'available',return_value=True),patch.object(cli.subprocess,'run'),patch.object(cli.subprocess,'Popen',side_effect=[backend,frontend]) as spawn,patch.object(cli,'reachable',return_value=True),patch.object(cli,'copy_key'),patch.object(cli.time,'sleep',side_effect=KeyboardInterrupt),patch.object(cli,'stop_children') as stop:
            with self.assertRaises(KeyboardInterrupt):cli.start(env)
        self.assertEqual(spawn.call_count,2);self.assertTrue(all(c.kwargs['start_new_session'] for c in spawn.call_args_list))
        stop.assert_called_once_with([backend,frontend])
