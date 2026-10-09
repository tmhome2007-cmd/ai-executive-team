"""Real byte decoding with mocked transport; no external requests."""
import unittest
from unittest.mock import patch
from tools.research_tool import PageReaderTool


class Response:
    status_code = 200
    encoding = 'ISO-8859-1'  # requests' implicit default, not an HTTP declaration
    def __init__(self, body, content_type):
        self.body = body
        self.headers = {'Content-Type': content_type}
    def iter_content(self, chunk_size):
        yield self.body
    def close(self):
        pass


class ResearchEncodingTests(unittest.TestCase):
    def read(self, body, content_type):
        with patch('tools.research_tool._is_safe_research_url', return_value=None), patch('tools.research_tool._get_safe_response', return_value=Response(body, content_type)):
            return PageReaderTool()._run('https://example.org/synthetic')

    def test_utf8_html_without_http_charset(self):
        text = 'Plans ↗︎ — €0'
        self.assertEqual(self.read(('<meta charset="utf-8"><p>' + text + '</p>').encode(), 'text/html'), text)

    def test_explicit_legacy_charset(self):
        self.assertEqual(self.read('<p>café</p>'.encode('iso-8859-1'), 'text/html; charset=iso-8859-1'), 'café')

    def test_plain_text_is_readable_without_html_paragraphs(self):
        self.assertEqual(self.read('Public €0 constraints'.encode(), 'text/plain; charset=utf-8'), 'Public €0 constraints')
