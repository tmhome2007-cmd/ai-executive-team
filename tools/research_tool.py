"""
tools/research_tool.py

Aangepaste tool voor het inlezen van webpagina's met geschikte User-Agent headers.

BELANGRIJK — SSRF-bescherming:
Dit is het ENIGE tool in het hele systeem dat een agent-gekozen URL
onmiddellijk opvraagt, ZONDER menselijke goedkeuring vooraf (in tegenstelling
tot propose_browser_action, dat wél door een approve-stap gaat en al
check_url_safety() gebruikt). Zonder validatie hier zou een agent — via een
misleidende taakomschrijving, of via prompt-injectie vanuit een kwaadaardige
pagina die het al aan het lezen was — dit tool kunnen gebruiken om interne
diensten te bereiken (bijv. de Ollama API, of vóór deze fix zelfs de eigen
FastAPI-backend). We valideren daarom niet alleen het schema, maar lossen de
hostnaam ook echt op naar een IP-adres en weigeren loopback/private/
link-local adressen — dit vangt ook DNS-rebinding-achtige trucs op waarbij
een op het oog extern domein toch naar 127.0.0.1 wijst.
"""

import ipaddress
import socket
from urllib.parse import urlparse

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


def _is_safe_research_url(url: str) -> str | None:
    """
    Controleert of een URL veilig is om op te vragen. Retourneert een
    reden-string als de URL geweigerd moet worden, anders None.
    """
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return f"Could not parse URL: {url}"

    if parsed.scheme not in ("http", "https"):
        return f"Only http/https URLs are allowed (got scheme: '{parsed.scheme or 'none'}')"

    if not parsed.hostname:
        return "URL has no valid hostname"

    try:
        resolved_addresses = {
            info[4][0]
            for info in socket.getaddrinfo(
                parsed.hostname,
                parsed.port or (443 if parsed.scheme == "https" else 80),
            )
        }
    except socket.gaierror as e:
        return f"Could not resolve hostname '{parsed.hostname}': {e}"

    for resolved_ip in resolved_addresses:
        try:
            ip_obj = ipaddress.ip_address(resolved_ip)
        except ValueError:
            return f"Could not validate resolved address '{resolved_ip}'"

        if (
            ip_obj.is_loopback
            or ip_obj.is_private
            or ip_obj.is_link_local
            or ip_obj.is_reserved
            or ip_obj.is_unspecified
        ):
            return (
                f"URL resolves to a loopback/private/internal address ({resolved_ip}) — "
                f"blocked to prevent the research tool from reaching internal services "
                f"(e.g. Ollama, the backend API, or anything else on the local network)"
            )

    return None


def _get_safe_response(url: str, headers: dict, timeout: float = 10.0, max_redirects: int = 5):
    """
    Volgt redirects handmatig zodat ELKE redirect-target opnieuw door de
    SSRF-check gaat. requests.get(..., allow_redirects=True) zou anders een
    publiek URL kunnen accepteren dat vervolgens naar localhost/private IP
    redirect en zo de eerste validatie omzeilt.
    """
    current_url = url
    for _ in range(max_redirects + 1):
        block_reason = _is_safe_research_url(current_url)
        if block_reason:
            raise ValueError(f"URL blocked for safety — {block_reason}")

        response = requests.get(
            current_url,
            headers=headers,
            timeout=timeout,
            allow_redirects=False,
        )

        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("Location")
            if not location:
                return response
            from urllib.parse import urljoin
            current_url = urljoin(current_url, location)
            continue

        return response

    raise ValueError(f"Too many redirects (>{max_redirects})")


class PageReaderTool(BaseTool):
    name: str = "read_web_page"
    description: str = "Reads the textual content from a given web page URL."

    def _run(self, url: str) -> str:
        global _CALL_COUNT

        block_reason = _is_safe_research_url(url)
        if block_reason:
            return f"Error: URL blocked for safety — {block_reason}"

        try:
            # Stel een User-Agent in om te voorkomen dat Wikipedia/servers het verzoek blokkeren (HTTP 403)
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            
            # Volg redirects handmatig; ieder doel wordt opnieuw tegen de
            # private/loopback/link-local SSRF-regels gevalideerd.
            response = _get_safe_response(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                return f"Error: Received status code {response.status_code} for URL {url}"

            # Structureer de HTML-tekst met BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")
            paragraphs = [p.get_text() for p in soup.find_all("p")]
            full_text = " ".join(paragraphs).strip()

            if not full_text:
                return "Error: No textual paragraph content found on page."

            # Alleen een ECHT succesvolle bron-read telt mee voor de workflow-
            # verificatie. Netwerkfouten/HTTP-fouten/lege pagina's mogen nooit
            # de 3/3 gate laten slagen.
            _CALL_COUNT += 1

            # Beperk de tekstlengte om de contextruimte van het model te besparen
            return full_text[:2000]
            
        except Exception as err:
            return f"Error reading page {url}: {str(err)}"