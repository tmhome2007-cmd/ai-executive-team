"""
tools/research_tool.py

Aangepaste tool voor het inlezen van webpagina's met geschikte User-Agent headers.
"""

import requests
from bs4 import BeautifulSoup
from crewai.tools import BaseTool

# Wereldwijde teller voor het bijhouden van geslaagde toolaanroepen
_CALL_COUNT = 0

def reset_call_count():
    global _CALL_COUNT
    _CALL_COUNT = 0

def get_call_count():
    return _CALL_COUNT

class PageReaderTool(BaseTool):
    name: str = "read_web_page"
    description: str = "Reads the textual content from a given web page URL."

    def _run(self, url: str) -> str:
        global _CALL_COUNT
        _CALL_COUNT += 1
        
        try:
            # Stel een User-Agent in om te voorkomen dat Wikipedia/servers het verzoek blokkeren (HTTP 403)
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            
            # Voer het netwerkverzoek uit met headers
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                return f"Error: Received status code {response.status_code} for URL {url}"

            # Structureer de HTML-tekst met BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")
            paragraphs = [p.get_text() for p in soup.find_all("p")]
            full_text = " ".join(paragraphs)

            # Beperk de tekstlengte om de contextruimte van het model te besparen
            return full_text[:2000] if full_text else "No content found on page."
            
        except Exception as err:
            return f"Error reading page {url}: {str(err)}"