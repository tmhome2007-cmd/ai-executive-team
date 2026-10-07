"""
config.py

Centrale configuratieklasse voor het AI Executive Team project.
Laadt omgevingsvariabelen uit .env en stelt veilige standaardwaarden in.
"""

import os
import tempfile
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
        stripped = line.strip()
        key = stripped.split("=", 1)[0].strip() if "=" in stripped else stripped
        if key == "SANDBOX_MODE":
            lines[i] = f"SANDBOX_MODE={new_value}\n"
            found = True
            break

    if not found:
        # Als de bestaande .env geen trailing newline heeft, zou writelines()
        # anders "LAST_KEY=valueSANDBOX_MODE=..." aan elkaar plakken.
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(f"SANDBOX_MODE={new_value}\n")

    # Schrijf atomair: eerst een tijdelijk bestand in dezelfde directory,
    # daarna os.replace(). Zo kan een crash halverwege .env niet afkappen.
    env_dir = env_path.parent
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=env_dir,
        prefix=".env.",
        suffix=".tmp",
        delete=False,
    ) as tmp:
        tmp.writelines(lines)
        tmp_path = Path(tmp.name)
    try:
        os.replace(tmp_path, env_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


class ConfigValidationError(Exception):
    """Wordt gegooid bij een fatale configuratiefout — de app mag dan niet starten."""
    pass


def validate_config() -> list[str]:
    """
    Controleert de belangrijkste instellingen bij het opstarten en gooit
    ConfigValidationError met een DUIDELIJKE, bruikbare foutmelding als er
    iets fundamenteel mist of verkeerd is — in plaats van dat de app start
    en pas minuten later, midden in een crew-run, verwarrend faalt.
    Retourneert een lijst met niet-fatale WAARSCHUWINGEN (dingen die geen
    startup blokkeren, maar wel de moeite waard zijn om te melden).
    """
    errors = []
    warnings = []

    if not config.API_SECRET_KEY:
        errors.append(
            "API_SECRET_KEY is leeg. Genereer er een met: openssl rand -hex 32, "
            "en zet die in .env."
        )
    elif len(config.API_SECRET_KEY) < 16:
        warnings.append(
            f"API_SECRET_KEY is slechts {len(config.API_SECRET_KEY)} tekens — "
            "overweeg een langere, willekeurige sleutel voor echte beveiliging."
        )

    if not config.TELEGRAM_BOT_TOKEN:
        warnings.append(
            "TELEGRAM_BOT_TOKEN is leeg — notificaties en de interactieve "
            "Approve/Reject/Execute-knoppen werken dan niet."
        )
    elif ":" not in config.TELEGRAM_BOT_TOKEN:
        warnings.append(
            "TELEGRAM_BOT_TOKEN ziet er niet uit als een geldig Telegram-token "
            "(verwacht formaat: cijfers:letters, bijv. 123456:ABC-...)."
        )

    if not config.TELEGRAM_CHAT_ID:
        warnings.append(
            "TELEGRAM_CHAT_ID is leeg — de interactieve Telegram-listener kan "
            "dan niemand als eigenaar herkennen en zal ALLE callbacks weigeren."
        )

    if not config.OLLAMA_BASE_URL.startswith(("http://", "https://")):
        errors.append(
            f"OLLAMA_BASE_URL ('{config.OLLAMA_BASE_URL}') ziet er niet uit als "
            "een geldige URL — verwacht iets als http://localhost:11434."
        )

    if errors:
        error_text = "\n".join(f"  - {e}" for e in errors)
        raise ConfigValidationError(
            f"Configuratie ongeldig, applicatie kan niet starten:\n{error_text}"
        )

    return warnings


if __name__ == "__main__":
    print("=" * 60)
    print("CONFIGURATION LOADED SUCCESSFULLY")
    print("=" * 60)
    print(f"Ollama Base URL : {config.OLLAMA_BASE_URL}")
    print(f"Ollama Model    : {config.OLLAMA_MODEL}")
    print(f"Database Path   : {config.DATABASE_PATH}")
    print(f"API Key Loaded  : {'Ja' if config.API_SECRET_KEY else 'Nee (Leeg)'}")
    print("=" * 60)

    try:
        config_warnings = validate_config()
        if config_warnings:
            print("⚠️  Waarschuwingen:")
            for w in config_warnings:
                print(f"   - {w}")
        else:
            print("✅ Geen configuratieproblemen gevonden.")
    except ConfigValidationError as e:
        print(f"❌ {e}")