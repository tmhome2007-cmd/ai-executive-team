"""
config.py

Centrale configuratieklasse voor het AI Executive Team project.
Laadt omgevingsvariabelen uit .env en stelt veilige standaardwaarden in.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

# 1. Laad de omgevingsvariabelen uit het .env bestand
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)


@dataclass
class Config:
    """
    Klasse die alle instellingen en omgevingsvariabelen van de applicatie beheert.
    """

    # Ollama LLM Instellingen
    OLLAMA_BASE_URL: str = field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()
    )
    
    # CrewAI / LiteLLM heeft het voorvoegsel 'ollama/' nodig om te weten welk protocol gebruikt moet worden
    OLLAMA_MODEL: str = field(
        default_factory=lambda: (
            os.getenv("OLLAMA_MODEL", "ollama/llama3.1").strip()
            if os.getenv("OLLAMA_MODEL", "").startswith("ollama/")
            else f"ollama/{os.getenv('OLLAMA_MODEL', 'llama3.1').strip()}"
        )
    )

    # Database Instellingen
    DATABASE_PATH: str = field(
        default_factory=lambda: os.getenv("DATABASE_PATH", "./memory/executive_team.db").strip()
    )

    # Telegram Notificatie Instellingen
    TELEGRAM_BOT_TOKEN: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    )
    TELEGRAM_CHAT_ID: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", "").strip()
    )

    # API Beveiliging Key
    API_SECRET_KEY: str = field(
        default_factory=lambda: os.getenv("API_SECRET_KEY", "").strip()
    )

    # Beveiliging & Sandboxing Instellingen
    WORKSPACE_ROOT: str = field(
        default_factory=lambda: os.getenv("WORKSPACE_ROOT", "./workspace").strip()
    )
    SANDBOX_MODE: bool = field(
        default_factory=lambda: os.getenv("SANDBOX_MODE", "true").lower() in ("true", "1", "yes")
    )
    # Optionele, komma-gescheiden lijst van toegestane domeinen voor browser_action.
    # Leeg (standaard) = geen beperking, elk http/https-domein is toegestaan.
    ALLOWED_BROWSER_DOMAINS: str = field(
        default_factory=lambda: os.getenv("ALLOWED_BROWSER_DOMAINS", "").strip()
    )


# 2. Centrale instantie
config = Config()


def set_sandbox_mode(enabled: bool) -> None:
    """
    Wijzigt SANDBOX_MODE onmiddellijk in het geheugen (elke module die
    `from config import config` gebruikt, ziet de wijziging meteen — geen
    herstart nodig, want config is één gedeelde, niet-bevroren instantie)
    EN schrijft de wijziging weg naar .env, zodat de instelling ook na een
    herstart behouden blijft. Dit vervangt het handmatig openen van .env in
    een editor door één functie-aanroep (blootgesteld via
    POST /system/sandbox-mode in main.py).
    """
    config.SANDBOX_MODE = enabled

    new_value = "true" if enabled else "false"
    lines = []
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    found = False
    for i, line in enumerate(lines):
        if line.strip().startswith("SANDBOX_MODE"):
            lines[i] = f"SANDBOX_MODE={new_value}\n"
            found = True
            break

    if not found:
        lines.append(f"SANDBOX_MODE={new_value}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

if __name__ == "__main__":
    print("=" * 60)
    print("CONFIGURATION LOADED SUCCESSFULLY")
    print("=" * 60)
    print(f"Ollama Base URL : {config.OLLAMA_BASE_URL}")
    print(f"Ollama Model    : {config.OLLAMA_MODEL}")
    print(f"Database Path   : {config.DATABASE_PATH}")
    print(f"API Key Loaded  : {'Ja' if config.API_SECRET_KEY else 'Nee (Leeg)'}")
    print("=" * 60)