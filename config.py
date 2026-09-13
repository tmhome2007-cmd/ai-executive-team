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


# 2. Centrale instantie
config = Config()

if __name__ == "__main__":
    print("=" * 60)
    print("CONFIGURATION LOADED SUCCESSFULLY")
    print("=" * 60)
    print(f"Ollama Base URL : {config.OLLAMA_BASE_URL}")
    print(f"Ollama Model    : {config.OLLAMA_MODEL}")
    print(f"Database Path   : {config.DATABASE_PATH}")
    print(f"API Key Loaded  : {'Ja' if config.API_SECRET_KEY else 'Nee (Leeg)'}")
    print("=" * 60)
